"""Bounded, deterministic evidence workflow. Never imports or queries fault controls."""
from datetime import datetime, timezone
from .db import rows

def rank(evidence):
    codes = {e.get('metadata',{}).get('sqlstate') for e in evidence}
    errors = [str(e['event_id']) for e in evidence if e['status']=='error']
    slow = [str(e['event_id']) for e in evidence if e['duration_ms']>500]
    code_ids = lambda code: [str(e['event_id']) for e in evidence if e.get('metadata',{}).get('sqlstate')==code]
    causes = []
    def add(name, score, support, contradiction, missing, next_check):
        causes.append(dict(cause=name,strength=score,support=support,contradiction=contradiction,missing=missing,next_check=next_check))
    add('Database lock contention', 95 if '55P03' in codes else 15 if slow else 0, code_ids('55P03'), code_ids('23505'),
        'Blocking session identity was not sampled.', 'Inspect pg_locks and pg_stat_activity during the bounded test.')
    add('Duplicate / invalid business data',95 if '23505' in codes else 0,code_ids('23505'),code_ids('55P03'),
        'This is a database constraint observation; the violated table may be a dedicated demo table.', 'Read the constraint and table named in the database error before checking payload uniqueness.')
    add('Slow database operation',60 if slow and not errors else 20 if slow else 0,slow,errors,
        'No EXPLAIN plan or query-level tracing.', 'Check query plan, lock waits and operation timing before attributing the delay to a query.')
    add('Worker resource pressure',45 if slow and not errors else 5,slow,errors,
        'No CPU, memory or scheduler metrics collected.', 'Collect worker CPU and memory readings; duration alone cannot establish pressure.')
    # Correlated prior-stage errors indicate downstream waiting, rather than failure of that downstream worker.
    upstream = [str(e['event_id']) for e in evidence if e.get('is_upstream') and e['status']=='error']
    add('Upstream failure',85 if upstream else 0,upstream,[], 'Only available correlated records were examined.', 'Trace the preceding stage for each blocked order.')
    add('Missing monitoring data',10,[],[], 'Missing telemetry cannot be distinguished from inactivity without heartbeats.', 'Compare heartbeat age with order backlog and worker service logs.')
    mismatch=[str(e['event_id']) for e in evidence if e.get('error_type')=='ValueError' and 'Quality hold: produced quantity does not match' in (e.get('error_message') or '')]
    add('Production quantity mismatch',90 if mismatch else 0,mismatch,[],
        'The inspection reconciles records only; physical quantities and dimensions were not observed.',
        'Compare the production order quantity with the recorded batch output; obtain human disposition before releasing a held batch.')
    causes.sort(key=lambda x: x['strength'],reverse=True)
    conclusion = causes[0]['cause'] if causes[0]['strength']>=80 and causes[0]['strength']-causes[1]['strength']>=20 else 'Competing explanations remain.' if causes[0]['strength']>=40 else 'Insufficient evidence'
    return conclusion, causes

def investigate(trigger, previous_ids=()):
    start = datetime.now(timezone.utc)
    evidence = rows('''SELECT event_id,timestamp,worker_id,process_stage,order_id,correlation_id,status,duration_ms,error_type,error_message,source,
        jsonb_build_object('sqlstate',metadata->>'sqlstate') AS metadata FROM events
        WHERE (worker_id=%s AND timestamp BETWEEN %s::timestamptz-interval '60 seconds' AND %s::timestamptz)
        OR (correlation_id=%s AND timestamp<=%s) ORDER BY timestamp DESC LIMIT 300''', (trigger['worker_id'],trigger['timestamp'],trigger['timestamp'],trigger['correlation_id'],trigger['timestamp']))
    stage_index={'Materials':0,'Production':1,'Quality':2}
    for e in evidence:
        e['is_upstream']=stage_index.get(e['process_stage'],99)<stage_index.get(trigger['process_stage'],99) and e['correlation_id']==trigger['correlation_id']
    conclusion, causes=rank(evidence)
    affected = set(previous_ids)
    affected.add(str(trigger['order_id'])) if trigger['order_id'] else None
    affected.update(str(e['order_id']) for e in evidence if e['order_id'] and (e['status']=='error' or e['duration_ms']>500))
    return dict(conclusion=conclusion, explanations=causes, evidence=evidence, affected_order_ids=sorted(affected)[:500],
        bounded=True,limits='At most 300 recent/correlated events and 500 affected order IDs. Historical snapshots do not infer missing telemetry.',
        steps=[{'step':s,'at':datetime.now(timezone.utc).isoformat()} for s in ['Located triggering event and stage','Retrieved up to 300 recent and correlated event records','Compared SQLSTATE, duration and upstream failures','Ranked seven candidate explanations','Saved evidence references and affected order IDs']],
        started_at=start.isoformat(),finished_at=datetime.now(timezone.utc).isoformat(),method='Rules + measured evidence; strength is NOT probability. No LLM or fault-mode lookup.')
