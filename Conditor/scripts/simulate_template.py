#!/usr/bin/env python3
"""Simple offline template preview tool for Conditor.

Usage: python scripts/simulate_template.py <template_name>

It will try `data/templates/<name>.json` first, then fall back to the sqlite DB used by the bot.
"""
import sys
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = ROOT / "data" / "templates"
PREVIEWS_DIR = ROOT / "data" / "previews"
DB_PATH = ROOT / "src" / "conditor" / "data" / "storage.db"


def load_from_file(name: str):
    p = TEMPLATES_DIR / f"{name}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def load_from_db(name: str):
    if not DB_PATH.exists():
        return None
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT content FROM templates WHERE name = ?", (name,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return json.loads(row[0])


def make_preview(template: dict) -> dict:
    roles = [r.get("name") or r.get("key") for r in template.get("roles", [])]
    categories = [c.get("name") for c in template.get("categories", [])]
    channels = [ch.get("name") for ch in template.get("channels", [])]
    return {
        "meta": template.get("meta", {}),
        "counts": {"roles": len(roles), "categories": len(categories), "channels": len(channels)},
        "roles": roles,
        "categories": categories,
        "channels": channels,
        "raw": template,
    }


def main(argv):
    if len(argv) < 2:
        print("Usage: simulate_template.py <template_name>")
        return 2
    name = argv[1]
    t = load_from_file(name)
    source = "file"
    if t is None:
        t = load_from_db(name)
        source = "db"
    if t is None:
        print(f"Template '{name}' not found in data/templates or DB.")
        return 3

    preview = make_preview(t)
    PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    out = PREVIEWS_DIR / f"{name}_preview.json"
    out.write_text(json.dumps(preview, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Loaded template '{name}' from {source}; preview written to: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
