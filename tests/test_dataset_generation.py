import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.generate_dataset import MINUTES, generate


class DatasetGenerationTests(unittest.TestCase):
    def test_outputs_schema_timestamps_quality_and_ground_truth_separation(self):
        with tempfile.TemporaryDirectory() as tmp:
            generate(tmp, 42)
            root = Path(tmp)
            with (root / "telemetry.csv").open() as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            with (root / "context.csv").open() as f:
                context = list(csv.DictReader(f))
            with (root / "tags.csv").open() as f:
                tags = list(csv.DictReader(f))
            truth = json.loads((root / "ground_truth.json").read_text())
            self.assertEqual(len(rows), MINUTES)
            self.assertEqual(len(context), MINUTES)
            self.assertEqual(len(tags), 36)
            tag_systems = {t["signal_name"]: t["equipment_system"] for t in tags}
            self.assertEqual(tag_systems["charge_air_temperature_c"], "cooling")
            times = [r["timestamp"] for r in rows]
            self.assertEqual(len(set(times)), MINUTES)
            self.assertEqual(times[0], "2026-09-01T00:00:00Z")
            self.assertEqual(times[-1], "2026-09-30T23:59:00Z")
            self.assertEqual([r["timestamp"] for r in rows], [r["timestamp"] for r in context])
            self.assertIn("cylinder_16_exhaust_temp_c", rows[0])
            self.assertNotIn("fault_scenarios", rows[0])
            self.assertEqual(len(truth["fault_scenarios"]), 5)
            for scenario in truth["fault_scenarios"]:
                for signal in scenario["affected_signals"]:
                    self.assertEqual(tag_systems[signal], scenario["system"], scenario["scenario_id"] + " system must match tag metadata")
            self.assertTrue(any(r["generator_running"] == "false" for r in context))
            self.assertTrue(any(q != "GOOD" for r in rows for q in [r["quality_lube_oil_pressure_bar"], r["quality_jacket_water_outlet_c"]]))
            running = {r["timestamp"]: r["generator_running"] == "true" for r in context}
            for scenario in truth["fault_scenarios"]:
                alarm = scenario["alarm"]
                if alarm is None:
                    continue
                crossings = [r["timestamp"] for r in rows
                             if r["timestamp"] >= scenario["onset"] and running[r["timestamp"]]
                             and r["quality_" + alarm["signal"]] == "GOOD"
                             and r[alarm["signal"]] != ""
                             and ((alarm["operator"] == ">=" and float(r[alarm["signal"]]) >= alarm["value"])
                                  or (alarm["operator"] == "<=" and float(r[alarm["signal"]]) <= alarm["value"]))]
                self.assertTrue(crossings, scenario["scenario_id"] + " must cross its alarm while running")
                self.assertGreater(crossings[0], scenario["onset"], scenario["scenario_id"] + " must progress before alarm")

    def test_same_seed_produces_identical_outputs(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            generate(a, 7); generate(b, 7)
            for name in ("telemetry.csv", "context.csv", "tags.csv", "ground_truth.json", "maintenance_reference.json"):
                self.assertEqual((Path(a)/name).read_bytes(), (Path(b)/name).read_bytes())


if __name__ == "__main__":
    unittest.main()
