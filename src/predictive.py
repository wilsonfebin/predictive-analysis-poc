"""Dependency-free deterministic Phase 2 CBM pipeline for the synthetic POC."""
import csv
import gzip
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


BASELINE_START = "2026-09-01T00:00:00Z"
BASELINE_END = "2026-09-07T00:00:00Z"
REQUIRED_TELEMETRY = {"timestamp", "vessel_id", "generator_id"}
REQUIRED_CONTEXT = {"timestamp", "generator_running", "generator_load_pct", "engine_speed_rpm", "ambient_air_temp_c", "seawater_temp_c"}
QUALITY = {"GOOD", "MISSING", "BAD_SPIKE", "BAD_QUALITY", "UNCERTAIN", "STALE"}


class InputValidationError(ValueError):
    """Raised when input structure or required values cannot be interpreted."""


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def parse_time(value):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError) as exc:
        raise InputValidationError("Invalid ISO-8601 timestamp: {!r}".format(value)) from exc


def load_inputs(data_dir):
    root = Path(data_dir)
    telemetry = read_csv(root / "telemetry.csv")
    tags = read_csv(root / "tags.csv")
    context = read_csv(root / "context.csv")
    maintenance = json.loads((root / "maintenance_reference.json").read_text(encoding="utf-8"))
    validate_inputs(telemetry, tags, context, maintenance)
    return telemetry, tags, context, maintenance


def validate_inputs(telemetry, tags, context, maintenance):
    errors = []
    if not telemetry or not context:
        raise InputValidationError("Telemetry and context must both contain rows")
    telemetry_cols, context_cols = set(telemetry[0]), set(context[0])
    if missing := REQUIRED_TELEMETRY - telemetry_cols:
        errors.append("telemetry.csv missing columns: " + ", ".join(sorted(missing)))
    if missing := REQUIRED_CONTEXT - context_cols:
        errors.append("context.csv missing columns: " + ", ".join(sorted(missing)))
    tag_names = [t.get("signal_name", "") for t in tags]
    if len(set(tag_names)) != len(tag_names) or not tag_names:
        errors.append("tags.csv signal_name values must be present and unique")
    for name in tag_names:
        if name not in telemetry_cols or "quality_" + name not in telemetry_cols:
            errors.append("telemetry.csv missing signal or quality column for " + name)
    if len(telemetry) != len(context):
        errors.append("telemetry/context row counts differ: {} vs {}".format(len(telemetry), len(context)))
    if not errors:
        last = None
        for i, (trow, crow) in enumerate(zip(telemetry, context)):
            try:
                ts = parse_time(trow["timestamp"])
                cts = parse_time(crow["timestamp"])
                if ts != cts:
                    errors.append("Timestamp misalignment at row {}".format(i + 2)); break
                if last is not None and ts - last != timedelta(minutes=1):
                    errors.append("Expected one-minute timestamp interval at row {}".format(i + 2)); break
                last = ts
                for col in ("generator_load_pct", "engine_speed_rpm", "ambient_air_temp_c", "seawater_temp_c"):
                    float(crow[col])
                if crow["generator_running"] not in ("true", "false"):
                    errors.append("Invalid generator_running value at row {}".format(i + 2)); break
            except (InputValidationError, ValueError, KeyError) as exc:
                errors.append("Invalid required input at row {}: {}".format(i + 2, exc)); break
        for t in tags:
            try:
                if float(t["valid_min"]) >= float(t["valid_max"]):
                    raise ValueError("minimum must be below maximum")
            except (ValueError, KeyError) as exc:
                errors.append("Invalid valid range for {}: {}".format(t.get("signal_name"), exc))
    if not isinstance(maintenance, dict) or not isinstance(maintenance.get("systems"), list):
        errors.append("maintenance_reference.json requires a systems list")
    if errors:
        raise InputValidationError("Input validation failed:\n- " + "\n- ".join(errors))


