import logging
import signal
import time
import uuid
from .db import connect
from .detector import tick
STOP=False

def produce():
    with connect() as c:
        if c.execute('SELECT running FROM controls WHERE id=1 FOR UPDATE').fetchone()['running']:
            # Bound unattended growth and overload during a demo.
            pending=c.execute("SELECT count(*) AS n FROM orders WHERE quality_state!='done'").fetchone()['n']
            if pending<150:
                c.execute('INSERT INTO orders(order_id,correlation_id,sku,quantity) VALUES(%s,%s,%s,%s)',(uuid.uuid4(),uuid.uuid4(),'BRACKET-'+str(int(time.time())%4+1),int(time.time())%3+1))

        c.execute("""INSERT INTO process_snapshots(backlog,production_queue,quality_queue,completed)
          SELECT count(*) FILTER(WHERE quality_state!='done'),count(*) FILTER(WHERE materials_state='done' AND production_state!='done'),
          count(*) FILTER(WHERE production_state='done' AND quality_state!='done'),count(*) FILTER(WHERE quality_state='done') FROM orders""")

def main():
    with connect() as lease:
        if not lease.execute('SELECT pg_try_advisory_lock(hashtext(current_schema()),7000) AS ok').fetchone()['ok']:
            raise RuntimeError('An engine is already running')
        lease.commit()
        while not STOP:
            try:
                produce()
                tick()
            except Exception:
                logging.exception('Engine cycle failed; retrying')
            time.sleep(0.65)

def stop(*_):
    global STOP
    STOP=True

if __name__=='__main__':
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    main()
