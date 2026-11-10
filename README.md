# ThinkPalm Predictive Maintenance POC

An advisory-only condition monitoring proof of concept for one synthetic marine diesel generator: DG-01 on VESSEL-01. It demonstrates a deterministic predictive pipeline, human review, role checks, audit history, and one bounded LangGraph workflow. It does not connect to vessel, PMS, ERP, or inventory systems and does not create work orders. Synthetic results do not establish real-vessel performance.

## Architecture

- Phase 1: deterministic standard-library data generation in `scripts/generate_dataset.py`.
- Phase 2: deterministic per-signal expected-value models, residuals, persistence detection, diagnostics, findings, and evaluation in `src/predictive.py`. Reports under `reports/` are its integration boundary.
- Phase 3: FastAPI reads reports and sensor history, SQLite stores review state and append-only events, Streamlit and Plotly provide the engineering UI, and one LangGraph routes existing findings to instrument or maintenance reference paths. Optional OpenAI use is limited to rewriting evidence into plain language; a deterministic template is the default and fallback.

Technology stack: Python 3.11; the generator and predictive pipeline use the standard library, including direct ordinary least-squares calculations; FastAPI, Streamlit, Plotly, SQLite, and one bounded LangGraph workflow provide the application. OpenAI is an optional wording provider; no paid service is required for the default run.

## Repository structure

```text
app/                 Streamlit application
config/              Baseline, quality, tolerance and persistence settings
data/                Synthetic telemetry, tags, context, ground truth and references
docs/                Data notes, delivery brief and demo walkthrough
reports/             Predictive outputs and validation reports
scripts/              Synthetic dataset generator
src/                 Predictive pipeline, API, persistence and workflow
tests/               Dataset, analytics, API, workflow and UI tests
```

## Requirements and setup

Use Python 3.11. Create a virtual environment and install the pinned app dependencies:

```sh
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Generate/rebuild the synthetic inputs and Phase 2 reports when needed:

```sh
python3.11 scripts/generate_dataset.py
python3.11 src/predictive.py
```

## Local startup

Start the API in one terminal:

```sh
source .venv/bin/activate
uvicorn src.api:app --reload --port 8000
```

Start Streamlit in a second terminal:

```sh
source .venv/bin/activate
streamlit run app/streamlit_app.py
```

Open `http://localhost:8501`. FastAPI and its interactive OpenAPI documentation are at `http://localhost:8000` and `http://localhost:8000/docs`. SQLite state defaults to `app_state.sqlite3` in the repository. Override paths with `APP_DB_PATH`, `DATA_DIR`, and `REPORT_DIR`.

## Demo users and roles

The local-only demo credentials are:

| Username | Password | Role |
|---|---|---|
| `chief` | `chief-demo` | Chief Engineer: investigate, approve, reject, view audit |
| `second` | `second-demo` | Second Engineer: investigate and add notes; cannot approve/reject |
| `fleet` | `fleet-demo` | Fleet Office: read-only |

The backend enforces roles on every protected endpoint. For custom local users, set `DEMO_USERS_JSON` to a JSON object keyed by username, e.g. `{"reviewer":{"password":"change-me","role":"Chief Engineer"}}`. These credentials are intentionally simple demo credentials, not production authentication.

## LLM mode

LLM-disabled mode is the default and needs no credentials or network access:

```sh
LLM_MODE=disabled uvicorn src.api:app --port 8000
```

Optional OpenAI wording can be enabled with `LLM_MODE=openai`, `OPENAI_API_KEY`, and optionally `OPENAI_MODEL` (default `gpt-4o-mini`). Missing credentials, provider errors, or unsupported generated claims fall back to the deterministic template. Finding evidence, severity, recommendation, and decision are unchanged. Do not commit API keys; `.env.example` lists supported variables.

## Docker Compose

With Docker and Compose installed:

```sh
docker compose up --build
```

The UI is at `http://localhost:8501`, the API at `http://localhost:8000/docs`, and the named `app-state` volume persists SQLite state. LLM-disabled mode works without secrets. To enable OpenAI, export `LLM_MODE=openai` and `OPENAI_API_KEY` before starting Compose. To stop the containers, run `docker compose down` (the named volume remains).

## API and screens

Endpoints include `GET /health`, `GET /api/v1/me`, overview, sensor list/history, findings/detail, investigate/workflow, approve/reject, and audit under `/api/v1`. OpenAPI schema and interactive request examples are served at `/docs`.

The Streamlit UI provides Generator Overview, Sensor Monitoring (actual/expected trends, deviation and finding markers, quality indicators), Findings, Maintenance Review, and Audit History. Historical sensor requests are time bounded and downsampled for plotting while retaining selected deviations and finding markers.

## Tests and CI

Run the complete automated suite (dataset, predictive, API/RBAC/audit, workflow/LLM fallback, and UI rendering):

```sh
python3.11 -m unittest discover -s tests -v
```

GitHub Actions is configured to run this suite and build the Docker image on pushes and pull requests; the presence of this workflow does not by itself establish that a hosted CI run passed. CI does not require OpenAI credentials. Run Phase 2 processing with `python3.11 src/predictive.py`; generated output contracts and configuration are described in `docs/POC_DELIVERY_BRIEF.md`.

For the acceptance evidence, outstanding verification items, and synthetic regression values, see [`reports/PHASE_4_ACCEPTANCE_REPORT.md`](reports/PHASE_4_ACCEPTANCE_REPORT.md). The timed walkthrough is in [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md). The delivery brief distinguishes implemented POC capabilities from proposed production work.

## Limitations

All telemetry, alarm values, findings and evaluation numbers are synthetic illustrative assumptions. OLS, tolerances, persistence settings, and mock maintenance data require marine-engineering validation. Demo Basic Auth and the single-host SQLite database are for local POC review only. No production security, deployment, or real data integration is claimed.
