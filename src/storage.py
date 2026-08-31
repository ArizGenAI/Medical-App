"""
SQLite persistence for assessments and a small saved profile.

This is separate from LangChain's SQLiteCache (which only stores LLM prompts).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from src.config import PROJECT_ROOT

DB_PATH = PROJECT_ROOT / "cache" / "mediguide_sessions.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they do not exist yet."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS assessments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                patient_name TEXT,
                age TEXT,
                gender TEXT,
                symptoms TEXT,
                duration TEXT,
                severity INTEGER,
                existing_conditions TEXT,
                medications TEXT,
                notes TEXT,
                language TEXT,
                urgency TEXT,
                assessment_json TEXT,
                raw_json TEXT,
                narrative TEXT,
                confidence REAL,
                elapsed REAL,
                followup_json TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                name TEXT,
                age TEXT,
                gender TEXT
            )
            """
        )
        conn.commit()


def save_assessment(record: dict[str, Any]) -> int:
    """Insert one assessment and return its row id."""
    init_db()
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO assessments (
                created_at, patient_name, age, gender, symptoms, duration, severity,
                existing_conditions, medications, notes, language, urgency,
                assessment_json, raw_json, narrative, confidence, elapsed, followup_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.get("created_at") or datetime.now().isoformat(timespec="seconds"),
                record.get("patient_name") or "",
                record.get("age") or "",
                record.get("gender") or "",
                record.get("symptoms") or "",
                record.get("duration") or "",
                int(record.get("severity") or 0),
                record.get("existing_conditions") or "",
                record.get("medications") or "",
                record.get("notes") or "",
                record.get("language") or "",
                record.get("urgency") or "",
                json.dumps(record.get("assessment") or {}, ensure_ascii=False),
                record.get("raw") or "",
                record.get("narrative") or "",
                float(record.get("confidence") or 0),
                float(record.get("elapsed") or 0),
                json.dumps(record.get("followup") or [], ensure_ascii=False),
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def list_assessments(search: str = "", urgency: str = "ALL", limit: int = 200) -> list[dict[str, Any]]:
    """Return stored assessments, newest first, with optional filters."""
    init_db()
    sql = "SELECT * FROM assessments WHERE 1=1"
    params: list[Any] = []
    if urgency and urgency != "ALL":
        sql += " AND urgency = ?"
        params.append(urgency)
    if search.strip():
        sql += " AND (symptoms LIKE ? OR patient_name LIKE ? OR notes LIKE ? OR assessment_json LIKE ?)"
        like = f"%{search.strip()}%"
        params.extend([like, like, like, like])
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_dict(row) for row in rows]


def get_assessment(row_id: int) -> dict[str, Any] | None:
    init_db()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM assessments WHERE id = ?", (row_id,)).fetchone()
    return _row_to_dict(row) if row else None


def delete_all_assessments() -> None:
    init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM assessments")
        conn.commit()


def urgency_counts() -> dict[str, int]:
    init_db()
    counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "EMERGENCY": 0}
    with _connect() as conn:
        rows = conn.execute(
            "SELECT urgency, COUNT(*) AS n FROM assessments GROUP BY urgency"
        ).fetchall()
    for row in rows:
        key = (row["urgency"] or "").upper()
        if key in counts:
            counts[key] = int(row["n"])
    return counts


def load_profile() -> dict[str, str]:
    init_db()
    with _connect() as conn:
        row = conn.execute("SELECT name, age, gender FROM profile WHERE id = 1").fetchone()
    if not row:
        return {"name": "", "age": "", "gender": "Prefer not to say"}
    return {"name": row["name"] or "", "age": row["age"] or "", "gender": row["gender"] or "Prefer not to say"}


def save_profile(name: str, age: str, gender: str) -> None:
    init_db()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO profile (id, name, age, gender) VALUES (1, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET name = excluded.name, age = excluded.age, gender = excluded.gender
            """,
            (name.strip(), age.strip(), gender),
        )
        conn.commit()


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    try:
        item["assessment"] = json.loads(item.get("assessment_json") or "{}")
    except json.JSONDecodeError:
        item["assessment"] = {}
    try:
        item["followup"] = json.loads(item.get("followup_json") or "[]")
    except json.JSONDecodeError:
        item["followup"] = []
    return item
