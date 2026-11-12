"""Streamlit engineering review UI; all mutations go through FastAPI RBAC."""
import html
import os
from datetime import date
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import streamlit as st


API = os.environ.get("API_BASE_URL", "http://localhost:8000").rstrip("/")
NAV = {
    "Generator Overview": "⌂",
    "Sensor Monitoring": "⌁",
    "Findings": "⚠",
    "Maintenance Review": "⚒",
    "Audit History": "▤",
}
SEVERITY_COLORS = {"high": "#F87171", "medium": "#FBBF24", "low": "#34D399"}
ACTUAL_COLOR = "#60A5FA"
EXPECTED_COLOR = "#94A3B8"

st.set_page_config(page_title="DG-01 Predictive Maintenance", page_icon="⚓", layout="wide")
DISPLAY_TZ = ZoneInfo("Asia/Kolkata")
def display_timestamp(value, fallback="—"):
    """Render UTC timestamps in the vessel display timezone (IST)."""
    if not value:
        return fallback
    stamp = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(stamp):
        return fallback
    return stamp.tz_convert(DISPLAY_TZ).strftime("%d %b %Y, %H:%M IST")


def format_sensor_value(value, unit=None, decimals=None):
    if value is None or value == "":
        return "—"
    try:
        if decimals is None:
            decimals = 2 if unit in {"degC", "rpm", "%", "V", "A", "Hz", "kW"} else 3
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return str(value)


def add_theme():
    st.markdown("""
    <style>
    :root {
      color-scheme: dark;
      --navy: #0B1220; --ink: #E5EDF8; --muted: #9AAAC0; --blue: #3B82F6;
      --border: #27364B; --surface: #151F2E; --soft: #0E1726;
    }
    html, body, [class*="css"], [data-testid="stAppViewContainer"] {
      font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
    }
    [data-testid="stAppViewContainer"] { background: var(--soft); }
    [data-testid="stHeader"] { background: rgba(14,23,38,.96); }
    [data-testid="stToolbar"], footer { visibility: hidden; }
    .block-container { width: 100%; max-width: 1680px; padding: 1.2rem clamp(.8rem, 2vw, 2rem) 2.5rem; }
    h1 { color: var(--ink); font-size: 1.85rem !important; font-weight: 720 !important; letter-spacing: -.035em; line-height: 1.2 !important; margin: .1rem 0 .35rem !important; }
    h2 { color: var(--ink); font-size: 1.28rem !important; font-weight: 680 !important; letter-spacing: -.02em; margin: .15rem 0 .65rem !important; }
    h3 { color: var(--ink); font-size: 1.02rem !important; font-weight: 650 !important; margin: .1rem 0 .55rem !important; }
    p, label, [data-testid="stCaptionContainer"] { line-height: 1.45; }
    [data-testid="stCaptionContainer"] { color: var(--muted); }
    [data-testid="stCaptionContainer"] p { white-space: normal; overflow-wrap: anywhere; }
    [data-testid="stVerticalBlockBorderWrapper"] { border-color: var(--border) !important; border-radius: 13px !important; background: var(--surface); }
    [data-testid="stMetric"] { min-width: 0; min-height: 82px; padding: .65rem .8rem; border: 1px solid var(--border); border-radius: 12px; background: var(--surface); }
    [data-testid="stMetricLabel"] p { color: var(--muted) !important; font-size: .78rem !important; font-weight: 620 !important; letter-spacing: .025em; }
    [data-testid="stMetricValue"] { color: var(--ink) !important; font-size: clamp(1rem, 1.35vw, 1.38rem) !important; font-weight: 720 !important; overflow-wrap: anywhere; }
    [data-testid="stDataFrame"] { border: 1px solid var(--border); border-radius: 9px; overflow: hidden; background:var(--surface); }
    [data-testid="stDataFrame"] [role="grid"] { font-size: .82rem; }
    div.stButton > button, div.stFormSubmitButton > button { border-radius: 8px; font-weight: 620; min-height: 2.45rem; }
    div.stButton > button[kind="primary"], div.stFormSubmitButton > button[kind="primary"] { background: var(--blue); border-color: var(--blue); }
    div[data-testid="stAlert"] { border-radius: 10px; }
    input, textarea, [data-baseweb="select"] > div, [data-baseweb="input"] > div { background:#111C2B !important; color:var(--ink) !important; border-color:var(--border) !important; }
    [data-testid="stDateInput"] input { background:#111C2B !important; color:var(--ink) !important; }
    [data-testid="stExpander"] { border-color:var(--border); }
    [data-testid="stJson"] { background:#111C2B; border:1px solid var(--border); border-radius:8px; }
    .eyebrow { color:#9AAAC0; font-size:.76rem; font-weight:700; letter-spacing:.09em; text-transform:uppercase; margin:0 0 .15rem; }
    .subhead { color:#A9B8CC; font-size:.91rem; margin-top:-.1rem; }
    .section-label { color:#8293AA; font-size:.69rem; font-weight:750; letter-spacing:.11em; text-transform:uppercase; margin:.5rem 0 .15rem; }
    .brand { display:flex; align-items:center; gap:.68rem; padding:.35rem .2rem 1rem; border-bottom:1px solid rgba(226,232,240,.16); margin-bottom:1rem; }
    .brand-mark { display:flex; width:2.35rem; height:2.35rem; align-items:center; justify-content:center; color:white; background:#2563EB; border-radius:10px; font-size:1.25rem; }
    .brand-name { color:#F8FAFC; font-size:1.02rem; font-weight:740; line-height:1.2; }
    .brand-subtitle { color:#CBD5E1; font-size:.75rem; margin-top:.2rem; }
    .side-context { color:#CBD5E1; font-size:.83rem; line-height:1.9; padding:.25rem .35rem; }
    .side-user { border:1px solid rgba(226,232,240,.18); border-radius:10px; padding:.7rem .75rem; margin-top:1rem; background:rgba(255,255,255,.045); }
    .side-user-name { color:#F8FAFC; font-size:.84rem; font-weight:650; }
    .side-user-role { color:#CBD5E1; font-size:.73rem; margin-top:.15rem; }
    [data-testid="stSidebar"] { background:var(--navy); border-right:1px solid #1E2C45; }
    [data-testid="stSidebar"] > div:first-child { background:var(--navy); }
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] label, [data-testid="stSidebar"] span { color:#E2E8F0; }
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] { color:#CBD5E1; }
    [data-testid="stSidebar"] hr { border-color:rgba(226,232,240,.18); margin:.8rem 0; }
    [data-testid="stSidebar"] div[role="radiogroup"] { gap:.28rem; }
    [data-testid="stSidebar"] div[role="radiogroup"] label { border-radius:8px; padding:.48rem .55rem; margin:0; transition:background .15s ease; }
    [data-testid="stSidebar"] div[role="radiogroup"] label:hover { background:rgba(255,255,255,.08); }
    [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) { background:#2563EB; }
    [data-testid="stSidebar"] div[role="radiogroup"] label p { font-size:.87rem; font-weight:560; }
    [data-testid="stSidebar"] div.stButton > button { width:100%; color:#E2E8F0; border-color:rgba(226,232,240,.22); background:transparent; }
    [data-testid="stSidebar"] div.stButton > button:hover { color:white; border-color:#93C5FD; background:rgba(37,99,235,.22); }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] { color:#DCE6F4; }
    div[role="radiogroup"] label { color:var(--ink); }
    div[role="radiogroup"] label:has(input:checked) { background:#1D3555; }
    button[kind="secondary"] { color:var(--ink); background:#182538; border-color:var(--border); }
    [data-testid="stDataFrame"] [role="grid"] { background:#151F2E; color:#E5EDF8; }
    .llm-mode { display:flex; align-items:center; justify-content:space-between; gap:.5rem; padding:.5rem .65rem; margin:.35rem 0 .2rem; border:1px solid var(--border); border-radius:9px; background:#111C2B; color:#CBD5E1; font-size:.78rem; }
    .llm-mode strong { color:#E5EDF8; font-size:.8rem; }
    .llm-mode.openai { border-color:#315C84; }
    .llm-mode.disabled { border-color:var(--border); }
    @media (max-width: 900px) {
      .block-container { padding-left:.8rem; padding-right:.8rem; }
      h1 { font-size:1.48rem !important; }
      [data-testid="stMetric"] { min-height:76px; padding:.55rem .6rem; }
      [data-testid="stMetricLabel"] p { font-size:.7rem !important; }
    }
    </style>
    """, unsafe_allow_html=True)


