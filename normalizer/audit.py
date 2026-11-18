from pathlib import Path
import json
import re
import tomllib

from .scanner import _walk_files


PROFILE_PATH = Path(__file__).resolve().parent.parent / "alignment.toml"
CODE_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".vue", ".svelte"}
STRUCTURE_NAMES = {"src", "app", "pages", "components", "lib", "hooks", "utils", "styles"}
FRAMEWORK_DEPENDENCIES = {
    "next", "vite", "react-scripts", "astro", "nuxt", "@angular/core", "svelte", "vue",
    "express", "fastify", "@nestjs/core", "koa", "hono", "@remix-run/node",
}


def _packages(root: Path) -> list[dict]:
    result = []
    for path in _walk_files(root):
        if path.name != "package.json":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        dependencies = {}
        for section in ("dependencies", "devDependencies"):
            values = data.get(section, {})
            if isinstance(values, dict):
                dependencies.update({str(key): str(value) for key, value in values.items()})
        result.append({"root": path.parent, "name": data.get("name", path.parent.name),
                       "dependencies": dependencies})
    return result


def _best_package(reference: dict, targets: list[dict]) -> dict | None:
    if not targets:
        return None
    expected = set(reference["dependencies"])
    return max(targets, key=lambda item: len(expected & set(item["dependencies"])))


def _checks(items: list[dict]) -> dict:
    passed = sum(item["status"] == "ok" for item in items)
    return {"configured": bool(items), "score": round(100 * passed / len(items)) if items else None,
            "passed": passed, "total": len(items), "items": items}


def _reference_component_files(template: Path) -> list[Path]:
    return [path for path in _walk_files(template)
            if path.suffix.lower() in CODE_SUFFIXES
            and any(part.lower() in {"component", "components"} for part in path.relative_to(template).parts[:-1])]


def _design_tokens(root: Path) -> set[str]:
    tokens = set()
    for path in _walk_files(root):
        if path.suffix.lower() != ".css":
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        tokens.update(re.findall(r"--([\w-]+)\s*:", content))
    return tokens


def _profile(profile_path: Path) -> dict:
    if not profile_path.is_file():
        return {}
    try:
        return tomllib.loads(profile_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return {"_error": f"No se pudo leer el perfil {profile_path}."}


def evaluate_alignment(target: Path, template: Path, profile_path: Path = PROFILE_PATH) -> dict:
    reference_packages = _packages(template)
    target_packages = _packages(target)
    profile = _profile(profile_path)
    if profile.get("_error"):
        return {"configured": False, "score": None, "axes": {}, "recommendations": [], "error": profile["_error"]}

    reference_dependencies = {}
    target_dependencies = {}
    for package in reference_packages:
        reference_dependencies.update(package["dependencies"])
    for package in target_packages:
        target_dependencies.update(package["dependencies"])

    stack_checks = []
    for name, version in sorted(reference_dependencies.items()):
        found = target_dependencies.get(name)
        status = "ok" if found == version else "drift" if found else "missing"
        message = (f"{name}: alineada ({found})" if status == "ok"
                   else f"{name}: versión {found}; el template declara {version}" if found
                   else f"{name}: falta; el template declara {version}")
        stack_checks.append({"criterion": name, "status": status, "message": message})
    target_frameworks = {name: version for package in target_packages
                         for name, version in package["dependencies"].items()
                         if name in FRAMEWORK_DEPENDENCIES}
    for name, version in sorted(target_frameworks.items()):
        if name not in reference_dependencies:
            stack_checks.append({"criterion": f"extra:{name}", "status": "drift",
                                 "message": f"{name} ({version}): no forma parte del stack del template; revisar reemplazo"})
    for name, version in profile.get("stack", {}).get("dependencies", {}).items():
        if name not in reference_dependencies:
            found = target_dependencies.get(name)
            stack_checks.append({"criterion": name, "status": "ok" if found else "missing",
                                 "message": f"{name}: {'presente' if found else 'falta'} (criterio adicional)"})

    primary_reference = max(reference_packages, key=lambda item: len(item["dependencies"])) if reference_packages else None
    primary_target = _best_package(primary_reference, target_packages) if primary_reference else None
    template_root = primary_reference["root"] if primary_reference else template
    target_root = primary_target["root"] if primary_target else target

    structure_checks = []
    reference_dirs = set()
    for path in _walk_files(template_root):
        for parent in path.relative_to(template_root).parents:
            if str(parent) != "." and parent.name.lower() in STRUCTURE_NAMES:
                reference_dirs.add(parent.as_posix())
    for relative in sorted(reference_dirs):
        exists = (target_root / relative).is_dir()
        structure_checks.append({"criterion": relative, "status": "ok" if exists else "missing",
                                 "message": f"Carpeta {relative}: {'encontrada' if exists else 'falta'}"})
    for relative in profile.get("structure", {}).get("paths", []):
        exists = (target / str(relative)).exists()
        structure_checks.append({"criterion": str(relative), "status": "ok" if exists else "missing",
                                 "message": f"Ruta adicional {relative}: {'encontrada' if exists else 'falta'}"})

    component_checks = []
    for path in _reference_component_files(template_root):
        relative = path.relative_to(template_root).as_posix()
        exists = (target_root / relative).is_file()
        component_checks.append({"criterion": relative, "status": "ok" if exists else "missing",
                                 "message": f"Componente {relative}: {'encontrado' if exists else 'falta'}"})
    existing_component_paths = {item["criterion"] for item in component_checks}
    for relative in profile.get("components", {}).get("paths", []):
        relative = str(relative)
        if relative in existing_component_paths:
            continue
        exists = (target / relative).is_file()
        component_checks.append({"criterion": relative, "status": "ok" if exists else "missing",
                                 "message": f"Componente adicional {relative}: {'encontrado' if exists else 'falta'}"})

    expected_tokens = _design_tokens(template)
    expected_tokens.update(str(value).removeprefix("--") for value in profile.get("design", {}).get("tokens", []))
    found_tokens = _design_tokens(target_root)
    design_checks = [{"criterion": token, "status": "ok" if token in found_tokens else "missing",
                      "message": f"Token --{token}: {'encontrado' if token in found_tokens else 'falta'}"}
                     for token in sorted(expected_tokens)]

    axes = {"stack": _checks(stack_checks), "structure": _checks(structure_checks),
            "components": _checks(component_checks), "design": _checks(design_checks)}
    configured_axes = [axis for axis in axes.values() if axis["configured"]]
    total_checks = sum(axis["total"] for axis in configured_axes)
    passed_checks = sum(axis["passed"] for axis in configured_axes)
    score = round(sum(axis["score"] for axis in configured_axes) / len(configured_axes)) if configured_axes else None
    recommendations = [item["message"] for axis in axes.values() for item in axis["items"]
                       if item["status"] != "ok"]
    if not reference_packages:
        recommendations.insert(0, "El template actualizado no contiene package.json; no se pudo auditar el stack.")
    if not total_checks:
        recommendations.append("No se encontraron criterios comparables en el template actualizado.")
    return {"configured": bool(total_checks), "score": score,
            "axes_scored": len(configured_axes), "criteria_passed": passed_checks,
            "criteria_total": total_checks, "axes": axes, "recommendations": recommendations,
            "template_package": primary_reference["name"] if primary_reference else None,
            "matched_project_package": primary_target["name"] if primary_target else None,
            "matched_project_package_path": (primary_target["root"].relative_to(target).as_posix()
                                              if primary_target and primary_target["root"] != target else "."),
            "profile": str(profile_path)}
