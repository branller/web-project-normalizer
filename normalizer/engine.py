from pathlib import Path
import shutil

from .backup import backup_file, create_backup_root
from .models import PlannedChange


class ApplyError(RuntimeError):
    pass


def apply_plan(
    plan: list[PlannedChange],
    target_root: Path,
    backup_parent: Path,
    dry_run: bool = False,
) -> tuple[list[str], Path | None]:
    errors = [item for item in plan if item.action == "error"]
    if errors:
        raise ApplyError("El plan contiene errores. Corregí las reglas antes de aplicar.")

    changes = [item for item in plan if item.action in {"create", "replace", "append"}]
    if dry_run or not changes:
        return ([f"{item.action}: {item.target}" for item in changes], None)

    backup_root = create_backup_root(backup_parent)
    created: list[Path] = []
    backed_up: list[tuple[Path, Path]] = []

    try:
        # Preflight: validar que todas las fuentes sigan disponibles y que los destinos
        # sean archivos o rutas inexistentes antes de tocar el proyecto.
        for item in changes:
            if not item.source.is_file():
                raise ApplyError(f"El archivo fuente dejó de existir: {item.source}")
            if item.target.exists() and not item.target.is_file():
                raise ApplyError(f"El destino existe y no es un archivo: {item.target}")

        for item in changes:
            item.target.parent.mkdir(parents=True, exist_ok=True)

            if item.target.exists():
                backup_path = backup_file(target_root, item.target, backup_root)
                backed_up.append((item.target, backup_path))
            else:
                created.append(item.target)

            if item.mode == "append" and item.target.exists():
                original = item.target.read_text(encoding="utf-8")
                source_text = item.source.read_text(encoding="utf-8")
                marker = f"/* BEGIN WEB PROJECT NORMALIZER: {item.source.name} */"
                end_marker = f"/* END WEB PROJECT NORMALIZER: {item.source.name} */"
                payload = (
                    f"\\n\\n{marker}\\n{source_text.rstrip()}\\n{end_marker}\\n"
                )
                item.target.write_text(original.rstrip() + payload, encoding="utf-8")
            else:
                shutil.copy2(item.source, item.target)

        return ([f"{item.action}: {item.target}" for item in changes], backup_root)

    except Exception as exc:
        # Rollback best-effort: restaurar archivos respaldados y eliminar los nuevos.
        for destination, backup in reversed(backed_up):
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, destination)
            except OSError:
                pass
        for destination in reversed(created):
            try:
                destination.unlink(missing_ok=True)
            except OSError:
                pass
        raise ApplyError(
            f"Falló la aplicación; se intentó revertir los cambios. Detalle: {exc}"
        ) from exc