def api(method, path, auth, **kwargs):
    response = requests.request(method, API + path, auth=auth, timeout=90, **kwargs)
    if response.status_code >= 400:
        detail = response.text
        try:
            detail = response.json().get("detail", detail)
        except ValueError:
            pass
        raise RuntimeError("API {}: {}".format(response.status_code, detail))
    return response.json() if response.content else None


def require_login():
    if "auth" not in st.session_state:
        st.title("DG-01 Condition Monitoring")
        st.caption("Synthetic advisory-only POC · Sign in with a configured demo user")
        with st.container(border=True):
            with st.form("login"):
                username = st.text_input("Demo username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Sign in", type="primary")
        if submitted:
            try:
                api("GET", "/api/v1/overview", (username, password))
                st.session_state.auth = (username, password)
                st.session_state.username = username
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        st.stop()


def page_heading(title, subtitle=None, eyebrow=None):
    if eyebrow:
        st.markdown('<div class="eyebrow">{}</div>'.format(html.escape(eyebrow)), unsafe_allow_html=True)
    st.title(title)
    if subtitle:
        st.markdown('<div class="subhead">{}</div>'.format(html.escape(subtitle)), unsafe_allow_html=True)


def chart_style(fig, height=370, y_title=None):
    fig.update_layout(
        template="plotly_dark", height=height, autosize=True,
        font=dict(family="Inter, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif", size=12, color="#DCE6F4"),
        paper_bgcolor="#151F2E", plot_bgcolor="#151F2E", margin=dict(l=12, r=14, t=12, b=12),
        hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(size=11, color="#C3D0E0")),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#27364B", zeroline=False, linecolor="#40516A", tickfont=dict(size=10, color="#9AAAC0"), title_font=dict(size=11, color="#9AAAC0"))
    fig.update_yaxes(showgrid=True, gridcolor="#27364B", zeroline=False, linecolor="#40516A", tickfont=dict(size=10, color="#9AAAC0"), title=y_title, title_font=dict(size=11, color="#9AAAC0"))
    return fig


def finding_title(finding):
    return "{} · {} · {} · {}".format(finding["finding_id"], finding["system"], finding["severity"].upper(), finding["review_status"])


def sort_findings(items):
    severity_rank = {"high":2, "medium":1, "low":0}
    def sort_key(finding):
        stamp = pd.to_datetime(finding.get("detection_timestamp") or finding.get("start_timestamp"), utc=True, errors="coerce")
        timestamp_rank = int(stamp.value) if not pd.isna(stamp) else -1
        return (-severity_rank.get(str(finding.get("severity", "")).lower(), -1), -timestamp_rank, finding.get("finding_id", ""))
    return sorted(items, key=sort_key)


def _severity_cell(value):
    colors = {"High":("#4B242D", "#FCA5A5"), "Medium":("#4A3920", "#FCD34D"), "Low":("#173B34", "#6EE7B7")}
    background, foreground = colors.get(str(value), ("#151F2E", "#DCE6F4"))
    return "background-color: {}; color: {}; font-weight: 700".format(background, foreground)


def _status_cell(value):
    colors = {"Open":("#1D3555", "#93C5FD"), "Under Investigation":("#4A3920", "#FCD34D"), "Approved":("#173B34", "#6EE7B7"), "Rejected":("#273244", "#CBD5E1")}
    background, foreground = colors.get(str(value), ("#151F2E", "#DCE6F4"))
    return "background-color: {}; color: {}; font-weight: 650".format(background, foreground)


def styled_findings(rows):
    frame = pd.DataFrame(rows)
    style = frame.style
    if "Severity" in frame.columns:
        style = style.map(_severity_cell, subset=["Severity"])
    if "Status" in frame.columns:
        style = style.map(_status_cell, subset=["Status"])
    return style


def finding_detail(f):
    with st.container(border=True):
        st.subheader("{} · {}".format(f["finding_id"], f["system"].replace("_", " ").title()))
        left, right = st.columns([1.25, 1])
        initial = f.get("initial_severity", f["severity"])
        left.caption("{}  /  {}  /  Initial {} · Current {}".format(f["equipment_id"], f["category"].replace("_", " ").title(), initial.title(), f["severity"].title()))
        right.caption("Status: {} · Start: {} · Detected: {}".format(f["review_status"], display_timestamp(f.get("start_timestamp")), display_timestamp(f.get("detection_timestamp"))))
        escalations = f.get("severity_escalations", [])
        if escalations:
            st.markdown("**Severity escalation history**")
            st.dataframe(pd.DataFrame([{
                "From":e.get("previous_severity", "—").title(),
                "To":e.get("new_severity", "—").title(),
                "Escalated (IST)":display_timestamp(e.get("escalation_timestamp")),
                "Reason":e.get("reason", ""),
            } for e in escalations]), use_container_width=True, hide_index=True)
        st.write("**Affected sensors** · " + ", ".join(f.get("affected_sensors", [])))
        st.markdown("**Finding summary · deterministic analytics**")
        st.write(f.get("explanation", ""))
        st.markdown("**Recommended next action**")
        st.info(f.get("recommended_next_action", ""), icon="🔎")
        evidence = f.get("detection_evidence")
        if isinstance(evidence, list) and evidence:
            ev = evidence[0]
            metrics = st.columns(4)
            metrics[0].metric("Actual", "{} {}".format(ev.get("actual", "—"), ev.get("unit", "")))
            metrics[1].metric("Expected", "{} {}".format(ev.get("expected", "—"), ev.get("unit", "")))
            metrics[2].metric("Deviation", "{} {}".format(ev.get("deviation", "—"), ev.get("unit", "")))
            metrics[3].metric("Valid observations", ev.get("persistence_valid_minutes", "—"))
            if len(evidence) > 1:
                st.dataframe(pd.DataFrame(evidence), use_container_width=True, hide_index=True)
        else:
            st.json(evidence or {})
        if f.get("spare_parts"):
            st.markdown("**Mock spare availability**")
            st.dataframe(pd.DataFrame(f["spare_parts"]), use_container_width=True, hide_index=True)


