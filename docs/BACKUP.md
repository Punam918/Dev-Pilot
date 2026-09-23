# Backup, restore and state migration

## Guarantees and limitations

The backup module creates an **offline** SQLite-consistent archive with an
application manifest, per-file SHA-256 and membership/size checks. It refuses an
active server lease, overwriting a backup, writing inside source/state, unsafe
archive members, or restoring over an existing directory. Credentials, `.env`,
`.secrets`, caches and ephemeral DB journal files are excluded. State/source data
and report content can still be sensitive.

An archive is **not encryption, offsite replication or a backup schedule**. Use
access-controlled encrypted storage, separate credentials and periodic restore
drills. Do not upload backups as public GitHub workflow artifacts. A PVC by itself
is not a backup. The data cap is 1GB; archive older runs before exceeding it.

## Host Python

In the configured virtualenv/project root:

```bash
python scripts/drain.py
# Stop the serving terminal with Ctrl+C after drain completes.
python -m devpilot.backup create --out backups/devpilot-before-update.tar.gz
sha256sum backups/devpilot-before-update.tar.gz

# Restore into a NEW directory; no existing state is overwritten.
python -m devpilot.backup restore backups/devpilot-before-update.tar.gz \
  --destination /path/to/new/devpilot-restored
```

After validation, point a separately reviewed `.env` at the restored `state/` and
`workspace/` directories, configure credentials separately, start one API process,
and inspect history/probes. Do not copy back old access tokens blindly.

## Compose named volume

Activate the Python environment so the drain helper has `httpx`, then:

```bash
bash scripts/compose-backup.sh --allow-downtime
```

The helper drains, stops only the DevPilot service, runs an offline backup against
the same named volume, streams a 0600 archive to `backups/`, and restarts the
original service even on backup failure. It does not use a host Docker socket in
the agent or delete volumes. Restore locally to a new directory first; validate
membership/hashes and application history before transferring reviewed files to a
**new** volume or changing your deployment's mount. A restore directly over a live
Compose volume is intentionally not automated.

Monitoring has its own volumes. This application backup does not include
Prometheus, Tempo or Grafana data; export provisioned configuration from Git and
use their operator-specific storage policies for historical metrics/traces.

## Kubernetes PVC

Argo automatic sync must remain off, and no other operator may start a rollout
during the window. Run as an operator with explicit context:

```bash
python scripts/k8s-backup.py --context YOUR_CONTEXT \
  --out backups/devpilot-before-update.tar.gz --allow-downtime
```

The helper authenticates a drain from inside the running app, waits for active
work, scales only that Deployment to zero, mounts the same PVC in a temporary
non-root/no-token maintenance pod, creates and streams the archive, deletes that
pod, and restores the replica count. A failed delete/scale must be inspected;
review the script before using it in a shared cluster. Check readiness afterwards.
The helper requires no application token in a process argument and does not grant
its operator privileges to the agent. It was not cluster-executed in the packaging
environment.

Restore to a new local directory first, then create a **new PVC** with reviewed
ownership and contents through your cluster's storage/backup tooling. Configure
`persistence.existingClaim` to that new PVC in a reviewed values change. Keep the
old PVC until the restored instance passes history/auth/fixture checks. Credential
restoration is separate. Do not simply revert an image when a data format changed.

## Permissions and interrupted maintenance

Archives are private by default; check parent-directory permissions and encrypt
before copying off-host. Treat tar contents as untrusted until validation. The
restore routine verifies all file hashes before creating its new destination.
If maintenance is interrupted, check the actual replica count, maintenance pod,
PVC attachments and readiness before reopening traffic; shell traps are not a
distributed transaction or guaranteed recovery after a host power failure.
