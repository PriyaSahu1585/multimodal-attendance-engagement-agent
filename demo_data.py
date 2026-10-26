"""Demo-mode data generator.

All rows created here are flagged `is_demo = 1` and engagement rows use
source = 'simulated-demo' so they are never confused with real observations.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd

from . import database as db

SAMPLE_CSV = Path(__file__).resolve().parent.parent / "sample_data" / "students.csv"

TOPICS = ["Fractions Intro", "Photosynthesis", "World War I", "Python Loops",
          "Poetry Analysis", "Newton's Laws", "Cell Division", "Data & Graphs"]


def load_demo(seed: int = 42) -> None:
    """Populate demo students, 8 sessions, attendance and engagement curves."""
    if db.has_demo_data():
        return
    rng = np.random.default_rng(seed)
    roster = pd.read_csv(SAMPLE_CSV)
    db.executemany("INSERT INTO students (roll, name, is_demo) VALUES (?, ?, 1)",
                   [(r.roll, r.name) for r in roster.itertuples()])
    stu = db.query("SELECT id FROM students WHERE is_demo = 1")["id"].tolist()
    # Each demo student has a personal "reliability" so reports look realistic.
    reliability = {s: rng.uniform(0.65, 0.98) for s in stu}

    start = dt.date.today() - dt.timedelta(days=7 * 2)
    for i, topic in enumerate(TOPICS):
        date = (start + dt.timedelta(days=i * 2)).isoformat()
        status = "active" if i == len(TOPICS) - 1 else "completed"
        sid = db.add_session(f"[Demo] {topic}", date, status, is_demo=1)
        for s in stu:
            present = rng.random() < reliability[s]
            part = int(rng.poisson(3 * reliability[s])) if present else 0
            db.upsert_attendance(sid, s, "present" if present else "absent", part, "demo", 1)
        # Engagement curve: starts high, dips mid-lesson, sometimes recovers.
        rows = []
        base = rng.uniform(62, 82)
        for m in range(0, 46, 3):
            dip = 18 * np.exp(-((m - rng.uniform(25, 35)) ** 2) / 120)
            score = float(np.clip(base - dip - m * 0.15 + rng.normal(0, 4), 20, 98))
            inactivity = float(np.clip(1 - score / 100 + rng.normal(0, 0.05), 0, 1))
            rows.append((sid, m, score, score / 100, float(rng.uniform(0.2, 0.6)),
                         inactivity, float(rng.uniform(0.1, 0.7)), "simulated-demo", 1))
        db.executemany(
            """INSERT INTO engagement (session_id, t_minute, score, facing, movement,
               inactivity, audio, source, is_demo) VALUES (?,?,?,?,?,?,?,?,?)""", rows)
