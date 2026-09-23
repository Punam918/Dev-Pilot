import json
import sqlite3
import sys
import pytest
from devpilot.safety import SafetyError, digest
from devpilot.retrieval import search
from devpilot.tools.database import query
from devpilot.tools.runner import docker_command, run_tests
from devpilot.tools.docker import inspect_container, list_containers
from devpilot.process import run_process
from devpilot.gitops import initialize, diff


def test_bm25_returns_provenance_and_reindexes(workspace):
    (workspace.root / "redis.py").write_text('REDIS_HOST = "localhost"\n')
    result = search(workspace, "Redis host")
    assert result["matches"][0]["path"] == "redis.py"
    assert result["matches"][0]["start_line"] == 1
    (workspace.root / "redis.py").write_text('REDIS_HOST = "redis"\n')
    assert '"redis"' in search(workspace, "Redis host")["matches"][0]["text"]


def test_bm25_does_not_read_secrets(workspace):
    (workspace.root / ".env").write_text("PASSWORD=hiddenword")
    assert search(workspace, "hiddenword")["matches"] == []


@pytest.fixture
def database(workspace):
    db = sqlite3.connect(workspace.root / "data.db")
    db.execute("CREATE TABLE things (id INTEGER, name TEXT)")
    db.executemany("INSERT INTO things VALUES (?, ?)", [(1, "alpha"), (2, "beta")])
    db.commit(); db.close()
    return workspace


def test_sqlite_readonly_and_row_limit(database):
    result = query(database, "data.db", "SELECT name FROM things ORDER BY id", 1)
    assert result["rows"] == [["alpha"]]
    assert result["truncated"]
    assert result["read_only"]


@pytest.mark.parametrize("sql", ["DELETE FROM things", "UPDATE things SET name='x'", "DROP TABLE things",
                                "ATTACH DATABASE '/tmp/other.db' AS other", "PRAGMA user_version=10",
                                "SELECT load_extension('anything')", "SELECT randomblob(1000000000)"])
def test_sql_authorizer_denies_mutations_and_dangerous_functions(database, sql):
    with pytest.raises((sqlite3.DatabaseError, SafetyError)):
        query(database, "data.db", sql)
    assert query(database, "data.db", "SELECT count(*) FROM things")["rows"] == [[2]]


def test_cte_select_is_supported(database):
    assert query(database, "data.db", "WITH c AS (SELECT name FROM things) SELECT count(*) FROM c")["rows"] == [[2]]


def test_disabled_runner_is_not_silently_enabled(workspace):
    with pytest.raises(SafetyError, match="disabled"):
        run_tests(workspace, {"runner": "disabled"})


def test_docker_command_has_expected_restrictions(workspace):
    args = docker_command(workspace.root, "devpilot-runner:local", "test-name")
    assert args[args.index("--network") + 1] == "none"
    assert "--read-only" in args
    assert "--cap-drop" in args and "ALL" in args
    assert "no-new-privileges" in args
    assert args[args.index("--user") + 1] == "65534:65534"
    assert any("readonly" in arg for arg in args if "source=" in arg)
    assert not any("docker.sock" in arg for arg in args)


def test_process_timeout_and_output_budget(workspace):
    result = run_process([sys.executable, "-c", "import time; time.sleep(5)"], workspace.root, timeout=1)
    assert result["timed_out"] and result["exit_code"] != 0
    result = run_process([sys.executable, "-c", "print('x'*20000)"], workspace.root, max_output=1000)
    assert result["output_limited"] and len(result["output"]) <= 1000


def test_git_patch_is_real_and_preserves_source_text(workspace):
    (workspace.root / "app.py").write_text('password="example-only"\n')
    initialize(workspace.root)
    (workspace.root / "app.py").write_text('password="changed-example"\n')
    patch = diff(workspace.root)
    assert '-password="example-only"' in patch
    assert '+password="changed-example"' in patch


def test_docker_observation_disabled(workspace):
    with pytest.raises(SafetyError):
        list_containers(workspace.root, {})


def test_docker_inspection_filters_environment_and_label(workspace, monkeypatch):
    from devpilot.tools import docker
    item = {"Id": "a" * 64, "Name": "/demo", "State": {"Running": True, "Status": "running"},
            "Config": {"Labels": {"devpilot.scope": "demo"}, "Env": ["PASSWORD=secret"]}}
    monkeypatch.setattr(docker, "command", lambda args, root: json.dumps([item]))
    result = inspect_container(workspace.root, {"docker_tools": True, "docker_label": "devpilot.scope=demo"}, "a" * 12)
    assert "secret" not in json.dumps(result)
    with pytest.raises(SafetyError):
        inspect_container(workspace.root, {"docker_tools": True, "docker_label": "devpilot.scope=other"}, "a" * 12)


def test_docker_json_is_parsed_before_redaction(workspace, monkeypatch):
    from devpilot.tools import docker
    payload = [{"Id": "a" * 64, "Name": "/demo", "Config": {
        "Labels": {"devpilot.scope": "demo"},
        "Env": ["PASSWORD=quoted-value", "API_KEY=private-value"]},
        "State": {"Status": "running", "Running": True, "ExitCode": 0}}]
    seen = {}
    def run(argv, cwd, **kwargs):
        seen.update(kwargs)
        return {"exit_code": 0, "output_limited": False, "output": __import__("json").dumps(payload)}
    monkeypatch.setattr(docker, "run_process", run)
    value = docker.inspect_container(workspace.root, {"docker_tools": True, "docker_label": "devpilot.scope=demo"}, "a" * 12)
    assert seen["sanitize"] is False
    assert value["status"] == "running"
    assert "PASSWORD" not in str(value) and "private-value" not in str(value)


def test_snapshot_tracks_sanitized_files_even_if_source_gitignore_hides_them(workspace):
    from devpilot import gitops
    (workspace.root / ".gitignore").write_text("*\n")
    gitops.initialize(workspace.root)
    (workspace.root / "app.py").write_text("value = 2\n")
    patch = gitops.diff(workspace.root)
    assert "-value = 1" in patch and "+value = 2" in patch
