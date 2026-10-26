"""Approximate engagement indicators from video (and optional WAV audio).

These are rough, aggregate *indicators*, NOT measurements of attention:
  * facing    – share of detected faces seen frontally (frontal vs profile
                Haar cascades). A crude stand-in for head pose.
  * movement  – mean absolute frame difference (classroom activity).
  * inactivity– share of sampled frames with almost no motion.
  * audio     – RMS loudness of an optional WAV file (OpenCV cannot read
                audio tracks from videos, so audio must be uploaded separately).
"""
from __future__ import annotations

import wave
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

_FRONT = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
_PROFILE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")

LOW_MOTION = 0.01  # normalised diff below this counts as "inactive"


def compute_score(facing: float, movement: float, inactivity: float, audio: float | None) -> float:
    """Combine indicators into a 0–100 approximate engagement score."""
    move_term = 1 - abs(movement - 0.35) / 0.65   # moderate movement is best
    parts = [(0.45, facing), (0.2, max(0.0, move_term)), (0.2, 1 - inactivity)]
    if audio is not None:
        parts.append((0.15, audio))
    total_w = sum(w for w, _ in parts)
    return round(100 * sum(w * v for w, v in parts) / total_w, 1)


def audio_levels(path: Path, window_s: float) -> list[float]:
    """Normalised RMS per window for a PCM WAV file."""
    with wave.open(str(path), "rb") as w:
        sr, ch, sw = w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(w.getnframes())
    dtype = {1: np.int8, 2: np.int16, 4: np.int32}.get(sw)
    if dtype is None:
        raise ValueError("Unsupported WAV sample width.")
    x = np.frombuffer(raw, dtype).astype(np.float32)
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    n = max(1, int(sr * window_s))
    rms = [float(np.sqrt(np.mean(x[i:i + n] ** 2))) for i in range(0, len(x), n) if len(x[i:i + n])]
    peak = max(rms) or 1.0
    return [r / peak for r in rms]


def analyze_video(path: Path, window_s: float = 30.0, sample_every_s: float = 1.0,
                  audio_path: Path | None = None, progress=None) -> pd.DataFrame:
    """Return one row per time window with indicators and a score."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError("Could not open this video.")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    step = max(1, int(fps * sample_every_s))
    samples, prev, idx = [], None, 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step == 0:
            small = cv2.resize(frame, (320, int(frame.shape[0] * 320 / frame.shape[1])))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            front = len(_FRONT.detectMultiScale(gray, 1.1, 5, minSize=(16, 16)))
            prof = len(_PROFILE.detectMultiScale(gray, 1.1, 5, minSize=(16, 16)))
            motion = float(np.mean(cv2.absdiff(gray, prev)) / 255) if prev is not None else 0.0
            prev = gray
            samples.append({"t": idx / fps, "front": front, "profile": prof, "motion": motion})
            if progress:
                progress(min(1.0, idx / total))
        idx += 1
    cap.release()
    if not samples:
        raise ValueError("No frames could be read from this video.")

    df = pd.DataFrame(samples)
    df["window"] = (df["t"] // window_s).astype(int)
    audio = None
    if audio_path is not None:
        audio = audio_levels(audio_path, window_s)

    rows = []
    max_motion = max(df["motion"].max(), 1e-6)
    for w, g in df.groupby("window"):
        faces = g["front"].sum() + g["profile"].sum()
        facing = float(g["front"].sum() / faces) if faces else 0.0
        movement = float(g["motion"].mean() / max_motion)
        inactivity = float((g["motion"] < LOW_MOTION).mean())
        a = audio[w] if audio is not None and w < len(audio) else None
        rows.append({"t_minute": round(w * window_s / 60, 2), "facing": facing, "movement": movement,
                     "inactivity": inactivity, "audio": a,
                     "score": compute_score(facing, movement, inactivity, a)})
    return pd.DataFrame(rows)
