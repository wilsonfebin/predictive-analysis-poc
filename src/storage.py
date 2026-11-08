"""SQLite persistence for review state and append-only audit events."""
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


FINAL_STATES = {"APPROVED", "REJECTED"}


def db_path():
    return os.environ.get("APP_DB_PATH", str(Path(__file__).resolve().parents[1] / "app_state.sqlite3"))


def now_utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def connect(path=None):
    target = path or db_path()
    Path(target).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def initialize(path=None):
    with connect(path) as conn:
        conn.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS finding_reviews (
            finding_id TEXT PRIMARY KEY,
            status TEXT NOT NULL CHECK(status IN ('OPEN','UNDER_INVESTIGATION','APPROVED','REJECTED')),
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS investigations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            finding_id TEXT NOT NULL,
            actor TEXT NOT NULL,
            role TEXT NOT NULL,
            note TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            finding_id TEXT NOT NULL,
            decision TEXT NOT NULL CHECK(decision IN ('APPROVED','REJECTED')),
            actor TEXT NOT NULL,
            role TEXT NOT NULL,
            rationale TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS workflow_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            finding_id TEXT NOT NULL,
            actor TEXT NOT NULL,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """)


def ensure_review(finding_id, path=None):
    with connect(path) as conn:
        conn.execute("INSERT OR IGNORE INTO finding_reviews(finding_id,status,updated_at) VALUES(?,?,?)", (finding_id, "OPEN", now_utc()))
        row = conn.execute("SELECT * FROM finding_reviews WHERE finding_id=?", (finding_id,)).fetchone()
        return dict(row)


def review_status(finding_id, path=None):
    row = ensure_review(finding_id, path)
    return row["status"]


def add_investigation(finding_id, actor, role, note, path=None):
    timestamp = now_utc()
    with connect(path) as conn:
        row = conn.execute("SELECT status FROM finding_reviews WHERE finding_id=?", (finding_id,)).fetchone()
        status = row["status"] if row else "OPEN"
        if status in FINAL_STATES:
            raise ValueError("Final decisions cannot be changed")
        conn.execute("INSERT OR IGNORE INTO finding_reviews(finding_id,status,updated_at) VALUES(?,?,?)", (finding_id, "OPEN", timestamp))
        conn.execute("INSERT INTO investigations(finding_id,actor,role,note,created_at) VALUES(?,?,?,?,?)", (finding_id, actor, role, note, timestamp))
        conn.execute("UPDATE finding_reviews SET status='UNDER_INVESTIGATION',updated_at=? WHERE finding_id=?", (timestamp, finding_id))
    return timestamp


def save_workflow(finding_id, actor, result, path=None):
    timestamp = now_utc()
    with connect(path) as conn:
        conn.execute("INSERT INTO workflow_runs(finding_id,actor,result_json,created_at) VALUES(?,?,?,?)", (finding_id, actor, json.dumps(result), timestamp))
    return timestamp


def latest_workflow(finding_id, path=None):
    with connect(path) as conn:
        row = conn.execute("SELECT result_json,created_at,actor FROM workflow_runs WHERE finding_id=? ORDER BY id DESC LIMIT 1", (finding_id,)).fetchone()
    return {"result": json.loads(row["result_json"]), "created_at": row["created_at"], "actor": row["actor"]} if row else None


def decide(finding_id, decision, actor, role, rationale, path=None):
    if decision not in FINAL_STATES:
        raise ValueError("Decision must be APPROVED or REJECTED")
    timestamp = now_utc()
    with connect(path) as conn:
        row = conn.execute("SELECT status FROM finding_reviews WHERE finding_id=?", (finding_id,)).fetchone()
        status = row["status"] if row else "OPEN"
        if status in FINAL_STATES:
            raise ValueError("Finding already has a final decision")
        conn.execute("INSERT OR IGNORE INTO finding_reviews(finding_id,status,updated_at) VALUES(?,?,?)", (finding_id, "OPEN", timestamp))
        conn.execute("INSERT INTO decisions(finding_id,decision,actor,role,rationale,created_at) VALUES(?,?,?,?,?,?)", (finding_id, decision, actor, role, rationale, timestamp))
        conn.execute("UPDATE finding_reviews SET status=?,updated_at=? WHERE finding_id=?", (decision, timestamp, finding_id))
    return timestamp


def investigations_for(finding_id, path=None):
    with connect(path) as conn:
        rows = conn.execute("SELECT id,finding_id,actor,role,note,created_at FROM investigations WHERE finding_id=? ORDER BY id", (finding_id,)).fetchall()
    return [dict(r) for r in rows]


def audit(path=None):
    with connect(path) as conn:
        decisions = conn.execute("SELECT id,finding_id,decision AS event,actor,role,rationale AS detail,created_at FROM decisions").fetchall()
        investigations = conn.execute("SELECT id,finding_id,'INVESTIGATED' AS event,actor,role,note AS detail,created_at FROM investigations").fetchall()
        workflow = conn.execute("SELECT id,finding_id,'WORKFLOW_RUN' AS event,actor,'system' AS role,'Workflow explanation prepared' AS detail,created_at FROM workflow_runs").fetchall()
    items = [dict(r) for r in list(decisions) + list(investigations) + list(workflow)]
    return sorted(items, key=lambda x: (x["created_at"], x["id"]))
