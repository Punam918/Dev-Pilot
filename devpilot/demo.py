"""Explicitly scripted fixtures. Nothing in this module is model intelligence."""
from pathlib import Path
from .safety import Workspace, copy_workspace, SafetyError

FIXTURES = Path(__file__).parent / "fixtures"
CASES = {
    "redis": {"repo": "demo-redis", "path": "service.py", "query": "redis hostname localhost configuration",
              "old": 'DEFAULT_REDIS_HOST = "localhost"', "new": 'DEFAULT_REDIS_HOST = "redis"',
              "task": "Fix the default Redis hostname for separate Docker Compose containers. Preserve host overrides and validate the patch."},
    "pagination": {"repo": "demo-pagination", "path": "pagination.py", "query": "pagination page size off by one",
                   "old": "return items[start : start + page_size - 1]", "new": "return items[start : start + page_size]",
                   "task": "Fix the pagination off-by-one error while preserving invalid-input checks."},
    "normalize": {"repo": "demo-normalize", "path": "normalize.py", "query": "username whitespace unicode casefold",
                  "old": "return value.lower()", "new": "return value.strip().casefold()",
                  "task": "Fix username normalization for whitespace and Unicode case folding without altering the tests."},
}


def seed(workspace_dir: Path) -> list[str]:
    workspace_dir.mkdir(parents=True, exist_ok=True)
    created = []
    for case_id, case in CASES.items():
        target = workspace_dir / case["repo"]
        if not target.exists():
            copy_workspace(FIXTURES / case_id, target)
            created.append(case["repo"])
    return created


def validate_demo(repo: str, source: Path) -> str:
    for case_id, case in CASES.items():
        if case["repo"] == repo:
            if Workspace(source).fingerprint() != Workspace(FIXTURES / case_id).fingerprint():
                raise SafetyError("Scripted demo accepts only unchanged bundled fixtures. Use real-model mode for other code")
            return case_id
    raise SafetyError("Scripted demo supports only the three bundled demo repositories")