def latest_workflow(auth, finding_id):
    try:
        return api("GET", "/api/v1/findings/{}/workflow".format(finding_id), auth)
    except RuntimeError as exc:
        if str(exc).startswith("API 404:"):
            return None
        raise


def workflow_payload(workflow):
    payload = workflow or {}
    while "explanation_mode" not in payload and isinstance(payload.get("result"), dict):
        payload = payload["result"]
    return payload


def workflow_source_label(payload):
    mode = payload.get("explanation_mode")
    if mode == "openai":
        return "OpenAI-generated · validated"
    if payload.get("fallback_reason"):
        return "Template fallback · OpenAI wording not used"
    return "Template-generated · LLM disabled"


def render_workflow_explanation(workflow):
    payload = workflow_payload(workflow)
    st.markdown("**Observations and LLM status**")
    st.caption("Wording source · {}".format(workflow_source_label(payload)))
    st.write(payload.get("explanation", "No workflow explanation is available."))
    if payload.get("fallback_reason"):
        st.caption("Fallback reason · {}".format(payload["fallback_reason"]))
    elif payload.get("explanation_mode") == "openai":
        st.caption("OpenAI wording passed evidence validation. Finding severity, evidence and recommendation remain deterministic.")
    else:
        st.caption("Deterministic template wording; no OpenAI wording was used.")


def workflow_mode_control(key):
    configured = globals().get("llm_mode", "disabled")
    choice = st.radio("Wording mode for workflow runs", ("Template", "OpenAI"), horizontal=True,
                      index=1 if configured == "openai" else 0, key="workflow_mode_" + key,
                      help="OpenAI is attempted only when selected. Provider errors or invalid output fall back to the deterministic template.")
    return "openai" if choice == "OpenAI" else "disabled"


def render_workflow_history(auth, finding_id):
    try:
        history = api("GET", "/api/v1/findings/{}/workflow/history".format(finding_id), auth)
    except Exception:
        return
    if len(history) > 1:
        with st.expander("Previous wording runs", expanded=False):
            for run in history[1:]:
                payload = workflow_payload(run)
                st.caption("{} · {} · {}".format(workflow_source_label(payload), display_timestamp(run.get("created_at")), run.get("actor", "")))
                st.write(payload.get("explanation", "No explanation available."))


def _trend_history(auth, start, end, sensor_id="jacket_water_outlet_c"):
    return api("GET", "/api/v1/sensors/{}/history".format(sensor_id), auth, params={"start":start,"end":end,"max_points":1200})


QUALITY_COLORS = {"GOOD":"#16A34A", "UNCERTAIN":"#F59E0B", "BAD_QUALITY":"#DC2626", "BAD_SPIKE":"#EF4444", "MISSING":"#64748B", "STALE":"#A855F7", "OUT_OF_RANGE":"#B91C1C"}
QUALITY_ORDER = ("GOOD", "UNCERTAIN", "BAD_QUALITY", "BAD_SPIKE", "MISSING", "STALE", "OUT_OF_RANGE")


def quality_distribution_figure(counts):
    total = sum(counts.values())
    if not total:
        return None
    fig = go.Figure()
    for status in QUALITY_ORDER:
        count = int(counts.get(status, 0))
        if not count:
            continue
        percent = 100 * count / total
        fig.add_trace(go.Bar(x=[count], y=["Observations"], orientation="h", name="{} · {:,} ({:.1f}%)".format(status, count, percent), marker_color=QUALITY_COLORS[status], hovertemplate="{}<br>Count: {:,}<br>Share: {:.1f}%<extra></extra>".format(status, count, percent)))
    fig.update_layout(barmode="stack", height=82, margin=dict(l=4,r=6,t=0,b=0), xaxis=dict(visible=False,range=[0,total]), yaxis=dict(visible=False), legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="left",x=0,font=dict(size=10,color="#C3D0E0")), bargap=.1)
    return fig


