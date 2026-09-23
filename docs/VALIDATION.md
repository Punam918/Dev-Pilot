# Validation report - DevPilot 0.3.0

Recorded on **2026-09-16**, Linux / Python **3.13.5**. This report separates actual execution from deployable source that still needs a suitable Docker/Kubernetes/GPU environment. Raw records are under `outputs/`; the separate `outputs-previous-0.2.0/` directory is historical and not current evidence.

## Executed for this release

| Check | Actual result | Evidence (paths from repository root) |
|---|---|---|
| Complete Python regression suite | **105 passed, 2 skipped, 0 failed** | `outputs/tests-console.txt`, `outputs/junit.xml` |
| Main-process statement coverage | **79.02%** (1574/1992 statements) | `outputs/coverage.json`; subprocess coverage is not merged |
| MCP subprocess transport / approvals / cancellation | Passed within the regression suite | `tests/test_protocol.py`, `tests/test_runtime_api.py` |
| Real localhost TCP/Uvicorn workflow | Authentication, seed repository, three approvals, actual before/after pytest, verified patch export passed | `outputs/http-smoke.json`, `outputs/http-fixture/`, `outputs/http-server.log` |
| Drain and resume through real HTTP | Drained readiness/new runs return 503; liveness/read access remain; resume restores readiness | `outputs/drain-smoke.json` |
| Metrics endpoint | Distinct bearer credential, bounded labels, no tested API credential leaks; actual sample captured | `outputs/metrics-sample.prom`, `tests/test_devops_api.py` |
| Actual OTLP HTTP export | Protobuf traces received by a local test server; reviewed attributes only; tested prompt/exception text excluded | `tests/test_otlp_export.py` in the full JUnit report |
| Kubernetes runner code | Snapshot bounds, command/pod restrictions, controlled API lifecycle, exit codes and cleanup tested | `tests/test_kubernetes_runner.py`; HTTP API responses are controlled, **not a live cluster** |
| Backup/restore | Real local SQLite/archive round trip; credentials excluded; active instance/path traversal rejected | `tests/test_backup.py` |
| Three scripted fixture replays | **3/3 resolved**, real MCP/edit/pytest/patch/extra checks | `outputs/replay/summary.json`, `outputs/replay-console.txt` |
| Wheel build / isolated-target install | Built 0.3.0 offline and installed into another directory using existing dependencies | `outputs/wheel-build.txt`, `outputs/wheel-install.txt` |
| Installed-wheel Redis workflow | Completed through the installed package rather than the source working directory | `outputs/installed-smoke.txt`, `outputs/installed-cli.txt` |
| Python / JavaScript / shell syntax | Python AST, Node syntax check, Bash syntax checks passed | `outputs/source-check.json` |
| Configuration and chart policy | YAML/JSON parsing, values JSON Schema, static rendered policy and six guard cases passed | `outputs/config-validation.txt`, `outputs/chart-static-default.yaml`, `outputs/chart-guard-checks.json` |

The chart was rendered with the included **limited Go text/template helper**, not Helm. This checks the template syntax used here and policy structure; it does **not** certify Helm/Sprig parity, Kubernetes admission, API schemas, storage, scheduling, RBAC effectiveness or networking. Synthetic all-zero digest values in guard tests are only in-memory test inputs, never actual release images.

Coverage is a test coverage statistic, not AI quality or security assurance. The archive contains actual failure/recovery and error-path tests; passing tests do not prove absence of vulnerabilities.

## Actual fixture results

| Fixture | Before repair | After repair | Final suite with extra checks |
|---|---|---|---|
| Redis hostname default | 1 failed, 3 passed | 4 passed | 6 passed |
| Pagination | 1 failed, 4 passed | 5 passed | 7 passed |
| Username normalization | 2 failed, 3 passed | 5 passed | 7 passed |

These known fixture policies run **without an LLM** and use trusted-host pytest. They are integration replays, not measured Qwen intelligence. Normal web runs require each approval; the fixture-only harness is explicitly allowed to auto-approve the bundled trusted cases. The Redis case checks a config value, not live Redis availability.

## Not executed or not established here

- **Docker image builds / Compose / Docker runner:** no Docker binary/daemon was available. The optional actual-Docker test was skipped. Container source is included, not labeled as locally verified.
- **Real Helm / promtool / Kubernetes / kind / Calico / Argo CD:** tools/cluster unavailable. CI and a manual kind workflow are provided to perform real deployment and deny-egress checks. YAML validity does not prove network isolation.
- **Terraform initialization or provider apply:** not run; existing-cluster provider configuration is included. Generate a reviewed lock on a connected machine.
- **Remote GitHub Actions, registry publishing, Trivy security scans and SBOM/provenance publication:** not run against your account. No green CI badge or clean vulnerability report is invented. Source guard tests are not those external tools.
- **Live Ollama/Qwen/vLLM/GPU:** no model download, live inference, GPU memory, latency or AI solve rate was measured. Model-client tests use controlled HTTP replies. Use MODEL-SETUP.md and real-model evaluation to establish your own results.
- **Official MCP SDK interoperability:** optional SDK unavailable, so the integration is skipped. The included subset is dated 2025-06-18, not full/latest-spec certification.
- **Collector/Tempo/Grafana runtime:** OTLP was actually exported to a local test receiver; the full containerized observability stack was not started.
- **New browser end-to-end session:** not performed for this release. The UI image is the original offline disconnected preview. Historical browser navigation was blocked by environment policy; no successful screenshot is fabricated.
- **Fresh network dependency resolution / all Python versions:** wheel installation used installed Python 3.13 dependencies, not a new online Python 3.11/3.12 container. The CI matrix remains an acceptance check. Exact constraints are not a generated hash lock.
- **Production hardening, hostile-code sandbox certification, HA, penetration testing, disaster-recovery on a cluster:** not established. One API replica and short update outages are intentional.

## Reproduce and complete acceptance

```bash
python -m pytest --cov=devpilot --cov-report=term-missing
python scripts/validate-configs.py
python -m devpilot evaluate --out outputs/local-replay --label my-scripted-check

# On a machine with the required tools:
helm lint helm/devpilot --strict
helm template devpilot helm/devpilot --namespace devpilot > /tmp/devpilot-rendered.yaml
python scripts/validate-configs.py --rendered /tmp/devpilot-rendered.yaml
docker build -f Dockerfile.runner -t devpilot-runner:local .
DP_TEST_DOCKER=1 python -m pytest tests/test_docker_integration.py -q
```

Follow KUBERNETES.md for the dedicated enforcing-CNI cluster and a real test Job; follow MODEL-SETUP.md for the live model. Record image digests, hardware, model revision/template, tool-call errors, latency and failures. Keep these separate from the packaged scripted evidence.
