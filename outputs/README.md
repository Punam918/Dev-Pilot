# Recorded execution outputs

`environment.json` records the evidence boundaries for these outputs. These are local packaging results, not remote CI outcomes. `replay/` and `http-fixture/` exercise known scripted fixtures, not an LLM. Chart rendering is the static helper, not real Helm. No GPU/cluster/Trivy/Grafana results are fabricated. `outputs-previous-0.2.0/` is retained separately as historical evidence only.

`coverage.json` stores the current main-process statement coverage. Optional SDK and real-Docker checks are skipped when their requirements are absent. Timing, UUIDs and temporary directory paths are actual local-run metadata; they are not stable benchmark identifiers.
