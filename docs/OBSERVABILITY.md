# Observability

## Local full stack

```bash
python3 scripts/bootstrap.py
docker compose -f compose.yaml -f compose.monitoring.yaml up -d --build
cat .secrets/grafana-password
```

DevPilot stays on 8088. Grafana is 13000 (`admin` + generated password), Prometheus
19090 and Alertmanager 19093; all published addresses bind **127.0.0.1**. Collector
and Tempo use internal Docker networking. Their image versions are explicit lab
candidates; execute/scan them locally before making a production compatibility
claim. Do not expose unauthenticated Prometheus/Alertmanager to a public network.

Grafana provisioning installs the Prometheus and Tempo data sources and the
`DevPilot | Agent and API Operations` dashboard. The repository includes the
actual dashboard JSON, not a screenshot of invented metrics. No Loki deployment
is claimed: logs are structured application records on stdout, inspected through
Compose/Kubernetes or forwarded by an operator's log collector.

## Metrics contract

`/metrics` requires its own bearer token. With no token configured it returns 404;
missing/wrong token returns 401. The API token is not the metrics token. Run the
included HTTP smoke test to check both authentication boundaries.

| Metric family | Interpretation |
|---|---|
| `devpilot_http_requests_total` | Bounded method, route template and status; excludes health/metrics scraping |
| `devpilot_http_request_duration_seconds` | Time until response headers; **not full SSE stream lifetime** |
| `devpilot_active_runs` | Zero or one active run |
| `devpilot_pending_approvals` | Waiting operator decisions |
| `devpilot_accepting_runs` | Admission state; zero while drained |
| `devpilot_ready` | Last evaluated application readiness |
| `devpilot_runs_total` | Terminal outcome grouped by provider, status and verification |
| `devpilot_run_duration_seconds` | Includes user-approval waiting time; not pure inference latency |
| `devpilot_tool_calls_total` | Known tool name and outcome; unknown names collapse into a bounded label |
| `devpilot_tool_duration_seconds` | Tool-boundary duration |
| `devpilot_model_request_duration_seconds` | Adapter completion-call duration, including retry cost |
| `devpilot_model_tokens_total` | Only actual usage fields returned by the provider; missing is not invented zero usage |

Each process also exports standard Python/process metrics. The application does
not measure GPU memory, TTFT, per-token throughput or infrastructure-wide CPU by
itself. Scrape your model/server/node exporters separately before claiming those
metrics. Separate `provider=demo` outcomes from `provider=openai` in every quality
chart. A scripted successful repair is not a model capability measurement.

No prompt, source path, task text, run UUID, user name, query string, token or tool
argument is a metric label. Route labels use templates/`unmatched`, preventing an
attacker from creating one timeseries per URL. Detailed traces/reports remain in
protected per-run artifacts, not public metric labels.

## OpenTelemetry and Tempo

Set `DP_OTEL_ENABLED=true` and an HTTP OTLP endpoint ending in `/v1/traces`. The
container runtime constraints already include the SDK/exporter; a minimal pip
installation needs `.[observability]`. The Compose overlay sets the internal
Collector URL. The Collector batches to Tempo. Local trace retention is 24 hours;
Prometheus retention is 7 days. Size these volumes deliberately.

Spans cover HTTP requests, model completion and MCP tool operations. Attributes
are bounded operational metadata, not prompt/response bodies. Raw exception
capture is disabled at this boundary. This is not an auto-instrumentation claim
for every library. Trace and metric recording are not durable transactional audit;
SQLite/artifacts provide the per-run evidence store. Collector failure must not
be confused with task verification failure.

## Alerts

Included rules: target down for two minutes, >5% HTTP 5xx with sufficient traffic,
and approval waiting for two minutes. They have matching runbooks and rule-test
fixtures. Approval waiting is informational, not automatically a fault.

```bash
docker run --rm --entrypoint promtool -v "$PWD/monitoring/prometheus:/work:ro" -w /work \
  prom/prometheus:v3.5.0 check rules rules/devpilot.yml
docker run --rm --entrypoint promtool -v "$PWD/monitoring/prometheus:/work:ro" -w /work \
  prom/prometheus:v3.5.0 test rules test-rules.yml
```

`Alertmanager` initially records alerts in its UI only. Configure a real
notification receiver, its secret injection and a delivery test before claiming
Slack/email paging. No external account is required by this archive.

## SLO proposal, not an achieved measurement

A useful staging objective is 99% successful **application HTTP requests** over a
reviewed window, excluding intentional authorization rejection and maintenance.
The included alert is a short-window symptom, not a full multiwindow error-budget
policy. Model quality, tool-call correctness, task verification and service uptime
are distinct SLIs. Publish an observed time window, traffic volume and failure
analysis before presenting an SLO as met.

In Kubernetes, ServiceMonitor is opt-in and requires the operator's CRDs and
selectors. The downward API adds the valid Pod IP to allowed hosts so authenticated
scrapes work. The chart does not install Prometheus Operator/cluster dashboards.
