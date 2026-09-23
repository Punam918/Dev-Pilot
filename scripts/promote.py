#!/usr/bin/env python3
"""Update reviewed image DIGESTS in GitOps values; never connects to a cluster."""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
import yaml
ROOT = Path(__file__).resolve().parents[1]

def digest(value: str) -> str:
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise argparse.ArgumentTypeError("Expected sha256: followed by 64 lowercase hex characters")
    return value

def image(value: str) -> str:
    if not re.fullmatch(r"ghcr\.io/[a-z0-9][a-z0-9._/-]*", value) or '..' in value or value.endswith('/'):
        raise argparse.ArgumentTypeError("Use a lowercase ghcr.io/owner/image repository WITHOUT a tag")
    return value

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True, help='release-manifest.json from a successful publish workflow')
    p.add_argument('--environment', choices=['staging','production'], default='production')
    a=p.parse_args()
    m=json.loads(a.manifest.read_text())
    if m.get('security_gate') != 'passed':
        p.error('Manifest must record a passed remote-image security scan')
    path=ROOT/'deploy/environments'/a.environment/'values.yaml'
    values=yaml.safe_load(path.read_text())
    for key, destination in [('app',values.setdefault('image',{})), ('runner',values.setdefault('runner',{}).setdefault('image',{}))]:
        destination.update(repository=image(m[key]['repository']), digest=digest(m[key]['digest']), tag='')
    path.write_text('# Generated promotion; review this diff and open a pull request.\n'+yaml.safe_dump(values,sort_keys=False))
    print(f'Updated {path.relative_to(ROOT)}. No cluster changes were made.')
    print('Review the source commit, scan artifacts and BOTH image digests before merging.')
if __name__=='__main__': main()
