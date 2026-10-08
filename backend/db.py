import os
import uuid
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

DSN = os.environ.get('DATABASE_URL', 'postgresql://rootlens:rootlens_local@localhost:5432/rootlens')
STAGES = {'A': 'Materials', 'B': 'Production', 'C': 'Quality'}

def connect():
    return psycopg.connect(DSN, row_factory=dict_row, connect_timeout=5)

def init():
    with connect() as c:
        old = c.execute("SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='orders' AND column_name='payment_state'").fetchone()
        if old:
            raise RuntimeError('Old order-processing schema detected. Use the rootlens-manufacturing Compose project and its separate volume; keep the old data intact.')
        c.execute(Path(__file__).with_name('schema.sql').read_text())

def rows(sql, args=()):
    with connect() as c:
        return c.execute(sql, args).fetchall()

def event(worker, order, status, duration, error=None, eligible=False, metadata=None):
    # Independent connection: evidence survives the business transaction's rollback.
    with connect() as c:
        return c.execute('''INSERT INTO events(event_id,worker_id,process_stage,order_id,correlation_id,operation,status,duration_ms,error_type,error_message,source,metadata,training_eligible)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'synthetic-local',%s,%s) RETURNING *''',
            (uuid.uuid4(), worker, STAGES[worker], order['order_id'], order['correlation_id'], 'process_' + STAGES[worker].lower(), status, duration,
             type(error).__name__ if error else None, str(error)[:1200] if error else None,
             Jsonb(metadata or {}), eligible)).fetchone()
