import os
import tempfile
import unittest
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
                    def local_request(method, url, auth=None, **kwargs):
                        path = url.split("localhost:8000", 1)[-1]
                        kwargs.pop("timeout", None)
                        return api_client.request(method, path, auth=auth, **kwargs)

                    with patch("requests.request", side_effect=local_request):
                        test_app = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"))
                        test_app.session_state["auth"] = ("chief", "chief-demo")
                        test_app.session_state["username"] = "chief"
                        test_app.session_state["role"] = "Chief Engineer"
                        test_app.run(timeout=30)
                        self.assertFalse(test_app.exception)
                        self.assertEqual(len(test_app.get("plotly_chart")), 1)
                        for page in ("Sensor Monitoring", "Findings", "Maintenance Review", "Audit History"):
                            test_app.radio[0].set_value(page).run(timeout=30)
                            self.assertFalse(test_app.exception, page)
                            if page == "Sensor Monitoring":
                                self.assertEqual(len(test_app.get("plotly_chart")), 1)
            finally:
                if previous is None:
                    os.environ.pop("APP_DB_PATH", None)
                else:
                    os.environ["APP_DB_PATH"] = previous


if __name__ == "__main__":
    unittest.main()
