# Kubernetes deployment

## Supported topology and prerequisites

One API Deployment, one persistent volume, MCP stdio subprocesses inside that
pod, and separate short-lived pytest Jobs. A model service is optional for the
scripted lab and required for real AI. No HPA and no host Docker socket.

Prerequisites: a reviewed Kubernetes cluster >=1.30, compatible Helm 3/kubectl,
a storage class, container registry access, scoped operator permissions, an
enforcing CNI, and Pod Security Admission. The bundled admission profile is pinned
to `restricted:v1.30`; review it when upgrading Kubernetes. Do not deploy to an
unreviewed production cluster merely because Helm can render the chart.

## A. Dedicated local kind lab

Install Docker, kind, kubectl and Helm. The helper is for a **new dedicated lab**:

```bash
python3 scripts/bootstrap.py
bash scripts/kind-up.sh
kubectl --context kind-devpilot -n devpilot port-forward svc/devpilot 8088:8080
```

It creates `devpilot` as the kind cluster name (`kind-devpilot` context), disables
kind's default CNI, installs the versioned Calico manifest, prepares namespace
policy and secrets, builds/loads app and runner images, installs the chart and
checks network denial. The external CNI manifest is a trusted administrator
installation, not model-generated content. Review the official source/version.
Allow enough RAM, disk and time for Kubernetes plus builds; no measured minimum
or successful local cluster result is claimed by the archive.

The helper refuses an existing `devpilot` cluster. Reuse it with explicit Helm
commands after reviewing its state; do not force-delete an unknown cluster.

From another terminal, after port forwarding is active:

```bash
cat .secrets/api-token
python scripts/http_smoke.py --token-file .secrets/api-token --metrics-token-file .secrets/metrics-token
python scripts/cluster-smoke.py --approve-trusted-fixture --out outputs/local-kind-smoke
```

The fixture's baseline and post-edit tests now run in Kubernetes Jobs, not inside
the API pod. The script refuses live-model mode. Review saved patch/trace/test
results and do not label a scripted run “LLM accuracy.”

To stop only this lab when finished, after exporting/backing up needed data:

```bash
kind delete cluster --name devpilot
```

Deleting a local kind cluster removes its local cluster storage. This is not the
same as merely stopping the application; keep backups outside the cluster.

## B. Existing cluster, reviewed release

Every command must carry an explicit context. Example shell setup:

```bash
export KUBE_CONTEXT='your-reviewed-context'
kubectl --context "$KUBE_CONTEXT" cluster-info
kubectl --context "$KUBE_CONTEXT" create namespace devpilot
kubectl --context "$KUBE_CONTEXT" apply -f infra/kubernetes/runner-namespace.yaml
python3 scripts/bootstrap.py
python3 scripts/create-k8s-secret.py --context "$KUBE_CONTEXT" --namespace devpilot
```

`create namespace` is for a new namespace; an existing one must be inspected, not
overwritten. The secret helper reads files and sends a Secret on stdin, not token
literals in argv/Git. Kubernetes Secrets are base64 transport, not automatic
etcd encryption. Configure encryption/access control or an external secret manager.

Build/publish both images through CI. Download a **successful** release manifest,
verify its source commit and scan artifacts, then:

```bash
python scripts/promote.py --manifest /path/to/release-manifest.json --environment production
# Review deploy/environments/production/values.yaml and configure your model URL.
helm lint helm/devpilot --strict -f deploy/environments/production/values.yaml
helm template devpilot helm/devpilot --namespace devpilot \
  -f deploy/environments/production/values.yaml > /tmp/devpilot-reviewed.yaml
python scripts/validate-configs.py --rendered /tmp/devpilot-reviewed.yaml
```

The production file intentionally has missing image digests initially. Helm must
reject it until both are supplied. It also requires the real provider, not demo.
Use either a reviewed `helm upgrade --install` for initial deployment **or Argo CD
from CI-CD.md**. Do not create multiple release owners.

```bash
helm upgrade --install devpilot helm/devpilot --kube-context "$KUBE_CONTEXT" \
  --namespace devpilot -f deploy/environments/production/values.yaml \
  --wait --timeout 300s
```

For subsequent updates, drain first. An automatic Helm readiness check does not
wait for user approvals; it is not a graceful update by itself.

## Registry credentials

Public GHCR images require no pull secret. For private images, create scoped
registry credentials independently in **both** application and runner namespaces.
Set `imagePullSecrets: [{name: your-app-pull-secret}]` and
`runner.imagePullSecret: your-runner-pull-secret`. These are image-pull-only
credentials, not the DevPilot API secret. Do not mount app secrets into runner Jobs.

## Prove network isolation

```bash
python scripts/check-runner-isolation.py --context "$KUBE_CONTEXT" \
  --image ghcr.io/your-owner/devpilot-runner@sha256:YOUR_REVIEWED_DIGEST
```

Replace the image placeholder. The operator test creates two fixed-command Jobs:
one must reach the Kubernetes Service from the app namespace, the runner must
fail to connect to that same endpoint. It refuses to report success when the
control is unreachable. A timeout, missing image, quota failure or unenforced
policy is a failed acceptance check, not evidence of security. This probes one
destination, not all possible exfiltration paths. Apply cluster-wide policies or
stronger runtimes appropriate to your threat model.

The app's namespace has ingress restrictions but **operator-managed egress**; it
needs DNS, model access, Kubernetes API and optional tracing. The runner namespace
default-denies both directions. Do not grant exceptions merely to let tests
install dependencies; bake dependencies into the reviewed runner image instead.

## Ingress, TLS and authentication

Start with port forwarding/private network access. For a reviewed private ingress:

```yaml
ingress:
  enabled: true
  className: your-ingress-controller
  host: devpilot.example.com
  tlsSecretName: existing-devpilot-tls
config:
  publicOrigin: https://devpilot.example.com
  allowedHosts: [localhost, "127.0.0.1", devpilot, devpilot.example.com]
networkPolicy:
  ingressNamespace: your-ingress-namespace
```

Use your real hostname, existing TLS secret, ingress controller and timeout/SSE
settings. External auth/SSO is not shipped. The application always retains its
own API bearer-token check. It does not trust arbitrary forwarded headers.
Allow only the intended ingress namespace, preserve the host, and avoid buffering
SSE responses. Never expose the model API, Prometheus or Tempo publicly by default.

## Monitoring in a cluster

The chart can create a ServiceMonitor when a compatible Prometheus Operator is
already installed. Set `serviceMonitor.enabled=true` and the label selector your
Prometheus deployment expects. That operator/controller and its CRDs are external
prerequisites. The separate metrics token comes from the existing app Secret.
Import the included Grafana dashboard and alert rules; configure Collector/Tempo
endpoints for your platform. The Compose monitoring stack is a local installation,
not secretly a Kubernetes monitoring operator installation.

## Acceptance checklist before real use

Check probes, auth rejection, exact image digests, one replica, retained PVC,
runner SA with no token, restricted admission, real CNI enforcement, network
control test, baseline-fail/post-edit-pass fixture, exported artifacts, drain and
restart behavior, metrics scrape, a backup/restore drill, and model-native tool
calling. Save outputs and versions. No cluster acceptance result was fabricated
in this package.
