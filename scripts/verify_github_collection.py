"""Read public Actions/archive evidence and actually restore the pinned archive."""
import gzip,hashlib,json,re,sqlite3,subprocess,sys,tempfile
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import requests
from src.common import ROOT,save_json
from src.telemetry_archive import validate_record
api='https://api.github.com/repos/ryanwulikenature-glitch/ryan-wu'
def get(url,**kwargs):
    r=requests.get(url,timeout=30,**kwargs);r.raise_for_status();return r
runs=[{k:x[k] for k in ['id','event','status','conclusion','created_at','updated_at','html_url','head_sha']} for x in get(api+'/actions/runs',params={'per_page':20}).json()['workflow_runs'] if x['name']=='Prospective GBFS inventory archive']
workflow=get(api+'/actions/workflows/collect-gbfs.yml').json();head=get(api+'/branches/gbfs-history').json()['commit']['sha']
tree=get(api+'/git/trees/'+head,params={'recursive':1}).json()
if tree.get('truncated'):raise ValueError('Archive tree incomplete')
dest=ROOT/'reports/evidence/github_collection';dest.mkdir(parents=True,exist_ok=True);digests={};polls={}
for item in tree['tree']:
    name=item['path']
    if not (re.fullmatch(r'data/\d{4}-\d{2}-\d{2}\.jsonl\.gz',name) or name in ['README.md','STATUS.json']):continue
    raw=get('https://raw.githubusercontent.com/ryanwulikenature-glitch/ryan-wu/'+head+'/'+name).content
    path=dest/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw);digests[name]=hashlib.sha256(raw).hexdigest()
    if name.endswith('.gz'):
        for line in gzip.decompress(raw).decode().splitlines():
            record=json.loads(line);validate_record(record);polls[record['poll']['poll_id']]=record
with tempfile.TemporaryDirectory(prefix='citibike-github-restore-') as tmp:
    database=Path(tmp)/'restored.sqlite'
    for _ in range(2):subprocess.run([sys.executable,str(ROOT/'scripts/import_telemetry_archive.py'),'--archive',str(dest),'--db',str(database)],check=True,capture_output=True)
    with sqlite3.connect(database) as db:
        result=dict(verification_utc=datetime.now(timezone.utc).isoformat(),archive_branch_head=head,workflow_state=workflow['state'],polls=db.execute('SELECT count(*) FROM polls').fetchone()[0],observations=db.execute('SELECT count(*) FROM observations').fetchone()[0],integrity_check=db.execute('PRAGMA integrity_check').fetchone()[0],latest_poll_utc=db.execute('SELECT max(started_utc) FROM polls').fetchone()[0],downloaded_sha256=digests,scheduled_successes_observed=sum(r['event']=='schedule' and r['conclusion']=='success' for r in runs))
        assert result['polls']==len(polls) and result['observations']==sum(len(x['observations']) for x in polls.values()) and result['integrity_check']=='ok'
save_json(ROOT/'reports/validation/github_collection_runs.json',runs);save_json(ROOT/'reports/validation/github_archive_restoration.json',result)
print(json.dumps(result,indent=2))
