"""Multimodal Attendance & Engagement Agent — Streamlit entry point.

Run with:  streamlit run app.py
Everything runs locally; no media leaves this computer.
"""
from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from mae import attendance as att_cv
from mae import database as db
from mae import demo_data
from mae import engagement as eng_cv
from mae import recommendations as rec

UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"
PURPLE, BLUE = "#7C6CF6", "#4F8CFF"

st.set_page_config(page_title="Attendance & Engagement Agent", page_icon="🎓", layout="wide")
db.init_db()

# ---------- styling ---------------------------------------------------------
st.markdown(f"""
<style>
.stApp {{ background: radial-gradient(1200px 600px at 10% -10%, #1b2152 0%, #0B1229 55%); }}
section[data-testid="stSidebar"] {{ background: #0E1633; border-right: 1px solid #1f2a55; }}
div[data-testid="stMetric"] {{ background: #131C3B; border: 1px solid #24306a; border-radius: 14px;
  padding: 16px 18px; box-shadow: 0 8px 24px -12px rgba(124,108,246,.45); }}
div[data-testid="stMetricValue"] {{ color: #fff; }}
.card {{ background:#131C3B; border:1px solid #24306a; border-radius:14px; padding:16px 18px; margin-bottom:10px; }}
.badge {{ display:inline-block; padding:2px 10px; border-radius:999px; font-size:12px; font-weight:600; }}
.b-high {{ background:#3b1d4f; color:#e2b4ff; }} .b-medium {{ background:#1d2f5f; color:#a9c6ff; }}
.b-info {{ background:#1d3b3a; color:#9fe8d8; }}
.note {{ color:#9aa3c7; font-size:13px; }}
h1, h2, h3 {{ letter-spacing:-.01em; }}
</style>""", unsafe_allow_html=True)


def plot_theme(fig):
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font_color="#E6E9F5", margin=dict(l=10, r=10, t=40, b=10),
                      colorway=[PURPLE, BLUE, "#38D9C0", "#F6C26C"])
    fig.update_xaxes(gridcolor="#1f2a55"); fig.update_yaxes(gridcolor="#1f2a55")
    return fig


def empty(msg: str):
    st.info(f"📭 {msg}")


# ---------- sidebar ---------------------------------------------------------
with st.sidebar:
    st.markdown("## 🎓 Engagement Agent")
    st.caption("Offline classroom intelligence")
    NAV = {"🏠 Dashboard": "Dashboard", "✅ Attendance": "Attendance", "📈 Engagement": "Engagement",
           "📊 Analytics": "Analytics", "👩‍🎓 Students": "Students", "⚙️ Settings": "Settings"}
    page = NAV[st.radio("Navigate", list(NAV), label_visibility="collapsed")]
    st.divider()
    include_demo = st.toggle("Show demo data", value=True,
                             help="Demo records are simulated and stored separately from real records.")
    if include_demo and not db.has_demo_data():
        if st.button("Load demo data", width="stretch"):
            with st.spinner("Creating demo classroom…"):
                demo_data.load_demo()
            st.rerun()
    st.caption("🔒 All processing is local. No media is uploaded to external services.")

STU = db.students(include_demo)
SES = db.sessions(include_demo)
ATT = db.attendance(include_demo)
ENG = db.engagement(include_demo)


def session_picker(label="Session", key=None):
    if SES.empty:
        return None
    opts = {f"{r.date} · {r.title}{' (active)' if r.status == 'active' else ''}": int(r.id)
            for r in SES.iloc[::-1].itertuples()}
    return opts[st.selectbox(label, list(opts), key=key)]