def add_sensor_chart(fig, history, sensor_id, unit, sensor_description=None):
    points = history.get("data", [])
    if not points:
        return fig
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[.62,.25,.13], vertical_spacing=.035)
    df = pd.DataFrame(points)
    df["timestamp_utc"] = pd.to_datetime(df["timestamp"], utc=True)
    df["timestamp"] = df["timestamp_utc"].dt.tz_convert(DISPLAY_TZ)
    good = df[df.quality_status == "GOOD"]
    unit_label = "°C" if unit == "degC" else unit
    sensor_description = sensor_description or sensor_id.replace("_", " ").title()
    display_name = "Jacket water outlet temp" if sensor_id == "jacket_water_outlet_c" else sensor_description
    hover_time = "%d %b %Y %H:%M IST"
    actual_custom = good[["expected", "residual", "residual_tolerance", "quality_status", "operating_state"]].to_numpy()
    expected_custom = good[["actual", "residual", "residual_tolerance", "quality_status", "operating_state"]].to_numpy()
    detail_hover = f"<br>Residual: %{{customdata[1]:.3f}} {unit_label}<br>Configured tolerance: ±%{{customdata[2]:.3f}} {unit_label}<br>Quality: %{{customdata[3]}}<br>Operating state: %{{customdata[4]}}"
    fig.add_trace(go.Scatter(x=good.timestamp, y=good.actual, customdata=actual_custom, name="Actual (GOOD)", mode="lines", line=dict(color=ACTUAL_COLOR, width=2.2), connectgaps=False, hovertemplate=f"%{{x|{hover_time}}}<br>Actual: %{{y:.3f}} {unit_label}<br>Expected: %{{customdata[0]:.3f}} {unit_label}" + detail_hover + "<extra></extra>"), row=1, col=1)
    fig.add_trace(go.Scatter(x=good.timestamp, y=good.expected, customdata=expected_custom, name="Expected", mode="lines", line=dict(color="#B7C5D8", dash="dash", width=1.5), connectgaps=False, hovertemplate=f"%{{x|{hover_time}}}<br>Expected: %{{y:.3f}} {unit_label}<br>Actual: %{{customdata[0]:.3f}} {unit_label}" + detail_hover + "<extra></extra>"), row=1, col=1)
    # Run starts are identified over the full API result before ordinary points
    # are downsampled, so the marker meaning cannot be changed by sampling gaps.
    anomaly = df[df.tolerance_run_start.fillna(False).astype(bool)]
    if not anomaly.empty:
        anomaly_data = anomaly[["residual", "residual_tolerance", "normalised_deviation"]].to_numpy()
        fig.add_trace(go.Scatter(x=anomaly.timestamp, y=anomaly.actual, customdata=anomaly_data, name="Tolerance-exceedance run start", mode="markers", marker=dict(color="#F87171", size=9, symbol="circle-open", line=dict(width=1.8)), hovertemplate=f"<b>Tolerance-exceedance run start</b><br>%{{x|{hover_time}}}<br>Residual: %{{customdata[0]:.2f}} {unit_label}<br>Tolerance: ±%{{customdata[1]:.2f}} {unit_label}<br>Residual / tolerance: %{{customdata[2]:.2f}}×<extra></extra>"), row=1, col=1)
    tolerance = pd.to_numeric(good.get("residual_tolerance"), errors="coerce").dropna()
    if not tolerance.empty:
        tol = float(tolerance.median())
        band_x = [df.timestamp.min(), df.timestamp.max()]
        fig.add_trace(go.Scatter(x=band_x, y=[-tol,-tol], name="− residual tolerance", mode="lines", line=dict(color="#FBBF24", dash="dot", width=1), hovertemplate=f"Tolerance: −{tol:.2f} {unit_label}<extra></extra>"), row=2,col=1)
        fig.add_trace(go.Scatter(x=band_x, y=[tol,tol], name="+ residual tolerance", mode="lines", line=dict(color="#FBBF24", dash="dot", width=1), fill="tonexty", fillcolor="rgba(251,191,36,.10)", hovertemplate=f"Tolerance: +{tol:.2f} {unit_label}<extra></extra>"), row=2,col=1)
        fig.add_trace(go.Scatter(x=good.timestamp, y=good.residual, name="Residual (actual − expected)", mode="lines", line=dict(color="#C4B5FD", width=1.3), connectgaps=False, hovertemplate=f"%{{x|{hover_time}}}<br>Residual: %{{y:.2f}} {unit_label}<extra></extra>"), row=2,col=1)
        fig.add_annotation(x=.99, y=.92, xref="x2 domain", yref="y2 domain", text=f"Tolerance band ±{tol:.2f} {unit_label}", showarrow=False, xanchor="right", bgcolor="rgba(21,31,46,.9)", bordercolor="#36547A", borderpad=4, font=dict(size=10,color="#FCD34D"))
    invalid = df[df.quality_status != "GOOD"]
    if not invalid.empty:
        quality_data = invalid[["actual", "expected", "residual", "residual_tolerance", "quality_status", "operating_state"]].to_numpy()
        fig.add_trace(go.Scatter(x=invalid.timestamp, y=[0] * len(invalid), customdata=quality_data, name="Quality-excluded observation", mode="markers", marker=dict(color="#FBBF24", size=8, symbol="x", line=dict(width=1.4)), hovertemplate=f"<b>Quality-excluded observation</b><br>%{{x|{hover_time}}}<br>Raw value: %{{customdata[0]}} {unit_label}<br>Expected: %{{customdata[1]}} {unit_label}<br>Residual: %{{customdata[2]}} {unit_label}<br>Tolerance: ±%{{customdata[3]}} {unit_label}<br>Quality: %{{customdata[4]}}<br>Operating state: %{{customdata[5]}}<extra></extra>"), row=3, col=1)
    finding_points, diagnostic_points = [], []
    for marker in history.get("finding_markers", []):
        if not marker.get("timestamp"):
            continue
        marker_time = pd.to_datetime(marker["timestamp"], utc=True)
        if marker_time < df.timestamp_utc.min() or marker_time > df.timestamp_utc.max():
            continue
        record = df[df.timestamp_utc == marker_time]
        marker_display_time = marker_time.tz_convert(DISPLAY_TZ)
        if marker.get("category") == "machinery_degradation" and not record.empty and record.iloc[0].quality_status == "GOOD":
            finding_points.append((marker_display_time, record.iloc[0].actual, marker))
            if marker.get("start_timestamp") and marker.get("end_timestamp"):
                start_mark = pd.to_datetime(marker["start_timestamp"], utc=True).tz_convert(DISPLAY_TZ).isoformat()
                end_mark = pd.to_datetime(marker["end_timestamp"], utc=True).tz_convert(DISPLAY_TZ).isoformat()
                for row in (1,2):
                    fig.add_vrect(x0=start_mark, x1=end_mark, fillcolor="rgba(196,181,253,.08)", line_width=0, layer="below", row=row, col=1)
            for row in (1,2):
                fig.add_vline(x=marker_display_time.isoformat(), line_dash="dot", line_color="#C4B5FD", line_width=1, row=row, col=1)
        else:
            diagnostic_points.append((marker_display_time, marker["finding_id"]))
    if finding_points:
        finding_custom = [[p[2].get("finding_id"), p[2].get("initial_severity",p[2].get("severity","unknown")).title(), p[2].get("severity","unknown").title(), p[2].get("explanation","")] for p in finding_points]
        fig.add_trace(go.Scatter(x=[x[0] for x in finding_points], y=[x[1] for x in finding_points], customdata=finding_custom, name="Persistent-finding detection", mode="markers", marker=dict(color="#C4B5FD", size=11, symbol="diamond", line=dict(color="#151F2E", width=1)), hovertemplate=f"<b>Persistent-finding detection</b><br>%{{x|{hover_time}}}<br>Finding: %{{customdata[0]}}<br>Severity at detection: %{{customdata[1]}}<br>Current severity: %{{customdata[2]}}<br>Description: %{{customdata[3]}}<br>Actual: %{{y:.2f}} {unit_label}<extra></extra>"), row=1, col=1)
    if diagnostic_points:
        fig.add_trace(go.Scatter(x=[x[0] for x in diagnostic_points], y=[0] * len(diagnostic_points), customdata=[[x[1]] for x in diagnostic_points], name="Sensor-diagnostic start", mode="markers", marker=dict(color="#C4B5FD", size=10, symbol="square"), hovertemplate=f"<b>Sensor-diagnostic start</b><br>%{{x|{hover_time}}}<br>Finding: %{{customdata[0]}}<extra></extra>"), row=3, col=1)
    overlay = history.get("predictive_evaluation")
    if overlay:
        fig.add_trace(go.Scatter(x=[None],y=[None],name="Predictive detection time",mode="lines",line=dict(color="#C4B5FD",dash="dash",width=1.8)),row=1,col=1)
        fig.add_trace(go.Scatter(x=[None],y=[None],name="Fixed alarm crossing time",mode="lines",line=dict(color="#FB923C",dash="dash",width=1.8)),row=1,col=1)
        threshold = overlay.get("threshold")
        if threshold is not None:
            fig.add_hline(y=threshold, line_dash="dash", line_color="#FB923C", line_width=1.6, annotation_text=f"Fixed alarm {overlay.get('operator')} {threshold:g} {unit_label}", annotation_position="top left", row=1, col=1)
        detection = pd.to_datetime(overlay["detection_timestamp"], utc=True).tz_convert(DISPLAY_TZ) if overlay.get("detection_timestamp") else None
        alarm_time = pd.to_datetime(overlay["alarm_timestamp"], utc=True).tz_convert(DISPLAY_TZ) if overlay.get("alarm_timestamp") else None
        for stamp, color, row in ((detection,"#C4B5FD",1),(detection,"#C4B5FD",2),(alarm_time,"#FB923C",1)):
            if stamp is not None and df.timestamp.min() <= stamp <= df.timestamp.max():
                fig.add_vline(x=stamp.isoformat(), line_dash="dash", line_color=color, line_width=1.8, row=row, col=1)
        if overlay.get("lead_time_hours") is not None:
            fig.add_annotation(x=.99, y=.96, xref="x domain", yref="y domain", text=f"Detected {overlay['lead_time_hours']:g} h before alarm", showarrow=False, xanchor="right", bgcolor="rgba(21,31,46,.9)", bordercolor="#36547A", borderpad=5, font=dict(size=11,color="#E5EDF8"), row=1,col=1)
    fig = chart_style(fig, height=560, y_title=None)
    fig.update_yaxes(title=f"{display_name} ({unit_label})", row=1,col=1)
    fig.update_yaxes(title=f"Residual ({unit_label})", zeroline=True, zerolinecolor="#53657C", row=2,col=1)
    fig.update_yaxes(title="Excluded", range=[-.6,.6], tickmode="array", tickvals=[0], ticktext=["Quality"], showgrid=False, zeroline=False, title_font=dict(size=11,color="#9AAAC0"), tickfont=dict(size=10,color="#9AAAC0"), row=3,col=1)
    fig.update_xaxes(range=[df.timestamp.min().isoformat(), df.timestamp.max().isoformat()], row=1,col=1)
    fig.update_xaxes(title="Timestamp (IST)", tickfont=dict(size=10,color="#9AAAC0"), title_font=dict(size=11,color="#9AAAC0"), row=3,col=1)
    primary_values = pd.concat([good.actual, good.expected], ignore_index=True).dropna()
    if not primary_values.empty:
        low, high = float(primary_values.min()), float(primary_values.max())
        padding = max((high-low)*.06, .1)
        fig.update_yaxes(range=[low-padding, high+padding], row=1,col=1)
    return fig