def _solve(matrix, target):
    """Gauss-Jordan solution with pivoting for a tiny normal-equation system."""
    n = len(target)
    a = [list(matrix[i]) + [target[i]] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-12:
            a[col][col] += 1e-8
            pivot = col
        a[col], a[pivot] = a[pivot], a[col]
        div = a[col][col]
        a[col] = [x / div for x in a[col]]
        for row in range(n):
            if row == col:
                continue
            factor = a[row][col]
            a[row] = [a[row][j] - factor * a[col][j] for j in range(n + 1)]
    return [a[i][-1] for i in range(n)]


def _feature_names(signal, system):
    if system == "operating_context" or signal == "generator_load_pct":
        return []
    features = ["generator_load_pct"]
    if system == "cooling" and signal != "seawater_inlet_c":
        features.append("seawater_temp_c")
    elif signal in ("lube_oil_temperature_c", "charge_air_temperature_c", "exhaust_receiver_temp_c"):
        features.append("ambient_air_temp_c")
    return features


def _design(row, features):
    return [1.0] + [float(row[name]) for name in features]


def fit_baselines(telemetry, tags, context, config):
    """Fit per-signal OLS on quality-valid running observations from the fixed past window."""
    tag_by_signal = {t["signal_name"]: t for t in tags}
    models, counts, rmses = {}, {}, {}
    accepted = set(config.get("quality_accepted_for_model", ["GOOD"]))
    baseline_start = config.get("baseline_start", BASELINE_START)
    baseline_end = config.get("baseline_end_exclusive", BASELINE_END)
    for signal, tag in tag_by_signal.items():
        features = _feature_names(signal, tag["equipment_system"])
        x_rows, ys = [], []
        for row, ctx in zip(telemetry, context):
            if not (baseline_start <= row["timestamp"] < baseline_end) or ctx["generator_running"] != "true":
                continue
            try:
                y = float(row[signal])
                if row["quality_" + signal] not in accepted or not float(tag["valid_min"]) <= y <= float(tag["valid_max"]):
                    continue
                x_rows.append(_design(ctx, features)); ys.append(y)
            except (ValueError, TypeError):
                continue
        if len(ys) < len(features) + 5:
            continue
        dim = len(features) + 1
        matrix = [[sum(x[i] * x[j] for x in x_rows) for j in range(dim)] for i in range(dim)]
        target = [sum(x[i] * y for x, y in zip(x_rows, ys)) for i in range(dim)]
        coeffs = _solve(matrix, target)
        residuals = [y - sum(a * b for a, b in zip(x, coeffs)) for x, y in zip(x_rows, ys)]
        models[signal] = {"features": features, "coefficients": coeffs}
        counts[signal] = len(ys)
        rmses[signal] = math.sqrt(sum(r * r for r in residuals) / len(residuals))
    return models, counts, rmses


def valid_observation(row, context, tag):
    if context["generator_running"] != "true":
        return False, "STOPPED"
    quality = row.get("quality_" + tag["signal_name"], "MISSING")
    if quality != "GOOD":
        return False, quality if quality in QUALITY else "UNKNOWN_QUALITY"
    try:
        value = float(row[tag["signal_name"]])
    except (ValueError, TypeError):
        return False, "MISSING"
    if not float(tag["valid_min"]) <= value <= float(tag["valid_max"]):
        return False, "OUT_OF_RANGE"
    return True, "GOOD"


def diagnostics(telemetry, context, tags, config):
    """Aggregate quality issues and detect persistent flatline behavior with evidence."""
    result = {}
    min_flat = int(config.get("sensor_frozen_minimum_running_minutes", 60))
    for tag in tags:
        signal = tag["signal_name"]
        counts = Counter()
        first_last = {}
        run_count, run_start, run_value = 0, None, None
        flat_runs = []
        prev_value = object()
        for row, ctx in zip(telemetry, context):
            ok, status = valid_observation(row, ctx, tag)
            if status != "STOPPED":
                counts[status] += 1
                if status not in first_last:
                    first_last[status] = {"first_timestamp": row["timestamp"]}
                first_last[status]["last_timestamp"] = row["timestamp"]
            if ctx["generator_running"] != "true" or not ok:
                if run_count >= min_flat:
                    flat_runs.append({"start_timestamp": run_start, "end_timestamp": row["timestamp"], "running_minutes": run_count, "constant_value": run_value})
                run_count, run_start, run_value = 0, None, None
                continue
            value = float(row[signal])
            if run_count == 0:
                run_start, run_value, run_count = row["timestamp"], value, 1
            elif value == run_value:
                run_count += 1
            else:
                if run_count >= min_flat:
                    flat_runs.append({"start_timestamp": run_start, "end_timestamp": row["timestamp"], "running_minutes": run_count, "constant_value": run_value})
                run_start, run_value, run_count = row["timestamp"], value, 1
        if run_count >= min_flat:
            flat_runs.append({"start_timestamp": run_start, "end_timestamp": telemetry[-1]["timestamp"], "running_minutes": run_count, "constant_value": run_value})
        result[signal] = {"quality_counts": dict(counts), "quality_period": first_last, "frozen_candidates": flat_runs}
    return result


def calculate_residuals(telemetry, context, tags, models, rmse, config, output_path):
    """Stream residual records to gzip CSV to keep the 1.5m row output compact."""
    tag_by_signal = {t["signal_name"]: t for t in tags}
    thresholds = config.get("minimum_tolerance_by_unit", {})
    tolerance = {}
    with gzip.open(output_path, "wt", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "signal", "actual", "expected", "residual", "normalised_deviation", "quality_status", "operating_state"])
        for row, ctx in zip(telemetry, context):
            running = ctx["generator_running"] == "true"
            for signal, tag in tag_by_signal.items():
                model = models.get(signal)
                ok, status = valid_observation(row, ctx, tag)
                if not model:
                    if not running:
                        continue
                    w.writerow([row["timestamp"], signal, row[signal], "", "", "", status, "RUNNING"])
                    continue
                if not running:
                    continue
                actual = row[signal]
                if not ok:
                    w.writerow([row["timestamp"], signal, actual, "", "", "", status, "RUNNING"])
                    continue
                expected = sum(a*b for a, b in zip(_design(ctx, model["features"]), model["coefficients"]))
                residual = float(actual) - expected
                tol = max(float(thresholds.get(tag["unit"], 1.0)), float(config.get("baseline_rmse_multiplier", 4.0)) * rmse.get(signal, 0.0))
                tolerance[signal] = tol
                w.writerow([row["timestamp"], signal, actual, round(expected, 6), round(residual, 6), round(residual/tol, 6) if tol else "", "GOOD", "RUNNING"])
    return tolerance


