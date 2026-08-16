# Security model and deployment limits

DevPilot is a **single trusted-operator** local/private workbench. It is not an
audited multi-tenant service, hostile-code VM, production incident responder or
unrestricted agent. Do not expose it directly to the Internet or point it at
production infrastructure/secrets. Public repository contents and tests can be
malicious even when they look harmless.

## Boundaries enforced in code

Repository selection stays under an operator-controlled workspace root. Copies
exclude sensitive-looking paths, Git metadata, caches, links, large files and
oversized repositories. Reads/edits use normalized safe paths. Exact replacements
require the current file hash; tests and new/deleted files are not editable. There
is no generic shell, pip-install, force push, host restart or prune tool. Detailed
redaction is best effort, not proof that all credentials are removed.

Mutations and pytest require a single-use HMAC approval capability that binds the
tool, canonical arguments, snapshot fingerprint and expiry. The server verifies
it independently. Model text/repository instructions cannot grant approval,
change runner settings, choose a Kubernetes manifest or mutate deployment policy.
A denial/expiry is not permission to try another route around the restriction.

Original source, copied run workspace and test execution are distinct. The app's
verification flag requires real test evidence and matching snapshot state. Passing
selected tests does not prove general correctness or absence of vulnerabilities.

## Authentication and secrets

Every `/api/*` route requires the operator token. Metrics has a **separate** token.
Tokens are not cookies and no cross-origin credentialed access is enabled. The
UI keeps its API token in tab session storage. Explicit Host and browser Origin
validation, security headers and no trusted arbitrary forwarded headers protect
the browser boundary. An exact externally visible origin is required for ingress.
The downward API can add a validated local Pod IP for authenticated scraping.

Use private TLS ingress/VPN and external identity policy as needed. SSO, users,
RBAC within the application, per-user quotas and tenant isolation are not shipped.
The API token is powerful. Local `.secrets/` protects files via directory
permissions but is not encrypted; Kubernetes Secret base64 is not encryption.
Credential rotation requires a controlled restart. Never embed keys in Git,
Terraform values/state, logs, request URLs, model prompts or public issue reports.

## Execution modes

`host-trusted` is arbitrary code execution on the host and must be explicitly
enabled. The default demo accepts only the known fixture fingerprints. Do not
modify the Compose demo to accept untrusted projects or assume a non-root user
alone makes arbitrary tests safe.

The local Docker runner uses an operator-controlled image, read-only source,
fixed pytest command, disabled network, read-only root, dropped capabilities,
non-root UID and resource limits. The host operator's Docker access is highly
privileged; it is not handed to the model. Optional Docker observation requires
that authority and remains disabled by default. **No host Docker socket is mounted
in the app Compose service or Helm chart.** A socket mount marked `:ro` would not
make Docker API actions read-only.

The Kubernetes runner creates bounded Jobs in `devpilot-runners`, not the app
namespace. Jobs have no app PVC, model secrets or service-account token, no arbitrary
command parameter, restricted non-root security context, finite resources and
active deadlines. An immutable ConfigMap carries a <=700KB compressed sanitized
snapshot, and is owner-linked to the Job for cleanup. Administrators with ConfigMap
read access can inspect source; this is a confidentiality boundary to review.

The app service account can create/get/delete Jobs, create ConfigMaps, and read
pods/logs only in the runner namespace. It cannot read Secrets, exec into pods or
create cluster-wide RBAC. The control-plane app is trusted; compromise of that
app is not equivalent to untrusted test code. Creating Jobs is still meaningful
authority and must be namespace-scoped with enforced admission and network policy.

**NetworkPolicy is effective only with an enforcing CNI.** The bundled kind config
uses Calico rather than assuming kindnet enforces policy. Run the positive-control
network test. Restricted Pod Security does not supply network isolation. Containers
share a host kernel; use dedicated nodes/VMs or a reviewed sandbox RuntimeClass for
stronger hostile-code isolation. This release is not a guarantee against kernel
exploits or every resource/exfiltration channel.

## Operational data and delivery

Metrics/traces use bounded metadata, not prompts, code, token literals or run-ID
labels. Raw per-run artifacts can contain source/logs despite best-effort redaction;
keep their store/backups private. Archives are not encrypted. Restore validates
membership/hashes and requires a new destination; test restoration before relying
on it. Historical package evidence is labeled separately from current results.

GitHub PR jobs use ephemeral hosted runners, no cloud credentials and read-only
repository permissions. Release package writes are scoped to the publisher.
Actions are SHA-pinned; image/dependency versions still need active maintenance.
BuildKit SBOM/provenance is not a claimed signed attestation. Candidate registry
uploads precede the promotion scan gate. The JSON promotion file is not a signature.
Review origin, scans and source commit. Terraform and Argo must not both own a release.

No production deployment is claimed until the documented acceptance checks are
run on the target environment. Report security issues privately through a channel
you configure on your repository; never include real tokens or private source in
public issues. There is no fabricated security audit, bug-bounty contact or SLA.
