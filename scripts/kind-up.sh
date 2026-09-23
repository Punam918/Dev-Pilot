#!/usr/bin/env bash
# Creates ONLY a dedicated local kind cluster. Never uses your default kubectl context.
set -euo pipefail
cd "$(dirname "$0")/.."
for cmd in docker kind kubectl helm python3; do command -v "$cmd" >/dev/null || { echo "Missing $cmd" >&2; exit 2; }; done
if kind get clusters | grep -qx devpilot; then
  echo 'Cluster devpilot already exists. Refusing to overwrite it; follow docs/KUBERNETES.md.' >&2; exit 2
fi
python3 scripts/bootstrap.py
kind create cluster --name devpilot --config infra/kind.yaml --wait 0s
# Dedicated lab network. A plain kindnet cluster does NOT enforce NetworkPolicy.
# Versioned Calico manifest; review vendor changes before using it beyond this lab.
kubectl --context kind-devpilot create -f https://raw.githubusercontent.com/projectcalico/calico/v3.32.2/manifests/calico.yaml
kubectl --context kind-devpilot -n kube-system rollout status daemonset/calico-node --timeout=300s
kubectl --context kind-devpilot wait --for=condition=Ready nodes --all --timeout=300s
kubectl --context kind-devpilot create namespace devpilot
kubectl --context kind-devpilot apply -f infra/kubernetes/runner-namespace.yaml
python3 scripts/create-k8s-secret.py --context kind-devpilot --namespace devpilot
# Context now remains explicit for EVERY cluster operation.
docker build -t devpilot:local .
docker build -f Dockerfile.runner -t devpilot-runner:local .
kind load docker-image --name devpilot devpilot:local devpilot-runner:local
helm upgrade --install devpilot helm/devpilot --kube-context kind-devpilot --namespace devpilot \
  -f deploy/environments/staging/values.yaml --wait --timeout 300s
python3 scripts/check-runner-isolation.py --context kind-devpilot
printf '\nNext: kubectl --context kind-devpilot -n devpilot port-forward svc/devpilot 8088:8080\n'
printf 'Then open http://127.0.0.1:8088 and use .secrets/api-token.\n'
