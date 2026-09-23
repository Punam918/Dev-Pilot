# Real model setup: Qwen through Ollama or vLLM

## What is used?

| Path | Model identifier | Inference host |
|---|---|---|
| Default demo | None | Scripted policy; real tools/tests, no LLM |
| Ollama | `qwen3:4b` | Ollama's OpenAI-compatible `/v1` endpoint |
| vLLM | `Qwen/Qwen3-4B-Instruct-2507` | vLLM's OpenAI-compatible endpoint |

These are distinct checkpoints/packagings. Model performance and tool parsing
must be measured for the exact model, template, quantization and serving version.
No model weights or fabricated inference benchmarks are bundled.

## Ollama: easiest local starting point

Install Ollama from its official distribution. Activate the project Python
virtualenv and build the runner before changing `.env`:

```bash
ollama pull qwen3:4b
# Only when the service is not already active: ollama serve
docker build -f Dockerfile.runner -t devpilot-runner:local .
```

Keep `.secrets/` settings and use:

```dotenv
DP_PROVIDER=openai
DP_BASE_URL=http://127.0.0.1:11434/v1
DP_MODEL=qwen3:4b
DP_LLM_API_KEY=local
DP_RUNNER=docker
DP_RUNNER_IMAGE=devpilot-runner:local
DP_TRUST_LOCAL_CODE=false
DP_MAX_CONTEXT_CHARS=16000
DP_MAX_OUTPUT_TOKENS=2048
DP_PORT=8088
```

```bash
python scripts/check_model.py
python -m devpilot serve --seed
```

A native-call failure is a real limitation; do not scrape apparent tool JSON from
arbitrary prose and execute it. Begin with the known fixtures and inspect invalid
arguments, repeated reads, missed conditions and latency.

Optional containerized Ollama requires you to choose a **reviewed image tag or
digest**, not a hidden `latest` dependency:

```bash
export OLLAMA_IMAGE='ollama/ollama:<reviewed-version-or-digest>'
docker compose -f compose.ollama.yaml up -d
docker compose -f compose.ollama.yaml exec ollama ollama pull qwen3:4b
```

Replace the placeholder before running. This model-only Compose file does not
start the agent, and GPU access is not configured for it by default.

## vLLM: separate NVIDIA inference service

Prerequisites: compatible NVIDIA GPU, driver, container runtime/toolkit, enough
host/GPU memory for your chosen weights/context, and model download access. The
archive does not assume a particular GPU model or guarantee an 8GB device fits.
CPU speed and quantization behavior differ from vLLM GPU serving.

```bash
docker compose -f compose.vllm.yaml up -d
docker compose -f compose.vllm.yaml logs -f vllm
```

This candidate configuration serves on **127.0.0.1:18000**, avoiding your previous
port 8000 conflict. Set:

```dotenv
DP_PROVIDER=openai
DP_BASE_URL=http://127.0.0.1:18000/v1
DP_MODEL=Qwen/Qwen3-4B-Instruct-2507
DP_LLM_API_KEY=local
DP_RUNNER=docker
DP_TRUST_LOCAL_CODE=false
DP_MAX_CONTEXT_CHARS=16000
DP_MAX_OUTPUT_TOKENS=2048
```

The model container uses `--enable-auto-tool-choice --tool-call-parser hermes`,
`--max-model-len 8192`, and a starting GPU-memory utilization fraction of 0.8.
These are **starting configuration values, not measured optimal settings**. The
character budget cannot guarantee tokenizer length. Adjust only after observing
memory, tool-format compatibility, context errors and task results.

For an existing host vLLM installation rather than Docker:

```bash
vllm serve Qwen/Qwen3-4B-Instruct-2507 \
  --host 127.0.0.1 --port 18000 --max-model-len 8192 \
  --enable-auto-tool-choice --tool-call-parser hermes
```

Operator-supplied `VLLM_IMAGE` can replace the lab pin; record its immutable digest
and review the model's official serving guidance before promotion.

## Kubernetes inference

The application and test Jobs are independent of the model server. The optional
`infra/kubernetes/vllm.yaml` is a **GPU lab starting point**, with one GPU request,
cache PVC, health probes and a private Service. It does not install GPU drivers,
NVIDIA device plugins, a storage class, or provision cloud GPUs. Install those as
cluster-operator prerequisites and review resources/image digests first.

Production application values point to
`http://vllm.models.svc.cluster.local:8000/v1` and explicitly allow a remote model.
Repository excerpts therefore leave the API pod for the model service. That
private HTTP hop is not end-to-end TLS; use a reviewed TLS/authenticated endpoint
and key where the trust model requires it. Do not publish the unauthenticated
vLLM Service to the Internet.

## Measure the real AI separately

```bash
python scripts/check_model.py
python -m devpilot evaluate --live --out outputs/live-qwen --label qwen-exact-config
```

Record hardware, model revision/quantization, image digest, parser/chat template,
context and output limits, temperature, task set, retries and run count. Three
public fixtures are an integration smoke set, not a representative coding-agent
benchmark. Add held-out tasks and failure analysis before making resume claims.
The evaluation harness has a real-model mode; **this package does not contain a
successfully measured live-model run**.
