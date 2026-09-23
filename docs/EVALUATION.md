# Evaluation protocol

## Three separate questions

1. **Does the software integration work?** Scripted replay exercises real files, MCP subprocesses, approvals, Git, and pytest with known actions.
2. **Can the configured model solve the task?** Live evaluation uses the actual local model, the same tool interface, and a Docker runner.
3. **Is the repair generally correct and safe?** Independent review and additional unseen checks are needed. Neither a scripted policy nor one passing test suite proves this.

Never report the scripted resolution rate as an LLM accuracy score.

## Included tasks

| Task | Seeded defect | Expected application-level repair |
|---|---|---|
| Redis default | `localhost` points at the backend container rather than a separate service | Use the intended Compose service default while retaining explicit overrides |
| Pagination | First item is skipped by an off-by-one slice | Preserve page validation and return the intended page slice |
| Username normalization | Case conversion does not normalize surrounding whitespace / full Unicode case | Strip surrounding whitespace and use Unicode-aware case folding |

These are deliberately small synthetic fixtures, not real GitHub issue resolutions. Baseline test code is visible to the agent. Extra grading checks are withheld from the run workspace until the agent finishes, but are public in this repository; this is not a contamination-proof secret benchmark.

## Commands

```bash
python -m devpilot evaluate --out outputs/local-replay --label replay
# Real model configured in .env; Docker runner required:
python -m devpilot evaluate --live --out outputs/live-model-run1 --label my-model-run1
```

The harness auto-approves the fixed test action and edits only to the task's known application file. This is a dedicated fixture runner, not the normal web approval behavior. Live evaluation must use Docker. Model quality will vary; failures are legitimate results.

## Resolution rule

A case is resolved only when the run completed, the app recorded a passing test execution on the unchanged final snapshot, and the separate grading run exited zero without timeout/output truncation.

Outputs per case:

- `trace.json`: exact tool events, approvals, run metadata, metrics, and verification.
- `changes.patch`: real patch from the fresh Git baseline.
- `report.md`: human-readable explanation and evidence.
- `heldout-tests.json`: output from the additional final checks.
- `result.json`: per-case resolution result.

`summary.json` and `summary.md` aggregate these exact cases. They never mix scripted and live results in one summary.

## Metrics and limitations

Tool count/error count and model turns are recorded. Tool/LLM/wall durations are measured locally; wall time includes startup and approval waits. Token counts are recorded only when the provider reports them and remain null in scripted mode. No fabricated cost estimate, token count, or throughput figure is generated.

Unit-test coverage is main-process instrumentation. It does not automatically include the spawned MCP server processes. Read the coverage report as a code-testing signal, not a security score or whole-system execution percentage.

## Before publishing a serious model benchmark

Create a larger independently authored task set, freeze inputs and grading criteria, separate development from held-out tasks, run multiple repetitions, retain every outcome, and report model identity/revision, weight format, inference engine version, runner image digest, hardware, parameters, and resource limits. Compare controlled ablations; MCP transport alone should not be credited with an intelligence improvement.

Include failures such as nonexistent tools, malformed arguments, denied approvals, wrong patches, tests that fail, and unsupported project dependencies. Do not select only the most attractive transcript.

## DevOps release distinction

The 0.3.0 additions test deployment boundaries, not new model intelligence.
Kubernetes API unit tests use controlled HTTP responses and cannot establish real
CNI/admission behavior. Execute the opt-in kind workflow for cluster evidence.
Record demo, model, Docker and Kubernetes results separately.
