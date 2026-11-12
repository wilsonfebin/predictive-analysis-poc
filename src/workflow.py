"""One bounded LangGraph workflow for explaining existing Phase 2 findings."""
import json
import os
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph


ROOT = Path(__file__).resolve().parents[1]


def _data_path(name):
    return Path(os.environ.get("DATA_DIR", str(ROOT / "data"))) / name


def _report_path(name):
    return Path(os.environ.get("REPORT_DIR", str(ROOT / "reports"))) / name


class WorkflowState(TypedDict, total=False):
    mode: str
    client: Any
    finding_id: str
    finding: Dict[str, Any]
    classification: str
    route: str
    maintenance_reference: Dict[str, Any]
    evidence_summary: Dict[str, Any]
    explanation: str
    explanation_mode: str
    fallback_reason: Optional[str]
    validation: Dict[str, Any]
    result: Dict[str, Any]


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load_finding(state):
    findings = _read_json(_report_path("findings.json"))
    finding = next((item for item in findings if item["finding_id"] == state["finding_id"]), None)
    if finding is None:
        raise ValueError("Finding not found: " + state["finding_id"])
    return {"finding": finding}


def _classify(state):
    finding = state["finding"]
    classification = "sensor" if finding.get("category") == "sensor_fault" else "machinery"
    return {"classification": classification, "route": classification}


def _sensor_path(state):
    maintenance = _read_json(_data_path("maintenance_reference.json"))
    system = next((s for s in maintenance["systems"] if s["system"] == "instrumentation"), {})
    action = (system.get("inspection_actions") or [state["finding"].get("recommended_next_action", "Instrument check")])[0]
    return {"maintenance_reference": {"route": "instrument_inspection", "action": action, "spare_parts": [], "machinery_work_order": False}}


def _machinery_path(state):
    maintenance = _read_json(_data_path("maintenance_reference.json"))
    finding = state["finding"]
    system = next((s for s in maintenance["systems"] if s["system"] == finding.get("system")), {})
    signal_actions = system.get("signal_maintenance_actions", {})
    selected = next((signal_actions[signal] for signal in finding.get("affected_sensors", []) if signal in signal_actions), None)
    actions = system.get("maintenance_actions") or []
    selected = selected or (actions[0] if actions else {"description": finding.get("recommended_next_action", "Inspect affected system"), "spares": []})
    inventory = {p["part_id"]: p for p in maintenance.get("inventory", [])}
    return {"maintenance_reference": {"route": "machinery_inspection", "action": selected.get("description", finding.get("recommended_next_action")), "spare_parts": [{"part_id": p, "description": inventory.get(p, {}).get("description", "Mock spare part"), "quantity_available": inventory.get(p, {}).get("quantity_available", 0)} for p in selected.get("spares", [])], "machinery_work_order": False}}


def _build_evidence(state):
    finding = state["finding"]
    evidence = finding.get("detection_evidence")
    if isinstance(evidence, list):
        signals = "; ".join("{signal}: actual {actual} {unit}, expected {expected} {unit}, deviation {deviation} {unit}".format(**item) for item in evidence)
    else:
        signals = "{signal}: quality {quality_status}, affected {count} readings".format(signal=", ".join(finding.get("affected_sensors", [])), quality_status=evidence.get("quality_status", "unavailable"), count=evidence.get("count", 0))
    summary = {"finding_id": finding["finding_id"], "category": finding["category"], "system": finding["system"], "severity": finding["severity"], "start_timestamp": finding.get("start_timestamp"), "detection_timestamp": finding.get("detection_timestamp"), "signals": signals, "action": state["maintenance_reference"]["action"]}
    return {"evidence_summary": summary}


def deterministic_explanation(finding, evidence_summary, maintenance_reference):
    sensor_names = ", ".join(finding.get("affected_sensors", []))
    return ("{category} finding {finding_id} concerns {system} sensor(s) {sensors}. "
            "Evidence: {signals}. Severity is {severity}. {action}.").format(
                category="Sensor diagnostic" if finding["category"] == "sensor_fault" else "Machinery degradation",
                finding_id=finding["finding_id"], system=finding["system"], sensors=sensor_names,
                signals=evidence_summary["signals"], severity=finding["severity"], action=maintenance_reference["action"])


def _number_token(value):
    try:
        decimal = Decimal(value)
        normalized = format(decimal.normalize(), "f")
        return normalized.rstrip("0").rstrip(".") if "." in normalized else normalized
    except InvalidOperation:
        return value


