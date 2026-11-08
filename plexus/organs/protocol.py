"""The organ contract (PLEXUS_SPEC.md section 8): all that core may know about an engine."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


class OrganError(RuntimeError):
    """An engine refused a job, failed it, or ran past the organ's deadline."""


@dataclass(frozen=True)
class Job:
    graph: dict
    seed: int
    colorspace: str
    correlation_id: str
    inputs: dict = field(default_factory=dict)


@dataclass(frozen=True)
class JobHandle:
    """The Plexus correlation id and nothing else. The engine's own job id stays inside the organ."""

    correlation_id: str


@dataclass(frozen=True)
class Progress:
    correlation_id: str
    state: str  # "queued", "done" or "failed"


@dataclass(frozen=True)
class OrganProfile:
    """The fields of PlexusOrganAPI."""

    organ_id: str
    kind: str
    endpoint: str
    capabilities: list[str]
    cost_hint: str


@dataclass(frozen=True)
class AssetRecord:
    path: Path
    sha256: str
    metadata: dict


class Organ(Protocol):
    @abstractmethod
    def profile(self) -> OrganProfile: ...

    @abstractmethod
    def capabilities(self) -> list[str]: ...

    @abstractmethod
    def submit(self, job: Job) -> JobHandle: ...

    @abstractmethod
    def stream(self, handle: JobHandle) -> Iterator[Progress]: ...

    @abstractmethod
    def result(self, handle: JobHandle) -> AssetRecord: ...
