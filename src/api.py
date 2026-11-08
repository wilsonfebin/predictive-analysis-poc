"""FastAPI boundary over immutable Phase 2 outputs and SQLite review state."""
import csv
import gzip
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field

from src import storage
from src.workflow import execute_workflow


ROOT = Path(__file__).resolve().parents[1]
security = HTTPBasic()
ROLES = {"Chief Engineer", "Second Engineer", "Fleet Office"}


def _path(env, default):
    return Path(os.environ.get(env, str(ROOT / default)))


def _json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HTTPException(503, "Required POC artifact is missing: " + path.name) from exc


def _demo_users():
    raw = os.environ.get("DEMO_USERS_JSON")
    if raw:
        try:
            users = json.loads(raw)
            if not isinstance(users, dict) or any(v.get("role") not in ROLES or not v.get("password") for v in users.values()):
                raise ValueError
            return users
        except (ValueError, AttributeError, json.JSONDecodeError) as exc:
            raise HTTPException(500, "DEMO_USERS_JSON must map usernames to password and a supported role") from exc
    return {
        "chief": {"password": "chief-demo", "role": "Chief Engineer"},
        "second": {"password": "second-demo", "role": "Second Engineer"},
        "fleet": {"password": "fleet-demo", "role": "Fleet Office"},
    }


def current_user(credentials: HTTPBasicCredentials = Depends(security)):
    users = _demo_users()
    user = users.get(credentials.username)
    if not user or not secrets.compare_digest(str(user["password"]), credentials.password):
        raise HTTPException(status_code=401, detail="Invalid demo credentials", headers={"WWW-Authenticate":"Basic"})
    return {"username": credentials.username, "role": user["role"]}


def _require(user, roles):
    if user["role"] not in roles:
        raise HTTPException(403, "Role is not allowed to perform this action")


def _findings():
    data = _json(_path("REPORT_DIR", "reports") / "findings.json")
    if not isinstance(data, list):
        raise HTTPException(503, "findings.json has an invalid schema")
    return data


def _tags():
    with _path("DATA_DIR", "data").joinpath("tags.csv").open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _finding(finding_id):
    finding = next((f for f in _findings() if f.get("finding_id") == finding_id), None)
    if finding is None:
        raise HTTPException(404, "Finding not found")
    return finding


def _with_status(finding):
    item = dict(finding)
    item["review_status"] = storage.review_status(item["finding_id"])
    return item


class InvestigationBody(BaseModel):
    note: str = Field(min_length=3, max_length=2000)


class DecisionBody(BaseModel):
    rationale: str = Field(min_length=3, max_length=2000)


app = FastAPI(title="ThinkPalm Generator CBM POC API", version="0.3.0", description="Advisory-only synthetic predictive-maintenance review API. OpenAPI docs are available at /docs.")


@app.on_event("startup")
def startup():
    storage.initialize()


@app.get("/health")
def health():
    report_dir = _path("REPORT_DIR", "reports")
    return {"status":"ok", "provenance":"synthetic", "reports_available":(report_dir / "findings.json").exists(), "llm_mode":os.environ.get("LLM_MODE", "disabled")}


@app.get("/api/v1/me")
def me(user=Depends(current_user)):
    return user


