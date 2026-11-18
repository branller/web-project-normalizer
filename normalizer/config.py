from pathlib import Path
import tomllib

from .models import FileRule


class ConfigError(ValueError):
    pass


def load_config(path: Path) -> list[FileRule]:
    if not path.exists():
        raise ConfigError(f"No existe el archivo de configuración: {path}")

    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError) as exc:
        raise ConfigError(f"No se pudo leer la configuración: {exc}") from exc

    rules = []
    for index, item in enumerate(data.get("files", []), start=1):
        source = item.get("source")
        target = item.get("target")
        mode = item.get("mode", "create_only")

        if not source or not target:
            raise ConfigError(f"La regla files #{index} requiere source y target.")
        if mode not in {"create_only", "replace", "append"}:
            raise ConfigError(
                f"Modo inválido en files #{index}: {mode}. "
                "Valores permitidos: create_only, replace, append."
            )

        rules.append(FileRule(source=str(source), target=str(target), mode=mode))

    return rules
