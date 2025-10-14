from pathlib import Path

from sqlalchemy import text  # ← add

from aura.core.persistence.db import get_session, init_db


def test_db_init_and_session(temp_cwd):
    init_db()
    with get_session() as s:
        # create a connection and run a trivial query
        s.exec(text("SELECT 1"))  # ← change from s.execute("SELECT 1")

    assert Path(".aura").exists()
    db_file = Path(".aura/aura.db")
    if db_file.exists():
        assert db_file.is_file()
