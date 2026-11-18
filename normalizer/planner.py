from pathlib import Path

from .models import FileRule, PlannedChange
from .paths import resolve_inside


class PlanningError(ValueError):
    pass


def build_plan(template: Path, target: Path, rules: list[FileRule]) -> list[PlannedChange]:
    plan = []

    for rule in rules:
        source = resolve_inside(template, rule.source)
        destination = resolve_inside(target, rule.target)

        if not source.is_file():
            plan.append(PlannedChange(
                source, destination, rule.mode, "error",
                f"No existe el archivo fuente del template: {rule.source}",
            ))
            continue

        if rule.mode == "create_only":
            if destination.exists():
                action, reason = "skip", "El destino ya existe; create_only no lo sobrescribe."
            else:
                action, reason = "create", "Se creará el archivo porque todavía no existe."
        elif rule.mode == "replace":
            if destination.exists():
                action, reason = "replace", "Se reemplazará el archivo según la regla explícita."
            else:
                action, reason = "create", "El destino no existe; se creará."
        else:  # append
            if destination.exists():
                marker = f"/* BEGIN WEB PROJECT NORMALIZER: {rule.source} */"
                current = destination.read_text(encoding="utf-8", errors="replace")
                if marker in current:
                    action, reason = "skip", "El contenido de esta regla ya fue agregado."
                else:
                    action, reason = "append", "Se agregará el contenido con marcadores de origen."
            else:
                action, reason = "create", "El destino no existe; se creará."

        plan.append(PlannedChange(source, destination, rule.mode, action, reason))

    return plan
