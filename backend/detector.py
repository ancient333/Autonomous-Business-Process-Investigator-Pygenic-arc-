import json
import uuid
import numpy as np
from sklearn.ensemble import IsolationForest
from psycopg.types.json import Jsonb
from .db import connect, rows
from .investigate import investigate

MIN_SAMPLES=40
CACHE={}

def serial(value):
    return json.loads(json.dumps(value,default=str))

def baseline(worker, before_seq):
    existing=rows('SELECT * FROM baselines WHERE worker_id=%s',(worker,))
    if existing:
        b=existing[0]
    else:
        history=rows("SELECT seq,event_id,duration_ms FROM events WHERE worker_id=%s AND seq<%s AND training_eligible AND status='success' AND source='synthetic-local' ORDER BY seq LIMIT %s",(worker,before_seq,MIN_SAMPLES))
        if len(history)<MIN_SAMPLES:
            return None
        values=[[e['duration_ms']] for e in history]
        durations=np.array(values).ravel()
        threshold=max(500.,float(np.median(durations)+8*max(np.median(abs(durations-np.median(durations))),1)))
        with connect() as c:
            b=c.execute('''INSERT INTO baselines(worker_id,sample_count,training_max_seq,event_ids,features,threshold_ms,metadata) VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(worker_id) DO UPDATE SET worker_id=excluded.worker_id RETURNING *''',
                (worker,len(history),history[-1]['seq'],Jsonb([str(e['event_id']) for e in history]),Jsonb(values),threshold,Jsonb({'algorithm':'IsolationForest','random_state':42,'contamination':0.05,'features':['duration_ms'],'historical_only':True,'excluded':'fault-active periods, failed and retried orders, external input','version':1}))).fetchone()
    if worker not in CACHE:
        CACHE[worker]=IsolationForest(n_estimators=100,contamination=.05,random_state=42,n_jobs=1).fit(b['features'])
    return b,CACHE[worker]

def analyze(event):
    b=baseline(event['worker_id'],event['seq']) if event['worker_id'] in ('A','B','C') else None
    score=float(b[1].decision_function([[event['duration_ms']]])[0]) if b and event['seq']>b[0]['training_max_seq'] else None
    threshold=b[0]['threshold_ms'] if b else 500
    detectors=[]
    if event['status']=='error': detectors.append('deterministic_error')
    if event['duration_ms']>threshold: detectors.append('statistical_safeguard')
    # ML is shown independently; only slow-tail ML events start investigations.
    if score is not None and score<0: detectors.append('ml_isolation_forest')
    significant=event['status']=='error' or event['duration_ms']>threshold or (score is not None and score<0 and event['duration_ms']>max(50,np.median(b[0]['features'])*3))
    if detectors:
        current=rows("SELECT * FROM investigations WHERE worker_id=%s AND status='open' ORDER BY started_at DESC LIMIT 1",(event['worker_id'],))
        inv=current[0] if current else None
        inv_id=inv['id'] if inv else uuid.uuid4() if significant else None
        report=investigate(event,inv['report'].get('affected_order_ids',[]) if inv else ()) if significant else None
        with connect() as c:
            if report:
                c.execute('''INSERT INTO investigations(id,worker_id,stage,started_at,last_anomaly_at,report) VALUES(%s,%s,%s,%s,%s,%s)
                    ON CONFLICT(id) DO UPDATE SET last_anomaly_at=excluded.last_anomaly_at,report=excluded.report''',
                    (inv_id,event['worker_id'],event['process_stage'],event['timestamp'],event['timestamp'],Jsonb(serial(report))))
            c.execute('INSERT INTO anomalies(id,event_id,worker_id,timestamp,detectors,ml_score,investigation_id) VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(event_id) DO NOTHING',
                      (uuid.uuid4(),event['event_id'],event['worker_id'],event['timestamp'],Jsonb(detectors),score,inv_id))
    # Recovery requires last three NEW observations, all successful and under the safeguard.
    for inv in rows("SELECT * FROM investigations WHERE worker_id=%s AND status='open'",(event['worker_id'],)):
        recent=rows('SELECT * FROM events WHERE worker_id=%s AND timestamp>%s AND source=%s AND seq<=%s ORDER BY seq DESC LIMIT 3',(event['worker_id'],inv['last_anomaly_at'],event['source'],event['seq']))
        if len(recent)==3 and all(e['status']=='success' and e['duration_ms']<=threshold for e in recent):
            with connect() as c:
                c.execute("UPDATE investigations SET status='recovered',recovered_at=%s WHERE id=%s",(recent[0]['timestamp'],inv['id']))

def tick():
    cursor=rows("SELECT seq FROM checkpoints WHERE name='detector'")[0]['seq']
    for e in rows('SELECT * FROM events WHERE seq>%s ORDER BY seq LIMIT 100',(cursor,)):
        if not rows('SELECT 1 FROM anomalies WHERE event_id=%s',(e['event_id'],)):
            analyze(e)
        with connect() as c:
            c.execute("UPDATE checkpoints SET seq=%s WHERE name='detector'",(e['seq'],))
