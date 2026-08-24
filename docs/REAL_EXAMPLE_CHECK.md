# Real-example check — 2026-09-21

## Verdict

**The demo works, but live AI repair is not yet validated on this machine.** A new shopping-cart example reproduced a genuine bug. Qwen connected and made a real MCP file-listing call, but neither supervised investigation reached a patch or test execution before I stopped the slow attempts. The isolated Docker runner also failed to start Python under its security settings.

These are incomplete, cancelled live investigations, not successful repairs and not proof that Qwen could never solve the task. No live-model success rate is claimed.

## New example

Source: [cart.py](../workspace/example-cart-discount/cart.py), [tests](../workspace/example-cart-discount/tests/test_cart.py).

This is a small independent example created for this check, not one of DevPilot's three predefined demos and not a production customer repository. It calculates a checkout total using `Decimal`.

| Input | Required total | Buggy total |
|---|---:|---:|
| 19.99 × 3, 10% discount | 53.97 | 59.87 |
| 12.50 × 2, 100% discount | 0.00 | 24.00 |

The implementation subtracts the discount fraction itself rather than the fraction of the subtotal. The baseline has **2 failures and 4 passes**. This diagnosis comes from inspecting and directly testing the fixture; it is not a successful DevPilot model diagnosis.

## What was actually checked

| Check | Result |
|---|---|
| Existing local demo HTTP health/readiness/authentication | Passed |
| Final regression suite after restoring original source | 105 passed, 2 optional checks skipped, 10.01 seconds; Docker was also tested separately and failed as recorded below |
| Download and load Qwen3 4B | Passed; approximately 2.5 GB of model weights |
| Real structured function call through DevPilot model adapter | Passed; returned the requested `add(2, 3)` tool call |
| New cart baseline on trusted host runner | Expected failure: 2 failed, 4 passed |
| Basic Docker runner image startup | Passed |
| Actual hardened Docker test execution | Failed: `exec /usr/local/bin/python: operation not permitted`, exit 255 in direct reproduction |
| Opt-in Docker integration test | Failed; its baseline expected exit 1, received 125 in the test environment |
| Live Qwen + DevPilot MCP | File listing succeeded |
| Live Qwen repair and post-edit tests | Not completed; cancelled after slow responses/timeouts |
| Original fixture isolation | Source unchanged in both live run records |
| Independent 179-case checker | Prepared outside model workspace, **not executed** because there is no repaired result |

The primary run used actual Qwen inference through the existing `OpenAIModel` adapter and `RunManager`, with real MCP subprocesses. It did not use `DemoModel`. It was a supervised Python harness, not a live-model browser test. The original browser instance continued to use the demo provider.

## Local findings

1. No model service was originally listening. An existing Snap Llama model store could not be used through the installed Snap launcher because of a permission error. After download authorization, a dedicated Ollama container and Qwen model were installed.
2. The NVIDIA GPU is present, but Ollama 0.34.2 reported driver 535 where it requires 550 or newer. It selected CPU inference. Observed generation was approximately 5–9 tokens/second; the first completed model response took 104.175 seconds.
3. The standard model run completed one model turn and one read tool call. It was cancelled after 340.940 seconds. Its `verified` and `tests_executed` flags are false; no edit was approved.
4. A temporary request-level reasoning control and local non-thinking-template alias were tried. The alias attempt also completed only one model turn/read call and was cancelled after 141.424 seconds. It is not evidence of a reliable workaround.
5. The downloaded template unconditionally starts a thinking block. A prompt-only `/no_think` instruction did not provide the desired short responses in this test. Ollama documents a request-level [reasoning-effort conversion](https://github.com/ollama/ollama/blob/v0.34.2/openai/openai.go), and Qwen distinguishes [hard and soft thinking controls](https://github.com/QwenLM/Qwen3/blob/main/docs/source/getting_started/quickstart.md); actual compatibility still needs verification with the selected server/model template.
6. All temporary application-code changes were removed. SHA256 checks confirmed `config.py`, `models.py`, `test_models.py`, and `.env.example` match the packaged originals. The experimental model alias was removed. No changes were made to the existing `.env` or `.gitignore`.

The failed Docker execution was reproduced with the runner's actual security settings. A successful basic container does not validate this hardened mode. No host security policy, Docker security flag, or NVIDIA driver was changed to force a pass. The supervised host harness was limited to this reviewed synthetic project and would have required individual edit/test approvals; it reached neither.

## Evidence files

- [Trusted-host baseline](../outputs/live-cart-check/host-trusted-baseline.json)
- [Docker baseline error](../outputs/live-cart-check/docker-baseline.json)
- [Original Qwen attempt trace](../outputs/live-cart-check/initial-attempt/trace.json)
- [Experimental attempt result](../outputs/live-cart-check/result.json)
- [Experimental attempt trace](../outputs/live-cart-check/trace.json)
- [Final regression JUnit](../outputs/live-cart-check/final-regression.xml)
- [Supervised harness](../outputs/live-cart-check/run_check.py)
- [Independent checker, not executed](../outputs/live-cart-check/independent_check.py)

The harness now selects the original `qwen3:4b` model again. The exported second-attempt result correctly retains the experimental alias name that was used at execution time. Local output and workspace directories are ignored by Git, as specified in the existing `.gitignore`.

## State left available

- Demo UI: http://127.0.0.1:8091, still configured as `demo`.
- Local model endpoint: http://127.0.0.1:11434/v1.
- Downloaded model: `qwen3:4b`.
- Model container: `devpilot-model-check`.
- Persistent model volume: `devpilot-qwen-models`.
- Built runner image: `devpilot-runner:local`.
- Model context setting: 8192 tokens.
- Original buggy example remains in `workspace/example-cart-discount` for reproduction.

Use `docker stop devpilot-model-check` to stop the local model service, and `docker start devpilot-model-check` to start it again. The downloaded model remains in its volume. The container currently falls back to CPU; its presence does not mean GPU inference works.

## What must pass before calling the live workflow working

Resolve or select a compatible model-serving configuration with practical response times. Resolve the host/container restriction affecting the hardened pytest runner. Then rerun this same example through baseline tests, reviewed model edit, post-edit tests, and the independent checker, preserving the resulting patch and source-unchanged checks. Those remaining conditions were not met in this session.