def overview_page(auth):
    data = api("GET", "/api/v1/overview", auth)
    findings = sort_findings(api("GET", "/api/v1/findings", auth))
    page_heading("Generator Overview — DG-01", "Synthetic telemetry and simulated findings. Advisory only; no vessel or maintenance systems are connected.", "VESSEL-01  /  Predictive Maintenance")
    period = data.get("observation_period") or {}
    st.markdown("<span style='display:inline-block;background:#1D3555;color:#BFDBFE;border:1px solid #36547A;border-radius:999px;padding:.35rem .72rem;font-size:.77rem;font-weight:700'>⚗ Synthetic POC</span>", unsafe_allow_html=True)
    observation, latest, processed = st.columns(3, gap="small")
    observation.caption("**Observation period · IST**  \n{} — {}".format(display_timestamp(period.get("start")), display_timestamp(period.get("end"))))
    latest.caption("**Last telemetry · IST**  \n{}".format(display_timestamp(data.get("last_observation_timestamp"))))
    processed.caption("**Analytics processed · IST**  \n{}".format(display_timestamp(data.get("processed_at"))))

    # Three cards per row keep every status legible at normal laptop widths.
    kpis_top = st.columns(3, gap="small")
    kpis_bottom = st.columns(3, gap="small")
    kpis_top[0].metric("Last Recorded Operating State", "RUNNING" if data["generator_running"] else "STOPPED")
    kpis_top[1].metric("Latest Recorded Load", "{:.2f}%".format(data["current_load_pct"] or 0))
    kpis_top[2].metric("Open Findings", data["finding_counts"]["active"])
    kpis_bottom[0].metric("Machinery", data["finding_counts"]["machinery"])
    kpis_bottom[1].metric("Sensor Diagnostics", data["sensor_diagnostic_count"])
    kpis_bottom[2].metric("Review State", data["overall_status"].replace("_", " "))

    left, right = st.columns([.82, 1.55], gap="medium")
    with left:
        with st.container(border=True):
            st.subheader("Severity Distribution")
            counts = data["severity_distribution"]
            fig = go.Figure(go.Pie(labels=["High", "Medium", "Low"], values=[counts["high"], counts["medium"], counts["low"]], hole=.62, sort=False, marker=dict(colors=[SEVERITY_COLORS["high"], SEVERITY_COLORS["medium"], SEVERITY_COLORS["low"]], line=dict(color="#151F2E", width=3)), textinfo="percent", textfont=dict(size=11, color="#0B1220"), hovertemplate="%{label}: %{value}<extra></extra>"))
            fig.update_layout(legend=dict(orientation="v", x=1.0, y=.5), annotations=[dict(text="{}<br><span style='font-size:11px'>Findings</span>".format(sum(counts.values())), x=.5,y=.5,showarrow=False,font=dict(size=22,color="#E5EDF8"))])
            chart_style(fig, height=285)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})
            sev_cols = st.columns(3)
            for col, sev in zip(sev_cols, ("high", "medium", "low")):
                col.caption("{} · {}".format(sev.title(), counts[sev]))
    with right:
        with st.container(border=True):
            title, link = st.columns([1.4, .6])
            title.subheader("Findings Requiring Review")
            link.caption("Timestamps · IST")
            rows = [{"Finding ID":f["finding_id"],"Type":"Machinery" if f["category"]=="machinery_degradation" else "Sensor fault","System":f["system"].replace("_"," ").title(),"Severity":("{} → {}".format(f.get("initial_severity",f["severity"]).title(),f["severity"].title()) if f.get("initial_severity",f["severity"]) != f["severity"] else f["severity"].title()),"Status":f["review_status"].replace("_"," ").title(),"Detected (IST)":display_timestamp(f.get("detection_timestamp") or f.get("start_timestamp"))} for f in findings]
            if rows:
                st.dataframe(styled_findings(rows), use_container_width=True, hide_index=True, height=min(330, 44+36*len(rows)), column_config={
                    "Finding ID":st.column_config.TextColumn(width=120), "Type":st.column_config.TextColumn(width=150),
                    "System":st.column_config.TextColumn(width=155), "Severity":st.column_config.TextColumn(width=175),
                    "Status":st.column_config.TextColumn(width=105), "Detected (IST)":st.column_config.TextColumn(width=220),
                })
                st.caption("Open the Findings workspace to inspect evidence and record an investigation.")
            else:
                st.success("No findings are available.")

    trend_col, system_col = st.columns([1.55,.82], gap="medium")
    with trend_col:
        with st.container(border=True):
            row1,row2 = st.columns([1.2,.8])
            row1.subheader("Key Sensor Trend · Jacket Water Outlet")
            window = row2.radio("Trend window", ["24H","7D","30D"], index=2, horizontal=True, label_visibility="collapsed", key="overview_trend_window")
            start_day = {"24H":"2026-09-30","7D":"2026-09-24","30D":"2026-09-01"}[window]
            history = _trend_history(auth, start_day+"T00:00:00Z", "2026-10-01T00:00:00Z")
            if history.get("data"):
                fig = add_sensor_chart(go.Figure(), history, history["sensor_id"], history["unit"])
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})
                overlay = history.get("predictive_evaluation") or {}
                lead_note = " · Detected {:.1f} h before the configured fixed alarm".format(overlay["lead_time_hours"]) if overlay.get("lead_time_hours") is not None else ""
                quality_counts = history.get("quality_counts_full_range", {})
                excluded_count = sum(value for key,value in quality_counts.items() if key != "GOOD")
                st.caption("{} window · {} plotted records · {} quality exclusions retained from the full window{} · synthetic evaluation.".format(window, history["returned_points"], excluded_count, lead_note))
            else:
                st.info("No sensor history is available for this window.")
    with system_col:
        with st.container(border=True):
            st.subheader("Findings by System and Category")
            system_counts = {}
            for finding in findings:
                name = finding["system"].replace("_", " ").title()
                category = "machinery" if finding["category"] == "machinery_degradation" else "sensor"
                system_counts.setdefault(name, {"machinery":0, "sensor":0})[category] += 1
            if system_counts:
                names = list(system_counts)
                fig = go.Figure()
                fig.add_trace(go.Bar(x=[system_counts[n]["machinery"] for n in names], y=names, orientation="h", name="Machinery", marker_color="#60A5FA", text=[system_counts[n]["machinery"] for n in names], textposition="outside", cliponaxis=False, hovertemplate="%{y}: %{x} machinery finding(s)<extra></extra>"))
                fig.add_trace(go.Bar(x=[system_counts[n]["sensor"] for n in names], y=names, orientation="h", name="Sensor diagnostics", marker_color="#FBBF24", text=[system_counts[n]["sensor"] for n in names], textposition="outside", cliponaxis=False, hovertemplate="%{y}: %{x} sensor diagnostic(s)<extra></extra>"))
                fig.update_layout(yaxis=dict(autorange="reversed"), xaxis=dict(dtick=1, tickmode="linear", rangemode="tozero"), barmode="group", bargap=.35, margin=dict(r=28))
                st.plotly_chart(chart_style(fig, height=300, y_title=None), use_container_width=True, config={"displayModeBar":False})
                st.caption("Machinery findings and sensor diagnostic findings are counted separately.")
            else:
                st.success("No findings by system.")


