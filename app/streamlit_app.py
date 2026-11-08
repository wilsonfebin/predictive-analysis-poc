"""Streamlit engineering review UI; all mutations go through FastAPI RBAC."""
import os
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st


API = os.environ.get("API_BASE_URL", "http://localhost:8000").rstrip("/")
st.set_page_config(page_title="DG-01 Predictive Maintenance", page_icon="⚙️", layout="wide")


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
        with st.form("login"):
            username = st.text_input("Demo username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in")
        if submitted:
            try:
                api("GET", "/api/v1/overview", (username, password))
                st.session_state.auth = (username, password)
                st.session_state.username = username
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        st.stop()


def finding_title(finding):
    return "{} · {} · {} · {}".format(finding["finding_id"], finding["system"], finding["severity"].upper(), finding["review_status"])


def finding_detail(f):
    st.markdown("#### {}".format(f["finding_id"]))
    left, right = st.columns(2)
    left.write("**System:** {} · **Type:** {} · **Severity:** {}".format(f["system"], f["category"], f["severity"].upper()))
    right.write("**Status:** {} · **Start:** {} · **First detected:** {} · **Latest evidence:** {}".format(f["review_status"], f.get("start_timestamp"), f.get("detection_timestamp", "—"), f.get("end_timestamp", "—")))
    st.write("**Affected sensors:** " + ", ".join(f.get("affected_sensors", [])))
    st.write(f.get("explanation", ""))
    st.write("**Recommended action:** " + f.get("recommended_next_action", ""))
    if isinstance(f.get("detection_evidence"), list):
        st.dataframe(pd.DataFrame(f["detection_evidence"]), use_container_width=True, hide_index=True)
    else:
        st.json(f.get("detection_evidence", {}))
    if f.get("spare_parts"):
        st.write("**Mock spare availability**")
        st.dataframe(pd.DataFrame(f["spare_parts"]), use_container_width=True, hide_index=True)


def overview_page(auth):
    st.header("Generator Overview")
    data = api("GET", "/api/v1/overview", auth)
    st.info("Synthetic telemetry and simulated findings for VESSEL-01 / DG-01. Advisory only; no vessel systems or maintenance system are connected.")
    cols = st.columns(7)
    cols[0].metric("Asset", data["generator_id"])
    cols[1].metric("Generator", "RUNNING" if data["generator_running"] else "STOPPED")
    cols[2].metric("Current load", "{}%".format(data["current_load_pct"]))
    cols[3].metric("Review state", data["overall_status"].replace("_", " "))
    cols[4].metric("Open findings", data["finding_counts"]["active"])
    cols[5].metric("Machinery", data["finding_counts"]["machinery"])
    cols[6].metric("Sensor diagnostics", data["sensor_diagnostic_count"])
    st.caption("Vessel {} · Latest analytics processing: {}".format(data["vessel_id"], data["latest_processing_timestamp"] or "unknown"))
    findings = api("GET", "/api/v1/findings", auth)
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("Severity distribution")
        counts = data["severity_distribution"]
        fig = go.Figure(go.Pie(labels=list(counts), values=list(counts.values()), hole=.45, sort=False))
        fig.update_layout(height=300, margin=dict(l=10,r=10,t=10,b=10), legend_title="Severity")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.subheader("Findings requiring review")
        if findings:
            st.dataframe(pd.DataFrame([{"ID":f["finding_id"],"Type":f["category"],"System":f["system"],"Severity":f["severity"],"Status":f["review_status"],"Detected":f.get("detection_timestamp")} for f in findings]), use_container_width=True, hide_index=True)
        else:
            st.success("No findings are available.")


