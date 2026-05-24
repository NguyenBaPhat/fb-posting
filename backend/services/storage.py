import json
import os
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent.parent / "data"

FILES = {
    "accounts": DATA_DIR / "accounts.json",
    "groups": DATA_DIR / "groups.json",
    "posts": DATA_DIR / "posts.json",
    "schedules": DATA_DIR / "schedules.json",
}


def _ensure_files():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "uploads").mkdir(exist_ok=True)
    for key, path in FILES.items():
        if not path.exists():
            path.write_text("[]", encoding="utf-8")


def read_json(key: str) -> list[Any]:
    _ensure_files()
    with open(FILES[key], "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(key: str, data: list[Any]) -> None:
    _ensure_files()
    with open(FILES[key], "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
