from dataclasses import dataclass
from pathlib import Path


@dataclass
class FileRule:
    source: str
    target: str
    mode: str = "create_only"


@dataclass
class PlannedChange:
    source: Path
    target: Path
    mode: str
    action: str
    reason: str