def sensor_page(auth):
    st.header("Sensor Monitoring")
    sensors = api("GET", "/api/v1/sensors", auth)
    lookup = {s["sensor_id"]:s for s in sensors}
    selected = st.selectbox("Sensor", list(lookup), format_func=lambda x: "{} · {} ({})".format(x, lookup[x]["system"], lookup[x]["unit"]))
    sensor = lookup[selected]
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("System", sensor["system"])
    c2.metric("Unit", sensor["unit"])
    c3.metric("Latest running value", sensor.get("current_value") or "—")
    c4.metric("Quality", sensor.get("current_quality", "—"))
    d1,d2 = st.columns(2)
    start_day = d1.date_input("From", value=date(2026,9,1), min_value=date(2026,9,1), max_value=date(2026,9,30), key="sensor_start")
    end_day = d2.date_input("Through", value=date(2026,9,30), min_value=date(2026,9,1), max_value=date(2026,9,30), key="sensor_end")
    if start_day > end_day:
        st.error("Start date must be earlier than or equal to end date."); return
    params = {"start":start_day.isoformat()+"T00:00:00Z", "end":end_day.isoformat()+"T23:59:59Z", "max_points":1200}
    history = api("GET", "/api/v1/sensors/{}/history".format(selected), auth, params=params)
    points = history["data"]
    if not points:
        st.warning("No running-state residual records are available in this range."); return
    df = pd.DataFrame(points)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.timestamp, y=df.actual, name="Actual", mode="lines", line=dict(color="#145DA0", width=1.5), connectgaps=False))
    fig.add_trace(go.Scatter(x=df.timestamp, y=df.expected, name="Expected", mode="lines", line=dict(color="#444", dash="dash", width=1.5), connectgaps=False))
    anomaly = df[df.anomaly]
    if not anomaly.empty:
        fig.add_trace(go.Scatter(x=anomaly.timestamp, y=anomaly.actual, name="Residual tolerance exceeded", mode="markers", marker=dict(color="#C0392B", size=7, symbol="x")))
    invalid = df[df.quality_status != "GOOD"]
    if not invalid.empty:
        fig.add_trace(go.Scatter(x=invalid.timestamp, y=invalid.actual, name="Quality excluded", mode="markers", marker=dict(color="#E67E22", size=6, symbol="circle-open")))
    for marker in history["finding_markers"]:
        if marker.get("timestamp"):
            fig.add_vline(x=marker["timestamp"], line_dash="dot", line_color="#8E44AD", annotation_text=marker["finding_id"], annotation_position="top")
    fig.update_layout(height=480, xaxis_title="Timestamp (UTC)", yaxis_title="{} ({})".format(selected, sensor["unit"]), hovermode="x unified", legend=dict(orientation="h", y=1.08))
    st.plotly_chart(fig, use_container_width=True)
    if history.get("current"):
        st.caption("Latest selected range: actual {} · expected {} · quality {}. Historical sampling returned {} of {} points; deviations and finding markers are retained.".format(history["current"]["value"], history["current"]["expected"], history["current"]["quality_status"], history["returned_points"], history["total_points"]))


def findings_page(auth):
    st.header("Findings")
    items = api("GET", "/api/v1/findings", auth)
    if not items:
        st.success("No findings."); return
    st.dataframe(pd.DataFrame([{"Finding":f["finding_id"],"Equipment":f["equipment_id"],"System":f["system"],"Category":f["category"],"Severity":f["severity"],"Start":f.get("start_timestamp"),"Sensors":", ".join(f["affected_sensors"]),"Status":f["review_status"]} for f in items]), use_container_width=True, hide_index=True)
    selected_id = st.selectbox("Inspect finding", [f["finding_id"] for f in items], format_func=lambda x: finding_title(next(f for f in items if f["finding_id"] == x)))
    f = api("GET", "/api/v1/findings/{}".format(selected_id), auth)
    finding_detail(f)
    if f["review_status"] not in ("APPROVED", "REJECTED") and st.session_state.role in ("Chief Engineer", "Second Engineer"):
        with st.form("investigate_findings"):
            note = st.text_area("Investigation note", placeholder="Record the evidence reviewed or checks to perform.")
            submit = st.form_submit_button("Run bounded workflow and save investigation")
        if submit:
            try:
                result = api("POST", "/api/v1/findings/{}/investigate".format(selected_id), auth, json={"note":note})
                st.success("Investigation saved; status is UNDER_INVESTIGATION.")
                st.json(result["workflow"])
            except Exception as exc:
                st.error(str(exc))
    if f.get("investigations"):
        st.subheader("Investigation notes")
        st.dataframe(pd.DataFrame(f["investigations"]), use_container_width=True, hide_index=True)


