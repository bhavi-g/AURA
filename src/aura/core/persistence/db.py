from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

# Where the local SQLite DB lives (created automatically)
DB_PATH = Path(".aura") / "aura.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# Create engine:
# - check_same_thread=False lets us reuse the engine across threads (OK for CLI/API dev)
# - echo=False keeps logs quiet
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    echo=False,
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    """Create tables if they don't exist."""

    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    """
    Return a Session with expire_on_commit disabled so ORM objects
    (e.g., project.id) can be accessed after the session closes.
    """
    return Session(engine, expire_on_commit=False)
