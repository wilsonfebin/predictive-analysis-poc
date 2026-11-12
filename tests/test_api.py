import json
import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from fastapi.testclient import TestClient

from src.api import app


ROOT = Path(__file__).resolve().parents[1]
FINDINGS = json.loads((ROOT / "reports" / "findings.json").read_text())
MACHINERY_ID = next(f["finding_id"] for f in FINDINGS if f["category"] == "machinery_degradation")
SENSOR_ID = next(f["finding_id"] for f in FINDINGS if f["category"] == "sensor_fault")


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_db = os.environ.get("APP_DB_PATH")
        self.old_mode = os.environ.get("LLM_MODE")
        os.environ["APP_DB_PATH"] = str(Path(self.temp.name) / "reviews.sqlite3")
        os.environ["LLM_MODE"] = "disabled"
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        if self.old_db is None: os.environ.pop("APP_DB_PATH", None)
        else: os.environ["APP_DB_PATH"] = self.old_db
        if self.old_mode is None: os.environ.pop("LLM_MODE", None)
        else: os.environ["LLM_MODE"] = self.old_mode
        self.temp.cleanup()

    def request(self, method, path, user="chief", password="chief-demo", **kwargs):
        return self.client.request(method, path, auth=(user,password), **kwargs)

    def test_health_overview_sensor_and_finding_endpoints(self):
        self.assertEqual(self.client.get("/health").status_code, 200)
        overview = self.request("GET", "/api/v1/overview")
        self.assertEqual(overview.status_code, 200)
        self.assertEqual(overview.json()["generator_id"], "DG-01")
        self.assertEqual(overview.json()["last_observation_timestamp"], "2026-09-30T23:59:00Z")
        self.assertEqual(overview.json()["observation_period"]["start"], "2026-09-01T00:00:00Z")
        self.assertEqual(overview.json()["observation_period"]["end"], "2026-09-30T23:59:00Z")
        self.assertTrue(overview.json()["processed_at"])
        self.assertEqual(overview.json()["latest_processing_timestamp"], overview.json()["processed_at"])
        sensors = self.request("GET", "/api/v1/sensors")
        self.assertEqual(len(sensors.json()), 36)
        self.assertEqual(sensors.json()[0]["current_observation_timestamp"], "2026-09-30T23:59:00Z")
        history = self.request("GET", "/api/v1/sensors/jacket_water_outlet_c/history", params={"start":"2026-09-12T00:00:00Z","end":"2026-09-12T03:00:00Z"})
        self.assertEqual(history.status_code, 200)
        self.assertTrue(history.json()["data"])
        comparison = self.request("GET", "/api/v1/sensors/jacket_water_outlet_c/history", params={"start":"2026-09-01T00:00:00Z","end":"2026-10-01T00:00:00Z","max_points":50}).json()
        self.assertEqual(comparison["predictive_evaluation"]["threshold"], 96)
        self.assertEqual(comparison["predictive_evaluation"]["lead_time_minutes"], 16374)
        self.assertTrue(comparison["quality_points_preserved_before_sampling"])
        excluded = sum(v for k,v in comparison["quality_counts_full_range"].items() if k != "GOOD")
        self.assertEqual(sum(point["quality_status"] != "GOOD" for point in comparison["data"]), excluded)
        self.assertTrue(all("residual_tolerance" in point for point in comparison["data"]))
        self.assertTrue(any(point["tolerance_run_start"] for point in comparison["data"]))
        narrow = self.request("GET", "/api/v1/sensors/jacket_water_outlet_c/history", params={"start":"2026-09-24T00:00:00Z","end":"2026-09-25T00:00:00Z","max_points":50}).json()
        full_run_starts = {p["timestamp"] for p in comparison["data"] if p["tolerance_run_start"]}
        narrow_run_starts = {p["timestamp"] for p in narrow["data"] if p["tolerance_run_start"]}
        self.assertTrue(narrow_run_starts.issubset(full_run_starts))
        finding = self.request("GET", "/api/v1/findings/{}".format(MACHINERY_ID))
        self.assertEqual(finding.status_code, 200)
        self.assertEqual(finding.json()["review_status"], "OPEN")
        self.assertEqual(self.request("GET", "/api/v1/findings/no-such-id").status_code, 404)
        self.assertEqual(self.request("GET", "/api/v1/sensors/no-such-sensor/history").status_code, 404)

    def test_backend_enforces_roles_and_decision_transitions(self):
        denied = self.request("POST", "/api/v1/findings/{}/approve".format(MACHINERY_ID), user="second", password="second-demo", json={"rationale":"Not permitted"})
        self.assertEqual(denied.status_code, 403)
        denied_reject = self.request("POST", "/api/v1/findings/{}/reject".format(MACHINERY_ID), user="second", password="second-demo", json={"rationale":"Not permitted"})
        self.assertEqual(denied_reject.status_code, 403)
        fleet_investigate = self.request("POST", "/api/v1/findings/{}/investigate".format(MACHINERY_ID), user="fleet", password="fleet-demo", json={"note":"Read only user"})
        self.assertEqual(fleet_investigate.status_code, 403)
        fleet_approve = self.request("POST", "/api/v1/findings/{}/approve".format(MACHINERY_ID), user="fleet", password="fleet-demo", json={"rationale":"Read only user"})
        self.assertEqual(fleet_approve.status_code, 403)
        self.assertEqual(self.request("GET", "/api/v1/findings", user="fleet", password="fleet-demo").status_code, 200)
        second_investigate = self.request("POST", "/api/v1/findings/{}/investigate".format(SENSOR_ID), user="second", password="second-demo", json={"note":"Compared stale flag with the flatline evidence"})
        self.assertEqual(second_investigate.status_code, 200)
        self.assertEqual(second_investigate.json()["review_status"], "UNDER_INVESTIGATION")
        self.assertEqual(self.request("GET", "/api/v1/findings/{}/workflow".format(SENSOR_ID), user="second", password="second-demo").status_code, 200)
        self.assertEqual(self.request("GET", "/api/v1/findings/{}".format(SENSOR_ID), user="second", password="second-demo").json()["investigations"][0]["note"], "Compared stale flag with the flatline evidence")
        chief_decision = self.request("POST", "/api/v1/findings/{}/approve".format(MACHINERY_ID), json={"rationale":"Evidence supports a planned cooling inspection"})
        self.assertEqual(chief_decision.status_code, 200)
        self.assertEqual(chief_decision.json()["decision_maker"], "chief")
        self.assertEqual(self.request("POST", "/api/v1/findings/{}/reject".format(MACHINERY_ID), json={"rationale":"Cannot reverse a final decision"}).status_code, 409)
        self.assertEqual(self.request("POST", "/api/v1/findings/{}/approve".format(SENSOR_ID), json={"rationale":"Invalid after investigation"}).status_code, 200)
        other_id = next(f["finding_id"] for f in FINDINGS if f["finding_id"] not in (MACHINERY_ID, SENSOR_ID))
        self.assertEqual(self.request("POST", "/api/v1/findings/{}/reject".format(other_id), json={"rationale":"Insufficient supporting evidence"}).status_code, 200)
        audit = self.request("GET", "/api/v1/audit").json()
        self.assertTrue(any(e["event"] == "REJECTED" and e["finding_id"] == other_id for e in audit))

    def test_validation_auth_and_audit_survive_app_reopen(self):
        self.assertEqual(self.client.get("/api/v1/findings").status_code, 401)
        invalid = self.request("POST", "/api/v1/findings/{}/approve".format(MACHINERY_ID), json={"rationale":"x"})
        self.assertEqual(invalid.status_code, 422)
        self.request("POST", "/api/v1/findings/{}/approve".format(MACHINERY_ID), json={"rationale":"Review approved after evidence check"})
        before = self.request("GET", "/api/v1/audit").json()
        self.assertTrue(any(e["event"] == "APPROVED" and e["actor"] == "chief" and e["role"] == "Chief Engineer" for e in before))
        self.client.__exit__(None, None, None)
        self.client = TestClient(app)
        self.client.__enter__()
        after = self.request("GET", "/api/v1/audit").json()
        self.assertGreaterEqual(len(after), len(before))
        self.assertTrue(any(e["event"] == "APPROVED" for e in after))

    def test_workflow_mode_can_change_for_new_and_existing_runs(self):
        first = {"explanation_mode":"template", "explanation":"Template wording", "maintenance_reference":{}}
        second = {"explanation_mode":"openai", "explanation":"OpenAI wording", "maintenance_reference":{}}
        path = "/api/v1/findings/{}/investigate".format(MACHINERY_ID)
        with patch("src.api.execute_workflow", side_effect=[first, second]) as execute:
            created = self.request("POST", path, json={"note":"Reviewing evidence", "mode":"disabled"})
            self.assertEqual(created.status_code, 200)
            self.assertEqual(created.json()["workflow"]["explanation_mode"], "template")
            regenerated = self.request("POST", "/api/v1/findings/{}/workflow/regenerate".format(MACHINERY_ID), json={"mode":"openai"})
            self.assertEqual(regenerated.status_code, 200)
            self.assertEqual(regenerated.json()["result"]["explanation_mode"], "openai")
            self.assertEqual([call.kwargs["mode"] for call in execute.call_args_list], ["disabled", "openai"])
        history = self.request("GET", "/api/v1/findings/{}/workflow/history".format(MACHINERY_ID)).json()
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["result"]["explanation"], "OpenAI wording")
        self.assertEqual(history[1]["result"]["explanation"], "Template wording")
        invalid = self.request("POST", "/api/v1/findings/{}/workflow/regenerate".format(MACHINERY_ID), json={"mode":"other"})
        self.assertEqual(invalid.status_code, 422)

    def test_fleet_cannot_regenerate_workflow(self):
        response = self.request("POST", "/api/v1/findings/{}/workflow/regenerate".format(MACHINERY_ID), user="fleet", password="fleet-demo", json={"mode":"disabled"})
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
