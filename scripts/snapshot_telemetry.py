"""Consistent SQLite backup of the running collector with dated audit receipts."""
import json,sqlite3,sys,hashlib,gzip
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.common import ROOT,save_json,sha256
from src.telemetry_archive import export_archives
live=ROOT/'data/telemetry';dest=ROOT/'reports/evidence/telemetry';dest.mkdir(parents=True,exist_ok=True)
snapshot=dest/'inventory.sqlite'
with sqlite3.connect(live/'inventory.sqlite') as source,sqlite3.connect(snapshot) as target:
    source.backup(target)
    assert target.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    target.execute('PRAGMA journal_mode=DELETE')
with sqlite3.connect(snapshot) as db:
    db.row_factory=sqlite3.Row
    polls=[dict(row) for row in db.execute('SELECT * FROM polls ORDER BY started_utc')]
    quality=dict(db.execute('SELECT quality,count(*) FROM observations GROUP BY quality').fetchall())
    observation_count=db.execute('SELECT count(*) FROM observations').fetchone()[0]
    assert observation_count==sum(row['station_count'] for row in polls)
    for row in db.execute('SELECT * FROM fetches WHERE sha256 IS NOT NULL'):
        folder=live/'raw'/next(p['started_utc'][:10] for p in polls if p['poll_id']==row['poll_id'])
        raw=folder/(row['poll_id'].replace(':','-')+'_'+row['feed']+'.json.gz')
        # Recovered captures retain their original raw basename, listed in a receipt.
        if raw.exists():
            with gzip.open(raw,'rb') as f:assert hashlib.sha256(f.read()).hexdigest()==row['sha256']
times=[datetime.fromisoformat(row['started_utc']) for row in polls]
gaps=[(b-a).total_seconds() for a,b in zip(times,times[1:])]
export_archives(snapshot,dest/'archive')
summary=dict(snapshot_created_utc=datetime.now(timezone.utc).isoformat(),polls=len(polls),observations=observation_count,first_poll_utc=polls[0]['started_utc'],last_poll_utc=polls[-1]['started_utc'],observed_span_minutes=(times[-1]-times[0]).total_seconds()/60,max_poll_gap_seconds=max(gaps,default=0),poll_status_counts={x:sum(p['status']==x for p in polls) for x in set(p['status'] for p in polls)},quality_counts=quality,sqlite_sha256=sha256(snapshot),snapshot_integrity='ok',scope='Actual dated prospective samples only; no inference of states between polls or 2025 backfill',scheduling='Local target 60s while VM alive; GitHub target 5min best effort, independent public gbfs-history branch; inspect actual run receipts')
save_json(ROOT/'reports/validation/telemetry_snapshot.json',summary)
for name in ['health.json','service.json','retention.json','raw_recovery_receipt.json']:
    path=live/name
    if path.exists():save_json(dest/name,json.loads(path.read_text()))
save_json(dest/'README.json',summary)
print(json.dumps(summary,indent=2))
