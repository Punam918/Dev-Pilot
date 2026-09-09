#!/usr/bin/env python3
"""Opt-in end-to-end test: automatically approve ONLY the bundled demo-redis fixture.
Never run this against a real-model instance or an untrusted repository.
"""
from __future__ import annotations
import argparse
import json
import time
from pathlib import Path
import httpx

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url',default='http://127.0.0.1:8088')
    p.add_argument('--token-file',type=Path,default=Path('.secrets/api-token'))
    p.add_argument('--out',type=Path,default=Path('outputs/local-cluster-smoke'))
    p.add_argument('--approve-trusted-fixture',action='store_true',required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    with httpx.Client(base_url=a.url,timeout=20,trust_env=False,headers={'Authorization':'Bearer '+a.token_file.read_text().strip()}) as c:
        config=c.get('/api/config');config.raise_for_status()
        if config.json()['provider']!='demo':
            raise SystemExit('Refusing automatic approvals: provider must be demo, never a real model.')
        started=c.post('/api/runs',json={'repo':'demo-redis','task':'Reproduce the Redis hostname configuration bug, fix it, and run tests.','mode':'repair'})
        started.raise_for_status();run_id=started.json()['id'];approved=set();deadline=time.monotonic()+900
        while time.monotonic()<deadline:
            response=c.get('/api/runs/'+run_id);response.raise_for_status();run=response.json()
            for item in ([run['pending_approval']] if run.get('pending_approval') else []):
                aid=item['id']
                if aid not in approved:
                    res=c.post(f'/api/runs/{run_id}/approvals/{aid}',json={'approved':True});res.raise_for_status();approved.add(aid)
            if run['status'] in {'completed','failed','cancelled','interrupted','limit_reached'}:
                (a.out/'result.json').write_text(json.dumps(run,indent=2))
                for kind,filename in [('patch','changes.patch'),('report','report.md'),('trace','trace.json')]:
                    artifact=c.get(f'/api/runs/{run_id}/artifacts/{kind}')
                    if artifact.is_success:(a.out/filename).write_bytes(artifact.content)
                print(json.dumps({'status':run['status'],'verification':run.get('verification'),'runner':config.json()['runner']},indent=2))
                if not run.get('verification',{}).get('verified'):raise SystemExit('The fixture was not independently verified; inspect saved artifacts.')
                return
            time.sleep(.5)
        raise SystemExit('Timed out. Review the run in the UI; the script does not hide or cancel it.')
if __name__=='__main__':main()
