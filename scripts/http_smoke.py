#!/usr/bin/env python3
"""Read-only HTTP smoke checks. Does not edit code or approve agent actions."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
import httpx
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from devpilot.api import ensure_token
from devpilot.config import Settings

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url',default='http://127.0.0.1:8088')
    p.add_argument('--token-file',type=Path)
    p.add_argument('--metrics-token-file',type=Path)
    a=p.parse_args()
    token=a.token_file.read_text().strip() if a.token_file else ensure_token(Settings())
    with httpx.Client(base_url=a.url, timeout=10, trust_env=False, follow_redirects=False) as c:
        h=c.get('/livez');h.raise_for_status()
        r=c.get('/readyz');r.raise_for_status()
        assert c.get('/api/repos').status_code == 401
        headers={'Authorization':'Bearer '+token}
        config=c.get('/api/config',headers=headers);config.raise_for_status()
        repos=c.get('/api/repos',headers=headers);repos.raise_for_status()
        result={'live':h.json(),'ready':r.json(),'auth_rejection':True,'config':config.json(),'repositories':repos.json()}
        if a.metrics_token_file:
            assert c.get('/metrics').status_code == 401
            assert c.get('/metrics',headers=headers).status_code == 401
            response=c.get('/metrics',headers={'Authorization':'Bearer '+a.metrics_token_file.read_text().strip()})
            response.raise_for_status()
            assert 'devpilot_http_requests_total' in response.text
            result['separate_metrics_auth']=True
        print(json.dumps(result,indent=2))
if __name__=='__main__': main()
