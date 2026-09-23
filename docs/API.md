# API reference

Local bootstrap URL: `http://127.0.0.1:8088`. Inside the container/cluster the port
is 8080. Interactive OpenAPI docs are at `/docs`. No cookie authentication is
used. `/api/*` requires `Authorization: Bearer <API token>`. The browser stores its
token only in tab session storage. `/metrics` uses a **different** token.

| Method/path | Behavior |
|---|---|
| `GET /` | Static browser UI |
| `GET /livez`, `/healthz` | Process liveness, no model/test execution |
| `GET /readyz` | DB/local-serving readiness and drain state; 503 while drained |
| `GET /metrics` | Prometheus text, separate bearer auth; 404 when unconfigured |
| `GET /api/config` | Non-secret provider/model/runner/limits/active run/drain information |
| `GET /api/model/health` | Model listing check, not a quality benchmark |
| `GET /api/repos` | Allowed source repositories |
| `POST /api/runs` | Start one run; 409 busy, 503 drained; validated repo/task/mode |
| `GET /api/runs` | Recent history |
| `GET /api/runs/{id}` | Status, pending approval and independent verification |
| `GET /api/runs/{id}/events?after=N` | SSE trace, route template metrics, reconnect cursor |
| `POST /api/runs/{id}/approvals/{approval_id}` | Exact single-use `{"approved": true/false}` |
| `POST /api/runs/{id}/cancel` | Explicitly cancel active work |
| `GET /api/runs/{id}/artifacts/{kind}` | Completed `patch`, `report` or `trace` download |
| `POST /api/admin/drain` | Reject new runs and preserve existing work |
| `POST /api/admin/resume` | Reopen admission after maintenance |

Example request body:

```json
{"repo":"demo-redis","task":"Reproduce and fix the Redis configuration bug; do not modify tests.","mode":"repair"}
```

`mode` is `repair` or `diagnose`; unknown extra fields are rejected. Diagnose omits
edit capability but still requires approval for tests. Run detail has a single
`pending_approval` object or null, not an unrestricted command queue. A stale or
already-decided capability is rejected. `verified=true` is derived from test exit
status and snapshot identity, not a model's final sentence.

Security headers, explicit allowed hosts and exact browser-origin checks are
applied. No arbitrary reverse-proxy headers are trusted. Configure `publicOrigin`
and TLS at a reviewed private ingress instead of disabling these protections.
SSE should not be proxy-buffered. Avoid putting tokens into URLs, screenshots,
logs or public issues. The supplied smoke scripts read tokens from files.
