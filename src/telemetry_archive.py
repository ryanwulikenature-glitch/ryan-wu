"""Durable append-only archives; verify complete poll contents before pruning."""
import gzip,hashlib,json,sqlite3
from pathlib import Path

def canonical_record(obj):
    """Stable content independent of row ordering and optional integrity metadata."""
    return {'poll':obj['poll'],'fetches':sorted(obj['fetches'],key=lambda x:x['feed']),
            'observations':sorted(obj['observations'],key=lambda x:x['station_id'])}

def fingerprint(obj):
    return hashlib.sha256(json.dumps(canonical_record(obj),sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def validate_record(obj):
    poll=obj['poll'];pid=poll['poll_id'];rows=obj['observations'];fetches=obj['fetches']
    if len(rows)!=poll['station_count'] or len({x['station_id'] for x in rows})!=len(rows):
        raise ValueError('Incomplete archive observations')
    if len(fetches)!=2 or len({x['feed'] for x in fetches})!=2 or any(x['poll_id']!=pid for x in rows+fetches):
        raise ValueError('Incomplete archive fetch evidence')
    digest=fingerprint(obj)
    if obj.get('sha256',digest)!=digest:raise ValueError('Archive content checksum mismatch')
    return digest

def read_day(dest):
    records={}
    if dest.exists():
        with gzip.open(dest,'rt') as f:
            for line in f:
                obj=json.loads(line);digest=validate_record(obj);pid=obj['poll']['poll_id']
                if pid in records and records[pid]!=digest:raise ValueError('Conflicting archive poll records')
                records[pid]=digest
    return records

def from_database(db,poll):
    pid=poll['poll_id']
    return {'poll':poll,'fetches':[dict(x) for x in db.execute('SELECT * FROM fetches WHERE poll_id=?',(pid,))],
            'observations':[dict(x) for x in db.execute('SELECT * FROM observations WHERE poll_id=? ORDER BY station_id',(pid,))]}

def export_archives(db_path,archive,before=None):
    archive=Path(archive);(archive/'data').mkdir(parents=True,exist_ok=True);seen={};exported=0
    with sqlite3.connect(db_path) as db:
        db.row_factory=sqlite3.Row
        sql='SELECT * FROM polls'+(' WHERE started_utc < ?' if before else '')+' ORDER BY started_utc'
        for row in db.execute(sql,(before,) if before else ()):
            poll=dict(row);day=poll['started_utc'][:10];dest=archive/'data'/f'{day}.jsonl.gz'
            if day not in seen:seen[day]=read_day(dest)
            obj=from_database(db,poll);digest=validate_record(obj)
            if poll['poll_id'] in seen[day]:
                if seen[day][poll['poll_id']]!=digest:raise ValueError('Archive differs from database: refusing export/pruning')
                continue
            obj['sha256']=digest
            with open(dest,'ab') as raw:
                with gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as f:f.write((json.dumps(obj,sort_keys=True)+'\n').encode())
            seen[day][poll['poll_id']]=digest;exported+=1
    return exported

def verified_prune(db_path,archive,before):
    """Prune only after re-reading and comparing every field of all old rows."""
    export_archives(db_path,archive,before);archive=Path(archive)
    with sqlite3.connect(db_path) as db:
        db.row_factory=sqlite3.Row;db.execute('BEGIN IMMEDIATE')
        rows=db.execute('SELECT * FROM polls WHERE started_utc < ?',(before,)).fetchall();byday={}
        for row in rows:
            poll=dict(row);day=poll['started_utc'][:10]
            if day not in byday:byday[day]=read_day(archive/'data'/f'{day}.jsonl.gz')
            if byday[day].get(poll['poll_id'])!=fingerprint(from_database(db,poll)):
                raise ValueError('Incomplete archive: refusing database pruning')
        for table in ['observations','fetches']:
            db.execute(f'DELETE FROM {table} WHERE poll_id IN (SELECT poll_id FROM polls WHERE started_utc < ?)',(before,))
        db.execute('DELETE FROM polls WHERE started_utc < ?',(before,))
    return len(rows)
