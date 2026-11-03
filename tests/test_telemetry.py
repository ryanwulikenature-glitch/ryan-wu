import gzip,json,sqlite3,subprocess,sys
from pathlib import Path
import pytest
from src.telemetry import collect_once,ROOT
from src.telemetry_archive import export_archives,verified_prune

def provider(renting=1):
    import time
    def get(url):
        stations=([{'short_name':'001','station_id':'uid','capacity':20}] if 'information' in url else [{'station_id':'uid','num_bikes_available':5,'num_docks_available':10,'last_reported':int(time.time()),'is_installed':1,'is_renting':renting,'is_returning':1}])
        return 200,json.dumps({'last_updated':int(time.time()),'data':{'stations':stations}}).encode()
    return get

def test_unchanged_counts_and_flag_only_changes_are_both_retained(tmp_path):
    collect_once(tmp_path,['001'],get=provider(1));collect_once(tmp_path,['001'],get=provider(0))
    with sqlite3.connect(tmp_path/'inventory.sqlite') as db:
        assert db.execute('SELECT count(*) FROM polls').fetchone()[0]==2
        assert db.execute('SELECT bikes,renting FROM observations ORDER BY observed_utc').fetchall()==[(5,1),(5,0)]
        assert db.execute('SELECT count(*) FROM fetches').fetchone()[0]==4

def test_failure_is_heartbeat_not_station_closure(tmp_path):
    def fail(url):raise OSError('offline')
    h=collect_once(tmp_path,['001'],get=fail)
    assert h['status']=='failed'
    with sqlite3.connect(tmp_path/'inventory.sqlite') as db:
        row=db.execute('SELECT bikes,installed,quality FROM observations').fetchone();assert row[:2]==(None,None) and row[2]=='information_fetch_failed'
        assert db.execute('SELECT count(*) FROM fetches WHERE error IS NOT NULL').fetchone()[0]==2

def test_archive_export_and_reimport_are_idempotent(tmp_path):
    live=tmp_path/'live';archive=tmp_path/'archive';collect_once(live,['001'],get=provider())
    assert export_archives(live/'inventory.sqlite',archive)==1
    assert export_archives(live/'inventory.sqlite',archive)==0
    restored=tmp_path/'restored.sqlite'
    for _ in range(2):subprocess.run([sys.executable,str(ROOT/'scripts/import_telemetry_archive.py'),'--archive',str(archive),'--db',str(restored)],check=True,capture_output=True)
    with sqlite3.connect(restored) as db:assert db.execute('SELECT count(*) FROM observations').fetchone()[0]==1

def test_prune_requires_readable_complete_archive(tmp_path):
    live=tmp_path/'live';archive=tmp_path/'archive';collect_once(live,['001'],get=provider())
    assert verified_prune(live/'inventory.sqlite',archive,'2100-01-01')==1
    with sqlite3.connect(live/'inventory.sqlite') as db:assert db.execute('SELECT count(*) FROM polls').fetchone()[0]==0
    assert list((archive/'data').glob('*.gz'))

def test_duplicate_station_configuration_rejected(tmp_path):
    with pytest.raises(ValueError,match='Unique'):collect_once(tmp_path,['001','001'],get=provider())

def test_retention_without_old_rows_keeps_current_database(tmp_path):
    live=tmp_path/'live';collect_once(live,['001'],get=provider())
    assert verified_prune(live/'inventory.sqlite',tmp_path/'archive','2000-01-01')==0
    with sqlite3.connect(live/'inventory.sqlite') as db:assert db.execute('SELECT count(*) FROM polls').fetchone()[0]==1
