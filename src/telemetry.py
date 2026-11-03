"""Continuous, unchanged-state-preserving prospective GBFS evidence collection.
Standard library only, for both managed-cloud daemon and GitHub scheduled jobs.
Never backfills 2025 from current feeds.
"""
import argparse,fcntl,gzip,hashlib,json,os,signal,sqlite3,time,uuid,urllib.request
from datetime import datetime,timezone
from contextlib import contextmanager
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FEEDS={k:f'https://gbfs.citibikenyc.com/gbfs/en/{k}.json' for k in ['station_information','station_status']}

def now():return datetime.now(timezone.utc).isoformat()
def atomic_json(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(obj,indent=2,ensure_ascii=False,default=str));os.replace(tmp,path)
@contextmanager
def connection(path):
    db=sqlite3.connect(path,timeout=30);db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA foreign_keys=ON')
    db.execute('CREATE TABLE IF NOT EXISTS polls (poll_id TEXT PRIMARY KEY, started_utc TEXT, completed_utc TEXT, status TEXT, station_count INTEGER, scope TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS fetches (poll_id TEXT,feed TEXT,retrieved_utc TEXT,http_status INTEGER,feed_updated TEXT,sha256 TEXT,bytes INTEGER,error TEXT,PRIMARY KEY(poll_id,feed),FOREIGN KEY(poll_id) REFERENCES polls(poll_id))')
    db.execute('CREATE TABLE IF NOT EXISTS observations (poll_id TEXT,station_id TEXT,gbfs_uid TEXT,observed_utc TEXT,reported_utc TEXT,bikes INTEGER,docks INTEGER,capacity INTEGER,installed INTEGER,renting INTEGER,is_returning INTEGER,quality TEXT,payload TEXT,PRIMARY KEY(poll_id,station_id),FOREIGN KEY(poll_id) REFERENCES polls(poll_id))')
    try:
        with db:yield db
    finally:db.close()

def fetch(url):
    request=urllib.request.Request(url,headers={'User-Agent':'CitiBikeResearchCollector/1.0','Accept':'application/json'})
    with urllib.request.urlopen(request,timeout=25) as response:return response.status,response.read()

def epoch(value):
    if value is None:return None
    try:
        if isinstance(value,(float,int)) or str(value).isdigit():return datetime.fromtimestamp(float(value),timezone.utc)
        d=datetime.fromisoformat(str(value).replace('Z','+00:00'));return d.astimezone(timezone.utc)
    except (ValueError,TypeError,OverflowError):return None

def collect_once(out,station_ids,get=fetch,retain_raw=True,context=None):
    if not station_ids or len(station_ids)!=len(set(station_ids)):raise ValueError('Unique selected station IDs required')
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    with connection(out/'inventory.sqlite'):pass
    context=context or {};start=context.get('started_utc',now());pid=context.get('poll_id',start+'_'+uuid.uuid4().hex[:8]);bodies={};retrieval=[]
    for feed,url in FEEDS.items():
        stamp=now()
        try:
            status,raw=get(url);body=json.loads(raw)
            if status!=200 or not isinstance(body.get('data',{}).get('stations'),list) or not body['data']['stations']:raise ValueError('Non-200/empty feed')
            bodies[feed]=body
            retrieval.append((pid,feed,context.get('retrieved_by_feed',{}).get(feed,now()),status,str(body.get('last_updated')),hashlib.sha256(raw).hexdigest(),len(raw),None))
            if retain_raw:
                folder=out/'raw'/start[:10];folder.mkdir(parents=True,exist_ok=True)
                with gzip.GzipFile(filename=str(folder/(pid.replace(':','-')+'_'+feed+'.json.gz')),mode='wb',mtime=0) as f:f.write(raw)
        except Exception as exc:
            retrieval.append((pid,feed,now(),None,None,None,0,str(exc)))
    completed=context.get('completed_utc',now());status='ok' if len(bodies)==2 else 'partial' if bodies else 'failed';info={str(s.get('short_name')):s for s in bodies.get('station_information',{}).get('data',{}).get('stations',[])}
    states={str(s['station_id']):s for s in bodies.get('station_status',{}).get('data',{}).get('stations',[])};rows=[]
    for sid in station_ids:
        meta=info.get(str(sid));uid=str(meta['station_id']) if meta else None;state=states.get(uid);reported=epoch(state.get('last_reported')) if state else None
        age=(datetime.fromisoformat(completed)-reported).total_seconds() if reported else None
        bikes=state.get('num_bikes_available') if state else None;docks=state.get('num_docks_available') if state else None;cap=meta.get('capacity') if meta else None
        quality='valid'
        if meta is None:quality='station_absent_from_information' if 'station_information' in bodies else 'information_fetch_failed'
        elif state is None:quality='station_absent_from_status' if 'station_status' in bodies else 'status_fetch_failed'
        elif age is None or age<0 or age>300:quality='stale_or_future_source_report'
        elif not all(isinstance(x,(int,float)) for x in [bikes,docks,cap]) or min(bikes,docks)<0 or cap<=0 or bikes+docks>cap:quality='inconsistent_capacity_counts'
        payload=json.dumps({'information':meta,'status':state,'source_age_seconds':age},sort_keys=True)
        rows.append((pid,str(sid),uid,completed,reported.isoformat() if reported else None,bikes,docks,cap,state.get('is_installed') if state else None,state.get('is_renting') if state else None,state.get('is_returning') if state else None,quality,payload))
    with connection(out/'inventory.sqlite') as db:
        db.execute('INSERT INTO polls VALUES (?,?,?,?,?,?)',(pid,start,completed,status,len(rows),context.get('scope','prospective only, not 2025 backfill')))
        db.executemany('INSERT INTO fetches VALUES (?,?,?,?,?,?,?,?)',retrieval);db.executemany('INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',rows)
    health={'poll_id':pid,'started_utc':start,'completed_utc':completed,'status':status,'stations':len(rows),'valid_station_reports':sum(r[-2]=='valid' for r in rows),'source_errors':[{'feed':r[1],'error':r[-1]} for r in retrieval if r[-1]],'scope':'prospective; all polls retained including unchanged counts and flag-only changes'}
    atomic_json(out/'health.json',health);return health

