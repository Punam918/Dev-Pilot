#!/usr/bin/env python3
"""Verify runner egress DENIAL against a reachable control target (not just YAML).
Creates two bounded test Jobs, one trusted control in app namespace and one in
runner namespace. Refuses success if the control cannot reach the cluster API.
Requires operator rights, not agent RBAC. No secrets are mounted in either Job.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import time
import uuid

CODE="""import socket,sys
s=socket.socket();s.settimeout(4)
try:
 s.connect((sys.argv[1],int(sys.argv[2])));reachable=True
except OSError:reachable=False
finally:s.close()
print('reachable='+str(reachable),flush=True)
sys.exit(0 if reachable==(sys.argv[3]=='allow') else 1)
"""

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--context',required=True);p.add_argument('--namespace',default='devpilot');p.add_argument('--runner-namespace',default='devpilot-runners')
    p.add_argument('--image',default='devpilot-runner:local')
    a=p.parse_args();prefix=['kubectl','--context',a.context]
    def call(args,input=None):
        return subprocess.run(prefix+args,input=input,text=True,capture_output=True,check=True,timeout=45).stdout
    api=json.loads(call(['-n','default','get','service','kubernetes','-o','json']))
    host=api['spec']['clusterIP'];port=str(api['spec']['ports'][0]['port']);created=[]
    try:
        for namespace,expect in [(a.namespace,'allow'),(a.runner_namespace,'deny')]:
            name='devpilot-netcheck-'+uuid.uuid4().hex[:10]
            manifest={'apiVersion':'batch/v1','kind':'Job','metadata':{'name':name,'namespace':namespace},'spec':{
              'backoffLimit':0,'activeDeadlineSeconds':90,'ttlSecondsAfterFinished':180,'template':{'spec':{
              'restartPolicy':'Never','automountServiceAccountToken':False,'enableServiceLinks':False,
              'securityContext':{'runAsNonRoot':True,'runAsUser':65534,'seccompProfile':{'type':'RuntimeDefault'}},
              'containers':[{'name':'check','image':a.image,'imagePullPolicy':'IfNotPresent','command':['python','-I','-c',CODE,host,port,expect],
              'securityContext':{'allowPrivilegeEscalation':False,'readOnlyRootFilesystem':True,'capabilities':{'drop':['ALL']}},
              'resources':{'requests':{'cpu':'50m','memory':'32Mi'},'limits':{'cpu':'200m','memory':'64Mi'}}}]}}}}
            call(['create','-f','-'],json.dumps(manifest));created.append((namespace,name))
            end=time.monotonic()+100
            while time.monotonic()<end:
                job=json.loads(call(['-n',namespace,'get','job',name,'-o','json']))
                if job.get('status',{}).get('succeeded')==1: print(f'{namespace}: expected {expect} verified');break
                if job.get('status',{}).get('failed',0)>0:raise SystemExit(f'Network check failed in {namespace}; do not run untrusted tests.')
                time.sleep(1)
            else:raise SystemExit('Network check timed out; no security success claim is valid.')
        print('Control reachable; runner denied. This tests one destination, not every escape path.')
    finally:
        for namespace,name in created:
            subprocess.run(prefix+['-n',namespace,'delete','job',name,'--ignore-not-found','--wait=false'],capture_output=True,timeout=30)
if __name__=='__main__':main()
