#!/usr/bin/env bash
# Lab tool pin, verified against the official Helm 3.19.0 release. Linux amd64.
set -euo pipefail
[[ "$(uname -s)/$(uname -m)" == "Linux/x86_64" ]] || { echo 'Install a reviewed Helm 3 build for your platform.' >&2; exit 2; }
DEST="${1:-$HOME/.local/bin}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
  https://get.helm.sh/helm-v3.19.0-linux-amd64.tar.gz -o "$WORK/helm.tar.gz"
echo 'a7f81ce08007091b86d8bd696eb4d86b8d0f2e1b9f6c714be62f82f96a594496  helm.tar.gz' > "$WORK/SHA256SUMS"
(cd "$WORK" && sha256sum -c SHA256SUMS && tar -xzf helm.tar.gz)
mkdir -p "$DEST"
install -m 0755 "$WORK/linux-amd64/helm" "$DEST/helm"
"$DEST/helm" version --short
