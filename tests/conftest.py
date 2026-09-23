import pytest
from pathlib import Path
from devpilot.safety import Workspace
from devpilot.config import Settings
from devpilot.demo import seed


@pytest.fixture
def workspace(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "app.py").write_text("value = 1\n")
    return Workspace(root)


@pytest.fixture
def config(tmp_path):
    settings = Settings(_env_file=None, provider="demo", workspace_dir=tmp_path / "workspace",
                        data_dir=tmp_path / "state", runner="host-trusted", trust_local_code=True,
                        api_token="unit-test-token-abcdefghijklmnopqrstuvwxyz")
    seed(settings.workspace_dir)
    return settings