def sensor_page(auth):
    page_heading("Sensor Monitoring", "Compare measurements with context-aware expectations and review quality flags.", "Telemetry  /  DG-01")
    sensors = api("GET", "/api/v1/sensors", auth)
    lookup = {sensor["sensor_id"]:sensor for sensor in sensors}
    overview = api("GET", "/api/v1/overview", auth)
    findings = sort_findings(api("GET", "/api/v1/findings", auth))
    period = overview.get("observation_period") or {}
    available_start = pd.to_datetime(period.get("start"), utc=True)
    available_end = pd.to_datetime(period.get("end"), utc=True) + pd.Timedelta(minutes=1)
    min_day, max_day = available_start.date(), pd.to_datetime(period.get("end"), utc=True).date()
    st.caption("Dataset observation period · {} — {} · Last recorded observation · {} · Timezone: IST".format(display_timestamp(period.get("start")), display_timestamp(period.get("end")), display_timestamp(overview.get("last_observation_timestamp"))))
    with st.container(border=True):
        selected = st.selectbox("Sensor", list(lookup), format_func=lambda x: "{}  ·  {}  ·  {}".format(lookup[x]["description"], lookup[x]["system"].replace("_"," ").title(), "°C" if lookup[x]["unit"] == "degC" else lookup[x]["unit"]))
        sensor = lookup[selected]
        st.caption("Valid measurement range · {} to {} {}".format(sensor["valid_min"], sensor["valid_max"], "°C" if sensor["unit"] == "degC" else sensor["unit"]))
        range_preset = st.radio("Date range", ["24 Hours", "7 Days", "30 Days", "Custom"], index=2, horizontal=True, key="sensor_range_preset")
        if range_preset == "Custom":
            date_cols = st.columns(2, gap="small")
            start_day = date_cols[0].date_input("From", value=min_day, min_value=min_day, max_value=max_day, key="sensor_start")
            end_day = date_cols[1].date_input("Through", value=max_day, min_value=min_day, max_value=max_day, key="sensor_end")
            if start_day > end_day:
                st.error("Start date must be earlier than or equal to end date."); return
            selected_start = max(available_start, pd.Timestamp(start_day, tz="UTC"))
            selected_end = min(available_end, pd.Timestamp(end_day + pd.Timedelta(days=1), tz="UTC"))
        else:
            span = {"24 Hours":pd.Timedelta(hours=24), "7 Days":pd.Timedelta(days=7), "30 Days":pd.Timedelta(days=30)}[range_preset]
            selected_end = available_end
            selected_start = max(available_start, selected_end - span)
    to_iso = lambda value: value.isoformat().replace("+00:00", "Z")
    params = {"start":to_iso(selected_start), "end":to_iso(selected_end), "max_points":1200}
    history = api("GET", "/api/v1/sensors/{}/history".format(selected), auth, params=params)
    tail_start = max(selected_start, selected_end - pd.Timedelta(days=1))
    latest_window = api("GET", "/api/v1/sensors/{}/history".format(selected), auth, params={"start":to_iso(tail_start),"end":to_iso(selected_end),"max_points":5000})
    latest_row = latest_window.get("data", [])[-1] if latest_window.get("data") else None
    quality_counts = history.get("quality_counts_full_range", {})
    valid_count = int(quality_counts.get("GOOD", 0))
    exceedance_count = sum(1 for point in history.get("data", []) if point.get("quality_status") == "GOOD" and point.get("anomaly"))
    kpis = st.columns(4, gap="small")
    latest_value = format_sensor_value(latest_row.get("actual") if latest_row else None, sensor["unit"])
    unit_label = "°C" if sensor["unit"] == "degC" else sensor["unit"]
    kpis[0].metric("Latest Recorded Value", "{} {}".format(latest_value, unit_label))
    kpis[1].metric("Data Quality", latest_row.get("quality_status", "—") if latest_row else "—")
    kpis[2].metric("Valid Observations", "{:,}".format(valid_count))
    kpis[3].metric("Tolerance Exceedances · sampled", "{:,}".format(exceedance_count))
    captions = st.columns(4, gap="small")
    captions[0].caption("Latest applicable observation · {}".format(display_timestamp(latest_row.get("timestamp")) if latest_row else "No valid record"))
    captions[1].caption("Latest quality status in selected range")
    captions[2].caption("GOOD quality observations in selected range")
    captions[3].caption("Returned samples only; separate from persistent findings")
    quality_fig = quality_distribution_figure(quality_counts)
    with st.container(border=True):
        st.subheader("Data Quality Distribution")
        if quality_fig is None:
            st.info("No observations are available for this sensor and date range.")
        else:
            st.plotly_chart(chart_style(quality_fig,height=105), use_container_width=True, config={"displayModeBar":False})
    with st.container(border=True):
        st.subheader("Actual vs Expected and Residual")
        if not history["data"]:
            st.warning("No running-state residual records are available in this range."); return
        sensor_findings = [finding for finding in findings if selected in finding.get("affected_sensors", [])]
        marker_lookup = {finding["finding_id"]:finding for finding in sensor_findings}
        for marker in history.get("finding_markers", []):
            finding = marker_lookup.get(marker.get("finding_id"))
            if finding:
                marker.update({key:finding.get(key) for key in ("initial_severity","severity","explanation","start_timestamp","end_timestamp")})
        fig = add_sensor_chart(go.Figure(), history, selected, sensor["unit"], sensor["description"])
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})
        st.caption("Residual = actual − expected. Positive values are above expected; negative values are below. Shaded limits show configured residual tolerance; vertical finding markers show persistent detections. Quality exclusions remain available in the strip and hover details.")
    if sensor.get("diagnostics", {}).get("frozen_candidates"):
        with st.container(border=True):
            st.subheader("Sensor diagnostic context")
            st.caption("Flatline candidates are diagnostic evidence only; a constant value alone does not prove sensor failure.")
            st.dataframe(pd.DataFrame(sensor["diagnostics"]["frozen_candidates"]), use_container_width=True, hide_index=True)


