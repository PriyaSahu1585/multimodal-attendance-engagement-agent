"""Offline, rule-based AI teaching assistant.

Each rule inspects session metrics and returns a practical suggestion. No
network or language model is needed.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class Suggestion:
    level: str      # 'high' | 'medium' | 'info'
    title: str
    detail: str
    reason: str


def session_metrics(eng: pd.DataFrame, att: pd.DataFrame) -> dict:
    m = {"avg_score": None, "trend": 0.0, "inactivity": None, "audio": None,
         "attendance_pct": None, "avg_participation": None, "low_participants": 0}
    if not eng.empty:
        m["avg_score"] = float(eng["score"].mean())
        half = len(eng) // 2 or 1
        m["trend"] = float(eng["score"].iloc[half:].mean() - eng["score"].iloc[:half].mean())
        m["inactivity"] = float(eng["inactivity"].iloc[-max(1, len(eng) // 3):].mean())
        if eng["audio"].notna().any():
            m["audio"] = float(eng["audio"].dropna().mean())
    if not att.empty:
        m["attendance_pct"] = 100 * float((att["status"] == "present").mean())
        present = att[att["status"] == "present"]
        if not present.empty:
            m["avg_participation"] = float(present["participation"].mean())
            m["low_participants"] = int((present["participation"] == 0).sum())
    return m


def suggest(m: dict) -> list[Suggestion]:
    out: list[Suggestion] = []
    if m["inactivity"] is not None and m["inactivity"] > 0.45:
        out.append(Suggestion("high", "Take a 2–3 minute movement break",
                              "Ask students to stand, stretch, or discuss with a neighbour before resuming.",
                              f"Recent inactivity indicator is {m['inactivity']:.0%}."))
    if m["trend"] < -8:
        out.append(Suggestion("high", "Switch format: add an interactive activity",
                              "Try a quick poll, think-pair-share, or a 3-question mini quiz.",
                              f"Engagement indicator fell by {abs(m['trend']):.0f} points over the session."))
    if m["avg_score"] is not None and m["avg_score"] < 55:
        out.append(Suggestion("medium", "Shorten lecture segments",
                              "Break content into 8–10 minute chunks with a check-for-understanding between them.",
                              f"Average engagement indicator is {m['avg_score']:.0f}/100."))
    if m["avg_participation"] is not None and m["avg_participation"] < 1.5:
        out.append(Suggestion("medium", "Invite more voices",
                              "Use cold-calling with wait time, or small-group roles (reporter, scribe).",
                              f"Average contributions per present student: {m['avg_participation']:.1f}."))
    if m["low_participants"] >= 3:
        out.append(Suggestion("medium", "Check in with quiet students",
                              "Offer low-stakes ways to contribute such as exit tickets or written questions.",
                              f"{m['low_participants']} present students made no recorded contribution."))
    if m["attendance_pct"] is not None and m["attendance_pct"] < 80:
        out.append(Suggestion("medium", "Follow up on absences",
                              "Share session notes and contact students with repeated absences.",
                              f"Attendance was {m['attendance_pct']:.0f}%."))
    if m["audio"] is not None and m["audio"] < 0.2:
        out.append(Suggestion("info", "Encourage discussion",
                              "Audio activity was low; pose an open question to spark conversation.",
                              f"Average audio indicator {m['audio']:.0%}."))
    if not out:
        out.append(Suggestion("info", "Keep going — things look healthy",
                              "Maintain the current pace and keep regular check-ins.",
                              "No rule thresholds were triggered."))
    return out
