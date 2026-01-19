import sqlite3
from pathlib import Path
from typing import Optional, List

DB_PATH = Path(__file__).parent.parent / "data" / "storage.db"


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS templates (
            name TEXT PRIMARY KEY,
            content TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def save_template(name: str, content: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("REPLACE INTO templates (name, content) VALUES (?,?)", (name, content))
    conn.commit()
    conn.close()


def load_template(name: str) -> Optional[str]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT content FROM templates WHERE name = ?", (name,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def list_templates() -> List[str]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT name FROM templates ORDER BY name")
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]


def _approvals_path() -> Path:
    p = Path(__file__).parent.parent / "data" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p / "approvals.json"


def append_approval(entry: dict) -> None:
    path = _approvals_path()
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding='utf-8')) or []
        else:
            data = []
    except Exception:
        data = []
    data.append(entry)
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        pass


def load_approvals() -> List[dict]:
    path = _approvals_path()
    try:
        if path.exists():
            return json.loads(path.read_text(encoding='utf-8')) or []
    except Exception:
        return []
    return []
