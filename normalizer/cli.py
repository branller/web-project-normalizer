from pathlib import Path
import argparse
import json
import sys

from .config import load_config, ConfigError
from .audit import evaluate_alignment
from .engine import apply_plan, ApplyError
from .paths import validate_target, PathSafetyError
from .planner import build_plan
from .reporter import print_json, print_scan, print_normalization_plan, write_report
from .reconciler import build_recommendations, build_safe_component_plan, build_theme_plan
from .scanner import scan_project
from .template_sync import DEFAULT_TEMPLATE_REPO, TemplateSyncError, sync_template
from .validator import validate_project


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--target", required=True, help="Ruta del proyecto web que se analizará.")
    parser.add_argument(
        "--template",
        default=str(Path(__file__).resolve().parent.parent / ".template-cache" / "web-development-template"),
        help="Ruta local del clon del template.",
    )
    parser.add_argument(
        "--config",
        default=str(Path(__file__).resolve().parent.parent / "normalizer.toml"),
        help="Ruta del archivo normalizer.toml.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="web-project-normalizer",
        description="Normalizador conservador de proyectos web basado en reglas explícitas.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("scan", "plan", "apply", "validate"):
        cmd = sub.add_parser(name)
        _common(cmd)
        if name == "apply":
            cmd.add_argument("--dry-run", action="store_true", help="Muestra acciones sin modificar archivos.")
            cmd.add_argument("--yes", action="store_true", help="No solicita confirmación interactiva.")
            cmd.add_argument(
                "--backup-dir",
                default=str(Path.home() / ".web-project-normalizer" / "backups"),
                help="Directorio externo donde se guardarán los respaldos.",
            )
        if name in {"scan", "plan", "apply", "validate"}:
            cmd.add_argument("--report", help="Ruta opcional para guardar un reporte JSON.")
        if name == "scan":
            cmd.add_argument("--json", action="store_true", help="Imprime el resultado completo en JSON.")
            cmd.add_argument("--no-pull", action="store_true", help="No actualiza el template; usa el clon local indicado.")
            cmd.add_argument("--template-repo", default=DEFAULT_TEMPLATE_REPO, help="URL Git del web development template.")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    try:
        target = validate_target(Path(args.target).expanduser())
        template = Path(args.template).expanduser().resolve()

        if args.command == "scan":
            revision = None
            if not args.no_pull:
                revision = sync_template(template, args.template_repo)
                print(f"Template actualizado desde {args.template_repo} · commit {revision}",
                      file=sys.stderr if args.json else sys.stdout)
            elif not template.is_dir():
                raise PathSafetyError(f"No existe el template local: {template}")
            result = scan_project(target)
            result["alignment"] = evaluate_alignment(target, template)
            safe_changes = build_safe_component_plan(template, target, result["alignment"])
            safe_changes.extend(build_theme_plan(template, target, result["alignment"]))
            automatic_components = {item.source.relative_to(template).as_posix() for item in safe_changes}
            automatic_axes = {"design"} if any(item.mode == "merge_theme" for item in safe_changes) else set()
            result["normalization_tasks"] = build_recommendations(
                result["alignment"], automatic_components, automatic_axes
            )
            result["safe_file_changes"] = [
                {"source": str(item.source), "target": str(item.target), "action": item.action,
                 "reason": item.reason} for item in safe_changes
            ]
            result["template"] = str(template)
            result["template_revision"] = revision
            print_json(result) if args.json else print_scan(result)
            if args.report:
                write_report(Path(args.report), result)
            return 0

        if args.command == "validate":
            checks = validate_project(target)
            for level, message in checks:
                print(f"[{level}] {message}")
            if args.report:
                write_report(Path(args.report), {
                    "target": str(target),
                    "checks": [{"level": level, "message": message} for level, message in checks],
                })
            return 1 if any(level == "ERROR" for level, _ in checks) else 0

        if not template.is_dir():
            raise PathSafetyError(f"No existe el directorio del template: {template}")

        rules = load_config(Path(args.config).expanduser())
        plan = build_plan(template, target, rules)
        alignment = evaluate_alignment(target, template)
        safe_changes = build_safe_component_plan(template, target, alignment)
        safe_changes.extend(build_theme_plan(template, target, alignment))
        planned_targets = {item.target for item in plan}
        plan.extend(item for item in safe_changes if item.target not in planned_targets)
        actual_safe_changes = [item for item in plan if item in safe_changes]
        automatic_components = {item.source.relative_to(template).as_posix() for item in actual_safe_changes
                                if "components" in {part.lower() for part in item.source.parts}}
        automatic_axes = {"design"} if any(item.mode == "merge_theme" for item in actual_safe_changes) else set()
        recommendations = build_recommendations(alignment, automatic_components, automatic_axes)
        print(f"\nPLAN DE NORMALIZACIÓN · {target}")
        print(f"Template: {template}")
        print_normalization_plan(alignment, recommendations, plan)

        if args.report:
            write_report(Path(args.report), {
                "target": str(target),
                "template": str(template),
                "alignment": alignment,
                "recommendations": recommendations,
                "changes": [
                    {
                        "source": str(item.source),
                        "target": str(item.target),
                        "mode": item.mode,
                        "action": item.action,
                        "reason": item.reason,
                    }
                    for item in plan
                ],
            })

        if args.command == "plan":
            return 1 if any(item.action == "error" for item in plan) else 0

        if any(item.action == "error" for item in plan):
            print("\nHay errores en las reglas. No se modificó ningún archivo.", file=sys.stderr)
            return 2

        if args.dry_run:
            apply_plan(plan, target, Path(args.backup_dir).expanduser(), dry_run=True)
            print("\nDry-run: no se modificó ningún archivo.")
            if recommendations:
                print("Las tareas NOTIFICAR/REVISAR requieren decisión antes de modificar el proyecto.")
            return 0

        pending = [item for item in plan if item.action in {"create", "replace", "append"}]
        if not pending:
            print("\nNo hay cambios de archivo seguros para aplicar con la configuración actual.")
            if not rules and not safe_changes:
                print("normalizer.toml no declara reglas y los componentes faltantes no son compatibles todavía.")
            if recommendations:
                print("Las diferencias quedan notificadas; no se aplicaron cambios estructurales automáticamente.")
            return 0

        if not args.yes:
            answer = input("\n¿Aplicar estos cambios? [y/N]: ").strip().lower()
            if answer not in {"y", "yes", "s", "si", "sí"}:
                print("Operación cancelada.")
                return 0

        messages, backup = apply_plan(
            plan, target, Path(args.backup_dir).expanduser(), dry_run=False
        )
        for message in messages:
            print(message)
        print(f"\nRespaldo: {backup}")
        print("Aplicación finalizada. Ejecutá validate y luego los tests/build de tu proyecto.")
        return 0

    except (ConfigError, ApplyError, PathSafetyError, TemplateSyncError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
