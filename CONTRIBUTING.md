# Contributing

Use public/synthetic data and no employer code. Start with the README quick start,
then read ARCHITECTURE.md and SECURITY.md before modifying a tool or runner.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements/dev.txt
python -m pip install --no-deps -e .
python -m ruff check devpilot tests scripts runner
python scripts/validate-configs.py
python -m pytest -q
```

Each change to a permission, approval, file boundary, native tool parser,
verification state or runner needs tests for both allowed and rejected cases.
Keep model output out of authority decisions. Never update fixture results by
inventing output or letting the agent modify expected tests.

Describe what was actually executed: static YAML checks, mock HTTP API tests,
real subprocess MCP tests, Docker runs, cluster runs and live-model runs are
separate evidence. Preserve failures. A CI YAML file is not a passing CI run.

Good next tasks: official MCP SDK migration with compatibility tests; tokenizer-
aware budgets; held-out model evaluation; encrypted object-store snapshots for
larger repositories; more robust VM-level execution; durable shared run/approval
ownership before attempting replicas; reviewed GitHub pull-request export;
external identity provider integration for a redesigned multi-user service.

Formatting/lint intentionally gates correctness-focused rules rather than
requiring a giant style rewrite. Keep PRs focused, document the tradeoff, and
update operator runbooks for deployment/state changes. Real clusters, cloud bills
and registry publication require explicit operator consent and credentials outside Git.
