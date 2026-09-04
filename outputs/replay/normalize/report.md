# DevPilot run report

- Run: `6aeb46345fc54fedbe9c09daf7813c58`
- Repository: `demo-normalize`
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
  "snapshot_sha256": "2c53e83184080b987d1f35e8af0884c4ddfcb9d025cf486bc8b25f41a99b2cf9"
}
```

A passing check is not proof of semantic correctness or production readiness.

## Assistant explanation

SCRIPTED DEMO - no language model was called.

Evidence: normalize.py and the captured pytest output.
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
  "tool_ms": 2704,
  "prompt_tokens": null,
  "completion_tokens": null,
  "wall_ms": 13248
}
```

## Tool evidence

### files__list_files

```json
{
  "files": [
    "README.md",
    "normalize.py",
    "tests/test_normalize.py"
  ]
}
```

### docs__search

```json
{
  "chunks_indexed": 3,
  "matches": [
    {
      "end_line": 23,
      "path": "tests/test_normalize.py",
      "score": 2.57183,
      "start_line": 1,
      "symbol": "test_ascii, test_whitespace, test_unicode_casefold, test_empty, test_type_check",
      "text": "import pytest\nfrom normalize import normalize_username\n\n\ndef test_ascii():\n    assert normalize_username(\"ALICE\") == \"alice\"\n\n\ndef test_whitespace():\n    assert normalize_username(\" Alice \\n\") == \"alice\"\n\n\ndef test_unicode_casefold():\n    assert normalize_username(\"Stra\\u00dfe\") == \"strasse\"\n\n\ndef test_empty():\n    assert normalize_username(\"\") == \"\"\n\n\ndef test_type_check():\n    with pytest.raises(TypeError):\n        normalize_username(42)"
    },
    {
      "end_line": 4,
      "path": "README.md",
      "score": 1.42235,
      "start_line": 1,
      "symbol": "",
      "text": "# Username normalization fixture\nNormalize strings by stripping leading/trailing whitespace and applying Unicode\ncase-folding. Do not remove internal whitespace. Non-string input is an error.\nThe current implementation mishandles both whitespace and German sharp-s."
    },
    {
      "end_line": 7,
      "path": "normalize.py",
      "score": 0.22279,
      "start_line": 1,
      "symbol": "normalize_username",
      "text": "\"\"\"Normalize a user name for case-insensitive matching.\"\"\"\n\n\ndef normalize_username(value: str) -> str:\n    if not isinstance(value, str):\n        raise TypeError(\"username must be a string\")\n    return value.lower()"
    }
  ],
  "method": "BM25; rebuilt from current snapshot"
}
```

### files__read_file

```json
{
  "content": "\"\"\"Normalize a user name for case-insensitive matching.\"\"\"\n\n\ndef normalize_username(value: str) -> str:\n    if not isinstance(value, str):\n        raise TypeError(\"username must be a string\")\n    return value.lower()",
  "end_line": 7,
  "numbered": "1: \"\"\"Normalize a user name for case-insensitive matching.\"\"\"\n2: \n3: \n4: def normalize_username(value: str) -> str:\n5:     if not isinstance(value, str):\n6:         raise TypeError(\"username must be a string\")\n7:     return value.lower()",
  "path": "normalize.py",
  "sha256": "d7e44c494a95278798160880de7332260b96d01d1d1888aa585ee18688d3a570",
  "start_line": 1,
  "total_lines": 7
}
```

### terminal__run_tests

```json
{
  "command": "python -m pytest -q -p no:cacheprovider -o addopts= -o pythonpath=. tests",
  "duration_ms": 1136,
  "exit_code": 1,
  "output": ".FF..                                                                    [100%]\n=================================== FAILURES ===================================\n_______________________________ test_whitespace ________________________________\n\n    def test_whitespace():\n>       assert normalize_username(\" Alice \\n\") == \"alice\"\nE       AssertionError: assert ' alice \\n' == 'alice'\nE         \nE         - alice\nE         +  alice \nE         ? +     ++\n\ntests/test_normalize.py:10: AssertionError\n____________________________ test_unicode_casefold _____________________________\n\n    def test_unicode_casefold():\n>       assert normalize_username(\"Stra\\u00dfe\") == \"strasse\"\nE       AssertionError: assert 'straße' == 'strasse'\nE         \nE         - strasse\nE         ?     ^^\nE         + straße\nE         ?     ^\n\ntests/test_normalize.py:14: AssertionError\n=========================== short test summary info ============================\nFAILED tests/test_normalize.py::test_whitespace - AssertionError: assert ' al...\nFAILED tests/test_normalize.py::test_unicode_casefold - AssertionError: asser...\n2 failed, 3 passed in 0.03s\n",
  "output_limited": false,
  "runner": "host-trusted",
  "snapshot_sha256": "e39f39e6c78da488cf7992874f6d53085a4e2440729e0c0a54527229150203ac",
  "snapshot_unchanged": true,
  "timed_out": false
}
```

### files__replace_text

```json
{
  "diff": "--- a/normalize.py\n+++ b/normalize.py\n@@ -4,4 +4,4 @@\n def normalize_username(value: str) -> str:\n     if not isinstance(value, str):\n         raise TypeError(\"username must be a string\")\n-    return value.lower()\n+    return value.strip().casefold()\n",
  "path": "normalize.py",
  "sha256": "a77c68109dcae2b091715328bc5e91a5c3f350d19b7734c6f0e2e2665648f43d"
}
```

### terminal__run_tests

```json
{
  "command": "python -m pytest -q -p no:cacheprovider -o addopts= -o pythonpath=. tests",
  "duration_ms": 1543,
  "exit_code": 0,
  "output": ".....                                                                    [100%]\n5 passed in 0.01s\n",
  "output_limited": false,
  "runner": "host-trusted",
  "snapshot_sha256": "2c53e83184080b987d1f35e8af0884c4ddfcb9d025cf486bc8b25f41a99b2cf9",
  "snapshot_unchanged": true,
  "timed_out": false
}
```

### git__diff

```json
{
  "diff": "diff --git a/normalize.py b/normalize.py\nindex 78bb71d..e4b617d 100644\n--- a/normalize.py\n+++ b/normalize.py\n@@ -4,4 +4,4 @@\n def normalize_username(value: str) -> str:\n     if not isinstance(value, str):\n         raise TypeError(\"username must be a string\")\n-    return value.lower()\n+    return value.strip().casefold()\n"
}
```

## Scope and limitations

This artifact is local development evidence. Repository data may still contain secrets; review before publishing.
Demo/replay runs do not measure a language model. Real-model quality, Docker isolation, and GPU performance require separate validation.
