import json
import tempfile
import unittest
from pathlib import Path

from src.predictive import (
    InputValidationError, calculate_residuals, detect_machinery, diagnostics,
    evaluate, fit_baselines, run_pipeline, sensor_findings, validate_inputs, valid_observation,
)


def tag(signal="test_temp", system="cooling", unit="degC", low=-20, high=150, criticality="high"):
    return {"tag_id":"T", "signal_name":signal, "description":"test", "equipment_system":system,
            "unit":unit, "valid_min":str(low), "valid_max":str(high), "criticality":criticality}


def row(i, value, quality="GOOD", timestamp=None):
    ts = timestamp or "2026-09-01T{:02d}:{:02d}:00Z".format(i//60, i%60)
    return {"timestamp":ts, "vessel_id":"VESSEL-01", "generator_id":"DG-01",
            "test_temp":str(value), "quality_test_temp":quality}


def context(i, load=50, sea=25, running=True, timestamp=None):
    ts = timestamp or "2026-09-01T{:02d}:{:02d}:00Z".format(i//60, i%60)
    return {"timestamp":ts, "generator_running":str(running).lower(), "generator_load_pct":str(load),
            "engine_speed_rpm":"750" if running else "0", "ambient_air_temp_c":"25", "seawater_temp_c":str(sea)}


class PredictiveTests(unittest.TestCase):
    def test_context_aware_baseline_uses_load_and_seawater_and_filters_data(self):
        t, c = [], []
        for i in range(240):
            load, sea = 20 + i % 60, 20 + i % 10
            # Cooling response is exactly 30 + .4*load + 1.2*sea.
            t.append(row(i, 30 + .4*load + 1.2*sea))
            c.append(context(i, load, sea))
        t[5]["test_temp"] = ""
        t[6]["quality_test_temp"] = "BAD_QUALITY"
        c[7]["generator_running"] = "false"
        tags = [tag()]
        models, counts, rmses = fit_baselines(t, tags, c, {"baseline_start":"2026-09-01T00:00:00Z", "baseline_end_exclusive":"2026-09-02T00:00:00Z", "quality_accepted_for_model":["GOOD"]})
        self.assertEqual(counts["test_temp"], 237)
        self.assertEqual(models["test_temp"]["features"], ["generator_load_pct", "seawater_temp_c"])
        self.assertAlmostEqual(models["test_temp"]["coefficients"][1], .4, places=5)
        self.assertAlmostEqual(models["test_temp"]["coefficients"][2], 1.2, places=5)
        self.assertLess(rmses["test_temp"], 1e-4)

    def test_quality_running_and_out_of_range_are_separate(self):
        t = tag()
        self.assertEqual(valid_observation(row(1, 30), context(1, running=False), t), (False, "STOPPED"))
        self.assertEqual(valid_observation(row(1, "", "MISSING"), context(1), t), (False, "MISSING"))
        self.assertEqual(valid_observation(row(1, 30, "STALE"), context(1), t), (False, "STALE"))
        self.assertEqual(valid_observation(row(1, 151), context(1), t), (False, "OUT_OF_RANGE"))

    def test_persistence_suppresses_spike_but_detects_sustained_deviation(self):
        tags = [tag()]
        contexts = [context(i) for i in range(200)]
        spike = [row(i, 30 if i == 15 else 10) for i in range(200)]
        args = (spike, contexts, tags, {"test_temp":{"features":[],"coefficients":[10]}}, {"test_temp":0},
                {"persistence_window_running_minutes":180,"persistence_required_minutes":120,"minimum_tolerance_by_unit":{"degC":1},"baseline_rmse_multiplier":4}, {"systems":[]})
        self.assertEqual(detect_machinery(*args), [])
        sustained = [row(i, 13 if i >= 20 else 10) for i in range(200)]
        args = (sustained,) + args[1:]
        findings = detect_machinery(*args)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["category"], "machinery_degradation")
        self.assertGreater(findings[0]["detection_timestamp"], findings[0]["start_timestamp"])

    def test_severity_uses_detection_time_and_records_only_later_escalation(self):
        tags = [tag()]
        contexts = [context(i) for i in range(200)]
        telemetry = [row(i, 10 if i < 20 else (13 if i < 140 else 14.5)) for i in range(200)]
        config = {"persistence_window_running_minutes":180,"persistence_required_minutes":120,
                  "minimum_tolerance_by_unit":{"degC":1},"baseline_rmse_multiplier":4}
        args = (telemetry, contexts, tags, {"test_temp":{"features":[],"coefficients":[10]}},
                {"test_temp":0}, config, {"systems":[]})

        at_detection = detect_machinery(telemetry[:140], contexts[:140], *args[2:])[0]
        complete_event = detect_machinery(*args)[0]
        self.assertEqual(at_detection["detection_timestamp"], complete_event["detection_timestamp"])
        self.assertEqual(complete_event["initial_severity"], "medium")
        self.assertEqual(complete_event["initial_severity_evidence"][0]["evaluation_timestamp"], complete_event["detection_timestamp"])
        self.assertEqual(at_detection["severity"], "medium")
        self.assertEqual(at_detection["severity_escalations"], [])
        self.assertEqual(complete_event["severity"], "high")
        self.assertEqual(len(complete_event["severity_escalations"]), 1)
        escalation = complete_event["severity_escalations"][0]
        self.assertGreater(escalation["escalation_timestamp"], complete_event["detection_timestamp"])
        self.assertEqual(escalation["previous_severity"], "medium")
        self.assertEqual(escalation["new_severity"], "high")
        self.assertEqual(escalation["supporting_evidence"]["timestamp"], escalation["escalation_timestamp"])
        self.assertGreaterEqual(escalation["supporting_evidence"]["max_absolute_deviation_ratio"], 4)

    def test_existing_synthetic_findings_start_medium_and_escalate_after_detection(self):
        with tempfile.TemporaryDirectory() as temp:
            result = run_pipeline(output_dir=temp)
        machinery = [f for f in result["findings"] if f["category"] == "machinery_degradation"]
        self.assertEqual([f["finding_id"] for f in machinery], ["MACH-001", "MACH-002", "MACH-003", "MACH-004"])
        self.assertEqual([f["initial_severity"] for f in machinery], ["medium"] * 4)
        self.assertEqual([f["severity"] for f in machinery], ["high"] * 4)
        self.assertEqual([f["detection_timestamp"] for f in machinery], [
            "2026-09-20T15:01:00Z", "2026-09-13T03:50:00Z",
            "2026-09-21T15:01:00Z", "2026-09-17T13:27:00Z",
        ])
        eval_by_scenario = {row["scenario_id"]:row for row in result["evaluation"]}
        self.assertEqual([(eval_by_scenario[s]["fixed_alarm_crossing_timestamp"], eval_by_scenario[s]["predictive_lead_time_minutes"]) for s in ("F-CYL-01", "F-COOL-01", "F-COOL-02", "F-LUBE-01")], [
            ("2026-09-24T11:31:00Z", 5550), ("2026-09-24T12:44:00Z", 16374),
            ("2026-09-23T11:01:00Z", 2640), ("2026-09-24T20:40:00Z", 10513),
        ])
        self.assertEqual(result["summary"]["observation_period"], {"start":"2026-09-01T00:00:00Z", "end":"2026-09-30T23:59:00Z"})
        self.assertTrue(result["summary"]["processed_at"].endswith("Z"))
        recommendations = {f["affected_sensors"][0]:f["recommended_next_action"] for f in machinery}
        self.assertEqual(recommendations["jacket_water_outlet_c"], "Inspect and clean cooling-water cooler")
        self.assertEqual(recommendations["charge_air_temperature_c"], "Inspect charge-air cooler and associated air-side path")
        self.assertEqual(recommendations["lube_oil_pressure_bar"], "Inspect lubrication circuit and renew filter if required")
        self.assertEqual(recommendations["cylinder_07_exhaust_temp_c"], "Inspect cylinder combustion condition")
        for finding in machinery:
            self.assertTrue(finding["severity_escalations"])
            self.assertTrue(all(e["escalation_timestamp"] > finding["detection_timestamp"] for e in finding["severity_escalations"]))
            self.assertEqual(finding["initial_severity_evidence"][0]["evaluation_timestamp"], finding["detection_timestamp"])
            self.assertTrue(all(e["supporting_evidence"]["evaluation_timestamp"] == e["escalation_timestamp"] and e["supporting_evidence"]["max_absolute_deviation_ratio"] >= 4 for e in finding["severity_escalations"]))
        sensor_result = next(row for row in result["evaluation"] if row["scenario_id"] == "F-SENSOR-01")
        self.assertTrue(sensor_result["instrument_check_routed"])
        self.assertFalse(sensor_result["machinery_finding_created"])
        self.assertEqual(result["summary"]["healthy_period_false_machinery_findings"], 0)

    def test_stale_frozen_sensor_routes_to_instrument_check_only(self):
        tags = [tag(signal="test_temp")]
        t = [row(i, 30, "GOOD" if i < 60 else "STALE") for i in range(70)]
        c = [context(i) for i in range(70)]
        diag = diagnostics(t, c, tags, {"sensor_frozen_minimum_running_minutes":60})
        self.assertEqual(diag["test_temp"]["quality_counts"]["STALE"], 10)
        self.assertEqual(diag["test_temp"]["frozen_candidates"][0]["running_minutes"], 60)
        findings = sensor_findings(diag, tags)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["maintenance_route"], "instrument_inspection")
        self.assertFalse(findings[0]["machinery_work_order"])

    def test_evaluation_uses_running_good_alarm_and_predictive_timestamp(self):
        tags = [tag()]
        t, c = [], []
        for i in range(4):
            timestamp = "2026-09-01T00:0{}:00Z".format(i)
            t.append(row(i, 99 if i >= 2 else 10, "GOOD", timestamp))
            c.append(context(i, running=i != 2, timestamp=timestamp))
        scenario = {"scenario_id":"F1","category":"machinery","system":"cooling","affected_signals":["test_temp"],"onset":"2026-09-01T00:00:00Z","alarm":{"signal":"test_temp","operator":">=","value":90}}
        finding = {"category":"machinery_degradation","system":"cooling","affected_sensors":["test_temp"],"detection_timestamp":"2026-09-01T00:01:00Z"}
        result = evaluate(t,c,[scenario],[finding])[0]
        self.assertEqual(result["fixed_alarm_crossing_timestamp"], "2026-09-01T00:03:00Z")
        self.assertEqual(result["predictive_lead_time_minutes"], 2)

    def test_input_validation_reports_timestamp_misalignment(self):
        t = [{"timestamp":"2026-09-01T00:00:00Z","vessel_id":"V","generator_id":"G","test_temp":"1","quality_test_temp":"GOOD"}]
        c = [{"timestamp":"2026-09-01T00:01:00Z","generator_running":"true","generator_load_pct":"1","engine_speed_rpm":"1","ambient_air_temp_c":"1","seawater_temp_c":"1"}]
        with self.assertRaisesRegex(InputValidationError, "Timestamp misalignment"):
            validate_inputs(t,[tag()],c,{"systems":[]})


if __name__ == "__main__":
    unittest.main()