# ---------- Dashboard -------------------------------------------------------
def page_dashboard():
    st.title("Dashboard")
    if SES.empty:
        st.markdown("""<div class="card"><h3 style="margin-top:0">👋 Welcome! Get started in 3 steps</h3>
        <ol><li><b>Students</b> page → add your class list (or click <b>Load demo data</b> in the sidebar to just explore).</li>
        <li><b>Attendance</b> page → create a session, tick who is present, click <b>Save attendance</b>.</li>
        <li>Come back here to see totals, charts and teaching suggestions.</li></ol></div>""",
                    unsafe_allow_html=True)
        return
    active = SES[SES.status == "active"]
    current = active.iloc[-1] if not active.empty else SES.iloc[-1]
    a = ATT[ATT.session_id == current.id]
    e = ENG[ENG.session_id == current.id]
    present = int((a.status == "present").sum())
    total = len(STU)
    c = st.columns(5)
    c[0].metric("Total students", total)
    c[1].metric("Present", present)
    c[2].metric("Absent", max(0, total - present))
    c[3].metric("Attendance", f"{(100 * present / total) if total else 0:.0f}%")
    c[4].metric("Engagement (approx.)", f"{e.score.mean():.0f}/100" if not e.empty else "—")
    st.markdown(f"**Current session:** {current.title} · {current.date} · "
                f"status `{current.status}`" + (" · 🧪 demo" if current.is_demo else ""))

    l, r = st.columns([3, 2])
    with l:
        if e.empty:
            empty("No engagement data for this session yet.")
        else:
            fig = px.area(e, x="t_minute", y="score", title="Engagement indicator over time")
            fig.update_traces(line_color=PURPLE, fillcolor="rgba(124,108,246,.25)")
            st.plotly_chart(plot_theme(fig), width="stretch")
            if (e.source == "simulated-demo").any():
                st.caption("⚠️ Simulated demo data — not a real observation.")
    with r:
        st.subheader("Teaching assistant")
        for s in rec.suggest(rec.session_metrics(e, a))[:3]:
            render_suggestion(s)


def render_suggestion(s: rec.Suggestion):
    st.markdown(f"""<div class="card"><span class="badge b-{s.level}">{s.level.upper()}</span>
    <h4 style="margin:6px 0 4px">{s.title}</h4><div>{s.detail}</div>
    <div class="note">Why: {s.reason}</div></div>""", unsafe_allow_html=True)


# ---------- Attendance ------------------------------------------------------
def page_attendance():
    st.title("Attendance")
    with st.expander("➕ Start a new session", expanded=SES.empty):
        with st.form("new_session"):
            title = st.text_input("Session title", placeholder="e.g. Algebra – Linear equations")
            date = st.date_input("Date", dt.date.today())
            if st.form_submit_button("Create session"):
                if not title.strip():
                    st.error("Please enter a title.")
                else:
                    db.add_session(title.strip(), date.isoformat(), "active")
                    st.success("Session created."); st.rerun()
    sid = session_picker()
    if sid is None:
        empty("Create a session to begin."); return
    sess = SES[SES.id == sid].iloc[0]
    roster = STU[STU.is_demo == sess.is_demo]
    if roster.empty:
        empty("No students for this session yet. Real sessions use the students you added on the "
              "Students page; demo sessions use demo students."); return

    tab_manual, tab_cv = st.tabs(["✍️ Manual attendance", "📷 Face-count assist (OpenCV)"])
    with tab_manual:
        existing = ATT[ATT.session_id == sid].set_index("student_id")
        df = pd.DataFrame({
            "student_id": roster.id.values, "roll": roster.roll.values, "name": roster.name.values,
            "present": [existing.status.get(i, "absent") == "present" for i in roster.id],
            "participation": [int(existing.participation.get(i, 0)) for i in roster.id],
        })
        edited = st.data_editor(df, hide_index=True, width="stretch",
                                disabled=["student_id", "roll", "name"],
                                column_config={"student_id": None,
                                               "participation": st.column_config.NumberColumn(
                                                   "Contributions", min_value=0, step=1)})
        c1, c2, c3 = st.columns(3)
        if c1.button("💾 Save attendance", type="primary"):
            for r in edited.itertuples():
                db.upsert_attendance(sid, int(r.student_id), "present" if r.present else "absent",
                                     int(r.participation), "manual", int(sess.is_demo))
            st.success(f"Saved — {int(edited.present.sum())} present."); st.rerun()
        if sess.status == "active" and c2.button("✅ End session"):
            db.set_session_status(sid, "completed"); st.rerun()
        if sess.status != "active" and c2.button("▶️ Reopen session"):
            db.set_session_status(sid, "active"); st.rerun()

    with tab_cv:
        st.markdown("""<div class="note">This tool <b>counts anonymous faces</b> using OpenCV's Haar cascade.
        It does <b>not</b> identify students by name. A face counts only after it is tracked for a sustained
        period. Use the headcount to cross-check your manual list.</div>""", unsafe_allow_html=True)
        min_sec = st.slider("Sustained detection required (seconds)", 1.0, 10.0, 3.0, 0.5)
        up = st.file_uploader("Classroom image or video", type=["jpg", "jpeg", "png", "mp4", "avi", "mov"])
        if up is not None:
            try:
                if up.type.startswith("image"):
                    with st.spinner("Detecting faces…"):
                        n, img = att_cv.analyze_image(up.getvalue())
                    st.image(img, caption=f"{n} face(s) detected in this single image")
                    st.warning("A single image cannot show sustained presence — upload a video for that.")
                    sustained, mx, frames = n, n, 1
                else:
                    path = att_cv.save_upload(up, UPLOAD_DIR)
                    bar = st.progress(0.0, "Analyzing video…")
                    res = att_cv.analyze_video(path, min_seconds=min_sec, progress=bar.progress)
                    bar.empty()
                    if res.preview_rgb is not None:
                        st.image(res.preview_rgb, caption="Frame with most detections")
                    sustained, mx, frames = res.sustained_faces, res.max_faces_in_frame, res.frames_analyzed
                c = st.columns(3)
                c[0].metric("Sustained faces", sustained)
                c[1].metric("Max in one frame", mx)
                c[2].metric("Roster size", len(roster))
                db.execute("""INSERT INTO detections (session_id, media_name, faces_sustained,
                              faces_max_frame, frames_analyzed) VALUES (?,?,?,?,?)""",
                           (sid, up.name, sustained, mx, frames))
                marked = int((ATT[ATT.session_id == sid].status == "present").sum())
                if marked and marked != sustained:
                    st.info(f"Manual list has {marked} present vs {sustained} sustained faces — worth double-checking.")
            except Exception as ex:  # noqa: BLE001 — show friendly error
                st.error(f"Analysis failed: {ex}")


