import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, db  # noqa: E402


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Point the app at a throwaway SQLite database."""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(config, "DB_PATH", db_path)
    db.init_db(db_path)
    return db_path
