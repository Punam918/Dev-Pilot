# Environment configuration

## Location and safe initialization

From the **project root** (the directory with `pyproject.toml`, `README.md` and `compose.yaml`):

```bash
python3 scripts/bootstrap.py
ls -la
nano .env
# or: code .env
```

The files start with a dot and are hidden by Ubuntu Files until **Ctrl+H**. The
bootstrap needs only Python's standard library. It creates `.env` (mode 0600),
`.secrets/` (0700) and three independently generated credential files. It never
overwrites existing values. Secret files are 0644 **inside that 0700 parent** so
non-root Compose services can read their bind-mounted secret; another host user
cannot traverse the parent. On shared systems use a proper secret manager and
review ACLs/backups. Compose file secrets are not encrypted at rest.

`.env.example` is a committed reference, not the file that the app normally reads.
`.env`, `.secrets/`, workspace data, state, backups and Terraform state are excluded
from Git and the package builder. Review `git status` before every commit.

## Which settings win?

Host Python reads `DP_` environment variables, then the `.env` in its working
directory, then code defaults. Token-file settings override literal token values.
Run from the project root. `python -m devpilot doctor` prints **non-secret** checks.

**Compose is different:** `.env` is used for `${...}` substitutions; it is not
implicitly passed into the container. The demo service deliberately sets
`DP_PROVIDER=demo` and `DP_RUNNER=host-trusted` in `compose.yaml`. Editing these
names in your host `.env` does not override that service's explicit values. Use
the documented host-Python live path or the Kubernetes live-model values. Do not
mount the Docker socket into the application as a shortcut.

Helm creates a ConfigMap for non-secrets and mounts an existing Secret. The local
`.env` is not copied into the image. `DP_POD_IP` comes from the downward API so a
ServiceMonitor can scrape the Pod IP without disabling trusted-host validation.

## Main settings

| Setting | Meaning / safe use |
|---|---|
| `DP_PROVIDER` | `demo` is scripted fixtures; `openai` is the compatible HTTP adapter, including local Qwen |
| `DP_BASE_URL` | Ollama `http://127.0.0.1:11434/v1`; optional vLLM Compose `http://127.0.0.1:18000/v1` |
| `DP_MODEL` | Exact name returned by the inference server's `/v1/models` |
| `DP_LLM_API_KEY` | `local` for an unauthenticated local endpoint; actual credential for an authenticated server |
| `DP_ALLOW_REMOTE_MODEL` | Explicitly allow non-local inference host; repository content will leave this host |
| `DP_API_TOKEN_FILE` | Local `.secrets/api-token`; Kubernetes `/run/devpilot-secrets/api-token` |
| `DP_METRICS_TOKEN_FILE` | Separate metrics credential; never reuse the UI token |
| `DP_API_TOKEN`, `DP_METRICS_TOKEN` | Literal alternatives; never commit values; metrics disabled when blank |
| `DP_PORT` | Host Python uses bootstrap value **8088**; code fallback is 8080 |
| `DP_HTTP_PORT` | Compose's host port, **8088**; the application inside the container uses 8080 |
| `DP_ALLOWED_HOSTS` | JSON array of exact hostnames/IPs, no wildcard |
| `DP_PUBLIC_ORIGIN` | Exact browser origin behind a proxy, e.g. `https://devpilot.example.com`; no path |
| `DP_DATA_DIR`, `DP_WORKSPACE_DIR` | State and source-repository roots; state cannot be inside source root |
| `DP_RUNNER` | `disabled`, `host-trusted`, `docker`, `kubernetes` |
| `DP_TRUST_LOCAL_CODE` | Required for host execution; only use with trusted fixtures/code |
| `DP_RUNNER_IMAGE` | Operator-built image with pytest and approved project dependencies |
| `DP_DOCKER_TOOLS` | Optional host Docker **observer**, disabled by default; not needed for Kubernetes |
| `DP_MAX_CONTEXT_CHARS` | Use 16000 to start with small models; character counts are not token counts |
| `DP_MAX_OUTPUT_TOKENS` | 2048 by default; reserve model context space for this output |
| `DP_MAX_RUNS` | 100 stored runs by default; archive/review before increasing storage limits |
| `DP_OTEL_ENABLED` | Enables safe-metadata spans; needs the observability extra or runtime constraints |
| `DP_OTEL_ENDPOINT` | HTTP OTLP `/v1/traces` URL; default host port 4318; Compose collector is internal |
| `DP_KUBE_NAMESPACE` | Dedicated runner namespace, normally `devpilot-runners` |
| `DP_KUBE_JOB_TIMEOUT` | Job scheduling/execution deadline, 180 seconds by default |
| `DP_TOOL_TIMEOUT` | Use **240** for Kubernetes; must exceed Job deadline by at least 15 seconds |
| `DP_KUBE_RUNTIME_CLASS` | Optional already-installed stronger runtime such as a reviewed sandbox runtime |
| `DP_KUBE_IMAGE_PULL_SECRET` | Existing image-pull Secret in the runner namespace; never application credentials |

Helm's `config.*` values map to these variables in `templates/configmap.yaml`.
Application secrets are read on startup. Rotate, restart during a drained window,
then verify authentication; mounted-file changes do not automatically update an
already-created Settings instance.

## Existing 0.2.0 configurations

Extract this release into a **new directory**. Back up old state first. The new
bootstrap preserves an existing `.env`, so an old port 8080 or literal API token
can remain active. Choose one credential source and port deliberately. The new
Compose named volume is separate from a host `.devpilot/`; they are not silently
synchronized. Do not overwrite a working repository or delete a volume to fix a
configuration mismatch.
