from datetime import datetime, timezone
from pathlib import Path
import shutil


def backup_file(target_root: Path, file_path: Path, backup_root: Path) -> Path:
    relative = file_path.relative_to(target_root)
    destination = backup_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(file_path, destination)
    return destination


def create_backup_root(base: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = base / f"backup-{stamp}"
    suffix = 1
    while path.exists():
        path = base / f"backup-{stamp}-{suffix}"
        suffix += 1
    path.mkdir(parents=True)
    return path
