from pathlib import Path


class PathSafetyError(ValueError):
    pass


def resolve_inside(base: Path, relative: str) -> Path:
    candidate = (base / relative).resolve()
    base_resolved = base.resolve()

    try:
        candidate.relative_to(base_resolved)
    except ValueError as exc:
        raise PathSafetyError(
            f"La ruta '{relative}' intenta salir del directorio permitido."
        ) from exc

    return candidate


def validate_target(target: Path) -> Path:
    if not target.exists() or not target.is_dir():
        raise PathSafetyError(f"El proyecto objetivo no existe o no es una carpeta: {target}")
    return target.resolve()