def _severity(tag, max_ratio, count, required):
    if max_ratio >= 4 or tag.get("criticality") == "high" and count >= required * 2:
        return "high"
    if max_ratio >= 2 or tag.get("criticality") in ("high", "medium"):
        return "medium"
    return "low"


def _severity_assessment(tag, points, tolerance, required, evaluation_timestamp):
    """Assess severity from evidence available at one timestamp only."""
    max_point = max(points, key=lambda point: abs(point[3]) / tolerance, default=None)
    max_ratio = abs(max_point[3]) / tolerance if max_point and tolerance else 0.0
    severity = _severity(tag, max_ratio, len(points), required)
    evidence = {
        "signal": tag["signal_name"],
        "unit": tag["unit"],
        "criticality": tag.get("criticality", "unknown"),
        "qualifying_observation_count": len(points),
        "tolerance": round(tolerance, 6),
        "max_absolute_deviation_ratio": round(max_ratio, 6),
        "evaluation_timestamp": evaluation_timestamp,
        "rule": "High if ratio >= 4 or high-criticality count >= {}; Medium if ratio >= 2 or criticality is high/medium; otherwise Low.".format(required * 2),
    }
    if max_point:
        evidence.update({
            "timestamp": max_point[0],
            "actual": round(max_point[1], 6),
            "expected": round(max_point[2], 6),
            "residual": round(max_point[3], 6),
        })
    return severity, evidence


