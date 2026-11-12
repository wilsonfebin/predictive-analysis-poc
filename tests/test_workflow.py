import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from src.workflow import execute_workflow, validate_explanation


ROOT = Path(__file__).resolve().parents[1]
FINDINGS = json.loads((ROOT / "reports" / "findings.json").read_text())
MACHINERY_ID = next(f["finding_id"] for f in FINDINGS if f["category"] == "machinery_degradation")
SENSOR_ID = next(f["finding_id"] for f in FINDINGS if f["category"] == "sensor_fault")


class FakeCompletion:
    def __init__(self, text=None, error=None):
        self.text, self.error = text, error

    def create(self, **kwargs):
        if self.error:
            raise self.error
        return type("Response", (), {"choices":[type("Choice", (), {"message":type("Message", (), {"content":self.text})()})()]})()


class FakeClient:
    def __init__(self, text=None, error=None):
        self.chat = type("Chat", (), {"completions":FakeCompletion(text, error)})()


class WorkflowTests(unittest.TestCase):
    def test_machinery_routes_to_maintenance_reference(self):
        result = execute_workflow(MACHINERY_ID, mode="disabled")
        self.assertEqual(result["classification"], "machinery")
        self.assertEqual(result["route"], "machinery_inspection")
        self.assertTrue(result["maintenance_reference"]["action"])
        self.assertFalse(result["work_order_created"])
        self.assertTrue(result["human_review_required"])
        self.assertTrue(result["validation"]["valid"])

    def test_each_machinery_scenario_uses_signal_specific_maintenance_reference(self):
        expected = {
            "jacket_water_outlet_c":("Inspect and clean cooling-water cooler", {"GASKET-COOL-01", "FILTER-SW-01"}),
            "charge_air_temperature_c":("Inspect charge-air cooler and associated air-side path", {"GASKET-CHARGE-AIR-01", "SEAL-CHARGE-AIR-01"}),
            "lube_oil_pressure_bar":("Inspect lubrication circuit and renew filter if required", {"FILTER-LO-01"}),
            "cylinder_07_exhaust_temp_c":("Inspect cylinder combustion condition", {"INJECTOR-SEAL-01"}),
        }
        for signal, (action, spare_ids) in expected.items():
            finding_id = next(f["finding_id"] for f in FINDINGS if signal in f.get("affected_sensors", []))
            result = execute_workflow(finding_id, mode="disabled")
            self.assertEqual(result["maintenance_reference"]["action"], action)
            self.assertEqual({p["part_id"] for p in result["maintenance_reference"]["spare_parts"]}, spare_ids)

    def test_sensor_fault_routes_to_instrument_check_without_work_order(self):
        result = execute_workflow(SENSOR_ID, mode="disabled")
        self.assertEqual(result["classification"], "sensor")
        self.assertEqual(result["route"], "instrument_inspection")
        self.assertFalse(result["work_order_created"])
        self.assertEqual(result["maintenance_reference"]["spare_parts"], [])

    def test_openai_missing_key_and_provider_failure_fall_back(self):
        with patch.dict(os.environ, {"LLM_MODE":"openai"}, clear=False):
            os.environ.pop("OPENAI_API_KEY", None)
            no_key = execute_workflow(MACHINERY_ID, mode="openai")
            failed = execute_workflow(MACHINERY_ID, mode="openai", client=FakeClient(error=RuntimeError("offline")))
        for result in (no_key, failed):
            self.assertEqual(result["explanation_mode"], "template")
            self.assertIn("Inspect", result["recommendation"])
            self.assertTrue(result["validation"]["valid"])
        self.assertEqual(no_key["recommendation"], failed["recommendation"])
        self.assertEqual(no_key["severity"], failed["severity"])

    def test_valid_openai_rewrite_uses_safe_paraphrase_without_numbers(self):
        template_result = execute_workflow(MACHINERY_ID, mode="disabled")
        finding = next(f for f in FINDINGS if f["finding_id"] == MACHINERY_ID)
        response = FakeClient(text="The {} system shows a persistent deviation in {}. Severity is {}. {}".format(
            template_result["evidence_summary"]["system"],
            finding["affected_sensors"][0],
            template_result["severity"],
            template_result["recommendation"],
        ))
        result = execute_workflow(MACHINERY_ID, mode="openai", client=response)
        self.assertEqual(result["explanation_mode"], "openai")
        self.assertNotEqual(result["explanation"], template_result["explanation"])
        self.assertEqual(result["recommendation"], template_result["recommendation"])
        self.assertEqual(result["severity"], template_result["severity"])
        self.assertEqual(result["evidence_summary"], template_result["evidence_summary"])
        self.assertTrue(result["validation"]["valid"])

    def test_unsupported_numeric_claim_is_rejected(self):
        f = next(x for x in FINDINGS if x["category"] == "machinery_degradation")
        summary = {"finding_id":f["finding_id"],"signals":"test evidence"}
        ref = {"action":"Inspect test system"}
        sensor = f["affected_sensors"][0]
        ok, reason = validate_explanation("{} {} severity {} reading is 9999. Inspect test system".format(f["system"], sensor, f["severity"]), f, summary, ref)
        self.assertFalse(ok)
        self.assertIn("number", reason)

    def test_unsupported_factual_claim_is_rejected(self):
        f = next(x for x in FINDINGS if x["category"] == "machinery_degradation")
        summary = {"finding_id":f["finding_id"],"signals":"test evidence"}
        ref = {"action":"Inspect test system"}
        text = "{} {} finding, severity {}. Inspect test system".format(f["system"], f["affected_sensors"][0], f["severity"])
        ok, reason = validate_explanation(text + " due to a cracked impeller", f, summary, ref)
        self.assertFalse(ok)
        self.assertIn("unsupported", reason)

    def test_unknown_finding_fails_clearly(self):
        with self.assertRaisesRegex(ValueError, "Finding not found"):
            execute_workflow("NO-SUCH-FINDING", mode="disabled")


if __name__ == "__main__":
    unittest.main()
