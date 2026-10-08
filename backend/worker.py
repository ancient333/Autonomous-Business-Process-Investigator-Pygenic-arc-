"""One long-running OS process per stage; no browser timer drives processing."""
import os
import random
import signal
import time
import uuid
import logging
import psycopg
from .db import connect, event, STAGES

FIELDS = {'A': 'materials_state', 'B': 'production_state', 'C': 'quality_state'}
CONDITIONS = {'A': "materials_state != 'done'", 'B': "materials_state='done' AND production_state!='done'", 'C': "production_state='done' AND quality_state NOT IN ('done','hold')"}
STOP = False

def tick(worker):
    with connect() as c:
        running = c.execute('SELECT running FROM controls WHERE id=1').fetchone()['running']
        c.execute('UPDATE workers SET heartbeat=now(), status=%s WHERE worker_id=%s', ('Running' if running else 'Stopped', worker))
        mode = c.execute('SELECT mode FROM faults WHERE worker_id=%s', (worker,)).fetchone()['mode']
        # Freeze baseline eligibility if ANY fault is active: downstream contaminated samples excluded.
        clean = not c.execute("SELECT 1 FROM faults WHERE mode!='NORMAL' LIMIT 1").fetchone()
    if not running:
        return None
    order = None
    holder = None
    quality_passed = True
    details = {}
    started = time.perf_counter()
    try:
        with connect() as c:
            c.execute("SET LOCAL statement_timeout='5s'")
            c.execute("SET LOCAL lock_timeout='450ms'")
            # Identifiers come only from fixed server constants.
            order = c.execute(f'SELECT * FROM orders WHERE {CONDITIONS[worker]} AND retry_at<=now() ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1').fetchone()
            if not order:
                return None
            if mode == 'SLOW QUERY':
                c.execute('SELECT pg_sleep(%s)', (1.25,))
            elif mode == 'LOCK TIMEOUT':
                holder = connect()
                holder.execute("SET LOCAL idle_in_transaction_session_timeout='3s'")
                holder.execute('SELECT * FROM demo_records WHERE worker_id=%s FOR UPDATE', (worker,))
                c.execute('UPDATE demo_records SET counter=counter+1 WHERE worker_id=%s', (worker,))
            elif mode == 'CONSTRAINT VIOLATION':
                c.execute('INSERT INTO demo_records(worker_id) VALUES (%s)', (worker,))
            # Small real SQL workload with variable batch size; durations are measured, not assigned.
            c.execute('SELECT sum(i*i::bigint) FROM generate_series(1,%s) i', (random.randint(2000, 16000),))
            if worker == 'A':
                c.execute('INSERT INTO materials_records(order_id,sku,quantity) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING', (order['order_id'],order['sku'],order['quantity']*2))
            elif worker == 'B':
                material = c.execute('SELECT quantity FROM materials_records WHERE order_id=%s', (order['order_id'],)).fetchone()
                produced = material['quantity']//2
                c.execute("INSERT INTO production_records(order_id,batch_id,produced_quantity,status) VALUES (%s,%s,%s,'completed') ON CONFLICT DO NOTHING", (order['order_id'],uuid.uuid4(),produced))
                details = {'produced_units': produced, 'material_units': material['quantity']}
            else:
                production = c.execute('SELECT produced_quantity FROM production_records WHERE order_id=%s', (order['order_id'],)).fetchone()
                quality_passed = production['produced_quantity']==order['quantity']
                details = {'expected_units':order['quantity'], 'checked_units':production['produced_quantity'], 'check':'quantity reconciliation; no physical sensors'}
                c.execute('INSERT INTO quality_records(order_id,inspection_id,expected_units,checked_units,outcome) VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING', (order['order_id'],uuid.uuid4(),order['quantity'],production['produced_quantity'],'pass' if quality_passed else 'hold'))
            c.execute(f"UPDATE orders SET {FIELDS[worker]}=%s,updated_at=now(),retry_at=now() WHERE order_id=%s", ('done' if quality_passed else 'hold',order['order_id']))
        elapsed = (time.perf_counter()-started)*1000
        return event(worker,order,'success' if quality_passed else 'error',elapsed,error=None if quality_passed else ValueError('Quality hold: produced quantity does not match the production order'),eligible=clean and order['attempts']==0 and quality_passed,metadata={'sqlstate': None,**details})
    except psycopg.Error as exc:
        elapsed = (time.perf_counter()-started)*1000
        if not order:
            raise
        # Previous context has rolled back. Persist order error state and evidence separately.
        with connect() as c:
            c.execute(f"UPDATE orders SET {FIELDS[worker]}='error',attempts=attempts+1,updated_at=now(),retry_at=now()+interval '2 seconds' WHERE order_id=%s", (order['order_id'],))
        return event(worker,order,'error',elapsed,error=exc,metadata={'sqlstate':exc.sqlstate})
    finally:
        if holder:
            holder.rollback()
            holder.close()

def main():
    worker = os.environ.get('WORKER_ID','A')
    assert worker in STAGES
    # Session advisory lock guarantees one process owns each worker identity.
    with connect() as lease:
        if not lease.execute('SELECT pg_try_advisory_lock(hashtext(current_schema()),%s) AS ok', (7000+ord(worker),)).fetchone()['ok']:
            raise RuntimeError('Worker identity already running')
        lease.commit()
        while not STOP:
            try:
                tick(worker)
            except psycopg.Error:
                logging.exception('Worker database operation unavailable')
            time.sleep(0.15)

def stop(*_):
    global STOP
    STOP=True

if __name__ == '__main__':
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    main()
