# Delivery: CI, release images, promotion and GitOps

## Workflows actually provided

| Workflow | Trigger | Purpose |
|---|---|---|
| `ci.yml` | main push, PR, manual, reusable workflow | Python 3.11/3.12/3.13 tests; lint/compile; offline configuration checks; real Helm lint/render; Prometheus rule tests; Docker runner and Compose HTTP/fixture integration |
| `security.yml` | PR/main/weekly/manual | Trivy secrets/dependency gate; separate IaC report for human review |
| `publish.yml` | version tag or manual | Requires CI; builds/pushes app+runner candidates; attaches BuildKit SBOM/provenance; scans exact pushed digests; emits promotion manifest only after scans pass |
| `kind.yml` | manual only | Builds a dedicated kind/Calico lab, tests runner egress denial and the actual Kubernetes fixture workflow, uploads diagnostics, deletes only that lab |

Reusable Actions are pinned to reviewed commit SHAs. Dependabot is configured for
Actions, Python and Docker. GitHub runners are ephemeral; never route untrusted
pull-request code to a privileged shared/self-hosted production runner.

**These workflows are source code, not a claim that they have already run on your
GitHub account.** See VALIDATION.md. An image vulnerability or incompatible pin
should fail a gate and trigger review; do not suppress it simply to obtain a badge.

## First GitHub setup

Publish the repository as described in GITHUB.md. Enable Actions, allow package
writes only for the release workflow, and create a `release` Environment with
required reviewers and tag/branch restrictions appropriate to your account.
Environment protection is a **GitHub setting**, not automatically configured by
committing YAML. Protect `main` and require the relevant CI/security checks.

CI does not require a cloud secret or a live model. The image publisher uses
`GITHUB_TOKEN` with `packages:write`, never a hard-coded registry password. The
private model endpoint/key is not needed in PR jobs.

## Build and publish

After reviewing the code, dependency constraints, third-party image pins and
security reports, create a version tag:

```bash
git tag v0.3.0
git push origin v0.3.0
```

The publisher builds **linux/amd64** app and runner images at:

```text
ghcr.io/<lowercase-owner>/<lowercase-repo>:sha-<commit>
ghcr.io/<lowercase-owner>/<lowercase-repo>-runner:sha-<commit>
```

Other architectures are not claimed. Each output also has an immutable digest.
Candidate images are uploaded **before** their remote scans, so an uploaded tag
alone is not release approval. A failed scan produces no passed promotion
manifest. The scan policy fails fixed HIGH/CRITICAL vulnerabilities; unfixed and
lower severity issues remain review responsibilities. IaC findings are a separate
report, not a blanket claim of secure configuration.

BuildKit `--sbom` / `--provenance` outputs are registry attachments. This is **not**
a claim of keyless Sigstore signatures or GitHub-signed artifact attestations.
Add a verified signing/verification policy before claiming that stronger supply
chain property. Release reproducibility also requires reviewed base-image
digests and hash locks; the lab Python base tag remains configurable.

Download `release-evidence` from the successful workflow. It contains metadata,
both image scan reports and `release-manifest.json`. Review provenance, the source
commit, the exact digest pair and the scan result, then:

```bash
git switch -c deploy/devpilot-0.3.0
python scripts/promote.py --manifest /path/to/release-manifest.json --environment production
git diff -- deploy/environments/production/values.yaml
# Configure model endpoint/resources/ingress separately, with no credentials in Git.
git add deploy/environments/production/values.yaml
git commit -m "deploy: promote reviewed DevPilot app and runner digests"
git push -u origin deploy/devpilot-0.3.0
```

Open a reviewed pull request. The script validates fields; a JSON file with
`security_gate=passed` is **not a cryptographic signature**. Treat workflow access,
artifact source and code review as trust boundaries. No app-token/registry-key
bytes belong in the manifest.

## Argo CD setup

Install a reviewed Argo CD version through your platform process. Customize
`argocd/project.yaml` and `argocd/application.yaml`: replace the example repository
URL and review namespaces/resource allowlists. Configure private Git repository
access through Argo, not embedded tokens in manifests. Prepare namespaces/CNI and
`devpilot-secrets` as in KUBERNETES.md.

```bash
kubectl --context YOUR_CONTEXT apply -f argocd/project.yaml
kubectl --context YOUR_CONTEXT apply -f argocd/application.yaml
```

Replace `YOUR_CONTEXT`. The AppProject limits repository and destination scopes.
The application reads `helm/devpilot` and the production values in this repository.
**Automatic sync is deliberately off.** Approval state lives in memory; a naive
auto-update can interrupt a reviewed run. Do not also let Terraform or a manual
Helm release controller own the same application.

## Update procedure

1. Merge the reviewed image/config promotion and check Argo's rendered diff.
2. Through a private endpoint/port-forward, run `python scripts/drain.py`. It
   rejects new work and waits; review pending approvals instead of bypassing them.
3. Record the outgoing digest and take the appropriate offline backup for state
   changes. Complete a maintenance window; one replica means a short outage.
4. Sync the reviewed Argo application, wait for readiness and run HTTP/auth plus
   fixture checks in **staging**. Do not auto-approve a real-model production run.
5. Inspect errors, model connectivity, metrics and disk. The restarted process
   accepts work normally; an unchanged drained process needs explicit resume.

`/livez` is not dependent on the model: model downtime must not produce a liveness
restart loop. `/readyz` becomes false during drain, while an existing connection
or port-forward can still show approvals. A drained backend may disappear from
ingress endpoints; use a private direct port-forward for maintenance review.

## Rollback

Revert the bad **GitOps promotion commit** in a reviewed PR, drain, and sync that
reverted desired state. Do not run `kubectl rollout undo` while Argo still desires
the bad image—it can be overwritten again. App and runner digests are a pair.
A code rollback is not a database restore; inspect state/schema compatibility and
use BACKUP.md only when appropriate. Stateful rollback is deliberately not
advertised as automatic canary recovery.

## Optional Terraform owner

`terraform/` installs this chart onto an existing cluster. It does not create
AWS/GCP resources or GPUs. It is an alternative to Argo, not additional GitOps
infrastructure. Explicit context and values path are required. Generate and review
the provider lock on a connected machine. Details: `terraform/README.md`.