def detect_machinery(telemetry, context, tags, models, rmses, config, maintenance):
    window = int(config.get("persistence_window_running_minutes", 180))
    required = int(config.get("persistence_required_minutes", 120))
    min_tols = config.get("minimum_tolerance_by_unit", {})
    grouping_gap = int(config.get("grouping_gap_minutes", 60))
    raw_events = []
    for tag in tags:
        signal, system = tag["signal_name"], tag["equipment_system"]
        if system == "operating_context" or signal == "generator_load_pct" or signal not in models:
            continue
        tol = max(float(min_tols.get(tag["unit"], 1.0)), float(config.get("baseline_rmse_multiplier", 4.0)) * rmses.get(signal, 0.0))
        history = []
        active_start = None
        active_detection = None
        active_rows = []
        active_initial_severity = None
        active_initial_evidence = None
        active_severity = None
        active_escalations = []

        def finish_event():
            if active_start is None:
                return
            raw_events.append({
                "tag": tag, "start": active_start, "points": active_rows[:], "tolerance": tol,
                "detection_time": active_detection, "initial_severity": active_initial_severity,
                "initial_severity_evidence": active_initial_evidence,
                "severity": active_severity, "severity_escalations": active_escalations[:],
            })

        for row, ctx in zip(telemetry, context):
            if ctx["generator_running"] != "true":
                continue
            ok, _ = valid_observation(row, ctx, tag)
            if not ok:
                history.append(None)
                history = history[-window:]
                continue
            model = models[signal]
            expected = sum(a*b for a, b in zip(_design(ctx, model["features"]), model["coefficients"]))
            actual = float(row[signal]); residual = actual - expected
            direction = 1 if residual > tol else (-1 if residual < -tol else 0)
            history.append((row["timestamp"], actual, expected, residual, direction))
            history = history[-window:]
            qualifying = [x for x in history if x and x[4] != 0]
            dirs = Counter(x[4] for x in qualifying)
            persistent = max(dirs.values(), default=0) >= required
            if persistent and active_start is None:
                predominant = dirs.most_common(1)[0][0]
                selected = [x for x in qualifying if x[4] == predominant]
                active_start = selected[0][0]
                active_detection = row["timestamp"]
                active_rows = selected[:]
                active_initial_severity, active_initial_evidence = _severity_assessment(tag, selected, tol, required, row["timestamp"])
                active_severity = active_initial_severity
                active_escalations = []
            elif persistent and active_start is not None:
                active_rows = [x for x in history if x and x[4] != 0]

            if active_start is not None and row["timestamp"] != active_detection:
                latest_severity, severity_evidence = _severity_assessment(tag, qualifying, tol, required, row["timestamp"])
                ranks = {"low": 0, "medium": 1, "high": 2}
                if ranks[latest_severity] > ranks[active_severity]:
                    previous = active_severity
                    active_severity = latest_severity
                    ratio = severity_evidence["max_absolute_deviation_ratio"]
                    active_escalations.append({
                        "previous_severity": previous,
                        "new_severity": latest_severity,
                        "escalation_timestamp": row["timestamp"],
                        "supporting_evidence": severity_evidence,
                        "reason": "The {} severity rule was crossed at {:.3f}x the configured residual tolerance.".format(latest_severity.title(), ratio),
                    })

            if not persistent and active_start is not None:
                # Keep a continuous event alive unless the rolling evidence clears.
                if not qualifying:
                    finish_event()
                    active_start, active_detection, active_rows = None, None, []
                    active_initial_severity, active_initial_evidence = None, None
                    active_severity, active_escalations = None, []
        if active_start is not None:
            finish_event()
    # Merge overlapping events from related signals in one system; do not merge categories.
    groups = []
    for event in sorted(raw_events, key=lambda e: (e["tag"]["equipment_system"], e["start"])):
        tag, start = event["tag"], event["start"]
        st = parse_time(start)
        match = next((g for g in groups if g["system"] == tag["equipment_system"] and abs((st-g["last_start"]).total_seconds()) <= grouping_gap*60), None)
        if match is None:
            match = {"system": tag["equipment_system"], "last_start": st, "events": []}; groups.append(match)
        match["events"].append(event)
        match["last_start"] = max(match["last_start"], st)
    systems = {s["system"]: s for s in maintenance.get("systems", [])}
    inventory = {p["part_id"]: p for p in maintenance.get("inventory", [])}
    findings = []
    for i, group in enumerate(groups, 1):
        all_points = [(e["tag"], point, e["tolerance"]) for e in group["events"] for point in e["points"]]
        tags_in = [e["tag"] for e in group["events"]]
        evidence = []
        for tag in tags_in:
            points = next(e["points"] for e in group["events"] if e["tag"] is tag)
            if not points:
                continue
            latest = points[-1]
            evidence.append({"signal": tag["signal_name"], "actual": round(latest[1], 4), "expected": round(latest[2], 4), "deviation": round(latest[3], 4), "unit": tag["unit"], "persistence_valid_minutes": len(points)})
        names = [t["signal_name"] for t in tags_in]
        ref = systems.get(group["system"], {})
        signal_actions = ref.get("signal_maintenance_actions", {})
        action = next((signal_actions[name] for name in names if name in signal_actions), None)
        action = action or (ref.get("maintenance_actions") or [{"description": "Inspect {} system".format(group["system"]), "spares": []}])[0]
        parts = [{"part_id": part, "available": inventory.get(part, {}).get("quantity_available", 0)} for part in action.get("spares", [])]
        start = min(e["start"] for e in group["events"])
        end = max((p[0] for _, p, _ in all_points), default=start)
        finding_id = "MACH-{0:03d}".format(i)
        explanation = "Persistent deviation in {} on {} signal(s), supported by {} valid observations.".format(group["system"], ", ".join(names), sum(e["persistence_valid_minutes"] for e in evidence))
        detection_time = min(e["detection_time"] for e in group["events"])
        ranks = {"low": 0, "medium": 1, "high": 2}
        initial_events = [e for e in group["events"] if e["detection_time"] == detection_time]
        initial_severity = max((e["initial_severity"] for e in initial_events), key=lambda v: ranks[v])
        initial_severity_evidence = [dict(e["initial_severity_evidence"]) for e in initial_events]
        current_severity = initial_severity
        escalations = []
        timeline = []
        for event in group["events"]:
            if event["detection_time"] > detection_time:
                timeline.append((event["detection_time"], event["initial_severity"], event["initial_severity_evidence"], None))
            for escalation in event["severity_escalations"]:
                timeline.append((escalation["escalation_timestamp"], escalation["new_severity"], escalation["supporting_evidence"], escalation["reason"]))
        for timestamp, new_severity, supporting, reason in sorted(timeline, key=lambda item: item[0]):
            if ranks[new_severity] <= ranks[current_severity]:
                continue
            previous = current_severity
            current_severity = new_severity
            escalations.append({
                "finding_id": finding_id,
                "previous_severity": previous,
                "new_severity": new_severity,
                "escalation_timestamp": timestamp,
                "supporting_evidence": supporting,
                "reason": reason or "A newly grouped signal met the configured {} severity rule at its first detection.".format(new_severity.title()),
            })
        for escalation in escalations:
            escalation["finding_id"] = finding_id
        findings.append({"finding_id": finding_id, "vessel_id": "VESSEL-01", "equipment_id": "DG-01", "system": group["system"], "affected_sensors": names, "category": "machinery_degradation", "start_timestamp": start, "end_timestamp": end, "detection_timestamp": detection_time, "actual_value": evidence[0]["actual"] if len(evidence)==1 else None, "expected_value": evidence[0]["expected"] if len(evidence)==1 else None, "deviation": evidence[0]["deviation"] if len(evidence)==1 else None, "initial_severity": initial_severity, "initial_severity_evidence": initial_severity_evidence, "severity": current_severity, "severity_escalations": escalations, "detection_evidence": evidence, "explanation": explanation, "recommended_next_action": action.get("description", "Inspect affected system"), "spare_parts": parts, "provenance": "synthetic"})
    return findings


