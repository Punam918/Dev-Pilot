import os
import pytest
from devpilot.safety import Workspace, SafetyError, Capabilities, copy_workspace, digest, redact, redact_tree


@pytest.mark.parametrize("path", ["../outside", "/etc/passwd", ".git/config", "a/../../b", "a\\b", "", "a\x00b"])
def test_unsafe_paths(workspace, path):
    with pytest.raises((SafetyError, FileNotFoundError)):
        workspace.path(path)


@pytest.mark.parametrize("name", [".env", ".env.production", "id_rsa", "key.pem", "secret.key", "credentials.json"])
def test_secret_paths(workspace, name):
    (workspace.root / name).write_text("secret")
    assert name not in workspace.files()
    with pytest.raises(SafetyError):
        workspace.read(name)


def test_final_symlink_rejected(workspace, tmp_path):
    outside = tmp_path / "outside"
    outside.write_text("private")
    (workspace.root / "link.py").symlink_to(outside)
    with pytest.raises(SafetyError):
        workspace.read("link.py")
    assert "link.py" not in workspace.files()


def test_parent_symlink_rejected(workspace, tmp_path):
    (workspace.root / "linked").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(SafetyError):
        workspace.path("linked/repo/app.py")


def test_hardlink_rejected(workspace):
    os.link(workspace.root / "app.py", workspace.root / "copy.py")
    with pytest.raises(SafetyError):
        workspace.read("copy.py")


def test_binary_and_large_files(workspace):
    (workspace.root / "binary.dat").write_bytes(b"abc\x00def")
    (workspace.root / "large.txt").write_bytes(b"x" * 120001)
    with pytest.raises(SafetyError):
        workspace.read("binary.dat")
    with pytest.raises(SafetyError):
        workspace.read("large.txt")


def test_replacement_is_hash_bound_and_atomic(workspace):
    before = workspace.read("app.py")
    result = workspace.replace("app.py", "value = 1", "value = 2", digest(before))
    assert workspace.read("app.py") == "value = 2\n"
    assert "+value = 2" in result["diff"]
    with pytest.raises(SafetyError, match="Stale"):
        workspace.replace("app.py", "value = 2", "value = 3", digest(before))


def test_replacement_must_match_once(workspace):
    (workspace.root / "app.py").write_text("x x\n")
    with pytest.raises(SafetyError, match="exactly once"):
        workspace.replace("app.py", "x", "y", digest("x x\n"))


def test_cannot_edit_tests(workspace):
    (workspace.root / "test_app.py").write_text("assert True\n")
    with pytest.raises(SafetyError, match="Changing tests"):
        workspace.replace("test_app.py", "True", "False", digest("assert True\n"))


def test_snapshot_excludes_git_and_env_and_does_not_edit_source(workspace, tmp_path):
    (workspace.root / ".git").mkdir()
    (workspace.root / ".git/config").write_text("unsafe config")
    (workspace.root / ".env").write_text("PASSWORD=private")
    target = tmp_path / "copy"
    summary = copy_workspace(workspace.root, target)
    assert summary["files"] == 1
    assert not (target / ".git").exists()
    assert not (target / ".env").exists()
    (target / "app.py").write_text("changed")
    assert workspace.read("app.py") == "value = 1\n"


def test_capability_single_use(workspace):
    cap = Capabilities("secret" * 10)
    token = cap.issue("files__replace_text", {"path": "app.py"}, workspace.fingerprint())
    cap.verify(token, "files__replace_text", {"path": "app.py"}, workspace.fingerprint())
    with pytest.raises(SafetyError):
        cap.verify(token, "files__replace_text", {"path": "app.py"}, workspace.fingerprint())


@pytest.mark.parametrize("change", ["tool", "args", "snapshot", "secret", "expired"])
def test_capability_boundaries(workspace, change):
    cap = Capabilities("a" * 64)
    token = cap.issue("files__replace_text", {"path": "app.py"}, "snapshot", ttl=-1 if change == "expired" else 60)
    verifier = Capabilities("b" * 64) if change == "secret" else cap
    with pytest.raises(SafetyError):
        verifier.verify(token, "terminal__run_tests" if change == "tool" else "files__replace_text",
                        {"path": "other.py"} if change == "args" else {"path": "app.py"},
                        "changed" if change == "snapshot" else "snapshot")


def test_redaction_preserves_structure():
    result = redact_tree({"output": "password=supersecret\nAuthorization: Bearer abc123", "exit_code": 0})
    assert "supersecret" not in result["output"]
    assert "abc123" not in result["output"]
    assert result["exit_code"] == 0