def findings_page(auth):
    page_heading("Findings", "Grouped predictive findings and sensor diagnostics supported by telemetry evidence.", "Review  /  Evidence")
    items = sort_findings(api("GET", "/api/v1/findings", auth))
    if not items:
        st.success("No findings."); return
    with st.container(border=True):
        st.subheader("Finding Register")
        rows = [{"Finding ID":f["finding_id"],"Type":"Machinery" if f["category"]=="machinery_degradation" else "Sensor fault","System":f["system"].replace("_"," ").title(),"Severity":("{} → {}".format(f.get("initial_severity",f["severity"]).title(),f["severity"].title()) if f.get("initial_severity",f["severity"]) != f["severity"] else f["severity"].title()),"Status":f["review_status"].replace("_"," ").title(),"Detected (IST)":display_timestamp(f.get("detection_timestamp") or f.get("start_timestamp"))} for f in items]
        st.dataframe(styled_findings(rows), use_container_width=True, hide_index=True, height=min(300, 45+37*len(rows)), column_config={
            "Finding ID":st.column_config.TextColumn(width=120),"Type":st.column_config.TextColumn(width=150),
            "System":st.column_config.TextColumn(width=155),"Severity":st.column_config.TextColumn(width=175),
            "Status":st.column_config.TextColumn(width=130),"Detected (IST)":st.column_config.TextColumn(width=220),
        })
        select_col, hint_col = st.columns([.7,1.3])
        selected_id = select_col.selectbox("Inspect finding", [f["finding_id"] for f in items], format_func=lambda x: finding_title(next(f for f in items if f["finding_id"] == x)), key="findings_select")
        selected = next(f for f in items if f["finding_id"] == selected_id)
        hint_col.caption("{} · {} sensor(s) · started {}".format(selected["category"].replace("_"," ").title(), len(selected["affected_sensors"]), display_timestamp(selected.get("start_timestamp"))))
    f = api("GET", "/api/v1/findings/{}".format(selected_id), auth)
    workflow = latest_workflow(auth, selected_id)
    selected_mode = workflow_mode_control("findings")
    with st.container(border=True):
        finding_detail(f)
        if workflow:
            render_workflow_explanation(workflow)
        else:
            st.caption("Observations and LLM status · Workflow not prepared. The finding summary above is deterministic.")
        if f["review_status"] not in ("APPROVED", "REJECTED") and st.session_state.role in ("Chief Engineer", "Second Engineer"):
            with st.form("investigate_findings"):
                note = st.text_area("Investigation note", placeholder="Record the evidence reviewed or checks to perform.")
                submit = st.form_submit_button("Run workflow and save investigation", type="primary")
            if submit:
                try:
                    result = api("POST", "/api/v1/findings/{}/investigate".format(selected_id), auth, json={"note":note,"mode":selected_mode})
                    st.success("Investigation saved; status is UNDER_INVESTIGATION.")
                    render_workflow_explanation(result["workflow"])
                except Exception as exc:
                    st.error(str(exc))
        if workflow and st.session_state.role in ("Chief Engineer", "Second Engineer"):
            if st.button("Regenerate wording using {}".format("OpenAI" if selected_mode == "openai" else "Template"), key="regen_findings"):
                try:
                    result = api("POST", "/api/v1/findings/{}/workflow/regenerate".format(selected_id), auth, json={"mode":selected_mode})
                    st.success("New wording run saved; prior runs remain in history.")
                    render_workflow_explanation(result)
                except Exception as exc:
                    st.error(str(exc))
        render_workflow_history(auth, selected_id)
        if f.get("investigations"):
            with st.expander("Investigation history", expanded=False):
                st.dataframe(pd.DataFrame(f["investigations"]), use_container_width=True, hide_index=True)


