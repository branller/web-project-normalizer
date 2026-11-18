from pathlib import Path
import json
import os


IGNORED_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", ".next",
    "dist", "build", "coverage", ".turbo", ".cache", "vendor",
}
STYLE_NAMES = {"globals.css", "global.css", "index.css", "app.css"}


def _walk_files(target: Path):
    """Walk project source while pruning dependency and generated directories."""
    for current, dirs, files in os.walk(target):
        dirs[:] = sorted(d for d in dirs if d not in IGNORED_DIRS)
        current_path = Path(current)
        for name in files:
            yield current_path / name


def _read_package(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"_error": "El contenido no es un objeto JSON."}
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {"_error": "No se pudo interpretar el archivo package.json."}


def _describe_package(path: Path, target: Path, files: list[Path], package_dirs: set[Path]) -> dict:
    package = _read_package(path)
    dependencies = {}
    for section in ("dependencies", "devDependencies"):
        values = package.get(section, {})
        if isinstance(values, dict):
            dependencies.update(values)

    frameworks = []
    for key, label in (("next", "Next.js"), ("vite", "Vite"), ("react-scripts", "Create React App"),
                       ("astro", "Astro"), ("nuxt", "Nuxt"), ("@angular/core", "Angular"),
                       ("svelte", "SvelteKit/Svelte"), ("vue", "Vue"),
                       ("express", "Express"), ("fastify", "Fastify"),
                       ("@nestjs/core", "NestJS"), ("koa", "Koa"), ("hono", "Hono"),
                       ("@remix-run/node", "Remix"), ("electron", "Electron")):
        if key in dependencies:
            frameworks.append(f"{label} ({dependencies[key]})")

    relative = path.parent.relative_to(target).as_posix()
    nested_packages = [directory for directory in package_dirs
                       if directory != path.parent and directory.is_relative_to(path.parent)]
    local_files = [file for file in files if file.is_relative_to(path.parent)
                   and not any(file.is_relative_to(directory) for directory in nested_packages)]
    ts_files = any(file.suffix.lower() in {".ts", ".tsx"} for file in local_files)
    typescript = dependencies.get("typescript")
    if not typescript and (ts_files or any((path.parent / name).is_file() for name in ("tsconfig.json",))):
        typescript = "Detectado por archivos/configuración (sin versión declarada)"

    stack = list(frameworks)
    for key, label in (("react", "React"), ("typescript", "TypeScript"),
                       ("tailwindcss", "Tailwind CSS"), ("vue", "Vue"), ("svelte", "Svelte")):
        version = dependencies.get(key)
        if key == "typescript":
            version = typescript
        if version and not any(item.startswith(label) for item in stack):
            stack.append(f"{label} ({version})")
    if frameworks:
        role = "Aplicación/servicio"
    elif relative == ".":
        role = "Raíz/workspace o metadatos"
    elif dependencies:
        role = "Paquete auxiliar (stack no identificado)"
    else:
        role = "Paquete sin dependencias detectadas"
    return {
        "path": relative or ".",
        "name": package.get("name") or (target.name if relative == "." else path.parent.name),
        "frameworks": frameworks,
        "stack": stack,
        "role": role,
        "react": dependencies.get("react"),
        "typescript": typescript,
        "tailwind": dependencies.get("tailwindcss"),
        "has_shadcn_config": (path.parent / "components.json").is_file(),
        "error": package.get("_error"),
    }


def scan_project(target: Path) -> dict:
    files = list(_walk_files(target))
    package_files = sorted((p for p in files if p.name == "package.json"), key=lambda p: str(p).lower())
    package_dirs = {path.parent for path in package_files}
    packages = [_describe_package(path, target, files, package_dirs) for path in package_files]
    root_package = next((p for p in packages if p["path"] == "."), None)
    styles = sorted(
        p.relative_to(target).as_posix()
        for p in files
        if p.suffix.lower() == ".css" and p.name.lower() in STYLE_NAMES
    )

    source_dirs = []
    for path in files:
        if path.is_dir():
            continue
        relative_parts = path.relative_to(target).parts
        for index, part in enumerate(relative_parts[:-1]):
            if part in {"src", "app", "pages", "components"}:
                candidate = Path(*relative_parts[:index + 1]).as_posix()
                if candidate not in source_dirs:
                    source_dirs.append(candidate)

    # Aggregate technology versions across packages for an explicit monorepo summary.
    summary = {}
    for key in ("react", "typescript", "tailwind"):
        summary[key] = next((pkg[key] for pkg in packages if pkg.get(key)), None)
    stacks = []
    for pkg in packages:
        for technology in pkg["stack"]:
            if technology not in stacks:
                stacks.append(technology)

    return {
        "target": str(target),
        "has_package_json": bool(package_files),
        "project_name": (root_package or (packages[0] if packages else {})).get("name"),
        "framework": ", ".join(stacks) if stacks else "No detectado",
        "stack": stacks,
        **summary,
        "packages": packages,
        "directories": sorted(source_dirs),
        "global_styles": styles,
        "has_shadcn_config": any(pkg["has_shadcn_config"] for pkg in packages),
        "git_repository": (target / ".git").exists(),
        "notes": [
            "El scanner es de solo lectura.",
            "Se recorren subcarpetas y se omiten dependencias y carpetas generadas.",
            "La detección tecnológica se basa en package.json; revisá el resultado antes de aplicar reglas.",
        ],
    }
