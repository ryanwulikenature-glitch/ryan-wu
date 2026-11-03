"""Durable append-only prospective archives; export verification precedes pruning."""
import gzip,json,sqlite3
from pathlib import Path

def export_archives(db_path,archive,before=None):
    archive=Path(archive);(archive/'data').mkdir(parents=True,exist_ok=True);seen={};exported=0
    with sqlite3.connect(db_path) as db:
        db.row_factory=sqlite3.Row
        sql='SELECT * FROM polls'+(' WHERE started_utc < ?' if before else '')+' ORDER BY started_utc'
        for row in db.execute(sql,(before,) if before else ()):
            poll=dict(row);day=poll['started_utc'][:10];dest=archive/'data'/f'{day}.jsonl.gz'
            if day not in seen:
                seen[day]=set()
                if dest.exists():
                    with gzip.open(dest,'rt') as f:seen[day]={json.loads(line)['poll']['poll_id'] for line in f}
            if poll['poll_id'] in seen[day]:continue
            obj={'poll':poll,'fetches':[dict(x) for x in db.execute('SELECT * FROM fetches WHERE poll_id=?',(poll['poll_id'],))],'observations':[dict(x) for x in db.execute('SELECT * FROM observations WHERE poll_id=? ORDER BY station_id',(poll['poll_id'],))]}
            with open(dest,'ab') as raw:
                with gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as f:f.write((json.dumps(obj,sort_keys=True)+'\n').encode())
            seen[day].add(poll['poll_id']);exported+=1
    return exported

def verified_prune(db_path,archive,before):
    """Remove old normalized rows only if all poll IDs exist in readable archives."""
    export_archives(db_path,archive,before);archive=Path(archive)
    with sqlite3.connect(db_path) as db:
        rows=db.execute('SELECT poll_id,started_utc FROM polls WHERE started_utc < ?',(before,)).fetchall();byday={}
        for poll,stamp in rows:byday.setdefault(stamp[:10],set()).add(poll)
        for day,expected in byday.items():
            with gzip.open(archive/'data'/f'{day}.jsonl.gz','rt') as f:actual={json.loads(line)['poll']['poll_id'] for line in f}
            if not expected.issubset(actual):raise ValueError('Incomplete archive: refusing database pruning')
        for table in ['observations','fetches']:
            db.execute(f'DELETE FROM {table} WHERE poll_id IN (SELECT poll_id FROM polls WHERE started_utc < ?)',(before,))
        db.execute('DELETE FROM polls WHERE started_utc < ?',(before,))
    return len(rows)
