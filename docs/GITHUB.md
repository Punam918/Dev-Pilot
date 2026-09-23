# Publish a portfolio repository

## Prepare the content

Extract into a fresh directory; do not overwrite your employer repository. This
project contains no employer code. Use public/synthetic tasks, and remove personal
source, credentials, logs, model files and Terraform state from any future commits.

```bash
cd /path/to/devpilot
git init -b main
git status --short
# Review .gitignore, README, docs/VALIDATION.md, and every staged file.
git add .
git diff --cached --stat
git diff --cached --name-only
git commit -m "feat: DevPilot MCP workbench with DevOps delivery and evidence"
```

Create an empty GitHub repository in your account, then replace the placeholder:

```bash
git remote add origin https://github.com/YOUR_USERNAME/devpilot.git
git push -u origin main
```

No remote repository was created or pushed by this archive. Enable Actions and
watch actual workflow outcomes. Do not add a green CI badge until its URL points
to your repository and the workflow genuinely passes.

## Make the README yours

Keep the honest scope/evidence sections. Replace Argo repo URLs, image owners and
any domain examples; configure GitHub Environment/branch protections. Add your own
recorded demo video, measured live-Qwen results, cluster exercise and failure
analysis. State which pieces you implemented/extended/reviewed and understand
before discussing them in an interview. Do not copy a fabricated solve rate.

Suggested repository description:

> Evidence-first AI debugging workbench: local Qwen + MCP, approval-gated patches,
> isolated pytest Jobs, Helm/GitOps delivery, metrics/traces and reproducible tests.

Suggested topics: `ai-agents`, `mcp`, `qwen`, `fastapi`, `kubernetes`, `helm`,
`gitops`, `devops`, `prometheus`, `opentelemetry`, `llm-evaluation`.

## An interview demonstration

Show the known fixture failure, the MCP read/search trace, human patch approval,
real failing/passing pytest output and downloaded patch. Then show how the same
app is packaged, why it is one replica, what a Job can access, a measured network
policy test, CI artifacts and the drain/rollback procedure. Explain why the demo
is not a model benchmark. Once live-model evaluation exists, show successes **and
failures**, exact model/serving versions and held-out tasks.

## Release safely

Follow CI-CD.md. Publish only reviewed source, protect the release Environment,
scan both image digests and promote them through a PR. No paid cloud account is
required to demonstrate the local product, Compose stack or kind lab.
