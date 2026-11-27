import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    serial = None

st.set_page_config(
    page_title="Smart Study Desk",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- Styling ----------
st.markdown("""
<style>
    /* Palette: slate navy base, teal accent, indigo secondary */
    :root {
        --bg: #0B1220;
        --surface: #131C2E;
        --surface-2: #1A2540;
        --border: #263451;
        --text: #E6EDF7;
        --muted: #8FA0BA;
        --accent: #2DD4BF;
        --accent-2: #818CF8;
    }
    .stApp { background: var(--bg); color: var(--text); }
    [data-testid="stSidebar"] { background: var(--surface); border-right: 1px solid var(--border); }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stMetric"] {
        background: var(--surface);
        border: 1px solid var(--border); border-left: 3px solid var(--accent);
        padding: 16px; border-radius: 12px;
    }
    [data-testid="stMetricLabel"] { color: var(--muted); }
    [data-testid="stMetricValue"] { color: var(--text); }
    .hero {
        padding: 22px 26px; border-radius: 16px; margin-bottom: 18px;
        background: linear-gradient(110deg, #0B1220, #16213A 55%, #0F4C5C);
        border: 1px solid var(--border);
        border-bottom: 2px solid var(--accent);
    }
    .hero h1 { margin: 0; color: var(--text); font-size: 2rem; letter-spacing: .04em; }
    .hero p { margin: 7px 0 0; color: var(--muted); }
    .panel {
        background: var(--surface); border: 1px solid var(--border);
        border-radius: 12px; padding: 16px 18px; margin-bottom: 12px;
    }
    .muted { color: var(--muted); font-size: .88rem; }
    .state-normal { color: #34D399; font-weight: 700; }
    .state-close { color: #FBBF24; font-weight: 700; }
    .state-sustained { color: #F87171; font-weight: 700; }
    .state-away { color: #94A3B8; font-weight: 700; }
    div[data-testid="stDataFrame"] { border: 1px solid var(--border); border-radius: 12px; }
</style>
""", unsafe_allow_html=True)

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
LOG_FILE = DATA_DIR / "study_readings.csv"

DEFAULTS = {
    "connected": False,
    "serial_obj": None,
    "session_active": False,
    "session_start": None,
    "session_seconds": 0,
    "last_state": "Waiting",
    "close_started": None,
    "away_started": None,
    "events": [],
    "readings": [],
    "last_distance": None,
    "demo_distance": 48.0,
    "demo_direction": 1,
    "last_tick": time.time(),
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

def add_event(message, level="Info"):
    st.session_state.events.insert(0, {
        "time": datetime.now().strftime("%H:%M:%S"),
        "event": message,
        "type": level
    })
    st.session_state.events = st.session_state.events[:100]

def classify(distance, close_limit, away_limit, sustained_seconds):
    now = time.time()
    if distance is None:
        return "Waiting"
    if distance >= away_limit:
        if st.session_state.away_started is None:
            st.session_state.away_started = now
        st.session_state.close_started = None
        return "Away from desk"
    st.session_state.away_started = None
    if distance < close_limit:
        if st.session_state.close_started is None:
            st.session_state.close_started = now
        if now - st.session_state.close_started >= sustained_seconds:
            return "Sustained close"
        return "Too close"
    st.session_state.close_started = None
    return "Normal study"

def record_reading(distance, active, source, close_limit, away_limit, sustained_seconds):
    now = datetime.now()
    state = classify(distance, close_limit, away_limit, sustained_seconds) if active else "Session paused"
    previous = st.session_state.last_state
    if active and state != previous:
        if state == "Too close":
            add_event(f"Student is too close ({distance:.1f} cm)", "Warning")
        elif state == "Sustained close":
            add_event("Sustained close proximity detected", "Warning")
        elif state == "Away from desk":
            add_event("Student appears to be away from the desk", "Notice")
        elif state == "Normal study":
            add_event("Normal study distance restored", "Success")
    st.session_state.last_state = state
    row = {
        "timestamp": now,
        "time": now.strftime("%H:%M:%S"),
        "distance_cm": round(float(distance), 1),
        "state": state,
        "session_active": bool(active),
        "source": source,
    }
    st.session_state.readings.append(row)
    st.session_state.readings = st.session_state.readings[-2000:]
    st.session_state.last_distance = float(distance)
    if active:
        try:
            pd.DataFrame([row]).to_csv(LOG_FILE, mode="a", header=not LOG_FILE.exists(), index=False)
        except Exception:
            pass

def focus_score(df):
    if df.empty:
        return 100
    active = df[df["session_active"] == True]
    if active.empty:
        return 100
    total = len(active)
    close_pct = active["state"].isin(["Too close", "Sustained close"]).sum() / total
    away_pct = (active["state"] == "Away from desk").sum() / total
    # Project-defined indicative score: proximity and away events reduce the score.
    score = 100 - (close_pct * 45) - (away_pct * 35)
    return max(0, min(100, round(score)))

def get_demo_reading():
    # Smooth, repeatable demo pattern with occasional close/away periods.
    elapsed = int(time.time()) % 100
    if 25 <= elapsed < 38:
        d = 23 + (elapsed % 4)
    elif 58 <= elapsed < 70:
        d = 145 + (elapsed % 8)
    else:
        d = 43 + 8 * __import__("math").sin(time.time() / 5)
    return max(10, min(180, d))

# ---------- Sidebar ----------
st.sidebar.markdown("## ⚙️ Dashboard settings")
mode = st.sidebar.radio("Input source", ["Demo mode", "Arduino USB"], index=0)
close_limit = st.sidebar.slider("Too-close limit (cm)", 10, 60, 30)
away_limit = st.sidebar.slider("Away limit (cm)", 60, 250, 120)
sustained_seconds = st.sidebar.slider("Sustained-close time (seconds)", 5, 90, 20)
st.sidebar.caption("Adjust these thresholds after testing the sensor position on your desk.")

if mode == "Arduino USB":
    if serial is None:
        st.sidebar.error("pyserial is not installed. Install requirements.txt.")
    else:
        ports = [p.device for p in serial.tools.list_ports.comports()]
        port_options = ports if ports else ["No serial ports found"]
        selected_port = st.sidebar.selectbox("Serial port", port_options)
        baud = st.sidebar.selectbox("Baud rate", [9600, 115200], index=0)
        c1, c2 = st.sidebar.columns(2)
        if c1.button("Connect", use_container_width=True, disabled=(selected_port == "No serial ports found")):
            try:
                if st.session_state.serial_obj:
                    st.session_state.serial_obj.close()
                st.session_state.serial_obj = serial.Serial(selected_port, baud, timeout=0.15)
                time.sleep(2)
                st.session_state.connected = True
                add_event(f"Connected to Arduino on {selected_port}", "Success")
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Connection failed: {e}")
        if c2.button("Disconnect", use_container_width=True):
            try:
                if st.session_state.serial_obj:
                    st.session_state.serial_obj.close()
            except Exception:
                pass
            st.session_state.serial_obj = None
            st.session_state.connected = False
            add_event("Arduino disconnected", "Notice")
        st.sidebar.caption("Arduino sends: distance_cm,session_active (example: 42.5,1)")
        if st.session_state.connected:
            st.sidebar.success("Arduino connected")
        else:
            st.sidebar.warning("Arduino not connected")
else:
    st.sidebar.success("Demo sensor active")
    st.sidebar.caption("Demo readings change automatically. No hardware is needed.")

st.sidebar.divider()
st.sidebar.markdown("### Session controls")
if st.sidebar.button("▶ Start session", use_container_width=True, disabled=st.session_state.session_active):
    st.session_state.session_active = True
    st.session_state.session_start = time.time()
    st.session_state.session_seconds = 0
    st.session_state.close_started = None
    st.session_state.away_started = None
    st.session_state.last_state = "Waiting"
    add_event("Study session started", "Success")
if st.sidebar.button("■ End session", use_container_width=True, disabled=not st.session_state.session_active):
    st.session_state.session_active = False
    add_event("Study session ended", "Info")

# ---------- Read input ----------
if mode == "Demo mode":
    distance = get_demo_reading()
    active = st.session_state.session_active
    record_reading(distance, active, "Demo", close_limit, away_limit, sustained_seconds)
elif st.session_state.connected and st.session_state.serial_obj:
    distance, active = None, st.session_state.session_active
    try:
        ser = st.session_state.serial_obj
        # Consume any available lines and keep the latest valid reading.
        for _ in range(20):
            if ser.in_waiting <= 0:
                break
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            parts = line.split(",")
            if len(parts) >= 2:
                d = float(parts[0])
                active = bool(int(float(parts[1])))
                distance = d
        if distance is not None:
            st.session_state.session_active = active
            if active and st.session_state.session_start is None:
                st.session_state.session_start = time.time()
                add_event("Session started from desk button", "Success")
            if not active and st.session_state.session_start is not None:
                st.session_state.session_start = None
                add_event("Session stopped from desk button", "Info")
            record_reading(distance, active, "Arduino", close_limit, away_limit, sustained_seconds)
    except Exception as e:
        st.error(f"Serial read error: {e}")
else:
    st.info("Choose Demo mode, or connect the Arduino from the sidebar to begin receiving readings.")

# ---------- Session timer ----------
if st.session_state.session_active and st.session_state.session_start is not None:
    st.session_state.session_seconds = int(time.time() - st.session_state.session_start)
elapsed = st.session_state.session_seconds
hours, rem = divmod(elapsed, 3600)
minutes, seconds = divmod(rem, 60)
timer_text = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

df = pd.DataFrame(st.session_state.readings)
if not df.empty:
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.tail(300)

# ---------- Main dashboard ----------
st.markdown("""
<div class="hero">
  <h1>📚 SMART STUDY DESK</h1>
  <p>Study Behaviour & Focus Monitoring · Arduino Uno R3 · HC-SR04 · Laptop Dashboard</p>
</div>
""", unsafe_allow_html=True)

state = st.session_state.last_state
state_class = {
    "Normal study": "state-normal",
    "Too close": "state-close",
    "Sustained close": "state-sustained",
    "Away from desk": "state-away",
}.get(state, "")
state_display = f'<span class="{state_class}">{state}</span>' if state_class else state

m1, m2, m3, m4 = st.columns(4)
m1.metric("Current distance", f"{st.session_state.last_distance:.1f} cm" if st.session_state.last_distance is not None else "--")
m2.metric("Current state", state)
m3.metric("Study duration", timer_text)
score = focus_score(df)
m4.metric("Focus Score", f"{score}/100", help="Project-defined indicator based on distance-state readings. It is not a medical or attention measurement.")

st.markdown("")

left, right = st.columns([1.7, 1])
with left:
    st.markdown("### 📈 Distance trend")
    if not df.empty:
        chart_df = df.copy()
        chart_df["Distance (cm)"] = chart_df["distance_cm"]
        fig = px.line(chart_df, x="timestamp", y="Distance (cm)", color_discrete_sequence=["#2DD4BF"])
        fig.add_hline(y=close_limit, line_dash="dash", line_color="#FBBF24",
                      annotation_text="Too-close limit")
        fig.add_hline(y=away_limit, line_dash="dash", line_color="#818CF8",
                      annotation_text="Away limit")
        fig.update_layout(
            height=330, margin=dict(l=10, r=10, t=20, b=10),
            paper_bgcolor="#0B1220", plot_bgcolor="#131C2E",
            font_color="#C5D1E3", xaxis_title="", yaxis_title="Distance (cm)",
            legend_title_text=""
        )
        fig.update_xaxes(gridcolor="#263451")
        fig.update_yaxes(gridcolor="#263451", rangemode="tozero")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Distance readings will appear here when the session is running.")

with right:
    st.markdown("### 🧭 Study state")
    st.markdown(f'<div class="panel"><div class="muted">LIVE CLASSIFICATION</div><div style="font-size:1.45rem;margin-top:8px">{state_display}</div><div class="muted" style="margin-top:8px">Based on the configured distance thresholds.</div></div>', unsafe_allow_html=True)
    st.markdown("### 🎯 Focus Score")
    st.progress(score / 100)
    st.caption("Indicative project score. It is not a measurement of intelligence, attention, sleep, posture or health.")
    st.markdown("### 🔔 Latest alert")
    if st.session_state.events:
        ev = st.session_state.events[0]
        st.markdown(f'<div class="panel"><b>{ev["event"]}</b><div class="muted">{ev["time"]} · {ev["type"]}</div></div>', unsafe_allow_html=True)
    else:
        st.info("No alerts yet.")

st.markdown("### 🗂️ Recent activity")
if st.session_state.events:
    events_df = pd.DataFrame(st.session_state.events[:8])
    st.dataframe(events_df, use_container_width=True, hide_index=True)
else:
    st.caption("Events will appear here when the system detects a state change.")

st.markdown("### 📥 Session data")
c1, c2 = st.columns([1, 3])
with c1:
    if not df.empty:
        csv_data = df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇ Download readings CSV", csv_data, "smart_study_desk_readings.csv", "text/csv", use_container_width=True)
    else:
        st.button("⬇ Download readings CSV", disabled=True, use_container_width=True)
with c2:
    st.caption(f"Showing up to the latest 300 readings in this dashboard. Appending active-session readings to: {LOG_FILE}")

with st.expander("How the dashboard works"):
    st.markdown("""
    - **Normal study:** distance is at or above the too-close threshold and below the away threshold.
    - **Too close:** distance is below the too-close threshold.
    - **Sustained close:** distance remains below the too-close threshold for the configured time.
    - **Away from desk:** distance is at or above the away threshold.
    - **Focus Score:** starts at 100 and is reduced by the proportion of too-close and away readings. This is a simple project-defined indicator.

    The HC-SR04 measures distance only. It cannot confirm posture, sleep, attention or health conditions.
    """)

# Refresh the dashboard periodically.
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=1500, key="dashboard_refresh")
except ImportError:
    st.caption("Tip: install all packages from requirements.txt for automatic live refresh.")
