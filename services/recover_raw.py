"""Recover real local raw captures after a database failure, preserving capture times."""
import sys,json,gzip,re,sqlite3
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.telemetry import ROOT,collect_once,connection,atomic_json
out=ROOT/'data/telemetry';receipts=[]
with connection(out/'inventory.sqlite') as db:seen={r[0] for r in db.execute('SELECT poll_id FROM polls')}
for info in sorted((out/'raw').glob('*/*_station_information.json.gz')):
    slug=info.name.removesuffix('_station_information.json.gz');status=info.with_name(slug+'_station_status.json.gz')
    if not status.exists():continue
    stamp,nonce=slug.rsplit('_',1);stamp=re.sub(r'T(\d\d)-(\d\d)-(\d\d)',r'T\1:\2:\3',stamp).replace('+00-00','+00:00');pid=stamp+'_'+nonce
    if pid in seen:continue
    records={}
    for feed,path in [('station_information',info),('station_status',status)]:
        with gzip.open(path,'rb') as f:records[feed]=f.read()
    times={feed:datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat() for feed,path in [('station_information',info),('station_status',status)]}
    def get(url):return 200,records['station_information' if 'information' in url else 'station_status']
    import csv
    with open(ROOT/'data/geography/original_station_audit.csv') as f:ids=[r['station_id'] for r in csv.DictReader(f)]
    context={'poll_id':pid,'started_utc':stamp,'completed_utc':max(times.values()),'retrieved_by_feed':times,'scope':'prospective raw recovery after initial schema error; original filename/file-write acquisition-time bounds preserved, not current or 2025 backfill'}
    receipts.append(collect_once(out,ids,get=get,retain_raw=False,context=context));seen.add(pid)
atomic_json(out/'raw_recovery_receipt.json',{'recovered_polls':len(receipts),'note':'Only complete real raw pairs were imported. HTTP 200 follows the original writer validation; feed retrieval times are original file-write bounds. No synthetic or backdated capture was created.','poll_ids':[r['poll_id'] for r in receipts]})
print(json.dumps({'recovered_real_polls':len(receipts)},indent=2))