@app.get("/api/v1/overview")
def overview(user=Depends(current_user)):
    findings = [_with_status(f) for f in _findings()]
    summary = _json(_path("REPORT_DIR", "reports") / "processing_summary.json")
    diagnostics = _json(_path("REPORT_DIR", "reports") / "diagnostics.json")
    severity = {level: sum(f.get("severity") == level for f in findings) for level in ("high", "medium", "low")}
    counts = {"active":sum(f["review_status"] in ("OPEN", "UNDER_INVESTIGATION") for f in findings), "machinery":sum(f.get("category") == "machinery_degradation" for f in findings), "sensor":sum(f.get("category") == "sensor_fault" for f in findings)}
    process_file = _path("REPORT_DIR", "reports") / "processing_summary.json"
    processed = datetime.fromtimestamp(process_file.stat().st_mtime, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z") if process_file.exists() else None
    with _path("DATA_DIR", "data").joinpath("context.csv").open(newline="", encoding="utf-8") as f:
        latest_context = None
        for latest_context in csv.DictReader(f):
            pass
    return {"vessel_id":"VESSEL-01", "generator_id":"DG-01", "provenance":"synthetic", "generator_running":latest_context["generator_running"] == "true" if latest_context else None, "current_load_pct":float(latest_context["generator_load_pct"]) if latest_context else None, "overall_status":"REVIEW_REQUIRED" if counts["active"] else "NO_OPEN_FINDINGS", "finding_counts":counts, "severity_distribution":severity, "sensor_diagnostic_count":sum(1 for v in diagnostics.values() if any(k in v.get("quality_counts", {}) for k in ("STALE", "MISSING", "OUT_OF_RANGE"))), "latest_processing_timestamp":processed, "load_transitions_false_findings":summary.get("healthy_30min_load_transitions_ge_10pp", 0)}


@app.get("/api/v1/sensors")
def sensors(user=Depends(current_user)):
    tags = _tags()
    diagnostics = _json(_path("REPORT_DIR", "reports") / "diagnostics.json")
    telemetry_path = _path("DATA_DIR", "data") / "telemetry.csv"
    current = {}
    context_path = _path("DATA_DIR", "data") / "context.csv"
    with telemetry_path.open(newline="", encoding="utf-8") as tf, context_path.open(newline="", encoding="utf-8") as cf:
        for row, ctx in zip(csv.DictReader(tf), csv.DictReader(cf)):
            if ctx["generator_running"] == "true":
                current = row
    result = []
    for tag in tags:
        signal = tag["signal_name"]
        result.append({"sensor_id":signal, "tag_id":tag["tag_id"], "name":signal, "description":tag["description"], "system":tag["equipment_system"], "unit":tag["unit"], "valid_min":float(tag["valid_min"]), "valid_max":float(tag["valid_max"]), "current_value":current.get(signal), "current_quality":current.get("quality_"+signal, "MISSING"), "diagnostics":diagnostics.get(signal, {})})
    return result


@app.get("/api/v1/sensors/{sensor_id}/history")
def sensor_history(sensor_id: str, start: Optional[str] = None, end: Optional[str] = None, max_points: int = Query(1200, ge=50, le=5000), user=Depends(current_user)):
    tag = next((t for t in _tags() if t["signal_name"] == sensor_id), None)
    if not tag:
        raise HTTPException(404, "Sensor not found")
    try:
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00")) if start else datetime(2026, 9, 30, 0, 0, tzinfo=timezone.utc)
        end_dt = datetime.fromisoformat(end.replace("Z", "+00:00")) if end else datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
    except ValueError as exc:
        raise HTTPException(422, "start/end must be ISO-8601 timestamps") from exc
    if start_dt >= end_dt:
        raise HTTPException(422, "start must be earlier than end")
    residual_path = _path("REPORT_DIR", "reports") / "residuals.csv.gz"
    selected = []
    if not residual_path.exists():
        raise HTTPException(503, "Residual history is not available")
    with gzip.open(residual_path, "rt", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["signal"] != sensor_id:
                continue
            stamp = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
            if not start_dt <= stamp < end_dt:
                continue
            selected.append(row)
    findings = [f for f in _findings() if sensor_id in f.get("affected_sensors", [])]
    anomaly_rows = [r for r in selected if r["normalised_deviation"] and abs(float(r["normalised_deviation"])) >= 1]
    keep = set(range(len(selected)))
    if len(selected) > max_points:
        stride = max(1, len(selected) // max_points)
        keep = set(range(0, len(selected), stride))
    if len(anomaly_rows) > 200:
        anomaly_stride = max(1, len(anomaly_rows) // 200)
        anomaly_rows = anomaly_rows[::anomaly_stride]
    important_times = {r["timestamp"] for r in anomaly_rows} | {f.get("detection_timestamp") or f.get("start_timestamp") for f in findings}
    filtered = [r for i, r in enumerate(selected) if i in keep or r["timestamp"] in important_times]
    latest = next((r for r in reversed(selected) if r["quality_status"] == "GOOD"), None)
    return {"sensor_id":sensor_id, "system":tag["equipment_system"], "unit":tag["unit"], "start":start_dt.isoformat(), "end":end_dt.isoformat(), "total_points":len(selected), "returned_points":len(filtered), "data":[{"timestamp":r["timestamp"], "actual":float(r["actual"]) if r["actual"] else None, "expected":float(r["expected"]) if r["expected"] else None, "residual":float(r["residual"]) if r["residual"] else None, "normalised_deviation":float(r["normalised_deviation"]) if r["normalised_deviation"] else None, "quality_status":r["quality_status"], "operating_state":r["operating_state"], "anomaly":bool(r["normalised_deviation"] and abs(float(r["normalised_deviation"])) >= 1)} for r in filtered], "finding_markers":[{"finding_id":f["finding_id"],"timestamp":f.get("detection_timestamp") or f.get("start_timestamp"),"category":f["category"]} for f in findings], "current":({"value":float(latest["actual"]),"expected":float(latest["expected"]),"quality_status":latest["quality_status"]} if latest else None)}


@app.get("/api/v1/findings")
def findings(user=Depends(current_user)):
    return [_with_status(f) for f in _findings()]


@app.get("/api/v1/findings/{finding_id}")
def finding_detail(finding_id: str, user=Depends(current_user)):
    finding = _with_status(_finding(finding_id))
    finding["investigations"] = storage.investigations_for(finding_id)
    return finding


@app.post("/api/v1/findings/{finding_id}/investigate")
def investigate(finding_id: str, body: InvestigationBody, user=Depends(current_user)):
    _require(user, {"Chief Engineer", "Second Engineer"})
    finding = _finding(finding_id)
    try:
        timestamp = storage.add_investigation(finding_id, user["username"], user["role"], body.note)
        workflow = execute_workflow(finding_id)
        storage.save_workflow(finding_id, user["username"], workflow)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"finding_id":finding_id, "review_status":storage.review_status(finding_id), "investigation_timestamp":timestamp, "workflow":workflow}


@app.get("/api/v1/findings/{finding_id}/workflow")
def get_workflow(finding_id: str, user=Depends(current_user)):
    _finding(finding_id)
    result = storage.latest_workflow(finding_id)
    if not result:
        raise HTTPException(404, "No workflow result exists for this finding")
    return result


def _decision(finding_id, body, user, decision):
    _require(user, {"Chief Engineer"})
    _finding(finding_id)
    try:
        timestamp = storage.decide(finding_id, decision, user["username"], user["role"], body.rationale)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"finding_id":finding_id, "decision":decision, "review_status":decision, "decision_maker":user["username"], "role":user["role"], "timestamp":timestamp, "rationale":body.rationale}


@app.post("/api/v1/findings/{finding_id}/approve")
def approve(finding_id: str, body: DecisionBody, user=Depends(current_user)):
    return _decision(finding_id, body, user, "APPROVED")


@app.post("/api/v1/findings/{finding_id}/reject")
def reject(finding_id: str, body: DecisionBody, user=Depends(current_user)):
    return _decision(finding_id, body, user, "REJECTED")


@app.get("/api/v1/audit")
def audit(user=Depends(current_user)):
    return storage.audit()
