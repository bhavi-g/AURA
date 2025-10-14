from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

# Lazily-created engine bound to the *current* DB path.
_ENGINE: Engine | None = None
_ENGINE_PATH: Path | None = None


def _db_path() -> Path:
    """
    Resolve the SQLite DB path. Default: ./.aura/aura.db
    Override the base dir with AURA_DB_DIR if set.
    """
    base = Path(os.environ.get("AURA_DB_DIR", ".aura"))
    return base / "aura.db"


def _get_engine() -> Engine:
    """
    Create (or reuse) an Engine for the current DB path.
    If the working directory or env var changes, recreate the engine.
    """
    global _ENGINE, _ENGINE_PATH
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)  # ensure .aura/ exists

    if _ENGINE is None or _ENGINE_PATH != path:
        _ENGINE_PATH = path
        _ENGINE = create_engine(
            f"sqlite:///{path}",
            echo=False,
            connect_args={"check_same_thread": False},
        )
    return _ENGINE


def init_db() -> None:
    """Create tables if they don't exist (ensures .aura/ exists too)."""
    engine = _get_engine()
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    """
    Return a Session with expire_on_commit disabled so ORM objects
    can be accessed after the session closes.
    """
    return Session(_get_engine(), expire_on_commit=False)
