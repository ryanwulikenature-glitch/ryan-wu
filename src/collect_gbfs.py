"""Prospective GBFS collection. Never labels current snapshots as 2025 history."""
import argparse
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
import requests
from .common import ROOT,save_json

BASE='https://gbfs.citibikenyc.com/gbfs/en/'

def collect(out, samples=1, interval=60, get=requests.get):
    if samples<1 or interval<0:raise ValueError('Invalid collection schedule')
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(out/'inventory.sqlite')
    db.execute('CREATE TABLE IF NOT EXISTS snapshots (collected_utc TEXT, feed TEXT, station_id TEXT, feed_updated TEXT, payload TEXT, PRIMARY KEY(collected_utc,feed,station_id))')
    db.execute('CREATE TABLE IF NOT EXISTS failures (collected_utc TEXT, feed TEXT, error TEXT)')
    records=[]
    for sample in range(samples):
        stamp=datetime.now(timezone.utc).isoformat();folder=out/stamp.replace(':','-');folder.mkdir()
        for feed in ['station_information','station_status']:
            try:
                response=get(BASE+feed+'.json',timeout=30);response.raise_for_status();body=response.json()
                stations=body['data']['stations']
                if not isinstance(stations,list) or not stations:raise ValueError('Empty or invalid GBFS station list')
                save_json(folder/(feed+'.json'),body)
                for station in stations:
                    sid=str(station['station_id'])
                    db.execute('INSERT OR REPLACE INTO snapshots VALUES (?,?,?,?,?)',(stamp,feed,sid,str(body.get('last_updated')),json.dumps(station,sort_keys=True)))
                db.commit();records.append(dict(collected_utc=stamp,feed=feed,stations=len(stations),status='collected',scope='current only, not 2025 inventory'))
            except (requests.RequestException,ValueError,KeyError) as exc:
                db.rollback();db.execute('INSERT INTO failures VALUES (?,?,?)',(stamp,feed,str(exc)));db.commit()
                records.append(dict(collected_utc=stamp,feed=feed,status='failed',error=str(exc)))
        if sample+1<samples:time.sleep(interval)
    db.close();save_json(out/'collection_log.json',records)
    return records

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=ROOT/'data/gbfs');p.add_argument('--samples',type=int,default=1);p.add_argument('--interval',type=float,default=60);a=p.parse_args()
    records=collect(a.out,a.samples,a.interval);print(json.dumps(records,indent=2))
    if any(r['status']=='failed' for r in records):raise SystemExit(1)
