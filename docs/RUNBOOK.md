# Runbook: first run, real models, diagnostics and safe shutdown

## 1. Pick one startup path

### Container demo (no GPU)

```bash
cd /path/to/extracted/devpilot
python3 scripts/bootstrap.py
docker compose up -d --build
docker compose ps
cat .secrets/api-token
```

Browse http://127.0.0.1:8088, connect with the token, select `demo-redis`, and review
the three approvals. The demo runs known bundled fixture code inside the app
container. It is **not a safe path for untrusted projects** and does not use Qwen.

### Host Python demo (no Docker)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements/dev.txt
python -m pip install --no-deps -e .
python scripts/bootstrap.py
python -m devpilot serve --seed
```

Host execution is explicit. Only use the unmodified bundled repositories in demo
mode. The API token is the same generated `.secrets/api-token`, but host state
lives in `.devpilot/` rather than the Compose named volume.

### Real AI

Follow [MODEL-SETUP.md](MODEL-SETUP.md). Use a real `DP_PROVIDER=openai` endpoint and
`DP_RUNNER=docker` on the host, or Kubernetes Jobs in the cluster. The demo Compose
file does not become live inference just because you edit the host `.env`.

## 2. Bring a small Python repository

Run real-model mode first. Copy a **trusted**, secret-free Python project to
`workspace/my-project/`. It must contain `tests/`. Begin with one focused bug:

> Reproduce the pagination failure, inspect the relevant code, propose the
> smallest change, and rerun the tests. Do not change tests or install packages.

The runner image ships pytest, not arbitrary project dependencies. Build an
operator-reviewed derivative image with pinned dependencies. For example:

```dockerfile
FROM devpilot-runner:local
USER root
COPY requirements.project.txt /tmp/project.txt
RUN python -m pip install --no-cache-dir -r /tmp/project.txt
USER 65534:65534
```

Build it yourself, scan it, then set `DP_RUNNER_IMAGE`. The agent has no pip-install
tool. Kubernetes must be able to pull that image by digest; `kind` can load a lab
image. The Kubernetes snapshot limit is **700KB compressed**, with existing
12MB/1500-file repository and 120KB/file bounds. Large monorepos are outside scope.

## 3. Evidence and checks

```bash
python -m devpilot doctor
python scripts/check_model.py  # requires configured real model
python scripts/http_smoke.py --token-file .secrets/api-token --metrics-token-file .secrets/metrics-token
python -m pytest -q
```

A green `/livez` is not proof the LLM is reachable. `/readyz` checks local serving
state and DB access, not model intelligence. `check_model.py` tests a small native
tool call; real quality still requires `evaluate --live` on unseen tasks.

For a connected **scripted fixture only** endpoint, this explicit test helper
approves the three demo actions automatically and exports actual output:

```bash
python scripts/cluster-smoke.py --approve-trusted-fixture --out outputs/local-http-smoke
```

It refuses `provider=openai`. Normal users must approve actions in the UI.

## 4. Safe shutdown and restart

Finish or explicitly cancel active work in the UI. To reject new tasks first:

```bash
python scripts/drain.py
```

The command waits without approving or cancelling anything. A pending approval
can block drain; review it in the UI. `/readyz` becomes 503 intentionally.

For Docker:

```bash
docker compose stop devpilot             # keeps containers and data
# Later:
docker compose start devpilot
```

For the monitoring stack:

```bash
docker compose -f compose.yaml -f compose.monitoring.yaml down
```

`down` removes this project's containers/network, **not named volumes by default**.
Do not add `--volumes` unless you intentionally want to erase stored history,
workspaces, metrics and traces after a tested backup. Never use global Docker
prune/kill commands to stop this one project.

For host Python, Ctrl+C stops the serving process. Interrupted work is recorded as
`interrupted` on restart, not silently resumed. An update needs a maintenance
window; this is not zero-downtime HA.

## Troubleshooting

| Symptom | Check / action |
|---|---|
| Another site opens | Verify port **8088**, not 8000/8080. Run `sudo lsof -nP -iTCP:8088 -sTCP:LISTEN`. Identify the owner before stopping it. |
| `docker ps` empty but Docker still owns a port | Inspect `docker context ls`, `docker context show`, `docker info`, and, only when relevant, the root daemon via `sudo docker ps`. Different contexts/rootless/Desktop daemons can have different containers. An empty list is not proof every local service is stopped. |
| Port 8088 occupied | For Compose: `DP_HTTP_PORT=8089 docker compose up -d --build`; for host Python set `DP_PORT=8089`. Browse the chosen port. |
| `.env` missing | Run `python3 scripts/bootstrap.py` from the root. Show hidden files with `ls -la` or Ctrl+H. |
| Token rejected | Use `.secrets/api-token` for new Compose/bootstrap setup, not the metrics or Grafana token. Existing `.env` can intentionally point to another token source. |
| Metrics 401 | Prometheus must use `.secrets/metrics-token`, never the API token. |
| `/readyz` 503 | The app may be drained; inspect `/api/config`, then `python scripts/drain.py --resume` only after maintenance. Check writable state and SQLite errors. |
| Model not listed / invalid tool call | Check exact model ID, endpoint, parser, API key and context budget. See MODEL-SETUP.md; no automatic model-success claim. |
| Tests fail on imports | Build an operator-reviewed runner with the project's dependencies; do not enable unrestricted shell/pip. |
| Second API worker fails | Deliberate state lock. Stop the other process; do not delete `service.lock` while it is running. |
| Kubernetes Job pending/failing | Namespace, RBAC, quotas, image-pull credentials, PSS, CNI and runtime resources. Follow OPERATIONS.md. |
| Run limit reached | Export/backup, stop the app and archive state deliberately. There is no silent deletion or infinite-retention claim. |

Source folders and bind-mounted project files are not erased by ordinary container
removal. A browser can also show cached content after a server stops; confirm the
listener and issue a new network request rather than relying on a tab alone.
