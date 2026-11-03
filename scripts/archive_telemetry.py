import argparse,json,sqlite3,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.telemetry_archive import export_archives
p=argparse.ArgumentParser();p.add_argument('--db',type=Path,required=True);p.add_argument('--archive',type=Path,required=True);a=p.parse_args()
count=export_archives(a.db,a.archive)
with sqlite3.connect(a.db) as db:
    db.row_factory=sqlite3.Row
    poll=db.execute('SELECT * FROM polls ORDER BY started_utc DESC LIMIT 1').fetchone()
    if poll:
        latest=dict(poll);quality=dict(db.execute('SELECT quality,count(*) FROM observations WHERE poll_id=? GROUP BY quality',(latest['poll_id'],)).fetchall())
        (a.archive/'STATUS.json').write_text(json.dumps({'latest_poll':latest,'quality_counts':quality,'daily_archive':'data/'+latest['started_utc'][:10]+'.jsonl.gz','scope':'Actual sample only. Check timestamp freshness and workflow run history; not a continuous-uptime claim.'},indent=2)+'\n')
(a.archive/'README.md').write_text('''# Prospective Citi Bike inventory evidence archive\n\nThis branch starts at actual collection time, not 2025. Each gzip JSONL member stores the poll, source/hash/time evidence and all 30 study-site observations including unchanged quantities, flag-only changes, absent/stale states and failures. No rider information or credentials. Source: https://gbfs.citibikenyc.com/gbfs/en/ ; underlying NYCBS data-use terms apply.\n\nGitHub Actions targets five-minute collection but can be delayed/disabled; audit actual timestamps and missing heartbeats. It is not a per-minute uptime guarantee. A separate managed-cloud process targets 60 seconds while its machine is active. Future coverage grows only as time passes.\n\nReconstruct the cumulative SQLite database with scripts/import_telemetry_archive.py from main. GitHub scheduling requires Actions to remain enabled and the public repository active.\n''')
print('Verified archive export:',count,'new polls')
