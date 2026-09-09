#!/usr/bin/env python3
"""Prepare values for the offline Go chart-rendering aid; actual Helm is used in CI."""
import argparse
import importlib.util
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('validation',ROOT/'scripts/validate-configs.py')
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
p=argparse.ArgumentParser();p.add_argument('--values',type=Path);a=p.parse_args()
values=v.load(ROOT/'helm/devpilot/values.yaml')
if a.values:values=v.merge(values,v.load(a.values))
v.validate(values,json.loads((ROOT/'helm/devpilot/values.schema.json').read_text()))
print(json.dumps({'Values':values,'Release':{'Name':'devpilot','Namespace':'devpilot','Service':'Helm'},'Chart':{'AppVersion':'0.3.0'},'Template':{'BasePath':'devpilot/templates'}}))
