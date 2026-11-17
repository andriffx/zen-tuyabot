"""Guard: no route or bot module may talk to sqlite3 on the event loop."""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "tuyabot"
GUARDED = [SRC / "web", SRC / "telegram"]


def _imports_sqlite(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name == "sqlite3" for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom) and node.module == "sqlite3":
            return True
    return False


def test_web_and_telegram_modules_do_not_import_sqlite3():
    offenders = [
        str(path.relative_to(SRC.parent.parent))
        for directory in GUARDED
        if directory.exists()
        for path in directory.rglob("*.py")
        if _imports_sqlite(path)
    ]
    assert offenders == [], f"modul berikut mengimpor sqlite3 langsung: {offenders}"
