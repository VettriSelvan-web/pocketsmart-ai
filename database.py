"""Tiny SQLite data layer (users + saved recommendations)."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Optional

from .config import settings


@contextmanager
def get_conn():
    settings.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                budget REAL NOT NULL,
                inputs_json TEXT NOT NULL,
                result_json TEXT NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_rec_user ON recommendations(user_id, created_at DESC);
            """
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------- users ----------
def create_user(username: str, email: str, password_hash: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (username, email, password_hash, _now()),
        )
        return cur.lastrowid


def get_user_by_username(username: str) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None


def get_user_by_email(email: str) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


# ---------- recommendations ----------
def _rec_from_row(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["inputs"] = json.loads(d.pop("inputs_json"))
    d["result"] = json.loads(d.pop("result_json"))
    return d


def save_recommendation(
    user_id: int, category: str, title: str, budget: float,
    inputs: dict[str, Any], result: dict[str, Any], source: str,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO recommendations
               (user_id, category, title, budget, inputs_json, result_json, source, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, category, title, budget, json.dumps(inputs), json.dumps(result), source, _now()),
        )
        return cur.lastrowid


def get_recommendation(rec_id: int, user_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM recommendations WHERE id = ? AND user_id = ?", (rec_id, user_id)
        ).fetchone()
        return _rec_from_row(row) if row else None


def list_recommendations(user_id: int, category: Optional[str] = None, limit: int = 100) -> list[dict]:
    query = "SELECT * FROM recommendations WHERE user_id = ?"
    params: list[Any] = [user_id]
    if category:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY created_at DESC, id DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        return [_rec_from_row(r) for r in conn.execute(query, params).fetchall()]


def delete_recommendation(rec_id: int, user_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM recommendations WHERE id = ? AND user_id = ?", (rec_id, user_id)
        )
        return cur.rowcount > 0


def count_by_category(user_id: int) -> dict[str, int]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT category, COUNT(*) AS n FROM recommendations WHERE user_id = ? GROUP BY category",
            (user_id,),
        ).fetchall()
        return {r["category"]: r["n"] for r in rows}
