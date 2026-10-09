from fastapi.middleware.cors import CORSMiddleware
import json
import uuid
from datetime import datetime
from typing import Literal
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, AwareDatetime
from psycopg.types.json import Jsonb
import psycopg
from .db import init, connect, rows

@asynccontextmanager
async def lifespan(app):
    init()
    yield

app=FastAPI(title='Pygenic Arc manufacturing investigator',version='2.0.0',lifespan=lifespan,docs_url='/api/docs',openapi_url='/api/openapi.json')

@app.exception_handler(psycopg.Error)
async def db_error(request:Request, exc):
    return JSONResponse(status_code=503,content={'detail':'Database unavailable. Check the db service and connection configuration.'})

# Prevent browser cross-origin mutations against an unauthenticated local demo.

@app.middleware('http')
async def local_origin(request: Request, call_next):
    origin = request.headers.get('origin')
    allowed_origins = (
        'http://localhost:8080',
        'http://127.0.0.1:8080',
        'http://localhost:5173',
        'http://127.0.0.1:5173',
        'https://autonomous-business-process-investi.vercel.app',
        'https://autonomous-business-process-investigator-pygenic-ofqtt8s5x.vercel.app',
        'https://autonomous-business-process-investigato-git-c7f828-akshaya-5742.vercel.app',
        'https://autonomous-business-process-investi.vercel.app',
    )
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and origin and origin not in allowed_origins:
        return JSONResponse(
            status_code=403,
            content={'detail': 'Origin not allowed.'}
        )
    return await call_next(request)


class Control(BaseModel):
    action:Literal['start','stop','recover']

class Fault(BaseModel):
    worker_id:Literal['A','B','C']
    mode:Literal['NORMAL','SLOW QUERY','LOCK TIMEOUT','CONSTRAINT VIOLATION']

class Log(BaseModel):
    event_id:uuid.UUID=Field(default_factory=uuid.uuid4)
    timestamp:AwareDatetime
    worker_id:str=Field(min_length=1,max_length=64)
    process_stage:Literal['Materials','Production','Quality']
    order_id:uuid.UUID|None=None
    correlation_id:uuid.UUID|None=None
    operation:str=Field(min_length=1,max_length=120)
    status:Literal['success','error','info']
    duration_ms:float=Field(ge=0,le=3600000,allow_inf_nan=False)
    error_type:str|None=Field(default=None,max_length=200)
    error_message:str|None=Field(default=None,max_length=2000)
    source:str=Field(default='external',min_length=1,max_length=120)
    metadata:dict=Field(default_factory=dict)

class Import(BaseModel):
    events:list[Log]=Field(min_length=1,max_length=500)

@app.get('/api/health')
def health():
    rows('SELECT 1')
    return {'status':'ok','database':'PostgreSQL'}

@app.post('/api/control')
def control(body:Control):
    with connect() as c:
        c.execute('SELECT * FROM controls WHERE id=1 FOR UPDATE')
        if body.action in ('start','stop'):
            c.execute('UPDATE controls SET running=%s,updated_at=now() WHERE id=1',(body.action=='start',))
        if body.action in ('stop','recover'):
            c.execute("UPDATE faults SET mode='NORMAL'")
        c.execute('INSERT INTO fault_audit(action) VALUES(%s)',(body.action,))
    return {'message':{'start':'Workload enabled; singleton engine produces orders.','stop':'Workload stopped. Bounded in-flight operations may finish within five seconds.','recover':'Faults cleared. Recovery remains pending until three new healthy observations; Start if stopped.'}[body.action]}

@app.post('/api/fault')
def fault(body:Fault):
    with connect() as c:
        c.execute('UPDATE faults SET mode=%s WHERE worker_id=%s',(body.mode,body.worker_id))
        c.execute('INSERT INTO fault_audit(worker_id,action) VALUES(%s,%s)',(body.worker_id,body.mode))
    return {'message':'Contained fault configured for next operation.'}

@app.post('/api/import')
def import_logs(body:Import):
    if len(json.dumps(body.model_dump(mode='json')))>1000000:
        raise HTTPException(413,'Import exceeds 1 MB')
    count=0
    with connect() as c:
        for e in body.events:
            # External sources cannot spoof trusted local telemetry or enter training.
            source='external:'+e.source.removeprefix('external:')
            count+=c.execute('''INSERT INTO events(event_id,timestamp,worker_id,process_stage,order_id,correlation_id,operation,status,duration_ms,error_type,error_message,source,metadata)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(event_id) DO NOTHING''',
            (e.event_id,e.timestamp,'ext:'+e.worker_id.removeprefix('ext:'),e.process_stage,e.order_id,e.correlation_id,e.operation,e.status,e.duration_ms,e.error_type,e.error_message,source,Jsonb(e.metadata))).rowcount
    return {'message':f'Committed {count} events. Duplicate event IDs ignored. External input is unverified and excluded from local baselines.'}

@app.get('/api/events')
def events(worker:str|None=None,order:str|None=None,severity:Literal['all','error','success','info']='all',after:int=0):
    return rows('''SELECT e.*,a.investigation_id,a.detectors FROM events e LEFT JOIN anomalies a USING(event_id)
       WHERE (%s::text IS NULL OR e.worker_id=%s) AND (%s::text IS NULL OR e.order_id::text ILIKE %s)
       AND (%s='all' OR e.status=%s) AND e.seq>%s ORDER BY e.seq DESC LIMIT 200''',
       (worker,worker,order,('%'+order+'%') if order else None,severity,severity,after))

