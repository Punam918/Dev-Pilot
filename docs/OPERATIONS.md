# Operations and incident runbooks

## Normal operations

Monitor readiness, HTTP errors, run/tool failures, approval waits, model health
and disk/PVC utilization. The app serves one active run and keeps at most the
configured run count; it is intentionally not a queueing fleet. Back up before
updates that affect data. Save exact image digests and dependency versions with
incident notes. Use scoped Docker/cluster commands; never globally prune unrelated
projects in response to one application failure.

## DevPilotDown

The Prometheus target is unreachable or rejects the metrics credential. Check
`docker compose ps/logs devpilot` or, with an explicit context,
`kubectl -n devpilot get pods,events` and the app logs. Check `/livez`, `/readyz`, the
metrics token mount and Prometheus target details. A wrong token is not proof the
application process is dead. Do not reset credentials or delete the state volume
without review. A model outage should not affect `/livez`.

## DevPilotHTTPErrorRate

Inspect sanitized JSON operational records for route/status/request ID, then the
protected run artifact if needed. Check disk permissions, SQLite availability,
state lock, configured origin/host, quotas, model connectivity and deployment
changes. Do not paste source code, tokens or raw user tasks into a public alert.
Compare pre/post release digests; drain and roll back through Git if a release is
at fault. Do not fix by enabling unrestricted shell or disabling authentication.

## DevPilotApprovalWaiting

Open the run and review the exact action and patch. Approve only the intended
snapshot or deny. A waiting approval can block drain; this is expected. The agent
must not self-approve because an alert fired. An expired approval is a recorded
failure/denial, not permission to retry a different path around the gate.

## Kubernetes Job pending

```bash
kubectl --context YOUR_CONTEXT -n devpilot-runners get jobs,pods
kubectl --context YOUR_CONTEXT -n devpilot-runners get events --sort-by=.lastTimestamp
kubectl --context YOUR_CONTEXT -n devpilot-runners describe pod EXACT_POD
```

Replace placeholders. Typical causes: missing runner image/imagePullSecret,
resource quota, admission denial, missing namespace or unavailable node/runtime.
The fixed command needs no outbound network. Bake dependencies into an approved
runner rather than allowing network installation. The snapshot ConfigMap is small
and immutable; large repositories are rejected intentionally. Cluster
administrators can read those ConfigMaps, so keep repository secrets out.

Jobs have active deadlines, no retry loop and TTL cleanup. The app deletes its
specific completed Job; owner references clean up its input ConfigMap. A forcibly
killed MCP process may not execute `finally`; Job deadline/TTL remain. Review
stranded objects with labels/ownership before any targeted deletion. Never delete
all namespaces or all Docker containers to clean one task.

## Restart, drain and interrupted runs

```bash
python scripts/drain.py
# Resolve existing work before any rollout.
```

Drain stops admission and marks readiness false. It does not cancel work or grant
approval. Existing runs finish under the same process. A new process cannot
resume old in-memory approvals; unfinished runs become `interrupted` and must be
reviewed/restarted by the operator. A second serving process on the same state
path fails its lease rather than silently sharing ownership.

A killed test subprocess can leave its Job until deadline/TTL; do not report a
completed fix without independent evidence. SIGTERM shutdown has a bounded window;
state is not proof that arbitrary long work can survive every restart.

## Deployment and rollback

Use the procedure in CI-CD.md. **One API replica + Recreate means downtime.** A
manual GitOps sync after drain is deliberate. An automated canary/HPA for this
stateful control plane would be misleading. Live-model serving is a separate
service; do not restart the API repeatedly for a model outage.

## Restore drill and recovery objectives

See BACKUP.md. Create an offline archive, verify its hash, restore to a new path
and run read-only HTTP/history checks. Run a fresh fixture only after inspection.
The archive excludes credentials; restore those through a separate secure process.
Define your own RPO/RTO based on an observed backup schedule and timed restore
exercise. This package does not claim measured disaster-recovery objectives.

## Storage and retention

SQLite, source snapshots and artifacts may contain sensitive data. Keep volumes
private, encrypted at rest where appropriate, and backed up off-host. No automatic
run deletion, scheduled offsite backup or encrypted archive service is shipped.
At the default 100-run limit, export/backup and deliberately rotate/archive the
state directory while the service is stopped. Raising the limit without watching
disk is not retention management. Preserve the original source repositories.
