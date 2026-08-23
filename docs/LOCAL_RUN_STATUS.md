# Local run and validation — 2026-09-21

The application was started successfully in this checkout using its existing Python 3.12.3 virtual environment and preserved configuration.

- URL: http://127.0.0.1:8091
- Version: 0.3.0
- Provider: `demo` (scripted, no model inference)
- Runner: `host-trusted` for bundled fixtures
- State directory: `.devpilot-local`
- Repository inputs: `workspace/demo-redis`, `workspace/demo-pagination`, `workspace/demo-normalize`

The server was launched directly with `DP_DATA_DIR=.devpilot-local DP_PORT=8091 .venv/bin/python -m devpilot serve --seed`. Its PID was recorded in `.devpilot-local/server.pid` so `./stop.sh` can stop this instance. For subsequent starts, use `./run.sh`. Availability here records this session's successful startup, not a guarantee that the process will survive a machine restart.

## Open and use

From the project directory, retrieve the token locally:

```bash
DP_DATA_DIR=.devpilot-local .venv/bin/python -m devpilot token
```

Open the URL, paste the token and click Connect. Select a demo and click Investigate. Review each test/edit approval. The existing history includes a completed Redis HTTP smoke run with a verified patch; its original input repository remained unchanged.

## Checks completed

| Check | Result |
|---|---|
| Installed dependency compatibility | `pip check`: no broken requirements |
| Test suite | **105 passed, 2 skipped**, 8.21 seconds |
| Configuration validator | **31 YAML/JSON files** parsed; schemas and runner policy intent passed |
| Live HTTP smoke | Liveness, readiness, API auth rejection, authenticated config/repositories passed |
| Metrics authentication | Separate metrics token accepted; missing/API token rejected |
| Redis workflow through running HTTP API | Completed, tests executed, final exit 0, tested snapshot matched, source unchanged |
| Three-fixture evaluation | **3/3 resolved**, including additional grading checks; scripted integration replay |

The skipped checks require opt-in Docker integration and the optional official MCP SDK. Docker containers, Kubernetes deployment, browser automation, a live Qwen model, full monitoring deployment, and CI publishing were not exercised in this session. The unit suite includes controlled Kubernetes API checks, which do not replace cluster execution.

Initial sandbox runs could not bind/connect to localhost, and subprocess-heavy validation did not complete normally there. Those attempts were stopped, and the successful server and validation runs used approved execution outside the sandbox. No application-code fix or dependency upgrade was needed.

## Evidence

- [Test suite JUnit output](../outputs/local-review-20260921/junit.xml)
- [Three-fixture summary](../outputs/local-review-20260921/replay/summary.md)
- [Replay result JSON](../outputs/local-review-20260921/replay/summary.json)
- [HTTP Redis result](../outputs/local-review-20260921/http-demo/result.json)
- [HTTP Redis patch](../outputs/local-review-20260921/http-demo/changes.patch)
- [HTTP Redis report](../outputs/local-review-20260921/http-demo/report.md)
- [HTTP Redis trace](../outputs/local-review-20260921/http-demo/trace.json)

The original packaged `outputs/` evidence remains separate from this session's `outputs/local-review-20260921/` results. Credentials are not included in this report.

Read the [codebase walkthrough](CODEBASE_WALKTHROUGH.md) for the complete architecture, module map, configuration, workflows and deployment explanation.