def run(out,station_ids,interval=60,max_polls=0):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    with open(out/'collector.lock','w') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise SystemExit('Collector already running for this database')
        atomic_json(out/'service.json',{'pid':os.getpid(),'started_utc':now(),'interval_seconds':interval,'state':'running'})
        stopping=False;last_maintenance=0
        def stop(*args):
            nonlocal stopping;stopping=True
        signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop);count=0
        while not stopping and (not max_polls or count<max_polls):
            begin=time.monotonic()
            try:print(json.dumps(collect_once(out,station_ids),ensure_ascii=False),flush=True)
            except Exception as exc:
                failure={'status':'worker_error','completed_utc':now(),'error':str(exc)}
                atomic_json(out/'health.json',failure)
                with open(out/'worker_errors.jsonl','a') as f:f.write(json.dumps(failure)+'\n')
                print(json.dumps(failure),flush=True)
            count+=1
            if time.time()-last_maintenance>86400:
                from .telemetry_archive import verified_prune
                from datetime import timedelta
                cutoff=(datetime.now(timezone.utc)-timedelta(days=30)).date().isoformat()
                try:
                    pruned=verified_prune(out/'inventory.sqlite',out/'archive',cutoff)
                    atomic_json(out/'retention.json',{'checked_utc':now(),'db_retention_days':30,'raw_retention_days':7,'archived_pruned_polls':pruned,'archive':'append-only daily gzip JSONL; all normalized states retained'})
                except Exception as exc:atomic_json(out/'retention.json',{'checked_utc':now(),'status':'failed_no_prune_assumed','error':str(exc)})
                last_maintenance=time.time()
            # Retain full raw JSON for seven days; all normalized heartbeats stay in SQLite.
            cutoff=time.time()-7*86400
            for file in (out/'raw').glob('*/*.json.gz'):
                if file.stat().st_mtime<cutoff:file.unlink()
            end=begin+interval
            while not stopping and time.monotonic()<end:time.sleep(max(0,min(1,end-time.monotonic())))
        atomic_json(out/'service.json',{'pid':os.getpid(),'stopped_utc':now(),'state':'stopped','polls_this_process':count})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=ROOT/'data/telemetry');p.add_argument('--stations',type=Path,default=ROOT/'data/geography/original_station_audit.csv');p.add_argument('--run',action='store_true');p.add_argument('--interval',type=int,default=60);p.add_argument('--max-polls',type=int,default=0);p.add_argument('--no-raw',action='store_true');a=p.parse_args()
    import csv
    with open(a.stations,newline='') as f:ids=[r['station_id'] for r in csv.DictReader(f)]
    if a.run:
        if a.interval<60:p.error('Live interval must be at least 60 seconds')
        run(a.out,ids,a.interval,a.max_polls)
    else:
        result=collect_once(a.out,ids,retain_raw=not a.no_raw);print(json.dumps(result,indent=2));raise SystemExit(0 if result['status']=='ok' else 1)
