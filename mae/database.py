"""SQLite storage layer.

Every table has an `is_demo` flag so demo data is kept clearly separate from
real classroom records and can be deleted independently.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "classroom.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    roll TEXT NOT NULL,
    name TEXT NOT NULL,
    is_demo INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'completed',   -- 'active' | 'completed'
    is_demo INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    status TEXT NOT NULL,                       -- 'present' | 'absent'
    method TEXT NOT NULL DEFAULT 'manual',      -- 'manual' | 'demo'
    participation INTEGER NOT NULL DEFAULT 0,   -- count of contributions
    is_demo INTEGER NOT NULL DEFAULT 0,
    UNIQUE(session_id, student_id)
);
CREATE TABLE IF NOT EXISTS engagement (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    t_minute REAL NOT NULL,
    score REAL NOT NULL,          -- 0..100 approximate indicator
    facing REAL,                  -- share of faces facing camera (0..1)
    movement REAL,                -- normalised motion (0..1)
    inactivity REAL,              -- share of low-motion time (0..1)
    audio REAL,                   -- normalised audio activity (0..1) or NULL
    source TEXT NOT NULL,         -- 'video-analysis' | 'simulated-demo'
    is_demo INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS detections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    media_name TEXT,
    faces_sustained INTEGER,
    faces_max_frame INTEGER,
    frames_analyzed INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as c:
        c.executescript(SCHEMA)


def query(sql: str, params: tuple = ()) -> pd.DataFrame:
    with connect() as c:
        return pd.read_sql_query(sql, c, params=params)


def execute(sql: str, params: tuple = ()) -> int:
    with connect() as c:
        cur = c.execute(sql, params)
        return cur.lastrowid


def executemany(sql: str, rows: list[tuple]) -> None:
    with connect() as c:
        c.executemany(sql, rows)


# ---------- helpers ---------------------------------------------------------

def _demo_clause(include_demo: bool, alias: str = "") -> str:
    prefix = f"{alias}." if alias else ""
    return "" if include_demo else f" AND {prefix}is_demo = 0"


def students(include_demo: bool = True) -> pd.DataFrame:
    return query("SELECT * FROM students WHERE 1=1" + _demo_clause(include_demo) + " ORDER BY roll")


def sessions(include_demo: bool = True) -> pd.DataFrame:
    return query("SELECT * FROM sessions WHERE 1=1" + _demo_clause(include_demo) + " ORDER BY date, id")


def attendance(include_demo: bool = True) -> pd.DataFrame:
    return query(
        """SELECT a.*, s.name, s.roll, se.title, se.date
           FROM attendance a
           JOIN students s ON s.id = a.student_id
           JOIN sessions se ON se.id = a.session_id
           WHERE 1=1""" + _demo_clause(include_demo, "a") + " ORDER BY se.date, s.roll"
    )


def engagement(include_demo: bool = True) -> pd.DataFrame:
    return query(
        """SELECT e.*, se.title, se.date FROM engagement e
           JOIN sessions se ON se.id = e.session_id
           WHERE 1=1""" + _demo_clause(include_demo, "e") + " ORDER BY se.date, e.t_minute"
    )


def validate_student(roll, name) -> tuple[bool, str]:
    """Return (ok, message). Accepts any non-empty roll (numbers, letters, - / _) and a name."""
    roll = str(roll or "").strip()
    name = str(name or "").strip()
    if not roll:
        return False, "Please enter a Roll / ID."
    if not name:
        return False, "Please enter the student's name."
    if len(roll) > 30 or len(name) > 80:
        return False, "Roll / ID must be ≤ 30 characters and name ≤ 80 characters."
    if not all(ch.isalnum() or ch in "-_/. " for ch in roll):
        return False, "Roll / ID can only contain letters, numbers, spaces and - _ / ."
    if not any(ch.isalpha() for ch in name):
        return False, "Name should contain at least one letter."
    dup = query("SELECT 1 FROM students WHERE is_demo = 0 AND lower(roll) = lower(?)", (roll,))
    if not dup.empty:
        return False, f"A student with Roll / ID '{roll}' already exists."
    return True, ""


def delete_student(student_id: int) -> None:
    with connect() as c:
        c.execute("DELETE FROM attendance WHERE student_id = ?", (student_id,))
        c.execute("DELETE FROM students WHERE id = ? AND is_demo = 0", (student_id,))


def add_student(roll: str, name: str) -> None:
    execute("INSERT INTO students (roll, name, is_demo) VALUES (?, ?, 0)", (str(roll).strip(), " ".join(str(name).split())))


def add_session(title: str, date: str, status: str = "active", is_demo: int = 0) -> int:
    return execute(
        "INSERT INTO sessions (title, date, status, is_demo) VALUES (?, ?, ?, ?)",
        (title, date, status, is_demo),
    )


def set_session_status(session_id: int, status: str) -> None:
    execute("UPDATE sessions SET status = ? WHERE id = ?", (status, session_id))


def upsert_attendance(session_id: int, student_id: int, status: str,
                      participation: int = 0, method: str = "manual", is_demo: int = 0) -> None:
    execute(
        """INSERT INTO attendance (session_id, student_id, status, method, participation, is_demo)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(session_id, student_id)
           DO UPDATE SET status=excluded.status, method=excluded.method,
                         participation=excluded.participation""",
        (session_id, student_id, status, method, participation, is_demo),
    )


def delete_demo_data() -> None:
    with connect() as c:
        c.execute("DELETE FROM engagement WHERE is_demo = 1")
        c.execute("DELETE FROM attendance WHERE is_demo = 1")
        c.execute("DELETE FROM sessions WHERE is_demo = 1")
        c.execute("DELETE FROM students WHERE is_demo = 1")


def delete_real_data() -> None:
    with connect() as c:
        for t in ("detections", "engagement", "attendance"):
            c.execute(f"DELETE FROM {t} WHERE " + ("1=1" if t == "detections" else "is_demo = 0"))
        c.execute("DELETE FROM sessions WHERE is_demo = 0")
        c.execute("DELETE FROM students WHERE is_demo = 0")


def has_demo_data() -> bool:
    return int(query("SELECT COUNT(*) n FROM sessions WHERE is_demo = 1")["n"][0]) > 0
