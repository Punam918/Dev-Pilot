#!/usr/bin/env python3
"""Controlled downtime backup from the existing app PVC. Explicit context/consent.
Drains through the local API INSIDE the app pod, scales only that deployment down,
mounts the PVC in a no-token maintenance pod, streams a private archive, restores
replica count. Run with operator RBAC, NEVER as an agent tool. Argo auto-sync must
be off; do not run another deployment controller during this maintenance window.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import subprocess
import uuid
from pathlib import Path

DRAIN="""import time,httpx
from devpilot.config import Settings
from devpilot.api import ensure_token
s=Settings()
with httpx.Client(base_url='http://127.0.0.1:8080',headers={'Authorization':'Bearer '+ensure_token(s)},timeout=10,trust_env=False) as c:
 c.post('/api/admin/drain').raise_for_status()
 for _ in range(450):
  r=c.get('/api/config');r.raise_for_status()
  if not r.json()['active_run']:break
  time.sleep(2)
 else:raise SystemExit('Drain timed out; resolve pending approvals before maintenance.')
"""

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--context',required=True);p.add_argument('--namespace',default='devpilot')
    p.add_argument('--deployment',default='devpilot');p.add_argument('--out',type=Path,required=True)
    p.add_argument('--allow-downtime',action='store_true',required=True);a=p.parse_args()
    if a.out.exists():raise SystemExit('Refusing to overwrite an existing archive.')
    a.out.parent.mkdir(parents=True,exist_ok=True)
    cmd=['kubectl','--context',a.context,'-n',a.namespace]
    def call(args,body=None,timeout=120):
        return subprocess.run(cmd+args,input=body,text=True,capture_output=True,check=True,timeout=timeout).stdout
    dep=json.loads(call(['get','deployment',a.deployment,'-o','json']))
    if dep['spec']['replicas']!=1:raise SystemExit('Expected exactly one serving replica. Resolve deployment state first.')
    labels=dep['spec']['selector']['matchLabels'];selector=','.join(k+'='+v for k,v in labels.items())
    podspec=dep['spec']['template']['spec'];app=next(c for c in podspec['containers'] if c['name']=='devpilot')
    claim=next(v['persistentVolumeClaim']['claimName'] for v in podspec['volumes'] if v['name']=='data')
    call(['exec','deployment/'+a.deployment,'--','python','-c',DRAIN],timeout=930)
    name='devpilot-backup-'+uuid.uuid4().hex[:10];scaled=False;created=False;complete=False
    try:
        call(['scale','deployment',a.deployment,'--replicas=0']);scaled=True
        call(['wait','--for=delete','pod','-l',selector,'--timeout=120s'],timeout=150)
        pod={'apiVersion':'v1','kind':'Pod','metadata':{'name':name,'namespace':a.namespace},'spec':{
          'restartPolicy':'Never','automountServiceAccountToken':False,'enableServiceLinks':False,
          'securityContext':{'runAsNonRoot':True,'runAsUser':10001,'runAsGroup':10001,'fsGroup':10001,'seccompProfile':{'type':'RuntimeDefault'}},
          'imagePullSecrets':podspec.get('imagePullSecrets',[]),
          'containers':[{'name':'backup','image':app['image'],'command':['python','-c','import time;time.sleep(900)'],
            'env':[{'name':'DP_DATA_DIR','value':'/data/state'},{'name':'DP_WORKSPACE_DIR','value':'/data/workspace'}],
            'securityContext':{'allowPrivilegeEscalation':False,'readOnlyRootFilesystem':True,'capabilities':{'drop':['ALL']}},
            'resources':{'requests':{'cpu':'100m','memory':'128Mi'},'limits':{'cpu':'1','memory':'512Mi','ephemeral-storage':'2Gi'}},
            'volumeMounts':[{'name':'data','mountPath':'/data'},{'name':'tmp','mountPath':'/tmp'}]}],
          'volumes':[{'name':'data','persistentVolumeClaim':{'claimName':claim}},{'name':'tmp','emptyDir':{'sizeLimit':'1500Mi'}}]}}
        call(['create','-f','-'],json.dumps(pod));created=True
        call(['wait','--for=condition=Ready','pod',name,'--timeout=180s'],timeout=210)
        call(['exec',name,'--','python','-m','devpilot.backup','create','--out','/tmp/archive.tar.gz'],timeout=300)
        fd=os.open(a.out,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as output:
            subprocess.run(cmd+['exec',name,'--','python','-c',
              'import shutil,sys;shutil.copyfileobj(open("/tmp/archive.tar.gz","rb"),sys.stdout.buffer)'],stdout=output,check=True,timeout=300)
        complete=True
        with a.out.open('rb') as f:checksum=hashlib.file_digest(f,'sha256').hexdigest()
        print(json.dumps({'archive':str(a.out),'sha256':checksum,'encrypted':False}))
    finally:
        if created:
            call(['delete','pod',name,'--ignore-not-found','--wait=true','--timeout=90s'],timeout=120)
        if scaled:
            call(['scale','deployment',a.deployment,'--replicas=1'])
            print('Original replica count restored. Verify /readyz and a fixture before accepting work.')
        if not complete:a.out.unlink(missing_ok=True)
if __name__=='__main__':main()
