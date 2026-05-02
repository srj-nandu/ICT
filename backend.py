from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
STORAGE_ROOT = BASE_DIR / "storage"
DATABASE_FILE = STORAGE_ROOT / "resumevault.sqlite3"
TEMPLATES_ROOT = BASE_DIR / "templates"
STATIC_ROOT = BASE_DIR / "static"


def get_db_connection() -> sqlite3.Connection:
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_FILE, timeout=30)
    connection.row_factory = sqlite3.Row
    return connection


def render_frontend_template(template_name: str, context: dict[str, Any]) -> str:
    template = (TEMPLATES_ROOT / template_name).read_text(encoding="utf-8")
    rendered = template
    for key, value in context.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", str(value))
    return rendered
