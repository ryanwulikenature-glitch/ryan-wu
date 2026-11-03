import argparse,gzip,json,sqlite3,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.telemetry import connection
from src.telemetry_archive import validate_record
p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--db',type=Path,required=True);a=p.parse_args();a.db.parent.mkdir(parents=True,exist_ok=True)
with connection(a.db) as db:
    for path in sorted((a.archive/'data').glob('*.jsonl.gz')):
        with gzip.open(path,'rt') as f:
            for line in f:
                obj=json.loads(line);validate_record(obj)
                for table,key in [('polls','poll'),('fetches','fetches'),('observations','observations')]:
                    rows=[obj[key]] if table=='polls' else obj[key]
                    for row in rows:
                        cols=list(row);db.execute(f'INSERT OR IGNORE INTO {table} ({",".join(cols)}) VALUES ({",".join("?" for _ in cols)})',[row[k] for k in cols])
print('Archive imported with poll/station primary keys; repeated imports are idempotent.')
