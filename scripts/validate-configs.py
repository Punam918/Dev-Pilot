#!/usr/bin/env python3
"""Offline parsing/schema/policy checks. NOT Helm, kube-apiserver, PromQL or Terraform validation."""
from __future__ import annotations
import argparse
import copy
import json
import re
from pathlib import Path
import yaml
from jsonschema import validate
ROOT=Path(__file__).resolve().parents[1]
class Loader(yaml.SafeLoader): pass
Loader.yaml_implicit_resolvers=copy.deepcopy(yaml.SafeLoader.yaml_implicit_resolvers)
for key,items in list(Loader.yaml_implicit_resolvers.items()):
    Loader.yaml_implicit_resolvers[key]=[(tag,regexp) for tag,regexp in items if tag!='tag:yaml.org,2002:bool']
Loader.add_implicit_resolver('tag:yaml.org,2002:bool',re.compile(r'^(?:true|false|True|False|TRUE|FALSE)$'),list('tTfF'))
def construct_map(loader,node,deep=False):
    result={}
    for key,value in node.value:
        k=loader.construct_object(key,deep=deep)
        if k in result:raise ValueError(f'Duplicate YAML key: {k!r}')
        result[k]=loader.construct_object(value,deep=deep)
    return result
Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,construct_map)
def load(path):return yaml.load(path.read_text(),Loader=Loader)
def merge(base,overlay):
    result=copy.deepcopy(base)
    for k,v in overlay.items():
        result[k]=merge(result[k],v) if isinstance(v,dict) and isinstance(result.get(k),dict) else copy.deepcopy(v)
    return result

def validate_documents(docs):
    docs=[d for d in docs if d]
    deployments=[d for d in docs if d.get('kind')=='Deployment' and d.get('metadata',{}).get('labels',{}).get('app.kubernetes.io/name')=='devpilot']
    assert len(deployments)==1,'Expected one DevPilot Deployment'
    dep=deployments[0];spec=dep['spec'];pod=spec['template']['spec']
    assert spec['replicas']==1 and spec['strategy']['type']=='Recreate'
    assert pod['securityContext']['runAsNonRoot'] is True
    for c in pod['containers']:
        assert c['securityContext']['allowPrivilegeEscalation'] is False
        assert c['securityContext']['readOnlyRootFilesystem'] is True
        assert c['securityContext']['capabilities']['drop']==['ALL']
        assert all(x in c for x in ['resources','startupProbe','readinessProbe','livenessProbe'])
    assert not any('hostPath' in v for v in pod['volumes']), 'No Docker socket or host directories'
    assert not any(d.get('kind') in ['HorizontalPodAutoscaler','ClusterRole','ClusterRoleBinding','Secret'] for d in docs)
    for role in [d for d in docs if d.get('kind')=='Role']:
        for rule in role['rules']:
            assert not any(x in rule['resources'] for x in ['secrets','pods/exec','*'])
            assert '*' not in rule['verbs']
            if 'pods' in rule['resources']:assert set(rule['verbs']) <= {'get','list'}
    print(f'Rendered chart policy checks: {len(docs)} resources; one replica; no host mounts, exec, cluster-wide RBAC or embedded secrets.')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--rendered',type=Path);a=p.parse_args()
    n=0
    for path in ROOT.rglob('*'):
        rel=path.relative_to(ROOT)
        if any(x in rel.parts for x in ['.git','.venv','.devpilot','.secrets','outputs','outputs-previous-0.2.0','__pycache__','.terraform']):continue
        if 'templates' in rel.parts or not path.is_file():continue
        if path.suffix in {'.yml','.yaml'}:
            list(yaml.load_all(path.read_text(),Loader=Loader));n+=1
        elif path.suffix=='.json':json.loads(path.read_text());n+=1
    base=load(ROOT/'helm/devpilot/values.yaml');schema=json.loads((ROOT/'helm/devpilot/values.schema.json').read_text())
    validate(base,schema)
    for env in ('staging','production'):validate(merge(base,load(ROOT/f'deploy/environments/{env}/values.yaml')),schema)
    docs=list(yaml.load_all((ROOT/'infra/kubernetes/runner-namespace.yaml').read_text(),Loader=Loader))
    net=next(d for d in docs if d['kind']=='NetworkPolicy')
    assert set(net['spec']['policyTypes'])=={'Ingress','Egress'} and not net['spec'].get('ingress') and not net['spec'].get('egress')
    for path in (ROOT/'.github/workflows').glob('*.yml'):
        doc=load(path);assert 'on' in doc
        assert doc.get('permissions',{}).get('contents')=='read'
        for job in doc['jobs'].values():
            for step in job.get('steps',[]):
                action=step.get('uses','')
                if action and not action.startswith('./'):assert re.fullmatch(r'[^@]+@[a-f0-9]{40}',action),f'Unpinned action in {path}'
    print(f'Parsed {n} YAML/JSON files; Helm values schemas and runner policy intent passed. Production placeholders are intentional.')
    if a.rendered:validate_documents(list(yaml.load_all(a.rendered.read_text(),Loader=Loader)))
    print('Not a live deployment. Actual helm lint, promtool, Terraform, Docker and cluster tests remain separate checks.')
if __name__=='__main__':main()