@app.get('/api/summary')
def summary():
    return dict(control=rows('SELECT * FROM controls')[0],faults=rows('SELECT * FROM faults ORDER BY worker_id'),
        workers=rows('''SELECT w.*, CASE WHEN heartbeat IS NULL THEN 'Not started' WHEN heartbeat<now()-interval '8 seconds' THEN 'Offline' ELSE status END AS observed_status,
        (SELECT count(*) FROM events e WHERE e.worker_id=w.worker_id AND e.status='success') AS completed,
        (SELECT count(*) FROM events e WHERE e.worker_id=w.worker_id AND e.status='error') AS errors,
        (SELECT count(*) FROM events e WHERE e.worker_id=w.worker_id AND training_eligible AND status='success') AS clean_samples
        FROM workers w ORDER BY worker_id'''),
        totals=rows("SELECT count(*) AS orders,count(*) FILTER(WHERE quality_state='done') AS completed,count(*) FILTER(WHERE quality_state!='done') AS backlog,count(*) FILTER(WHERE production_state='error') AS production_errors,count(*) FILTER(WHERE materials_state='done' AND production_state!='done') AS production_queue,count(*) FILTER(WHERE production_state='done' AND quality_state!='done') AS quality_queue FROM orders")[0],
        baseline=rows('SELECT worker_id,trained_at,sample_count,training_max_seq,threshold_ms,metadata FROM baselines ORDER BY worker_id'),
        investigations=rows('SELECT * FROM investigations ORDER BY started_at DESC LIMIT 50'),
        trend=rows("SELECT date_trunc('minute',timestamp) AS time,count(*) AS operations,count(*) FILTER(WHERE status='error') AS errors,round(avg(duration_ms)::numeric,1) AS duration FROM events WHERE timestamp>now()-interval '30 minutes' GROUP BY 1 ORDER BY 1"))

@app.get('/api/investigations/{inv_id}')
def detail(inv_id:uuid.UUID):
    result=rows('SELECT * FROM investigations WHERE id=%s',(inv_id,))
    if not result: raise HTTPException(404,'Investigation not found')
    inv=result[0]
    ids=inv['report']['affected_order_ids']
    inv['orders']=rows('SELECT * FROM orders WHERE order_id::text=ANY(%s) ORDER BY created_at LIMIT 500',(ids,))
    inv['timeline']=rows('SELECT a.*,e.duration_ms,e.status,e.error_type FROM anomalies a JOIN events e USING(event_id) WHERE investigation_id=%s ORDER BY timestamp LIMIT 300',(inv_id,))
    inv['impact']={'affected_order_count':len(inv['orders']),'still_incomplete':sum(o['quality_state']!='done' for o in inv['orders']),'waiting_for_production':sum(o['materials_state']=='done' and o['production_state']!='done' for o in inv['orders']),'waiting_for_materials':sum(o['materials_state']!='done' for o in inv['orders']),'quality_pending':sum(o['production_state']=='done' and o['quality_state']!='done' for o in inv['orders'])}
    inv['comparison']=rows('''SELECT avg(duration_ms) FILTER(WHERE timestamp<%s) AS before_ms,avg(duration_ms) FILTER(WHERE timestamp>=%s) AS incident_ms FROM events WHERE worker_id=%s AND timestamp BETWEEN %s::timestamptz-interval '60 seconds' AND COALESCE(%s::timestamptz,now())''',(inv['started_at'],inv['started_at'],inv['worker_id'],inv['started_at'],inv['recovered_at']))[0]
    before=rows('SELECT * FROM process_snapshots WHERE timestamp<=%s ORDER BY timestamp DESC LIMIT 1',(inv['started_at'],))
    latest=rows('SELECT * FROM process_snapshots WHERE timestamp<=COALESCE(%s::timestamptz,now()) ORDER BY timestamp DESC LIMIT 1',(inv['recovered_at'],))
    inv['queue_change']={'before':before[0] if before else None,'latest':latest[0] if latest else None,'backlog_delta':latest[0]['backlog']-before[0]['backlog'] if before and latest else None,'scope':'Whole local process; comparison does not establish that every queued order was affected by this incident.'}
    return inv

QUERIES={
 'orders':'SELECT * FROM orders ORDER BY created_at DESC LIMIT 100',
 'events':'SELECT * FROM events ORDER BY seq DESC LIMIT 100',
 'workers':'SELECT * FROM workers ORDER BY worker_id',
 'materials':'SELECT * FROM materials_records ORDER BY reserved_at DESC LIMIT 100',
 'production':'SELECT * FROM production_records ORDER BY processed_at DESC LIMIT 100',
 'quality':'SELECT * FROM quality_records ORDER BY inspected_at DESC LIMIT 100',
 'baselines':'SELECT * FROM baselines ORDER BY worker_id',
 'anomalies':'SELECT * FROM anomalies ORDER BY timestamp DESC LIMIT 100',
 'investigations':'SELECT * FROM investigations ORDER BY started_at DESC LIMIT 100',
 'fault_audit':'SELECT * FROM fault_audit ORDER BY id DESC LIMIT 100',
 'queues':'SELECT * FROM process_snapshots ORDER BY id DESC LIMIT 100'}

@app.get('/api/explorer/{name}')
def explorer(name:str):
    if name not in QUERIES: raise HTTPException(404,'Unknown predefined query')
    with connect() as c:
        c.execute('SET TRANSACTION READ ONLY')
        result=c.execute(QUERIES[name]).fetchall()
    return {'sql':QUERIES[name],'rows':result}