def sensor_findings(diag, tags):
    tagmap = {t["signal_name"]: t for t in tags}
    findings = []
    for signal, info in diag.items():
        tag = tagmap[signal]
        counts, periods = info["quality_counts"], info["quality_period"]
        for status in ("STALE", "MISSING", "OUT_OF_RANGE", "BAD_SPIKE", "BAD_QUALITY", "UNCERTAIN"):
            count = counts.get(status, 0)
            frozen = info["frozen_candidates"]
            if not count and not (status == "STALE" and frozen):
                continue
            # Isolated explicitly bad/uncertain records are retained in diagnostic summaries,
            # but do not each become maintenance findings.
            if status in ("BAD_SPIKE", "BAD_QUALITY", "UNCERTAIN"):
                continue
            first_last = periods.get(status, {})
            finding_id = "SENS-{0:03d}".format(len(findings)+1)
            if status == "STALE" and frozen:
                reason = "Stale quality flag coincides with a sustained frozen-value candidate."
                recommended = "Check transmitter, wiring and signal freshness; compare with an independent measurement."
            elif status == "MISSING":
                reason = "Missing telemetry values were explicitly excluded from machinery scoring."
                recommended = "Check instrument signal availability and data acquisition path."
            else:
                reason = "Out-of-range or stale observations were excluded from machinery scoring."
                recommended = "Inspect instrument and verify the measurement independently."
            findings.append({"finding_id": finding_id, "vessel_id": "VESSEL-01", "equipment_id": "DG-01", "system": tag["equipment_system"], "affected_sensors": [signal], "category": "sensor_fault", "start_timestamp": first_last.get("first_timestamp", frozen[0]["start_timestamp"] if frozen else None), "end_timestamp": first_last.get("last_timestamp"), "severity": "medium" if status == "STALE" else "low", "detection_evidence": {"quality_status": status, "count": count, "quality_period": first_last, "frozen_candidates": frozen}, "explanation": reason, "recommended_next_action": recommended, "maintenance_route": "instrument_inspection", "machinery_work_order": False, "provenance": "synthetic"})
            # Only create one summary finding per signal/status, not one per row.
            if status == "STALE" and frozen:
                break
    return findings


