import uuid
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sklearn.ensemble import IsolationForest
from backend.investigate import rank
from backend.api import app


def observation(code=None,duration=10,status='success'):
    return dict(event_id=str(uuid.uuid4()),status=status,duration_ms=duration,metadata={'sqlstate':code})


def test_lock_evidence_outweighs_unspecific_duration():
    e=observation('55P03',460,'error')
    conclusion,ranked=rank([e])
    assert conclusion=='Database lock contention'
    assert ranked[0]['support']==[e['event_id']]
    assert ranked[0]['missing']


def test_competing_specific_causes_abstain():
    conclusion,causes=rank([observation('55P03',450,'error'),observation('23505',5,'error')])
    assert conclusion=='Competing explanations remain.'
    assert causes[0]['contradiction']


def test_duration_does_not_prove_root_cause():
    assert rank([observation(duration=1300)])[0]=='Competing explanations remain.'
    assert rank([observation()])[0]=='Insufficient evidence'


def test_actual_isolation_forest_separate_training_and_evaluation():
    normal=np.random.default_rng(42).normal(10,1,size=(80,1))
    model=IsolationForest(random_state=42,contamination=.05).fit(normal)
    assert model.decision_function([[1300]])[0]<0
    assert model.decision_function([[10]])[0]>0


@pytest.mark.parametrize('body',[{'action':'delete'},{'action':1},{}])
def test_invalid_controls_rejected_before_db(body):
    assert TestClient(app).post('/api/control',json=body).status_code==422


def test_unrestricted_sql_not_available():
    assert TestClient(app).get('/api/explorer/DROP%20TABLE%20orders').status_code==404


def test_invalid_logs_and_faults_rejected():
    client=TestClient(app)
    assert client.post('/api/import',json={'events':[]}).status_code==422
    assert client.post('/api/import',json={'events':[{'duration_ms':-1}]}).status_code==422
    assert client.post('/api/fault',json={'worker_id':'X','mode':'NORMAL'}).status_code==422
    assert client.post('/api/control',json={'action':'start'},headers={'origin':'https://untrusted.example'}).status_code==403


def test_database_unavailable_is_a_visible_service_error(monkeypatch):
    import psycopg
    import backend.api as module
    def unavailable(*args,**kwargs):
        raise psycopg.OperationalError('unit-test unavailable')
    monkeypatch.setattr(module,'rows',unavailable)
    result=TestClient(app).get('/api/health')
    assert result.status_code==503
    assert 'Database unavailable' in result.json()['detail']


def test_manufacturing_quality_mismatch_uses_observed_validation():
    e=observation(status='error')
    e.update(error_type='ValueError',error_message='Quality hold: produced quantity does not match the production order')
    conclusion,causes=rank([e])
    assert conclusion=='Production quantity mismatch'
    assert causes[0]['support']==[e['event_id']]
