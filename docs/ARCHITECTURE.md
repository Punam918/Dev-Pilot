# Architecture and tradeoffs

## Product boundary

DevPilot is a single-operator local/private debugging workbench, not a production
multi-tenant software engineer. Source repositories must be small Python projects
with pytest tests. The original source is copied, not edited in place. A reviewed
patch is the output; push/merge/deployment to another application is not a tool.

## Request and evidence flow

1. FastAPI authenticates the request and validates an allowed repository/task.
2. The run manager acquires the one-active-run slot and prepares a sanitized copy.
3. A scripted demo policy or a real OpenAI-compatible model returns structured tool calls.
4. The gateway validates the names/arguments and dispatches over MCP stdio.
5. Read/search tools return line references and bounded context. Mutations and
   pytest execution require a single-use approval bound to the exact action.
6. The fixed runner executes tests against the approved snapshot; the original
   repository is separate. The model receives the result, but cannot forge the
   application's verification field.
7. The app records events in SQLite and exports a patch, report, trace and test evidence.

The native MCP implementation supports a documented 2025-06-18 **subset**. Five
servers are subprocesses, not remote services: files, Git, docs/BM25, terminal/fixed
pytest, and read-only SQLite. The Docker observer is optional. See MCP.md for the
exact supported methods and official-SDK interoperability status.

## Why the API is not horizontally scaled

Approvals, active task state and concurrency ownership are in memory; history is
SQLite on one persistent volume. Two replicas could disagree on pending actions
or interrupt each other's work. Accordingly:

- the chart enforces one replica and `Recreate`;
- serving/backup uses an OS process lease on the data directory;
- only one active run is accepted, with 409 when busy and 503 when drained;
- a restart marks unfinished runs interrupted instead of claiming seamless resume.

The lease is a local-filesystem guard, not a distributed lock service. A future HA
design needs a shared database, durable queue, shared approval capabilities,
lease/ownership model, artifact store, idempotent job dispatch and tested recovery.
No HPA, Redis or PostgreSQL placeholder is added simply to lengthen the stack.

## Runner choices

| Mode | Location | Authority / intended use |
|---|---|---|
| disabled | none | Investigate without executing tests |
| host-trusted | local process | Arbitrary code execution on the host; only trusted fixtures/code |
| docker | separate local container | Operator has Docker authority; read-only repo mount, no network, fixed command, resource limits |
| kubernetes | Job in separate namespace | App creates a bounded Job and immutable snapshot ConfigMap through scoped API permissions |

Kubernetes tests receive no API credential, app PVC, model credential, arbitrary
command argument or host socket. Small snapshots use ConfigMaps to avoid giving
jobs shared access to all runs. This costs a 700KB compressed bound and Kubernetes
API/etcd exposure of source to authorized cluster administrators. A future large
repo runner should use encrypted short-lived object storage, not increase these
limits blindly.

A Job's authoritative container exit status and the approved snapshot identity
feed verification. Console text such as “all tests passed” is not sufficient.
A zero exit code proves the selected tests ran successfully, not general program
correctness or security. Test code is still arbitrary code.

## Trust boundaries

The operator, control-plane app, model configuration, tool implementations,
service-account policy and runner image are trusted. Model text and repository
contents are untrusted for authorization. The model can select allowlisted tools;
it cannot select the image, namespace, shell, Kubernetes manifest, secret path,
network policy or approval outcome.

NetworkPolicy needs an enforcing CNI. Restricted Pod Security Admission limits
pod capabilities, but containers share a kernel and are not a hostile-code VM.
App API credentials are powerful single-operator credentials. Keep the app on a
private network and do not point it at production repositories containing secrets.

## DevOps ownership

CI builds/tests the code. Publishing creates app/runner candidates and scans their
immutable digests. A reviewed values change records the desired release. Argo CD
synchronizes manually after drain; Terraform is an alternative owner, never a
second controller for the same release. Backups and restore drills are operator
responsibilities, not a claim of disaster recovery simply because a PVC exists.

Metrics and traces contain bounded operational metadata, not full prompts or file
contents. Detailed per-run evidence remains in local audit artifacts and may be
sensitive despite best-effort redaction. See SECURITY.md and OBSERVABILITY.md.
