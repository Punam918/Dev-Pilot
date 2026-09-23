# DevPilot run report

- Run: `ed1cfe4b196446f9926fbfa048261b87`
- Repository: `demo-redis`
- Mode: `repair`
- Provider: `demo`
- Model: `scripted-fixture-policy (NOT an LLM)`
- Status: `completed`
- Runner: `host-trusted`

## Independently recorded validation

```json
{
  "verified": true,
  "tests_executed": true,
  "last_exit_code": 0,
  "snapshot_matches_tested": true,
  "source_unchanged": true,
  "snapshot_sha256": "05c6e1ec7b8708bf19517d3cbda1bd61b57bd7c2024f3597f1eed405d39e76f2"
}
```

A passing check is not proof of semantic correctness or production readiness.

## Assistant explanation

SCRIPTED DEMO - no language model was called.

Evidence: service.py and the captured pytest output.
Applied the fixture's predefined one-line repair after approval.
Baseline pytest exit code: 1.
Post-patch pytest exit code: 0.
The original repository was not changed. Download and review the patch.
These results validate the integration workflow, not autonomous model quality.

## Metrics

```json
{
  "model_turns": 8,
  "tool_calls": 7,
  "tool_errors": 0,
  "llm_ms": 0,
  "tool_ms": 2479,
  "prompt_tokens": null,
  "completion_tokens": null,
  "wall_ms": 12952
}
```

## Tool evidence

### files__list_files

```json
{
  "files": [
    "README.md",
    "app.py",
    "service.py",
    "tests/test_service.py"
  ]
}
```

### docs__search

```json
{
  "chunks_indexed": 4,
  "matches": [
    {
      "end_line": 9,
      "path": "README.md",
      "score": 2.38822,
      "start_line": 1,
      "symbol": "",
      "text": "# Redis configuration fixture\nThis is intentionally broken, synthetic evaluation data, not a production outage.\nThe API and Redis run in separate Compose containers. The service hostname is\n`redis`; `localhost` refers to the API's own container. An explicit host override\nmust still work. Fix the default configuration without changing the tests.\n\n`app.py` is an optional FastAPI demonstration. The tests exercise the configuration\nfunction without a running Redis instance. Do not interpret this as a live Docker\nhealth-check experiment."
    },
    {
      "end_line": 8,
      "path": "service.py",
      "score": 1.34316,
      "start_line": 1,
      "symbol": "redis_url",
      "text": "\"\"\"Redis endpoint configuration for a Compose-based API.\"\"\"\nDEFAULT_REDIS_HOST = \"localhost\"\n\n\ndef redis_url(host: str | None = None, port: int = 6379) -> str:\n    if not 1 <= port <= 65535:\n        raise ValueError(\"port must be in 1..65535\")\n    return f\"redis://{host or DEFAULT_REDIS_HOST}:{port}/0\""
    },
    {
      "end_line": 10,
      "path": "app.py",
      "score": 0.59128,
      "start_line": 1,
      "symbol": "health",
      "text": "\"\"\"Small FastAPI example; no real Redis connection is made by this fixture.\"\"\"\nfrom fastapi import FastAPI\nfrom service import redis_url\n\napp = FastAPI(title=\"DevPilot Redis fixture\")\n\n\n@app.get(\"/health\")\ndef health():\n    return {\"status\": \"configuration-only demo\", \"redis_url\": redis_url()}"
    }
  ],
  "method": "BM25; rebuilt from current snapshot"
}
```

### files__read_file

```json
{
  "content": "\"\"\"Redis endpoint configuration for a Compose-based API.\"\"\"\nDEFAULT_REDIS_HOST = \"localhost\"\n\n\ndef redis_url(host: str | None = None, port: int = 6379) -> str:\n    if not 1 <= port <= 65535:\n        raise ValueError(\"port must be in 1..65535\")\n    return f\"redis://{host or DEFAULT_REDIS_HOST}:{port}/0\"",
  "end_line": 8,
  "numbered": "1: \"\"\"Redis endpoint configuration for a Compose-based API.\"\"\"\n2: DEFAULT_REDIS_HOST = \"localhost\"\n3: \n4: \n5: def redis_url(host: str | None = None, port: int = 6379) -> str:\n6:     if not 1 <= port <= 65535:\n7:         raise ValueError(\"port must be in 1..65535\")\n8:     return f\"redis://{host or DEFAULT_REDIS_HOST}:{port}/0\"",
  "path": "service.py",
  "sha256": "368be40f53c6036b76559bc4cc1f17293fd3e96db14533af333d17ca0fe9f327",
  "start_line": 1,
  "total_lines": 8
}
```

### terminal__run_tests

```json
{
  "command": "python -m pytest -q -p no:cacheprovider -o addopts= -o pythonpath=. tests",
  "duration_ms": 1305,
  "exit_code": 1,
  "output": "F...                                                                     [100%]\n=================================== FAILURES ===================================\n_____________________________ test_compose_default _____________________________\n\n    def test_compose_default():\n>       assert redis_url() == \"redis://redis:6379/0\"\nE       AssertionError: assert 'redis://localhost:6379/0' == 'redis://redis:6379/0'\nE         \nE         - redis://redis:6379/0\nE         + redis://localhost:6379/0\n\ntests/test_service.py:6: AssertionError\n=========================== short test summary info ============================\nFAILED tests/test_service.py::test_compose_default - AssertionError: assert '...\n1 failed, 3 passed in 0.03s\n",
  "output_limited": false,
  "runner": "host-trusted",
  "snapshot_sha256": "473b9a3747f16da6ef10d09a20c6cb6f6b3efb5947b473118349488171567c5a",
  "snapshot_unchanged": true,
  "timed_out": false
}
```

### files__replace_text

```json
{
  "diff": "--- a/service.py\n+++ b/service.py\n@@ -1,5 +1,5 @@\n \"\"\"Redis endpoint configuration for a Compose-based API.\"\"\"\n-DEFAULT_REDIS_HOST = \"localhost\"\n+DEFAULT_REDIS_HOST = \"redis\"\n \n \n def redis_url(host: str | None = None, port: int = 6379) -> str:\n",
  "path": "service.py",
  "sha256": "4677bd76c5277e8fe7dc3093aba3fcc23d0dd14e7841652094bfb125302515b6"
}
```

### terminal__run_tests

```json
{
  "command": "python -m pytest -q -p no:cacheprovider -o addopts= -o pythonpath=. tests",
  "duration_ms": 1141,
  "exit_code": 0,
  "output": "....                                                                     [100%]\n4 passed in 0.01s\n",
  "output_limited": false,
  "runner": "host-trusted",
  "snapshot_sha256": "05c6e1ec7b8708bf19517d3cbda1bd61b57bd7c2024f3597f1eed405d39e76f2",
  "snapshot_unchanged": true,
  "timed_out": false
}
```

### git__diff

```json
{
  "diff": "diff --git a/service.py b/service.py\nindex e4fb587..10581db 100644\n--- a/service.py\n+++ b/service.py\n@@ -1,5 +1,5 @@\n \"\"\"Redis endpoint configuration for a Compose-based API.\"\"\"\n-DEFAULT_REDIS_HOST = \"localhost\"\n+DEFAULT_REDIS_HOST = \"redis\"\n \n \n def redis_url(host: str | None = None, port: int = 6379) -> str:\n"
}
```

## Scope and limitations

This artifact is local development evidence. Repository data may still contain secrets; review before publishing.
Demo/replay runs do not measure a language model. Real-model quality, Docker isolation, and GPU performance require separate validation.