def evaluate(telemetry, context, scenarios, findings):
    """Ground truth is read only here, after models/detections are complete."""
    output = []
    for scenario in scenarios:
        alarm = scenario.get("alarm")
        crossing = None
        if alarm:
            signal = alarm["signal"]
            for row, ctx in zip(telemetry, context):
                if row["timestamp"] < scenario["onset"] or ctx["generator_running"] != "true" or row.get("quality_"+signal) != "GOOD":
                    continue
                try:
                    value = float(row[signal])
                except (ValueError, TypeError):
                    continue
                if alarm["operator"] == ">=" and value >= float(alarm["value"]) or alarm["operator"] == "<=" and value <= float(alarm["value"]):
                    crossing = row["timestamp"]; break
        related = [f for f in findings if f["category"] == "machinery_degradation" and set(scenario["affected_signals"]) & set(f["affected_sensors"])]
        system_match = any(f["system"] == scenario["system"] for f in related)
        detected = min((f["detection_timestamp"] for f in related if f.get("detection_timestamp")), default=None)
        if scenario["category"] == "sensor_fault":
            related_sensor = [f for f in findings if f["category"] == "sensor_fault" and set(scenario["affected_signals"]) & set(f["affected_sensors"])]
            output.append({"scenario_id": scenario["scenario_id"], "category": "sensor_fault", "sensor_issue_detected": bool(related_sensor), "instrument_check_routed": bool(related_sensor and all(f.get("maintenance_route")=="instrument_inspection" and not f.get("machinery_work_order") for f in related_sensor)), "machinery_finding_created": bool(related), "first_predictive_detection_timestamp": min((f["start_timestamp"] for f in related_sensor if f.get("start_timestamp")), default=None), "provenance": "synthetic"})
            continue
        lead = None
        if detected and crossing:
            lead = int((parse_time(crossing)-parse_time(detected)).total_seconds()/60)
        output.append({"scenario_id": scenario["scenario_id"], "category": "machinery", "first_predictive_detection_timestamp": detected, "fixed_alarm_crossing_timestamp": crossing, "predictive_lead_time_minutes": lead, "detected_before_alarm": bool(lead is not None and lead > 0), "missed_detection": detected is None, "scenario_tag_system_match": system_match, "provenance": "synthetic"})
    return output