def maintenance_page(auth):
    page_heading("Maintenance Review", "Review recommendations and record an advisory decision.", "Human review  /  Audit trail")
    items = sort_findings(api("GET", "/api/v1/findings", auth))
    if not items:
        st.info("There are no findings to review."); return
    selection, _ = st.columns([1,1.1])
    selected_id = selection.selectbox("Finding", [f["finding_id"] for f in items], format_func=lambda x: finding_title(next(f for f in items if f["finding_id"] == x)), key="maintenance_finding")
    f = api("GET", "/api/v1/findings/{}".format(selected_id), auth)
    workflow = latest_workflow(auth, selected_id)
    selected_mode = workflow_mode_control("maintenance")
    content_col, action_col = st.columns([1.45,.85], gap="medium")
    with content_col:
        finding_detail(f)
        if workflow:
            render_workflow_explanation(workflow)
        else:
            st.caption("Observations and LLM status · Workflow not prepared. The finding summary above is deterministic.")
        if f.get("investigations"):
            with st.container(border=True):
                st.subheader("Investigation Notes")
                st.dataframe(pd.DataFrame(f["investigations"]), use_container_width=True, hide_index=True)
    with action_col:
        with st.container(border=True):
            st.subheader("Review Actions")
            st.caption("Current status · {}".format(f["review_status"].replace("_"," ")))
            if workflow:
                result = workflow_payload(workflow)
                st.caption("Explanation source · {} · Human decision required · No work order created".format(workflow_source_label(result)))
                st.json(result["maintenance_reference"])
            if f["review_status"] not in ("APPROVED", "REJECTED") and st.session_state.role in ("Chief Engineer", "Second Engineer"):
                with st.form("investigate_maintenance"):
                    note = st.text_area("Investigation note", key="maintenance_note")
                    submit = st.form_submit_button("Save investigation and prepare recommendation")
                if submit:
                    try:
                        result = api("POST", "/api/v1/findings/{}/investigate".format(selected_id), auth, json={"note":note,"mode":selected_mode})
                        st.success("Investigation and workflow summary saved.")
                        render_workflow_explanation(result["workflow"])
                    except Exception as exc:
                        st.error(str(exc))
            if workflow and st.session_state.role in ("Chief Engineer", "Second Engineer"):
                if st.button("Regenerate wording using {}".format("OpenAI" if selected_mode == "openai" else "Template"), key="regen_maintenance"):
                    try:
                        result = api("POST", "/api/v1/findings/{}/workflow/regenerate".format(selected_id), auth, json={"mode":selected_mode})
                        st.success("New wording run saved; prior runs remain in history.")
                        render_workflow_explanation(result)
                    except Exception as exc:
                        st.error(str(exc))
            render_workflow_history(auth, selected_id)
            if f["review_status"] not in ("APPROVED", "REJECTED") and st.session_state.role == "Chief Engineer":
                with st.form("decision"):
                    rationale = st.text_area(
                        "Decision rationale",
                        key="decision_rationale",
                        placeholder="Explain why you are approving or rejecting this finding.",
                        help="Required for the audit trail (at least 3 non-space characters).",
                    )
                    approve_click = st.form_submit_button("Approve finding", type="primary")
                    reject_click = st.form_submit_button("Reject finding")
                if approve_click or reject_click:
                    cleaned_rationale = rationale.strip()
                    if len(cleaned_rationale) < 3:
                        st.warning("Enter a decision rationale with at least 3 non-space characters before recording your decision.")
                    else:
                        try:
                            decision = "approve" if approve_click else "reject"
                            result = api("POST", "/api/v1/findings/{}/{}".format(selected_id, decision), auth, json={"rationale":cleaned_rationale})
                            st.success("{} recorded at {}.".format(result["decision"], display_timestamp(result["timestamp"])))
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))
            elif f["review_status"] in ("APPROVED", "REJECTED"):
                st.info("Final decision recorded: {}. Evidence and audit history remain available.".format(f["review_status"]))
            elif st.session_state.role == "Fleet Office":
                st.info("Fleet Office access is read-only.")


def audit_page(auth):
    page_heading("Audit History", "Append-only investigation and decision events.", "Governance  /  Review record")
    events = api("GET", "/api/v1/audit", auth)
    if events:
        with st.container(border=True):
            st.subheader("Recorded events")
            rows = [{"Finding ID":e["finding_id"],"Event":e["event"].replace("_"," ").title(),"Decision Maker":e["actor"],"Role":e["role"],"Timestamp (IST)":display_timestamp(e["created_at"]),"Rationale / Note":e["detail"]} for e in events]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=min(560, 42+37*len(rows)), column_config={
                "Finding ID":st.column_config.TextColumn(width="small"),"Event":st.column_config.TextColumn(width="small"),
                "Decision Maker":st.column_config.TextColumn(width="small"),"Role":st.column_config.TextColumn(width="medium"),
                "Timestamp (IST)":st.column_config.TextColumn(width="medium"),"Rationale / Note":st.column_config.TextColumn(width="large"),
            })
    else:
        with st.container(border=True):
            st.info("No investigation or decision events have been recorded.")


add_theme()
require_login()
auth = st.session_state.auth
try:
    overview = api("GET", "/api/v1/overview", auth)
    profile = api("GET", "/api/v1/me", auth)
    health = api("GET", "/health", auth)
    st.session_state.role = profile["role"]
except Exception as exc:
    st.error("Cannot reach the API at {}: {}".format(API, exc)); st.stop()

llm_mode = str(health.get("llm_mode", "disabled")).strip().lower()
llm_mode_label = {"disabled":"Disabled", "openai":"OpenAI"}.get(llm_mode, "Unknown")

with st.sidebar:
    st.markdown('<div class="brand"><div class="brand-mark">⚓</div><div><div class="brand-name">Marine AI</div><div class="brand-subtitle">Predictive Maintenance</div></div></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Workspace</div>', unsafe_allow_html=True)
    pages = list(NAV)
    open_findings = overview["finding_counts"]["active"]
    nav_labels = {"{}   {}{}".format(NAV[name], name, "   ·   {}".format(open_findings) if name == "Findings" else ""):name for name in pages}
    selected_page = st.radio("Workspace", list(nav_labels), label_visibility="collapsed", key="workspace_nav")
    page = nav_labels[selected_page]
    st.divider()
    st.markdown('<div class="section-label">Context</div>', unsafe_allow_html=True)
    st.markdown('<div class="side-context">Vessel · VESSEL-01<br>Generator · DG-01</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Default wording mode</div>', unsafe_allow_html=True)
    st.markdown('<div class="llm-mode {}"><span>Startup default</span><strong>{}</strong></div>'.format(html.escape(llm_mode), html.escape(llm_mode_label)), unsafe_allow_html=True)
    st.caption("Select Template or OpenAI in Findings or Maintenance Review to set the mode for each run.")
    st.markdown('<div class="side-user"><div class="side-user-name">{}</div><div class="side-user-role">{}</div></div>'.format(html.escape(st.session_state.username), html.escape(st.session_state.role)), unsafe_allow_html=True)
    if st.button("Sign out", key="sign_out"):
        st.session_state.clear(); st.rerun()

try:
    {"Generator Overview":overview_page, "Sensor Monitoring":sensor_page, "Findings":findings_page, "Maintenance Review":maintenance_page, "Audit History":audit_page}[page](auth)
except Exception as exc:
    st.error(str(exc))
