from pathlib import Path
import subprocess


DEFAULT_TEMPLATE_REPO = "https://github.com/branller/web-development-template.git"


class TemplateSyncError(RuntimeError):
    pass


def _git(args: list[str], cwd: Path | None = None) -> str:
    try:
        result = subprocess.run(
            ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
    except FileNotFoundError as exc:
        raise TemplateSyncError("No se encontró Git. Instalalo para actualizar el template.") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise TemplateSyncError(f"Falló git {' '.join(args)}: {detail}") from exc
    return result.stdout.strip()


def sync_template(destination: Path, repo_url: str = DEFAULT_TEMPLATE_REPO) -> str:
    """Clone the configured template once and fast-forward it on every scan."""
    destination = destination.expanduser().resolve()
    if destination.exists():
        if not (destination / ".git").exists():
            if any(destination.iterdir()):
                raise TemplateSyncError(
                    f"La carpeta de template no es un clon Git y no está vacía: {destination}. "
                    "Usá la carpeta de caché predeterminada o indicá --no-pull para un template local."
                )
            destination.rmdir()
        else:
            current_url = _git(["remote", "get-url", "origin"], cwd=destination).removesuffix(".git").rstrip("/").lower()
            expected_url = repo_url.removesuffix(".git").rstrip("/").lower()
            if current_url != expected_url:
                raise TemplateSyncError(
                    f"El remoto de {destination} es {current_url}, pero se esperaba {expected_url}."
                )
            _git(["pull", "--ff-only"], cwd=destination)
            return _git(["rev-parse", "--short", "HEAD"], cwd=destination)

    destination.parent.mkdir(parents=True, exist_ok=True)
    _git(["clone", repo_url, str(destination)])
    return _git(["rev-parse", "--short", "HEAD"], cwd=destination)
