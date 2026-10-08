"""Real PostgreSQL integration tests. Each test uses a disposable UNIQUE schema.
No production rows are deleted. Run with TEST_DATABASE_URL pointing at local PostgreSQL.
"""
import os
import subprocess
import sys
import time
import uuid
import pytest
import psycopg
from psycopg.conninfo import make_conninfo
from fastapi.testclient import TestClient
from backend import db,detector
from backend.api import app
from backend.worker import tick as work
from backend.engine import produce

@pytest.fixture
def database():
    dsn=os.getenv('TEST_DATABASE_URL')
    if not dsn:
        pytest.skip('Set TEST_DATABASE_URL to run actual PostgreSQL checks')
    schema='rootlens_test_'+uuid.uuid4().hex
    with psycopg.connect(dsn,autocommit=True) as c:
        c.execute(psycopg.sql.SQL('CREATE SCHEMA {}').format(psycopg.sql.Identifier(schema)))
    old=db.DSN
    db.DSN=make_conninfo(dsn,options='-c search_path='+schema)
    detector.CACHE.clear()
    db.init()
    yield db.DSN
    db.DSN=old
    detector.CACHE.clear()
    with psycopg.connect(dsn,autocommit=True) as c:
        c.execute(psycopg.sql.SQL('DROP SCHEMA {} CASCADE').format(psycopg.sql.Identifier(schema)))


def start():
    client=TestClient(app)
    assert client.post('/api/control',json={'action':'start'}).status_code==200
    return client


def order():
    produce()
    return db.rows('SELECT * FROM orders ORDER BY created_at DESC LIMIT 1')[0]


def test_normal_pipeline_and_correlation(database):
    start();o=order()
    for w in 'ABC':assert work(w)['status']=='success'
    result=db.rows('SELECT * FROM orders WHERE order_id=%s',(o['order_id'],))[0]
    assert result['quality_state']=='done'
    logs=db.rows('SELECT * FROM events ORDER BY seq')
    assert [e['worker_id'] for e in logs]==list('ABC')
    assert len({e['correlation_id'] for e in logs})==1
    assert len(db.rows('SELECT * FROM production_records'))==1


@pytest.mark.parametrize('mode,code,min_ms',[('SLOW QUERY',None,1200),('LOCK TIMEOUT','55P03',400),('CONSTRAINT VIOLATION','23505',0)])
def test_real_faults_rollback_and_recovery(database,mode,code,min_ms):
    client=start();o=order();work('A')
    client.post('/api/fault',json={'worker_id':'B','mode':mode})
    e=work('B')
    assert e['duration_ms']>=min_ms
    assert e['metadata']['sqlstate']==code
    detector.tick()
    inv=db.rows('SELECT * FROM investigations')[0]
    if code:
        assert e['status']=='error'
        assert not db.rows('SELECT * FROM production_records') # rolled back
        assert db.rows("SELECT * FROM events WHERE status='error'") # independent committed evidence
        assert work('C') is None # healthy quality waits
        assert client.get('/api/investigations/'+str(inv['id'])).json()['impact']['waiting_for_production']==1
    client.post('/api/control',json={'action':'recover'})
    assert db.rows('SELECT status FROM investigations')[0]['status']=='open'
    with db.connect() as c:c.execute('UPDATE orders SET retry_at=now()')
    for _ in range(3):
        order();work('A');work('B');work('C');detector.tick()
    assert db.rows('SELECT status FROM investigations WHERE id=%s',(inv['id'],))[0]['status']=='recovered'
    assert db.rows('SELECT * FROM demo_records WHERE worker_id=%s',('B',))[0]['counter']==0