def maintenance_page(auth):
    st.header("Maintenance Review")
    items = api("GET", "/api/v1/findings", auth)
    if not items:
        st.info("There are no findings to review."); return
    selected_id = st.selectbox("Finding", [f["finding_id"] for f in items], format_func=lambda x: finding_title(next(f for f in items if f["finding_id"] == x)), key="maintenance_finding")
    f = api("GET", "/api/v1/findings/{}".format(selected_id), auth)
    finding_detail(f)
    workflow = None
    try:
        workflow = api("GET", "/api/v1/findings/{}/workflow".format(selected_id), auth)
    except RuntimeError:
        pass
    if workflow:
        st.subheader("Workflow proposal for human review")
        st.caption("Explanation mode: {} · Human decision required · No work order created".format(workflow["result"]["explanation_mode"]))
        st.write(workflow["result"]["explanation"])
        st.json(workflow["result"]["maintenance_reference"])
    if f["review_status"] not in ("APPROVED", "REJECTED") and st.session_state.role in ("Chief Engineer", "Second Engineer"):
        with st.form("investigate_maintenance"):
            note = st.text_area("Investigation note", key="maintenance_note")
            submit = st.form_submit_button("Save investigation and prepare recommendation")
        if submit:
            try:
                result = api("POST", "/api/v1/findings/{}/investigate".format(selected_id), auth, json={"note":note})
                st.success("Investigation and workflow summary saved.")
                st.json(result["workflow"])
            except Exception as exc:
                st.error(str(exc))
    if f["review_status"] not in ("APPROVED", "REJECTED") and st.session_state.role == "Chief Engineer":
        with st.form("decision"):
            rationale = st.text_area("Decision rationale", key="decision_rationale")
            a,b = st.columns(2)
            approve_click = a.form_submit_button("Approve finding")
            reject_click = b.form_submit_button("Reject finding")
        if approve_click or reject_click:
            try:
                decision = "approve" if approve_click else "reject"
                result = api("POST", "/api/v1/findings/{}/{}".format(selected_id, decision), auth, json={"rationale":rationale})
                st.success("{} recorded at {}.".format(result["decision"], result["timestamp"]))
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    elif f["review_status"] in ("APPROVED", "REJECTED"):
        st.info("Final decision recorded: {}. Evidence and audit history remain available.".format(f["review_status"]))
    elif st.session_state.role == "Fleet Office":
        st.info("Fleet Office access is read-only.")


def audit_page(auth):
    st.header("Audit History")
    events = api("GET", "/api/v1/audit", auth)
    if events:
        st.dataframe(pd.DataFrame(events), use_container_width=True, hide_index=True)
    else:
        st.info("No investigation or decision events have been recorded.")


require_login()
auth = st.session_state.auth
try:
    api("GET", "/api/v1/overview", auth)
    profile = api("GET", "/api/v1/me", auth)
    st.session_state.role = profile["role"]
except Exception as exc:
    st.error("Cannot reach the API at {}: {}".format(API, exc)); st.stop()

with st.sidebar:
    st.title("DG-01 CBM")
    st.caption("{} · {}".format(st.session_state.username, st.session_state.role))
    page = st.radio("Workspace", ["Generator Overview", "Sensor Monitoring", "Findings", "Maintenance Review", "Audit History"])
    if st.button("Sign out"):
        st.session_state.clear(); st.rerun()

try:
    {"Generator Overview":overview_page, "Sensor Monitoring":sensor_page, "Findings":findings_page, "Maintenance Review":maintenance_page, "Audit History":audit_page}[page](auth)
except Exception as exc:
    st.error(str(exc))
