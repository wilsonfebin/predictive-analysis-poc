import json
import tempfile
import unittest
from pathlib import Path

from src.predictive import (
    InputValidationError, calculate_residuals, detect_machinery, diagnostics,
    evaluate, fit_baselines, sensor_findings, validate_inputs, valid_observation,
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
