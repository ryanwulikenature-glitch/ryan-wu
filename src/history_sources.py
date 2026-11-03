"""Download attributed historical evidence without treating archive gaps as zeros."""
import json
from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import pyarrow.parquet as pq
import requests
from .common import ROOT,sha256,save_json

HISTORY=ROOT/'data/historical'
ATTRIBUTION='Bike-share data by CityBikes contributors and available from https://data.citybik.es .'

def download_history():
    HISTORY.mkdir(parents=True,exist_ok=True);raw=HISTORY/'raw';raw.mkdir(exist_ok=True)
    old_manifest=HISTORY/'manifest.csv'
    expected=pd.read_csv(old_manifest).set_index('filename').sha256.to_dict() if old_manifest.exists() else {}
    base='https://data.citybik.es/dumps/by-network/2025/'
    listing=requests.get(base,timeout=45);listing.raise_for_status();save_json(HISTORY/'directory.json',listing.json())
    entries=[x for x in listing.json() if x['name'].endswith('-citi-bike-nyc-stats.parquet') and x['name'].startswith('2025')]
    if len(entries)!=12:raise ValueError('Expected 12 NYC files')
    def get(entry):
        path=raw/entry['name'];url=base+entry['name']
        if not path.exists():
            tmp=path.with_suffix('.part')
            try:
                with requests.get(url,stream=True,timeout=(20,120)) as r:
                    r.raise_for_status()
                    with open(tmp,'wb') as f:
                        for block in r.iter_content(1024*1024):f.write(block)
                if tmp.stat().st_size!=entry['size']:raise ValueError('Length mismatch')
                pq.ParquetFile(tmp)
                if entry['name'] in expected and sha256(tmp)!=expected[entry['name']]:raise ValueError('Historical source differs from recorded SHA256; investigate revision')
                tmp.replace(path)
            finally:tmp.unlink(missing_ok=True)
        p=pq.ParquetFile(path)
        if entry['name'] in expected and sha256(path)!=expected[entry['name']]:raise ValueError('Historical cache differs from recorded SHA256')
        return dict(filename=path.name,url=url,bytes=path.stat().st_size,sha256=sha256(path),rows=p.metadata.num_rows,
          downloaded_utc=datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat(),verified_utc=datetime.now(timezone.utc).isoformat(),license='ODbL-1.0',attribution=ATTRIBUTION)
    records=list(ThreadPoolExecutor(3).map(get,entries));pd.DataFrame(records).to_csv(HISTORY/'manifest.csv',index=False)
    # Exact captured official feeds: point evidence, never forward-filled across months.
    wb=HISTORY/'wayback';wb.mkdir(exist_ok=True);captures=[]
    for feed in ['station_information','station_status']:
        original=f'https://gbfs.citibikenyc.com/gbfs/en/{feed}.json'
        url='https://web.archive.org/cdx/search/cdx'
        r=requests.get(url,params={'url':original,'output':'json','filter':'statuscode:200','from':'2025','to':'2025','limit':10000},timeout=60);r.raise_for_status()
        index=r.json();save_json(wb/(feed+'_cdx.json'),index)
        for row in index[1:]:
            stamp=row[index[0].index('timestamp')];source=f'https://web.archive.org/web/{stamp}id_/{original}'
            path=wb/f'{feed}_{stamp}.json'
            try:
                if not path.exists():
                    response=requests.get(source,timeout=60);response.raise_for_status();body=response.json();save_json(path,body)
                body=json.loads(path.read_text());stations=body['data']['stations']
                captures.append(dict(feed=feed,captured_at=stamp,url=source,sha256=sha256(path),stations=len(stations),feed_updated=body.get('last_updated'),status='downloaded'))
            except (requests.RequestException,ValueError,KeyError) as exc:captures.append(dict(feed=feed,captured_at=stamp,url=source,status='failed',error=str(exc)))
    pd.DataFrame(captures).to_csv(HISTORY/'wayback_manifest.csv',index=False)
    save_json(HISTORY/'ATTRIBUTION.json',{'attribution':ATTRIBUTION,'citation':'CityBikes contributors. (2026) Bike-share data retrieved from https://data.citybik.es .','database_license':'https://opendatacommons.org/licenses/odbl/1-0/','scope':'CityBikes raw and derived historical databases; underlying operator terms also apply. Software is separate.','official_archives':'Internet Archive copies of official Citi Bike GBFS; sparse point observations, not continuous coverage.'})
    print(pd.DataFrame(records)[['filename','rows','bytes']].to_string(index=False),flush=True)
    return records

if __name__=='__main__':download_history()
