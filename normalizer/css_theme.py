from pathlib import Path
import re


THEME_MARKER = "/* BEGIN WEB PROJECT NORMALIZER: theme tokens */"
THEME_END_MARKER = "/* END WEB PROJECT NORMALIZER: theme tokens */"


def extract_theme_blocks(css: str) -> str:
    blocks = []
    for selector in ("@theme inline", ":root", ".dark"):
        pattern = re.compile(rf"(?m)^[ \t]*{re.escape(selector)}[ \t]*\{{[^{{}}]*\}}")
        match = pattern.search(css)
        if match:
            blocks.append(match.group(0).strip())
    return "\n\n".join(blocks)


def merge_theme_blocks(original: str, theme: str) -> str:
    if THEME_MARKER in original:
        return original
    payload = f"{THEME_MARKER}\n{theme.rstrip()}\n{THEME_END_MARKER}"
    imports = list(re.finditer(r"(?m)^[ \t]*@import\b[^;]*;[ \t]*(?:\r?\n)?", original))
    position = imports[-1].end() if imports else 0
    before = original[:position]
    after = original[position:]
    separator_before = "" if not before or before.endswith("\n\n") else "\n"
    separator_after = "" if not after or after.startswith("\n") else "\n"
    return f"{before}{separator_before}{payload}{separator_after}{after}"


def source_theme(path: Path) -> str:
    return extract_theme_blocks(path.read_text(encoding="utf-8"))
