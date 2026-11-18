from pathlib import Path
import json
import re

from .models import PlannedChange
from .scanner import _walk_files
from .css_theme import THEME_MARKER, source_theme


def _examples(values: list[str], limit: int = 5) -> str:
    shown = ", ".join(values[:limit])
    remaining = len(values) - limit
    return f"{shown} y {remaining} más" if remaining > 0 else shown


def _package_dependencies(package_root: Path) -> set[str]:
    package_file = package_root / "package.json"
    try:
        package = json.loads(package_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return set()
    dependencies = set()
    for section in ("dependencies", "devDependencies"):
        values = package.get(section, {})
        if isinstance(values, dict):
            dependencies.update(values)
    return dependencies


def _has_alias_support(package_root: Path) -> bool:
    for name in ("tsconfig.json", "jsconfig.json", "vite.config.js", "vite.config.ts", "vite.config.mjs"):
        path = package_root / name
        if path.is_file():
            try:
                if re.search(r"['\"]@['\"]|['\"]@/", path.read_text(encoding="utf-8")):
                    return True
            except (OSError, UnicodeDecodeError):
                pass
    return False


def build_safe_component_plan(template: Path, target: Path, alignment: dict) -> list[PlannedChange]:
    """Plan create-only copies only when all external imports resolve in the target package."""
    template_package = alignment.get("template_package")
    target_package_path = alignment.get("matched_project_package_path")
    if not template_package or not target_package_path:
        return []
    template_root = template
    target_root = target if target_package_path == "." else target / target_package_path
    dependencies = _package_dependencies(target_root)
    has_alias = _has_alias_support(target_root)
    plan = []
    for source in _walk_files(template_root):
        parts = source.relative_to(template_root).parts
        if "components" not in {part.lower() for part in parts[:-1]}:
            continue
        if source.suffix.lower() not in {".tsx", ".ts", ".jsx", ".js"}:
            continue
        destination = target_root / source.relative_to(template_root)
        if destination.exists():
            continue

        imports = re.findall(r"(?:from\s+|import\s*)['\"]([^'\"]+)['\"]", source.read_text(encoding="utf-8"))
        missing = []
        for module in imports:
            if module.startswith(("./", "../")):
                local_base = (source.parent / module).resolve()
                local_candidates = [local_base, *(local_base.with_suffix(suffix) for suffix in
                                   (".tsx", ".ts", ".jsx", ".js", ".css", ".json"))]
                if not any(candidate.is_file() for candidate in local_candidates):
                    missing.append(module)
                continue
            if module.startswith("@/"):
                if not has_alias:
                    missing.append(f"alias {module}")
                continue
            package_name = "/".join(module.split("/")[:2]) if module.startswith("@") else module.split("/")[0]
            if package_name not in dependencies:
                missing.append(package_name)

        if missing:
            continue
        plan.append(PlannedChange(
            source=source,
            target=destination,
            mode="create_only",
            action="create",
            reason="Se copiará como archivo nuevo; imports externos y alias detectados en el paquete objetivo.",
        ))
    return plan


def build_theme_plan(template: Path, target: Path, alignment: dict) -> list[PlannedChange]:
    """Merge template design tokens into an existing Tailwind v4 global stylesheet."""
    target_package_path = alignment.get("matched_project_package_path")
    if not target_package_path:
        return []
    target_root = target if target_package_path == "." else target / target_package_path
    package_file = target_root / "package.json"
    try:
        package = json.loads(package_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    dependencies = {}
    for section in ("dependencies", "devDependencies"):
        values = package.get(section, {})
        if isinstance(values, dict):
            dependencies.update(values)
    tailwind_version = str(dependencies.get("tailwindcss", ""))
    if not tailwind_version.startswith(("^4", "~4", "4")):
        return []

    source_candidates = [template / "src" / "app" / "globals.css"]
    source = next((path for path in source_candidates if path.is_file()), None)
    if source is None or not source_theme(source):
        return []
    preferred = [target_root / "src" / "index.css", target_root / "src" / "globals.css",
                 target_root / "src" / "app" / "globals.css"]
    destination = next((path for path in preferred if path.is_file()), None)
    if destination is None:
        destination = next((path for path in _walk_files(target_root)
                            if path.suffix.lower() == ".css" and path.name.lower() in {"index.css", "globals.css", "global.css"}), None)
    if destination is None or THEME_MARKER in destination.read_text(encoding="utf-8", errors="replace"):
        return []
    if "@import\"tailwindcss\"" not in destination.read_text(encoding="utf-8").replace(" ", ""):
        return []
    return [PlannedChange(
        source=source,
        target=destination,
        mode="merge_theme",
        action="append",
        reason="Se integrarán los tokens del template después de los imports Tailwind; se conserva el CSS existente.",
    )]


def build_recommendations(alignment: dict, automatic_components: set[str] | None = None,
                          automatic_axes: set[str] | None = None) -> list[dict]:
    """Turn audit findings into concrete, reviewable migration tasks."""
    axes = alignment.get("axes", {})
    tasks = []

    stack_items = [item for item in axes.get("stack", {}).get("items", [])
                   if item.get("status") != "ok"]
    if stack_items:
        missing = [item["criterion"] for item in stack_items
                   if item.get("status") == "missing" and not item["criterion"].startswith("extra:")]
        versions = [item for item in stack_items
                    if item.get("status") == "drift" and not item["criterion"].startswith("extra:")]
        extras = [item["message"] for item in stack_items if item["criterion"].startswith("extra:")]
        details = []
        if missing:
            details.append(f"Faltan {len(missing)}: {_examples(missing)}")
        if versions:
            details.append("Versiones distintas: " + "; ".join(item["message"] for item in versions[:4])
                           + (f"; y {len(versions) - 4} más" if len(versions) > 4 else ""))
        if extras:
            details.append("Frameworks/herramientas adicionales: " + "; ".join(extras))
        tasks.append({
            "axis": "Stack",
            "automatic": False,
            "classification": "NOTIFICAR",
            "message": f"Revisar {len(missing)} dependencias faltantes, {len(versions)} versiones y {len(extras)} frameworks adicionales.",
            "details": details,
        })

    structure = [item["criterion"] for item in axes.get("structure", {}).get("items", [])
                 if item.get("status") != "ok"]
    if structure:
        tasks.append({
            "axis": "Estructura",
            "automatic": False,
            "classification": "NOTIFICAR",
            "message": "Evaluar estas rutas del template para crear o adaptar en el paquete objetivo: "
                       + ", ".join(structure),
            "details": [],
        })

    automatic_components = automatic_components or set()
    automatic_axes = automatic_axes or set()
    components = [item["criterion"] for item in axes.get("components", {}).get("items", [])
                  if item.get("status") != "ok" and item["criterion"] not in automatic_components]
    if components:
        tasks.append({
            "axis": "Componentes",
            "automatic": False,
            "classification": "NOTIFICAR",
            "message": "Integrar componentes faltantes después de resolver imports, dependencias y alias del cliente: "
                       + ", ".join(components),
            "details": [],
        })

    tokens = [item["criterion"] for item in axes.get("design", {}).get("items", [])
              if item.get("status") != "ok"]
    if tokens and "design" in automatic_axes:
        tasks.append({
            "axis": "Diseño visual",
            "automatic": False,
            "classification": "REVISAR",
            "message": "Se integrarán los tokens del template, pero las clases y estilos propios del frontend no se reemplazan.",
            "details": ["La apariencia puede requerir una adaptación visual posterior."],
        })
    elif tokens:
        shown = ", ".join(f"--{name}" for name in tokens[:12])
        if len(tokens) > 12:
            shown += f" y {len(tokens) - 12} más"
        tasks.append({
            "axis": "Diseño",
            "automatic": False,
            "classification": "REVISAR",
            "message": f"Faltan {len(tokens)} de los nombres de variables CSS del template.",
            "details": [f"Ejemplos: {shown}", "La puntuación verifica nombres de variables CSS, no similitud visual de la interfaz."],
        })

    return tasks