def validate_explanation(text, finding, evidence_summary, maintenance_reference):
    if not isinstance(text, str) or not text.strip():
        return False, "Explanation is empty"
    required = list(finding.get("affected_sensors", []))
    if any(sensor not in text for sensor in required):
        return False, "Explanation omitted an affected sensor"
    if finding.get("severity", "").lower() not in text.lower() or finding.get("system", "").lower() not in text.lower():
        return False, "Explanation omitted the system or computed severity"
    tokens = re.findall(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?", text)
    allowed = set()
    raw = json.dumps({"finding": finding.get("detection_evidence", {}), "signals": evidence_summary.get("signals", "")}, ensure_ascii=False)
    allowed.update(_number_token(token) for token in re.findall(r"[-+]?\d+(?:\.\d+)?", raw))
    identifiers = " ".join(finding.get("affected_sensors", []) + [finding.get("finding_id", "")])
    allowed.update(_number_token(token) for token in re.findall(r"\d+(?:\.\d+)?", identifiers))
    if any(_number_token(token) not in allowed for token in tokens):
        return False, "Explanation contains a number not present in finding evidence"
    source_text = " ".join([deterministic_explanation(finding, evidence_summary, maintenance_reference), finding.get("explanation", "")])
    supported_words = {word.lower() for word in re.findall(r"[A-Za-z_]+", source_text)}
    connector_words = {"a", "an", "and", "as", "at", "by", "for", "from", "in", "is", "it", "of", "on", "or", "the", "to", "was", "were", "with", "than", "that", "this", "which", "while", "shows", "showing", "indicates", "indicated", "measured", "measurement", "value", "values", "compared", "comparison", "remains", "observed", "consistent", "suggests", "support", "supports", "supported", "during", "over", "above", "below", "higher", "lower", "positive", "negative", "persistent", "requires", "review", "inspection", "check", "should", "be", "investigated", "system"}
    added_words = {word.lower() for word in re.findall(r"[A-Za-z_]+", text)} - supported_words - connector_words
    if added_words:
        return False, "Explanation contains unsupported descriptive terms: " + ", ".join(sorted(added_words))
    if maintenance_reference["action"] not in text:
        return False, "Explanation changed or omitted the deterministic recommendation"
    return True, "Explanation uses supported finding evidence"


def _generate_explanation(state, mode, client):
    finding = state["finding"]
    summary = state["evidence_summary"]
    reference = state["maintenance_reference"]
    fallback = deterministic_explanation(finding, summary, reference)
    if mode != "openai":
        return {"explanation": fallback, "explanation_mode": "template", "fallback_reason": None}
    if not os.environ.get("OPENAI_API_KEY") and client is None:
        return {"explanation": fallback, "explanation_mode": "template", "fallback_reason": "OPENAI_API_KEY is not configured"}
    try:
        if client is None:
            from openai import OpenAI
            client = OpenAI()
        response = client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0.1,
            messages=[
                {"role": "system", "content": "Rewrite the supplied evidence as a concise engineering explanation. Use only supplied facts. Do not include measurement values, dates, counts, or any other numbers; do not round or restate numbers. Copy affected sensor identifiers exactly, including any digits embedded in their names. Include the system and computed severity, and preserve the exact recommendation verbatim. Do not add a diagnosis, cause, urgency, risk, or action. Use neutral wording about the reported deviation only. A safe style is: '<system> shows a persistent deviation in <sensor>. Severity is <severity>. <exact recommendation>'."},
                {"role": "user", "content": json.dumps({"finding": finding, "evidence_summary": summary, "required_system": finding.get("system"), "required_sensors": finding.get("affected_sensors", []), "computed_severity": finding.get("severity"), "deterministic_recommendation": reference["action"]})},
            ],
        )
        text = response.choices[0].message.content or ""
        return {"explanation": text, "explanation_mode": "openai", "fallback_reason": None}
    except Exception as exc:  # provider errors must not interrupt the bounded workflow
        return {"explanation": fallback, "explanation_mode": "template", "fallback_reason": "OpenAI request failed: {}".format(type(exc).__name__)}


def _validate_node(state):
    result = _generate_explanation(state, state.get("mode", "disabled"), state.get("client"))
    valid, reason = validate_explanation(result["explanation"], state["finding"], state["evidence_summary"], state["maintenance_reference"])
    if not valid:
        result = {"explanation": deterministic_explanation(state["finding"], state["evidence_summary"], state["maintenance_reference"]), "explanation_mode": "template", "fallback_reason": reason}
        valid, reason = validate_explanation(result["explanation"], state["finding"], state["evidence_summary"], state["maintenance_reference"])
    return {**result, "validation": {"valid": valid, "message": reason}}


def _result(state):
    finding = state["finding"]
    return {"result": {"finding_id": finding["finding_id"], "classification": state["classification"], "route": state["maintenance_reference"]["route"], "explanation": state["explanation"], "explanation_mode": state["explanation_mode"], "fallback_reason": state.get("fallback_reason"), "validation": state["validation"], "recommendation": finding.get("recommended_next_action"), "severity": finding.get("severity"), "maintenance_reference": state["maintenance_reference"], "evidence_summary": state["evidence_summary"], "human_review_required": True, "work_order_created": False}}


def build_workflow(mode="disabled", client=None):
    graph = StateGraph(WorkflowState)
    graph.add_node("load_finding", _load_finding)
    graph.add_node("classify", _classify)
    graph.add_node("sensor_path", _sensor_path)
    graph.add_node("machinery_path", _machinery_path)
    graph.add_node("build_evidence", _build_evidence)
    graph.add_node("explain_and_validate", _validate_node)
    graph.add_node("prepare_review", _result)
    graph.add_edge(START, "load_finding")
    graph.add_edge("load_finding", "classify")
    graph.add_conditional_edges("classify", lambda s: s["route"], {"sensor":"sensor_path", "machinery":"machinery_path"})
    graph.add_edge("sensor_path", "build_evidence")
    graph.add_edge("machinery_path", "build_evidence")
    graph.add_edge("build_evidence", "explain_and_validate")
    graph.add_edge("explain_and_validate", "prepare_review")
    graph.add_edge("prepare_review", END)
    return graph.compile(), mode, client


def execute_workflow(finding_id, mode=None, client=None):
    selected_mode = (mode or os.environ.get("LLM_MODE", "disabled")).lower()
    if selected_mode not in ("disabled", "openai"):
        raise ValueError("LLM_MODE must be 'disabled' or 'openai'")
    graph, _, _ = build_workflow(selected_mode, client)
    result = graph.invoke({"finding_id": finding_id, "mode": selected_mode, "client": client})
    return result["result"]
