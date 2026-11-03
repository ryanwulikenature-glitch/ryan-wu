import sqlite3
from src.collect_gbfs import collect

def test_collection_idempotent_database_and_failure_log(tmp_path):
    class Response:
        def raise_for_status(self):pass
        def json(self):return {'last_updated':123,'data':{'stations':[{'station_id':'001','capacity':25}]}}
    rows=collect(tmp_path,samples=2,interval=0,get=lambda *a,**k:Response())
    assert len(rows)==4 and all(r['status']=='collected' for r in rows)
    with sqlite3.connect(tmp_path/'inventory.sqlite') as db:
        assert db.execute('SELECT count(*) FROM snapshots').fetchone()[0]==4
        assert db.execute('SELECT distinct station_id FROM snapshots').fetchone()[0]=='001'
    class Bad(Response):
        def json(self):return {'data':{'stations':[]}}
    bad=collect(tmp_path,samples=1,interval=0,get=lambda *a,**k:Bad())
    assert all(r['status']=='failed' for r in bad)
    with sqlite3.connect(tmp_path/'inventory.sqlite') as db:assert db.execute('SELECT count(*) FROM failures').fetchone()[0]==2
