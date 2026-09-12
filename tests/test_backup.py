import io
import tarfile
import pytest
from devpilot.backup import create_backup, restore_backup
from devpilot.lease import InstanceLease
from devpilot.store import Store


def test_offline_backup_roundtrip_excludes_credentials(config, tmp_path):
    config.data_dir.mkdir(exist_ok=True)
    store = Store(config.data_dir / "audit.sqlite3")
    store.create("example-run", {"repo": "demo-redis"})
    (config.data_dir / "access-token").write_text("never-back-up-credentials")
    (config.workspace_dir / ".env").write_text("also-excluded")
    archive = tmp_path / "backup.tar.gz"
    result = create_backup(config, archive)
    assert "state/audit.sqlite3" in result["files"]
    assert not any("access-token" in n or ".env" in n for n in result["files"])
    restored = tmp_path / "restored"
    restore_backup(archive, restored)
    assert Store(restored / "state/audit.sqlite3").get("example-run")["repo"] == "demo-redis"
    assert (restored / "workspace/demo-redis").is_dir()
    with pytest.raises(FileExistsError):
        restore_backup(archive, restored)


def test_backup_refuses_live_instance_or_overwrite(config, tmp_path):
    with InstanceLease(config.data_dir):
        with pytest.raises(RuntimeError):
            create_backup(config, tmp_path / "backup.tar.gz")
    target = tmp_path / "existing.tar.gz"
    target.write_bytes(b"existing")
    with pytest.raises(FileExistsError):
        create_backup(config, target)
    with pytest.raises(ValueError):
        create_backup(config, config.data_dir / "bad.tar.gz")


def test_restore_rejects_path_traversal_before_writing(tmp_path):
    path = tmp_path / "bad.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        for name, raw in [("../escaped", b"bad"), ("manifest.json", b'{}')]:
            item = tarfile.TarInfo(name)
            item.size = len(raw)
            archive.addfile(item, io.BytesIO(raw))
    destination = tmp_path / "restore"
    with pytest.raises(ValueError):
        restore_backup(path, destination)
    assert not destination.exists()
    assert not (tmp_path / "escaped").exists()