# ---------- Engagement ------------------------------------------------------
def page_engagement():
    st.title("Engagement")
    st.warning("These are **approximate engagement indicators** derived from simple visual and audio "
               "signals. They are not definitive measurements of attention or learning.")
    sid = session_picker(key="eng_s")
    if sid is None:
        empty("Create a session first."); return
    e = ENG[ENG.session_id == sid]
    tab_view, tab_analyze = st.tabs(["📈 Session indicators", "🎥 Analyze a recording"])
    with tab_view:
        if e.empty:
            empty("No engagement data for this session. Analyze a recording in the next tab.")
        else:
            src = e.source.iloc[0]
            st.caption("Source: " + ("🧪 simulated demo data" if src == "simulated-demo" else "🎥 local video analysis"))
            long = e.melt(id_vars="t_minute", value_vars=["facing", "movement", "inactivity", "audio"],
                          var_name="indicator", value_name="value").dropna()
            st.plotly_chart(plot_theme(px.line(e, x="t_minute", y="score", markers=True,
                                               title="Engagement score (0–100)")), width="stretch")
            st.plotly_chart(plot_theme(px.line(long, x="t_minute", y="value", color="indicator",
                                               title="Underlying indicators (0–1)")), width="stretch")
            st.subheader("Teaching assistant")
            for s in rec.suggest(rec.session_metrics(e, ATT[ATT.session_id == sid])):
                render_suggestion(s)
    with tab_analyze:
        st.markdown("""<div class="note"><b>How it works:</b> facing = frontal vs profile face detections
        (a crude head-position proxy, not true head-pose estimation); movement = frame differences;
        inactivity = share of near-still frames; audio = loudness from an optional WAV file
        (OpenCV can't read video audio tracks, so audio is skipped unless you upload one).</div>""",
                    unsafe_allow_html=True)
        vid = st.file_uploader("Classroom video", type=["mp4", "avi", "mov"], key="eng_vid")
        wav = st.file_uploader("Optional audio (WAV)", type=["wav"], key="eng_wav")
        window = st.select_slider("Window size (seconds)", [10, 15, 30, 60, 120], value=30)
        if vid and st.button("Analyze", type="primary"):
            try:
                vpath = att_cv.save_upload(vid, UPLOAD_DIR)
                apath = att_cv.save_upload(wav, UPLOAD_DIR) if wav else None
                bar = st.progress(0.0, "Analyzing…")
                df = eng_cv.analyze_video(vpath, window_s=window, audio_path=apath, progress=bar.progress)
                bar.empty()
                is_demo = int(SES[SES.id == sid].is_demo.iloc[0])
                db.execute("DELETE FROM engagement WHERE session_id = ? AND source = 'video-analysis'", (sid,))
                db.executemany("""INSERT INTO engagement (session_id, t_minute, score, facing, movement,
                                  inactivity, audio, source, is_demo) VALUES (?,?,?,?,?,?,?,?,?)""",
                               [(sid, r.t_minute, r.score, r.facing, r.movement, r.inactivity,
                                 None if pd.isna(r.audio) else r.audio, "video-analysis", is_demo)
                                for r in df.itertuples()])
                st.success(f"Stored {len(df)} windows of indicators."); st.dataframe(df, hide_index=True)
                if not wav:
                    st.caption("Audio indicator unavailable — no WAV uploaded; score uses visual signals only.")
            except Exception as ex:  # noqa: BLE001
                st.error(f"Analysis failed: {ex}")


