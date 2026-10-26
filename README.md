# 🎓 Multimodal Attendance & Engagement Agent

An offline-first classroom dashboard built with **Python, Streamlit, OpenCV, Pandas, Plotly and SQLite**.
It tracks attendance, estimates *approximate* engagement indicators, shows analytics and gives
rule-based teaching suggestions — all on your own computer.

> 🌐 **Want it online?** See [DEPLOY.md](DEPLOY.md) for a no-experience-needed step-by-step guide.

## 1. Setup (beginner friendly)

1. Install **Python 3.10+** from <https://python.org>.
2. Open a terminal in this folder and create a virtual environment:
   ```bash
   python -m venv .venv
   # Windows:   .venv\Scripts\activate
   # macOS/Linux: source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the app:
   ```bash
   streamlit run app.py
   ```
   Your browser opens at <http://localhost:8501>.
5. In the sidebar click **Load demo data** to explore every page instantly.

## 2. Pages

| Page | What it does |
|------|--------------|
| Dashboard | Totals, present/absent, attendance %, session status, engagement score, top suggestions |
| Attendance | Create sessions, manual attendance + contributions, OpenCV face-count assist from image/video |
| Engagement | View indicator charts; analyze a recording (+ optional WAV audio) |
| Analytics | Attendance %, participation and engagement trends, records table, CSV export |
| Students | Add students, summary table, individual reports, CSV downloads |
| Settings | Delete uploaded media, delete demo or real records, feature status |

## 3. Project structure

```
app.py                  # Streamlit UI and navigation
mae/database.py         # SQLite schema + queries (data/classroom.db)
mae/attendance.py       # Face detection (Haar cascade) + centroid tracker
mae/engagement.py       # Approximate engagement indicators from video/audio
mae/recommendations.py  # Offline rule-based teaching assistant
mae/demo_data.py        # Demo generator (flagged is_demo = 1)
sample_data/students.csv
.streamlit/config.toml  # Dark navy / purple theme
```

## 4. What is real, approximate, or simulated

- **Real & working:** manual attendance, database, analytics, CSV export, suggestions.
- **Face detection:** counts *anonymous* faces; a face is counted only after it is tracked for a
  configurable number of seconds. **It never identifies a student by name.**
- **Head position:** approximated with frontal vs profile face detectors — *not* true head-pose estimation.
- **Movement / inactivity:** frame-difference based.
- **Audio:** OpenCV cannot read audio tracks, so audio activity is computed only from an optional WAV file.
- **Demo data:** simulated, labelled "simulated-demo", stored with `is_demo = 1`, and deletable in Settings.

Engagement values are **approximate indicators, not measurements of attention.**

## 5. Privacy

No cloud APIs, no internet needed. Media is saved only to `uploads/` (git-ignored) and can be deleted
from Settings. The database `data/classroom.db` is also git-ignored.

## 6. Quick tests

```bash
python -c "from mae import recommendations as r; print(r.suggest({'avg_score':40,'trend':-12,'inactivity':0.6,'audio':None,'attendance_pct':70,'avg_participation':1,'low_participants':4}))"
```
