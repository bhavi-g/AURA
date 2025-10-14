from datetime import datetime

from sqlmodel import Field, Relationship, SQLModel


class Project(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    artifacts: list["Artifact"] = Relationship(back_populates="project")


class Artifact(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")
    kind: str
    path: str
    project: Project = Relationship(back_populates="artifacts")
    runs: list["Run"] = Relationship(back_populates="artifact")


class Run(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    artifact_id: int = Field(foreign_key="artifact.id")
    tool: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    artifact: Artifact = Relationship(back_populates="runs")
    findings: list["Finding"] = Relationship(back_populates="run")


class Finding(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="run.id")
    tool: str
    rule_id: str
    title: str
    severity: str
    confidence: str
    category: str
    score: float
    data: str  # JSON string
    run: Run = Relationship(back_populates="findings")
