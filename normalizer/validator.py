from pathlib import Path
import json


def validate_project(target: Path) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []

    package_file = target / "package.json"
    if package_file.exists():
        try:
            json.loads(package_file.read_text(encoding="utf-8"))
            results.append(("OK", "package.json contiene JSON válido."))
        except (json.JSONDecodeError, OSError) as exc:
            results.append(("ERROR", f"package.json no es válido: {exc}"))
    else:
        results.append(("WARN", "No se encontró package.json; no parece un proyecto Node convencional."))

    css_files = []
    for pattern in ("**/*.css",):
        css_files.extend(target.glob(pattern))

    for css_file in css_files:
        if any(part in {".git", "node_modules", ".venv"} for part in css_file.parts):
            continue
        try:
            content = css_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            results.append(("WARN", f"No se pudo leer {css_file.relative_to(target)}"))
            continue

        # Comprobación básica, no reemplaza un parser CSS.
        if content.count("{") != content.count("}"):
            results.append(("WARN", f"Posible desbalance de llaves en {css_file.relative_to(target)}"))

    if not any(level == "ERROR" for level, _ in results):
        results.append(("OK", "Validaciones básicas completadas. No se ejecutó el build del proyecto."))

    return results
