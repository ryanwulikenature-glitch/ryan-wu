"""Inspect dated local and pinned GitHub archive samples; no external alerts."""
import gzip,json,sqlite3,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.common import ROOT,save_json
from src.monitoring import poll_cadence
local=ROOT/'data/telemetry/inventory.sqlite'
with sqlite3.connect('file:'+str(local)+'?mode=ro',uri=True) as db:
    db.row_factory=sqlite3.Row;polls=[dict(x) for x in db.execute('SELECT * FROM polls ORDER BY started_utc')]
github={}
for path in sorted((ROOT/'reports/evidence/github_collection/data').glob('*.jsonl.gz')):
    with gzip.open(path,'rt') as f:
        for line in f:
            obj=json.loads(line);github[obj['poll']['poll_id']]=obj['poll']
runs=json.loads((ROOT/'reports/validation/github_collection_runs.json').read_text())
scheduled=[r for r in runs if r['event']=='schedule' and r['conclusion']=='success']
linked=[p for p in github.values() if any(f"github_actions_run={r['id']};" in p['scope'] for r in scheduled)]
result=dict(local=poll_cadence(polls),github=poll_cadence(list(github.values()),expected_seconds=300,grace_factor=2),successful_schedule_runs=len(scheduled),successful_scheduled_polls_linked_to_run_ids=len(linked),schedule_trigger_verified=bool(scheduled),archive_and_schedule_link_verified=bool(linked),scope='Observed windows only. Historic/current unmatched station IDs remain unknown; no historical backfill or long-term uptime claim.')
save_json(ROOT/'reports/validation/monitoring_audit.json',result)
print(json.dumps(result,indent=2))