def test_baseline_train_history_only_and_exclude_faults(database):
    client=start()
    for _ in range(42):
        order()
        for w in 'ABC':work(w)
        detector.tick()
    assert len(db.rows('SELECT * FROM baselines'))==3
    client.post('/api/fault',json={'worker_id':'B','mode':'SLOW QUERY'})
    order();work('A');e=work('B');work('C');detector.tick()
    assert e['training_eligible'] is False
    b=db.rows("SELECT * FROM baselines WHERE worker_id='B'")[0]
    assert str(e['event_id']) not in b['event_ids']
    assert b['training_max_seq']<e['seq']
    assert db.rows('SELECT ml_score FROM anomalies WHERE event_id=%s',(e['event_id'],))[0]['ml_score'] is not None


def test_duplicate_start_stop_and_data_persistence(database):
    client=start();client.post('/api/control',json={'action':'start'})
    assert len(db.rows('SELECT * FROM controls'))==1
    o=order();work('A')
    env=dict(os.environ,DATABASE_URL=database)
    output=subprocess.check_output([sys.executable,'-c',"from backend.db import rows; print(rows('SELECT count(*) AS n FROM orders')[0]['n'])"],env=env,text=True)
    assert output.strip()=='1' # persisted across new application process/connection
    client.post('/api/fault',json={'worker_id':'B','mode':'LOCK TIMEOUT'})
    client.post('/api/control',json={'action':'stop'})
    assert work('B') is None
    assert all(f['mode']=='NORMAL' for f in db.rows('SELECT * FROM faults'))
    produce();assert len(db.rows('SELECT * FROM orders'))==1
    with db.connect() as first,db.connect() as second:
        assert first.execute('SELECT pg_try_advisory_lock(hashtext(current_schema()),7000) AS ok').fetchone()['ok']
        assert not second.execute('SELECT pg_try_advisory_lock(hashtext(current_schema()),7000) AS ok').fetchone()['ok']


def test_import_readonly_and_duplicate_ids(database):
    c=TestClient(app);payload={'events':[{'event_id':str(uuid.uuid4()),'timestamp':'2026-10-08T12:00:00Z','worker_id':'B','process_stage':'Production','operation':'external_test','status':'error','duration_ms':4,'source':'synthetic-local','metadata':{'sqlstate':'23505'}}]}
    assert c.post('/api/import',json=payload).status_code==200
    c.post('/api/import',json=payload)
    logs=db.rows('SELECT * FROM events')
    assert len(logs)==1 and not logs[0]['training_eligible'] and logs[0]['worker_id']=='ext:B'
    assert c.get('/api/explorer/events').json()['rows']


def test_three_independent_worker_processes(database):
    start();order()
    env=dict(os.environ,DATABASE_URL=database)
    processes=[subprocess.Popen([sys.executable,'-m','backend.worker'],env=dict(env,WORKER_ID=w)) for w in 'ABC']
    try:
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            if db.rows('SELECT * FROM orders')[0]['quality_state']=='done':break
            time.sleep(.1)
        assert db.rows('SELECT * FROM orders')[0]['quality_state']=='done'
        assert len({p.pid for p in processes})==3
    finally:
        for p in processes:p.terminate()
        for p in processes:p.wait(timeout=8)


def test_manufacturing_materials_batch_and_quality_hold(database):
    start();o=order()
    with db.connect() as c:
        c.execute('UPDATE orders SET quantity=3 WHERE order_id=%s',(o['order_id'],))
    work('A')
    assert db.rows('SELECT quantity FROM materials_records')[0]['quantity']==6
    work('B')
    assert db.rows('SELECT produced_quantity FROM production_records')[0]['produced_quantity']==3
    # Alter only this disposable test schema to verify the actual quantity check.
    with db.connect() as c:
        c.execute('UPDATE production_records SET produced_quantity=2 WHERE order_id=%s',(o['order_id'],))
    observation=work('C')
    assert observation['status']=='error' and observation['error_type']=='ValueError'
    assert observation['metadata']['sqlstate'] is None
    assert db.rows('SELECT outcome,checked_units,expected_units FROM quality_records')[0]=={'outcome':'hold','checked_units':2,'expected_units':3}
    assert db.rows('SELECT quality_state FROM orders')[0]['quality_state']=='hold'
    assert work('C') is None # no automatic release of a held batch
