"""Face detection + simple tracking for attendance *counting*.

IMPORTANT LIMITATION: this module detects and tracks *anonymous faces*. It does
NOT identify who a person is. The result is a headcount of faces that stayed
visible for a sustained number of frames, which the teacher can compare with
the roster while marking attendance manually.
"""
from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")


def detect_faces(frame_bgr: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Return face boxes (x, y, w, h) using OpenCV's bundled Haar cascade."""
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    faces = _CASCADE.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(24, 24))
    return [tuple(map(int, f)) for f in faces]


def draw_boxes(frame_bgr: np.ndarray, boxes, labels=None) -> np.ndarray:
    out = frame_bgr.copy()
    for i, (x, y, w, h) in enumerate(boxes):
        cv2.rectangle(out, (x, y), (x + w, y + h), (246, 108, 124), 2)
        text = labels[i] if labels else f"face {i + 1}"
        cv2.putText(out, text, (x, max(12, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (246, 108, 124), 1)
    return out


@dataclass
class Track:
    tid: int
    centroid: tuple[float, float]
    hits: int = 1
    missed: int = 0


@dataclass
class CentroidTracker:
    """Very small nearest-centroid tracker (no identity, just continuity)."""
    max_distance: float = 80.0
    max_missed: int = 5
    tracks: dict[int, Track] = field(default_factory=dict)
    _next: int = 1

    def update(self, boxes) -> dict[int, Track]:
        cents = [(x + w / 2, y + h / 2) for x, y, w, h in boxes]
        unmatched = set(range(len(cents)))
        for t in list(self.tracks.values()):
            best, best_d = None, self.max_distance
            for i in unmatched:
                d = np.hypot(cents[i][0] - t.centroid[0], cents[i][1] - t.centroid[1])
                if d < best_d:
                    best, best_d = i, d
            if best is None:
                t.missed += 1
                if t.missed > self.max_missed:
                    # keep finished tracks for counting, mark as inactive
                    t.missed = 10**6
            else:
                t.centroid, t.hits, t.missed = cents[best], t.hits + 1, 0
                unmatched.discard(best)
        for i in unmatched:
            self.tracks[self._next] = Track(self._next, cents[i])
            self._next += 1
        return self.tracks


@dataclass
class VideoResult:
    frames_analyzed: int
    sustained_faces: int
    max_faces_in_frame: int
    preview_rgb: np.ndarray | None
    fps: float


def save_upload(uploaded, folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / Path(uploaded.name).name
    path.write_bytes(uploaded.getbuffer())
    return path


def analyze_image(data: bytes):
    """Detect faces in a single image. Returns (face_count, annotated_rgb)."""
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not read this image. Try a JPG or PNG file.")
    boxes = detect_faces(img)
    return len(boxes), cv2.cvtColor(draw_boxes(img, boxes), cv2.COLOR_BGR2RGB)


def analyze_video(path: Path, sample_every_s: float = 0.5, min_seconds: float = 3.0,
                  max_frames: int = 600, progress=None) -> VideoResult:
    """Track faces across sampled frames; a face counts as 'sustained' when it
    is seen for at least `min_seconds` of sampled time."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError("Could not open this video. Try an MP4 (H.264) file.")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    step = max(1, int(fps * sample_every_s))
    need_hits = max(2, int(min_seconds / sample_every_s))
    tracker, analyzed, max_faces, preview, idx = CentroidTracker(), 0, 0, None, 0
    while analyzed < max_frames:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step == 0:
            frame = _resize(frame)
            boxes = detect_faces(frame)
            tracker.update(boxes)
            analyzed += 1
            if len(boxes) >= max_faces:
                max_faces, preview = len(boxes), cv2.cvtColor(draw_boxes(frame, boxes), cv2.COLOR_BGR2RGB)
            if progress:
                progress(min(1.0, idx / total))
        idx += 1
    cap.release()
    sustained = sum(1 for t in tracker.tracks.values() if t.hits >= need_hits)
    return VideoResult(analyzed, sustained, max_faces, preview, fps)


def _resize(frame, width: int = 640):
    h, w = frame.shape[:2]
    if w <= width:
        return frame
    return cv2.resize(frame, (width, int(h * width / w)))