# ---------- Analytics -------------------------------------------------------
def page_analytics():
    st.title("Analytics")
    if ATT.empty and ENG.empty:
        empty("No records yet. Load demo data or record a session."); return
    if not ATT.empty:
        per = ATT.groupby(["date", "title"]).agg(present=("status", lambda s: (s == "present").sum()),
                                                 total=("status", "size"),
                                                 participation=("participation", "sum")).reset_index()
        per["attendance_%"] = (100 * per.present / per.total).round(1)
        c1, c2 = st.columns(2)
        c1.plotly_chart(plot_theme(px.bar(per, x="date", y="attendance_%", hover_data=["title"],
                                          title="Attendance % per session")), width="stretch")
        c2.plotly_chart(plot_theme(px.bar(per, x="date", y="participation", hover_data=["title"],
                                          title="Total contributions per session",
                                          color_discrete_sequence=[BLUE])), width="stretch")
    if not ENG.empty:
        trend = ENG.groupby(["date", "title"]).score.mean().reset_index()
        st.plotly_chart(plot_theme(px.line(trend, x="date", y="score", markers=True, hover_data=["title"],
                                           title="Average engagement indicator per session")),
                        width="stretch")
    if not ATT.empty:
        st.subheader("Attendance records")
        st.dataframe(ATT[["date", "title", "roll", "name", "status", "participation", "method"]],
                     hide_index=True, width="stretch")
        st.download_button("⬇️ Download attendance CSV", ATT.to_csv(index=False), "attendance.csv", "text/csv")


