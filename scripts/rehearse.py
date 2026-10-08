"""Run after docker compose up. Exercises REAL running services through HTTP.
Does not claim success if the database/services are unavailable. Leaves history intact.
"""
import json
import time
import urllib.request

BASE='http://localhost:8080/api/'

def request(path,body=None):
    req=urllib.request.Request(BASE+path,data=json.dumps(body).encode() if body else None,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=15) as response:return json.load(response)

def until(label,check,timeout=100):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        result=check()
        if result:
            print('PASS:',label,flush=True)
            return result
        time.sleep(1)
    raise AssertionError('Timed out: '+label)

try:
    assert request('health')['database']=='PostgreSQL'
    request('control',{'action':'recover'})
    request('control',{'action':'start'})
    request('control',{'action':'start'})
    until('three workers + historical baselines',lambda:len(request('summary')['baseline'])==3)
    until('normal orders complete',lambda:int(request('summary')['totals']['completed'])>0)
    for mode,sqlstate in [('LOCK TIMEOUT','55P03'),('CONSTRAINT VIOLATION','23505'),('SLOW QUERY',None)]:
        seq=max([e['seq'] for e in request('events')],default=0)
        request('fault',{'worker_id':'B','mode':mode})
        evidence=until(mode+' observed',lambda:next((e for e in request('events?worker=B&after='+str(seq)) if (e['metadata'].get('sqlstate')==sqlstate and (e['duration_ms']>=1200 if sqlstate is None else e['status']=='error'))),None))
        report=until(mode+' investigated',lambda:next((r for r in request('summary')['investigations'] if r['worker_id']=='B' and r['status']=='open'),None))
        detail=request('investigations/'+report['id'])
        assert detail['report']['evidence']
        assert any(str(evidence['order_id'])==o['order_id'] for o in detail['orders'])
        if sqlstate:
            assert evidence['error_type']
            assert evidence['error_message']
        request('control',{'action':'recover'})
        until(mode+' recovered from observations',lambda:request('investigations/'+report['id'])['status']=='recovered')
        assert request('explorer/investigations')['rows']
    print('PASS: full local rehearsal, evidence saved in History. Restart verification is a separate step in README.')
finally:
    try:request('control',{'action':'stop'})
    except Exception:pass
