from __future__ import annotations

import os
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

# Lazily create the engine so the DB path is resolved **after** tests change CWD.
# This fixes the “.aura not found” issue when tests chdir into a tmp dir.

AURA_HOME = Path(os.getenv("AURA_HOME", ".aura"))
DB_URL = os.getenv("AURA_DB_URL", f"sqlite:///{AURA_HOME / 'aura.db'}")

_engine = None  # created on first use


def _connect_args_for(url: str) -> dict:
    # Needed for sqlite usage across threads (fine for CLI/API dev)
    if url.startswith("sqlite:///"):
        return {"check_same_thread": False}
    return {}


def get_engine():
    """Return a singleton SQLModel engine, creating the .aura dir if sqlite is used."""
    global _engine
    if _engine is None:
        # Ensure parent dir exists for sqlite DBs, **in the current CWD**.
        if DB_URL.startswith("sqlite:///"):
            AURA_HOME.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(DB_URL, echo=False, connect_args=_connect_args_for(DB_URL))
    return _engine


def init_db() -> None:
    """Create tables if they don't exist and ensure local .aura/ exists.

    Tests and some tooling expect a .aura/ folder in the CWD regardless of
    where the DB actually lives, so we always create it.
    """
    # Ensure the conventional local folder exists for artifacts/tests
    Path(".aura").mkdir(parents=True, exist_ok=True)

    eng = get_engine()
    SQLModel.metadata.create_all(eng)


def get_session() -> Session:
    """
    Return a Session with expire_on_commit disabled so ORM objects
    remain accessible after commit. The Session itself supports `with` usage.
    """
    return Session(get_engine(), expire_on_commit=False)
