import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from src.api import app


ROOT = Path(__file__).resolve().parents[1]


class StreamlitUiTests(unittest.TestCase):
    def test_primary_pages_render_and_plotly_charts_are_present(self):
        with tempfile.TemporaryDirectory() as temp:
            previous = os.environ.get("APP_DB_PATH")
            os.environ["APP_DB_PATH"] = str(Path(temp) / "ui.sqlite3")
            try:
                with TestClient(app) as api_client:
                    request_log = []
                    def local_request(method, url, auth=None, **kwargs):
                        path = url.split("localhost:8000", 1)[-1]
                        kwargs.pop("timeout", None)
                        request_log.append((method, path, kwargs.get("params")))
                        return api_client.request(method, path, auth=auth, **kwargs)

                    with patch("requests.request", side_effect=local_request):
                        test_app = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"))
                        test_app.session_state["auth"] = ("chief", "chief-demo")
                        test_app.session_state["username"] = "chief"
                        test_app.session_state["role"] = "Chief Engineer"
                        test_app.run(timeout=30)
                        self.assertFalse(test_app.exception)
                        overview_specs = [json.loads(chart.proto.spec) for chart in test_app.get("plotly_chart")]
                        self.assertGreaterEqual(len(overview_specs), 1)
                        summary_trace_names = {trace.get("name") for trace in overview_specs[-1]["data"]}
                        self.assertEqual(summary_trace_names, {"Machinery", "Sensor diagnostics"})
                        captions = " ".join(element.proto.body for element in test_app.caption)
                        self.assertIn("Observation period · IST", captions)
                        self.assertIn("Last telemetry · IST", captions)
                        self.assertIn("Analytics processed · IST", captions)
                        self.assertIn("Last Recorded Operating State", [metric.proto.label for metric in test_app.metric])
                        self.assertIn("Latest Recorded Load", [metric.proto.label for metric in test_app.metric])
                        self.assertIn("Review State", [metric.proto.label for metric in test_app.metric])
                        self.assertTrue(any("Synthetic POC" in element.proto.body for element in test_app.markdown if hasattr(element.proto, "body")))
                        for page in ("Sensor Monitoring", "Findings", "Maintenance Review", "Audit History"):
                            nav = next(radio for radio in test_app.radio if radio.key == "workspace_nav")
                            option = next(value for value in nav.options if page in value)
                            nav.set_value(option).run(timeout=30)
                            self.assertFalse(test_app.exception, page)
                            if page == "Sensor Monitoring":
                                range_select = next(radio for radio in test_app.radio if radio.key == "sensor_range_preset")
                                self.assertEqual(range_select.value, "30 Days")
                                self.assertEqual(range_select.options, ["24 Hours", "7 Days", "30 Days", "Custom"])
                                range_select.set_value("7 Days").run(timeout=30)
                                self.assertFalse(test_app.exception)
                                history_calls = [entry for entry in request_log if entry[1].endswith("/history") and entry[2] and entry[2].get("max_points") == 1200]
                                self.assertEqual(history_calls[-1][2]["start"], "2026-09-24T00:00:00Z")
                                range_select = next(radio for radio in test_app.radio if radio.key == "sensor_range_preset")
                                range_select.set_value("Custom").run(timeout=30)
                                self.assertFalse(test_app.exception)
                                start_control = next(item for item in test_app.date_input if item.label == "From")
                                end_control = next(item for item in test_app.date_input if item.label == "Through")
                                start_control.set_value(date(2026,9,10))
                                end_control.set_value(date(2026,9,12)).run(timeout=30)
                                self.assertFalse(test_app.exception)
                                history_calls = [entry for entry in request_log if entry[1].endswith("/history") and entry[2] and entry[2].get("max_points") == 1200]
                                self.assertEqual(history_calls[-1][2]["start"], "2026-09-10T00:00:00Z")
                                self.assertEqual(history_calls[-1][2]["end"], "2026-09-13T00:00:00Z")
                                range_select = next(radio for radio in test_app.radio if radio.key == "sensor_range_preset")
                                range_select.set_value("30 Days").run(timeout=30)
                                self.assertFalse(test_app.exception)
                                sensor = next(select for select in test_app.selectbox if select.label == "Sensor")
                                sensor.set_value("jacket_water_outlet_c").run(timeout=30)
                                self.assertFalse(test_app.exception)
                                self.assertEqual([metric.proto.label for metric in test_app.metric][-4:], ["Latest Recorded Value", "Data Quality", "Valid Observations", "Tolerance Exceedances · sampled"])
                                self.assertEqual(len(test_app.get("plotly_chart")), 2)
                                latest_metric = next(metric for metric in test_app.metric if metric.proto.label == "Latest Recorded Value")
                                self.assertRegex(latest_metric.value, r"\d+\.\d{2} °C")
                                sensor_captions = " ".join(element.proto.body for element in test_app.caption)
                                self.assertIn("Latest applicable observation", sensor_captions)
                                quality_chart = json.loads(test_app.get("plotly_chart")[0].proto.spec)
                                self.assertGreater(len(quality_chart["data"]), 0)
                                quality_history = api_client.get("/api/v1/sensors/jacket_water_outlet_c/history", auth=("chief","chief-demo"), params={"start":"2026-09-01T00:00:00Z","end":"2026-10-01T00:00:00Z","max_points":1200}).json()
                                counts = quality_history["quality_counts_full_range"]
                                self.assertEqual(sum(int(trace["x"][0]) for trace in quality_chart["data"]), sum(counts.values()))
                                valid_metric = next(metric for metric in test_app.metric if metric.proto.label == "Valid Observations")
                                self.assertEqual(int(valid_metric.value.replace(",", "")), counts["GOOD"])
                                chart = json.loads(test_app.get("plotly_chart")[1].proto.spec)
                                traces = {trace.get("name"):trace for trace in chart["data"]}
                                self.assertIn("Actual (GOOD)", traces)
                                self.assertIn("Expected", traces)
                                self.assertIn("Tolerance-exceedance run start", traces)
                                self.assertIn("Persistent-finding detection", traces)
                                self.assertIn("Quality-excluded observation", traces)
                                quality_values = [float(point[0]) for point in traces["Quality-excluded observation"]["customdata"] if point[0] is not None]
                                primary_range = chart["layout"]["yaxis"]["range"]
                                self.assertGreater(max(quality_values), primary_range[1])
                                self.assertEqual(chart["layout"]["yaxis3"]["range"], [-.6,.6])
                                self.assertEqual(chart["layout"]["xaxis3"]["title"]["text"], "Timestamp (IST)")
                                actual_x = traces["Actual (GOOD)"]["x"]
                                self.assertIn("T07:30:", actual_x[0])
                                self.assertIn("Residual (actual − expected)", traces)
                                self.assertIn("+ residual tolerance", traces)
                                self.assertIn("96", str(chart["layout"]))
                                self.assertIn("Detected 272.9 h before alarm", str(chart["layout"]))
                                sensor = next(select for select in test_app.selectbox if select.label == "Sensor")
                                sensor.set_value("lube_oil_temperature_c").run(timeout=30)
                                no_finding_chart = json.loads(test_app.get("plotly_chart")[1].proto.spec)
                                self.assertNotIn("Persistent-finding detection", {trace.get("name") for trace in no_finding_chart["data"]})
                            if page == "Findings":
                                selector = next(select for select in test_app.selectbox if select.key == "findings_select")
                                self.assertEqual(len(selector.options), 7)
                                self.assertEqual([option.split(" · ")[0] for option in selector.options], ["MACH-003", "MACH-001", "MACH-004", "MACH-002", "SENS-003", "SENS-002", "SENS-001"])
                                self.assertTrue(any("Severity escalation history" in element.proto.body for element in test_app.markdown if hasattr(element.proto, "body")))
                                selector.set_value("SENS-001").run(timeout=30)
                                self.assertFalse(test_app.exception, "legacy sensor finding without escalation fields")
            finally:
                if previous is None:
                    os.environ.pop("APP_DB_PATH", None)
                else:
                    os.environ["APP_DB_PATH"] = previous


if __name__ == "__main__":
    unittest.main()