def run_pipeline(data_dir="data", output_dir="reports", config_path="config/detection.json"):
    telemetry, tags, context, maintenance = load_inputs(data_dir)
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    # The ground-truth file is deliberately opened only after fitting/detection.
    models, baseline_counts, rmses = fit_baselines(telemetry, tags, context, config)
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    tolerances = calculate_residuals(telemetry, context, tags, models, rmses, config, out / "residuals.csv.gz")
    machinery = detect_machinery(telemetry, context, tags, models, rmses, config, maintenance)
    diagnostics_by_signal = diagnostics(telemetry, context, tags, config)
    sensors = sensor_findings(diagnostics_by_signal, tags)
    findings = machinery + sensors
    ground_truth = json.loads((Path(data_dir) / "ground_truth.json").read_text(encoding="utf-8"))
    evaluation = evaluate(telemetry, context, ground_truth["fault_scenarios"], findings)
    healthy_false = [f for f in machinery if f["start_timestamp"] < BASELINE_END]
    transitions = sum(1 for i in range(len(context)-30) if context[i]["timestamp"] < BASELINE_END and context[i]["generator_running"] == "true" and context[i+30]["generator_running"] == "true" and abs(float(context[i+30]["generator_load_pct"])-float(context[i]["generator_load_pct"])) >= 10)
    context_by_time = {c["timestamp"]: c for c in context}
    telemetry_by_time = {r["timestamp"]: r for r in telemetry}
    bad_quality_findings = 0
    stopped_detection_findings = 0
    for finding in machinery:
        detection_time = finding.get("detection_timestamp")
        context_row = context_by_time.get(detection_time, {})
        telemetry_row = telemetry_by_time.get(detection_time, {})
        if context_row.get("generator_running") != "true":
            stopped_detection_findings += 1
        if any(telemetry_row.get("quality_"+signal) != "GOOD" for signal in finding["affected_sensors"]):
            bad_quality_findings += 1
    bad_spike_times = {r["timestamp"] for r in telemetry if any(r.get("quality_"+t["signal_name"]) == "BAD_SPIKE" for t in tags)}
    spike_detection_findings = sum(f.get("detection_timestamp") in bad_spike_times for f in machinery)
    summary = {"provenance": "synthetic", "asset": "DG-01", "vessel": "VESSEL-01", "input_rows": len(telemetry), "sensor_count": len(tags), "observation_period": {"start": telemetry[0]["timestamp"], "end": telemetry[-1]["timestamp"]}, "processed_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"), "baseline_period": {"start": BASELINE_START, "end_exclusive": BASELINE_END}, "baseline_training_rows_by_signal": baseline_counts, "model_type": "per-signal ordinary least squares; load context plus seawater temperature for cooling and ambient temperature for selected temperatures", "detection_configuration": config, "model_count": len(models), "tolerance_by_signal": tolerances, "machinery_finding_count": len(machinery), "sensor_finding_count": len(sensors), "healthy_period_false_machinery_findings": len(healthy_false), "healthy_30min_load_transitions_ge_10pp": transitions, "quality_issue_counts_by_signal": {s:v["quality_counts"] for s,v in diagnostics_by_signal.items()}, "stopped_rows_excluded_from_machinery_detection": sum(c["generator_running"] != "true" for c in context), "limitations": ["Synthetic illustrative relationships and alarms are not validated marine-engineering models.", "OLS and residual tolerance settings are intentionally simple and need validation against real telemetry.", "Reference alarms are fixed thresholds only for benchmark timing; they are not detection thresholds."]}
    for name, payload in (("findings.json", findings), ("diagnostics.json", diagnostics_by_signal), ("evaluation.json", {"provenance":"synthetic", "scenario_results":evaluation, "healthy_period_false_machinery_findings":len(healthy_false), "healthy_load_transition_machinery_findings":len([f for f in machinery if f["start_timestamp"] < BASELINE_END]), "isolated_spike_machinery_findings":spike_detection_findings, "stopped_period_machinery_findings":stopped_detection_findings, "poor_quality_machinery_findings":bad_quality_findings}), ("processing_summary.json", summary)):
        (out/name).write_text(json.dumps(payload, indent=2)+"\n", encoding="utf-8")
    return {"findings": findings, "evaluation": evaluation, "summary": summary, "diagnostics": diagnostics_by_signal}


if __name__ == "__main__":
    result = run_pipeline()
    print(json.dumps({"machinery_findings": result["summary"]["machinery_finding_count"], "sensor_findings": result["summary"]["sensor_finding_count"], "evaluation": result["evaluation"]}, indent=2))
