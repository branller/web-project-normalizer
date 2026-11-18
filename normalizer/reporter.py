import json
from pathlib import Path
from textwrap import fill


def _axis_label(name: str) -> str:
    return {"stack": "Stack", "structure": "Estructura", "components": "Componentes",
            "design": "Tokens CSS", "Diseño visual": "Diseño visual"}.get(name, name)


def _print_task(task: dict, indent: str = "  ") -> None:
    prefix = f"{indent}[{task.get('classification', 'REVISAR')} · {task['axis']}] "
    print(fill(task["message"], width=100, initial_indent=prefix,
               subsequent_indent=" " * len(prefix)))
    for detail in task.get("details", []):
        print(fill(detail, width=100, initial_indent=f"{indent}    • ",
                   subsequent_indent=f"{indent}      "))


def print_json(data: dict) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def print_normalization_plan(alignment: dict, tasks: list[dict], file_changes: list) -> None:
    print("\nDIAGNÓSTICO ACTUAL · antes de aplicar cambios")
    if alignment.get("score") is None:
        print("  Porcentaje: no calculable; el template no contiene criterios comparables.")
    else:
        print(f"  Alineación: {alignment['score']}% (promedio simple de {alignment['axes_scored']} ejes)")
    if alignment.get("template_package"):
        print(f"  Paquete comparado: {alignment['template_package']} → "
              f"{alignment.get('matched_project_package') or 'sin equivalente detectado'}")

    for name, axis in alignment.get("axes", {}).items():
        label = _axis_label(name)
        if axis.get("configured"):
            print(f"  {label}: {axis['score']}% ({axis['passed']}/{axis['total']})")

    if alignment.get("score") is not None:
        print("  Cada eje pesa lo mismo; compara versiones, rutas/archivos y nombres de variables CSS, no apariencia visual.")

    print("\nCAMBIOS PROPUESTOS")
    if tasks:
        for task in tasks:
            _print_task(task)
    if file_changes:
        for item in file_changes:
            print(f"  [{item.action.upper()}] {item.target}")
            print(f"    {item.reason}")
    if not tasks and not file_changes:
        print("  No se detectaron diferencias ni reglas explícitas de archivo.")


def print_scan(data: dict) -> None:
    """Print a readable terminal summary; JSON remains available for automation."""
    line = "═" * 68
    print(f"\n╔{line}╗")
    print(f"║  🔎  ANÁLISIS DEL PROYECTO{' ' * 39}║")
    print(f"╚{line}╝")
    print(f"  Proyecto   {data.get('project_name') or 'Sin nombre'}")
    print(f"  Ubicación  {data['target']}")
    if data.get("template_revision"):
        print(f"  Template   {data['template_revision']} (Git)")
    print(f"  Stack      {data.get('framework', 'No detectado')}")

    audit = data.get("alignment", {})
    print("\n  📊 Alineación con el template")
    if audit.get("score") is None:
        print("    No calculable: falta configurar criterios de referencia.")
    else:
        print(f"    Coincidencia general: {audit['score']}% (promedio simple de {audit['axes_scored']} ejes)")
    if audit.get("template_package"):
        print(f"    Base: {audit['template_package']} → {audit.get('matched_project_package') or 'sin paquete equivalente'}")
    for name, axis in audit.get("axes", {}).items():
        label = _axis_label(name)
        if axis["configured"]:
            print(f"    {label}: {axis['score']}% ({axis['passed']}/{axis['total']})")
        else:
            print(f"    {label}: sin criterios")
    if audit.get("error"):
        print(f"    ⚠ {audit['error']}")
    tasks = data.get("normalization_tasks", [])
    safe_changes = data.get("safe_file_changes", [])
    if safe_changes:
        print("    Cambios seguros disponibles:")
        for change in safe_changes:
            print(f"      [CREAR] {change['target']}")
    if tasks:
        print("    Avisos del normalizador:")
        for task in tasks:
            _print_task(task, indent="      ")
    elif audit.get("recommendations"):
        print("    Recomendaciones:")
        for recommendation in audit["recommendations"][:8]:
            print(f"      • {recommendation}")
        if len(audit["recommendations"]) > 8:
            print(f"      • y {len(audit['recommendations']) - 8} más; consultá el reporte JSON")

    packages = data.get("packages", [])
    print("\n  📦 Paquetes detectados")
    if packages:
        for package in packages:
            stack = ", ".join(package.get("stack", []))
            description = stack or "Stack no detectado en este paquete"
            print(f"    • {package.get('name')}  [{package['path']}] ({package.get('role')})")
            print(f"      Stack: {description}")
            details = [
                f"React: {package.get('react') or 'no detectado'}",
                f"TypeScript: {package.get('typescript') or 'no detectado'}",
                f"Tailwind CSS: {package.get('tailwind') or 'no detectado'}",
            ]
            print(f"      {' · '.join(details)}")
            if package.get("error"):
                print(f"      ⚠ {package['error']}")
    else:
        print("    No se encontraron archivos package.json.")

    print("\n  🗂️  Estructura")
    print(f"    Carpetas de código: {', '.join(data.get('directories', [])) or 'No detectadas'}")
    print(f"    Estilos globales:   {', '.join(data.get('global_styles', [])) or 'No encontrados'}")
    flags = ["Git" if data.get("git_repository") else None,
             "shadcn/ui" if data.get("has_shadcn_config") else None]
    print(f"    Configuración:      {' · '.join(flag for flag in flags if flag) or 'Sin indicadores adicionales'}")
    print(f"\n  ✓ Escaneo de solo lectura · {len(packages)} paquete(s) · {len(data.get('global_styles', []))} hoja(s) de estilo\n")


def write_report(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
