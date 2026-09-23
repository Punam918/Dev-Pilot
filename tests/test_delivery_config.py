"""Offline policy checks are intentionally distinct from real Helm/Kubernetes validation."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]

def script(name):
    spec=importlib.util.spec_from_file_location('testscript_'+name.replace('-','_'),ROOT/'scripts'/name)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def test_configs_parse_and_pass_policy_intent():
    result=subprocess.run([sys.executable,'scripts/validate-configs.py'],cwd=ROOT,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr

def test_helm_values_reject_horizontal_scaling():
    v=script('validate-configs.py');values=v.load(ROOT/'helm/devpilot/values.yaml');values['replicaCount']=2
    with pytest.raises(Exception):v.validate(values,json.loads((ROOT/'helm/devpilot/values.schema.json').read_text()))

def test_promotion_validates_immutable_digest_and_repository():
    m=script('promote.py')
    assert m.digest('sha256:'+'a'*64)=='sha256:'+'a'*64
    assert m.image('ghcr.io/example/devpilot')=='ghcr.io/example/devpilot'
    for x in ['latest','sha256:123','sha256:'+'A'*64]:
        with pytest.raises(Exception):m.digest(x)
    for x in ['ghcr.io/User/app','ghcr.io/test/app:latest','x;rm -rf /','ghcr.io/test/../image']:
        with pytest.raises(Exception):m.image(x)

def test_packager_excludes_credentials_state_and_plans():
    m=script('package_zip.py')
    for relative in ['.env','.env.production','.secrets/api-token','backups/data.tar.gz','terraform/terraform.tfvars','terraform/dev.tfstate','terraform/change.tfplan','workspace/secret.py']:
        assert not m.included(ROOT/relative)
    assert m.included(ROOT/'.env.example')
    assert m.included(ROOT/'terraform/terraform.tfvars.example')

def test_smoke_script_uses_real_api_approval_contract():
    text=(ROOT/'scripts/cluster-smoke.py').read_text()
    assert "run.get('pending_approval')" in text
    assert "config.json()['provider']!='demo'" in text
    assert "--approve-trusted-fixture" in text
