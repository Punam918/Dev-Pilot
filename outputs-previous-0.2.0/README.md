# Recorded evidence

These artifacts were generated from the source in this package, not invented benchmark numbers.

| Artifact | Meaning |
|---|---|
| `tests-console.txt` | Final pytest console result and main-process coverage summary |
| `junit.xml` | Machine-readable test result, including skipped integrations |
| `coverage.json` | Main-process coverage; MCP child process coverage is not automatically combined |
| `environment.json` | Selected observed package/environment versions, not a full lockfile |
| `replay/summary.md` and `.json` | Three-case **scripted** integration results; no LLM called |
| `replay/<case>/` | Actual patch, tool trace, report, and additional final test output |
| `installed-smoke.txt` | Replay from a built wheel installed to a separate target outside the source tree |
| `wheel-build.txt`, `wheel-install.txt` | Actual offline wheel build/install logs using existing dependencies |
| `js-syntax.txt` | Node syntax-check result for shipped browser JavaScript |
| `ui-smoke.json` | Explicit live-browser limitation and offline preview provenance |
| `ui-console.txt` | Browser test's actual environment-policy failure, not a passing test |

No live Qwen/Ollama/vLLM result, GPU benchmark, Docker daemon test result, remote CI run, or certified MCP compliance report is bundled. Run the optional checks on your machine before claiming those integrations as tested.

Run your own experiments under `outputs/local-*` or `outputs/live-*`, which are Git-ignored by default so private traces are not accidentally committed. Review any output before publishing it.