# ---------- Students --------------------------------------------------------
def page_students():
    st.title("Students")
    st.caption("Add your class list here. Each student needs a unique Roll / ID and a name.")
    with st.expander("➕ Add a student", expanded=STU[STU.is_demo == 0].empty):
        with st.form("add_student", clear_on_submit=True):
            c1, c2 = st.columns([1, 2])
            roll = c1.text_input("Roll / ID", placeholder="e.g. 1 or 21CS045", max_chars=30)
            name = c2.text_input("Full name", placeholder="e.g. Priya Sahu", max_chars=80)
            submitted = st.form_submit_button("Add student", type="primary")
        if submitted:
            ok, msg = db.validate_student(roll, name)
            if ok:
                db.add_student(roll, name)
                st.toast(f"✅ Added {name.strip()} (Roll {roll.strip()})")
                st.rerun()
            else:
                st.error(msg)
    with st.expander("📄 Add many students from a CSV file"):
        st.caption("The file needs two columns named **roll** and **name**. "
                   "See `sample_data/students.csv` for an example.")
        up = st.file_uploader("Choose CSV", type=["csv"], key="stu_csv")
        if up is not None and st.button("Import students"):
            try:
                df = pd.read_csv(up, dtype=str).rename(columns=str.lower)
                if not {"roll", "name"} <= set(df.columns):
                    st.error("The CSV must have columns 'roll' and 'name'.")
                else:
                    added, skipped = 0, []
                    for r in df.fillna("").itertuples():
                        ok, msg = db.validate_student(r.roll, r.name)
                        if ok:
                            db.add_student(r.roll, r.name); added += 1
                        else:
                            skipped.append(f"Row '{r.roll}, {r.name}': {msg}")
                    st.success(f"Imported {added} student(s).")
                    for m in skipped[:20]:
                        st.warning(m)
            except Exception as ex:  # noqa: BLE001
                st.error(f"Could not read the file: {ex}")
    if STU.empty:
        empty("No students yet. Add one above, or load demo data from the sidebar."); return
    summary = ATT.groupby("student_id").agg(sessions=("status", "size"),
                                            present=("status", lambda s: (s == "present").sum()),
                                            contributions=("participation", "sum")).reset_index()
    table = STU.merge(summary, left_on="id", right_on="student_id", how="left")
    for col in ("sessions", "present", "contributions"):
        table[col] = pd.to_numeric(table[col], errors="coerce").fillna(0).astype(int)
    # Safe percentage: students with no sessions yet show 0 instead of crashing.
    table["attendance_%"] = [round(100 * p / s, 1) if s else 0.0
                             for p, s in zip(table.present, table.sessions)]
    table["type"] = table.is_demo.map({1: "🧪 demo", 0: "real"})
    show = table[["roll", "name", "sessions", "present", "attendance_%", "contributions", "type"]]
    st.dataframe(show, hide_index=True, width="stretch",
                 column_config={"attendance_%": st.column_config.ProgressColumn(
                     "Attendance", format="%.0f%%", min_value=0, max_value=100)})
    st.download_button("⬇️ Download summary CSV", show.to_csv(index=False), "student_summary.csv", "text/csv")

    real = STU[STU.is_demo == 0]
    if not real.empty:
        with st.expander("🗑️ Remove a student"):
            opts = {f"{r.roll} · {r.name}": int(r.id) for r in real.itertuples()}
            sel = st.selectbox("Student to remove", list(opts), key="del_stu")
            if st.button("Remove student and their attendance"):
                db.delete_student(opts[sel]); st.toast("Student removed."); st.rerun()

    st.subheader("Individual report")
    pick = st.selectbox("Student", [f"{r.roll} · {r.name}" for r in STU.itertuples()])
    srow = STU.iloc[[f"{r.roll} · {r.name}" for r in STU.itertuples()].index(pick)]
    hist = ATT[ATT.student_id == srow.id][["date", "title", "status", "participation", "method"]]
    if hist.empty:
        empty("No attendance history for this student.")
    else:
        c = st.columns(3)
        c[0].metric("Sessions", len(hist))
        c[1].metric("Attendance", f"{100 * (hist.status == 'present').mean():.0f}%")
        c[2].metric("Contributions", int(hist.participation.sum()))
        st.plotly_chart(plot_theme(px.bar(hist, x="date", y="participation", color="status",
                                          title="Participation by session")), width="stretch")
        st.dataframe(hist, hide_index=True, width="stretch")
        st.download_button("⬇️ Download this report", hist.to_csv(index=False),
                           f"report_{srow.roll}.csv", "text/csv")


# ---------- Settings --------------------------------------------------------
def page_settings():
    st.title("Settings & Privacy")
    st.markdown("""<div class="card"><b>Privacy</b><br>All video, images and audio are processed on this
    computer with OpenCV/NumPy. Nothing is sent to external services. Uploaded files are kept in the local
    <code>uploads/</code> folder until you delete them below.</div>""", unsafe_allow_html=True)
    files = list(UPLOAD_DIR.glob("*")) if UPLOAD_DIR.exists() else []
    st.write(f"Uploaded media files stored locally: **{len(files)}**")
    if st.button("🗑️ Delete uploaded media", disabled=not files):
        shutil.rmtree(UPLOAD_DIR, ignore_errors=True); st.success("Uploaded media deleted."); st.rerun()
    st.divider()
    c1, c2 = st.columns(2)
    if c1.button("🧪 Delete demo records", disabled=not db.has_demo_data()):
        db.delete_demo_data(); st.success("Demo records deleted."); st.rerun()
    confirm = c2.checkbox("I understand this permanently deletes real classroom records")
    if c2.button("⚠️ Delete real records", disabled=not confirm):
        db.delete_real_data(); st.success("Real records deleted."); st.rerun()
    st.divider()
    st.markdown("""**Feature status**
- ✅ Manual attendance, analytics, reports, CSV export, rule-based assistant — fully working offline
- ✅ Face detection & tracking (anonymous headcount) — OpenCV Haar cascade
- ⚠️ Head position — approximated via frontal vs profile detection, not true head-pose estimation
- ⚠️ Audio — only from a separately uploaded WAV file
- ❌ Face recognition by name — intentionally not implemented (requires explicit consent & setup)
- 🧪 Demo data — simulated, flagged and removable""")


{"Dashboard": page_dashboard, "Attendance": page_attendance, "Engagement": page_engagement,
 "Analytics": page_analytics, "Students": page_students, "Settings": page_settings}[page]()
