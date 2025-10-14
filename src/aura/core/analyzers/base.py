from typing import Protocol, runtime_checkable

from .normalize import Finding


@runtime_checkable
class Analyzer(Protocol):
    name: str

    def run(self, target: str) -> list[Finding]: ...
