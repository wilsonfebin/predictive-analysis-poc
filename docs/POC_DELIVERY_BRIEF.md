# Marine Generator Predictive Maintenance POC — Delivery Brief

**Status:** Phase 1–4 implementation and validation summary, 10 November 2026

**Asset:** DG-01 / VESSEL-01

**Data provenance:** Synthetic, illustrative only

## 1. Project Charter

### Purpose and objectives

This proof of concept demonstrates condition-based monitoring for one marine diesel generator. It prepares reproducible minute-level synthetic telemetry, estimates context-dependent expected sensor values, detects persistent residuals, distinguishes sensor diagnostics from machinery findings, and presents evidence and mock maintenance recommendations for human review.

The intended outcome is a reviewable technical demonstration of data quality treatment, early-warning calculations, explainability, access restrictions, and audit history. It is not a production system or proof of predictive performance on a vessel.

### Scope and boundaries

**Implemented:** 30 days of synthetic data for 36 signals; separate ground truth; deterministic regression and persistence detection; sensor diagnostics; finding/evaluation reports; FastAPI; Streamlit; SQLite review state; one bounded LangGraph workflow; optional OpenAI wording with deterministic fallback; Chief Engineer decisions and audit events; Docker/Compose and GitHub Actions configuration.

**Excluded:** real vessel, PMS, ERP, or inventory connectivity; automatic work execution; production authentication or deployment; validated marine-engineering models; any LLM authority over detection, severity, recommendations, or decisions.

### Success criteria

The project is successful as a POC when a reviewer can regenerate the synthetic input, run the deterministic pipeline, inspect findings and lead times, exercise the bounded review workflow, verify server-side role restrictions, and reproduce tests from a clean Python 3.11 setup. See [`../reports/PHASE_4_ACCEPTANCE_REPORT.md`](../reports/PHASE_4_ACCEPTANCE_REPORT.md) for the current evidence and verification gaps.

## 2. Requirements Traceability

| Requirement | Implementation / evidence | Status |
|---|---|---|
| 30 days, 36 signals, explicit context and tags | `scripts/generate_dataset.py`; `data/telemetry.csv`, `context.csv`, `tags.csv`; dataset tests | Implemented; generation tests pass |
| Keep scenario labels out of model inputs | Separate `data/ground_truth.json`; loader/model boundary in `src/predictive.py` | Implemented; tested |
| Quality, valid ranges, running-state treatment | `src/predictive.py`; `docs/SYNTHETIC_DATA_ASSUMPTIONS.md` | Implemented; tested |
| Context-aware expected values and persistent drift | Per-signal OLS, load context, seawater for cooling, configured persistence/tolerances | Implemented; synthetic assumptions only |
| Sensor/machinery separation and maintenance mapping | `reports/findings.json`; `data/maintenance_reference.json`; workflow tests | Implemented; tested |
| Compare predictive detection with fixed alarms | `reports/evaluation.json`; detailed below | Implemented; synthetic benchmark |
| Review, roles, decisions and audit | `src/api.py`, `src/storage.py`; API tests | Implemented; tests verify denied roles and decision recording |
| Overview, sensors, findings and review screens | `app/streamlit_app.py`; `tests/test_ui.py` AppTest | Implemented; render tests pass |
| Bounded workflow and optional LLM wording | `src/workflow.py`; `tests/test_workflow.py` | Implemented; disabled, missing-key, failure, and validation paths tested |
| Reproducible setup, Docker, CI | `README.md`, `Dockerfile`, `docker-compose.yml`, `.github/workflows/ci.yml` | Files/config present; see verification status |

## 3. Solution Architecture

The codebase is a small Python application. The standard-library generator creates aligned telemetry, context, tag metadata, maintenance reference data, and separate ground truth. The dependency-free Phase 2 pipeline uses standard-library input handling and direct ordinary least-squares calculations to fit per-signal expectations on the documented healthy candidate period. It applies data quality, operating-state, residual tolerance, and persistence rules, then writes JSON/CSV reports under `reports/`.

FastAPI reads those reports and raw input files without rewriting them. It serves health, overview, sensor history, findings, investigation, workflow, decision, and audit endpoints. SQLite stores investigation notes, review state, workflow summaries, and append-only decisions/audit events. Streamlit consumes the API and Plotly renders monitoring charts. A single conditional LangGraph workflow routes sensor findings to instrument inspection and machinery findings to mock maintenance lookup. OpenAI is optional and may only rewrite an evidence-bounded explanation; deterministic wording is the default and fallback.

### Repository map

| Path | Purpose |
|---|---|
| `scripts/generate_dataset.py` | Reproducible synthetic input generation |
| `data/` | Telemetry, context, tags, ground truth, maintenance reference |
| `config/detection.json` | Baseline period, accepted quality, tolerances, persistence and grouping settings |
| `src/predictive.py` | Deterministic preparation, detection, finding and evaluation pipeline |
| `reports/` | Current pipeline outputs and audit note |
| `src/api.py`, `src/storage.py`, `src/workflow.py` | API, SQLite persistence, bounded workflow |
| `app/streamlit_app.py` | User interface |
| `tests/` | Dataset, prediction, API, workflow, and UI tests |
| `docs/` | Assumptions, data dictionary, delivery and demo notes |

## 4. Delivery Plan

| Phase | Deliverable | Current state |
|---|---|---|
| 1 — Synthetic data | Seeded 30-day input set, tags, context, quality events, scenarios and documentation | Implemented; tests pass |
| 2 — Predictive analytics | Contextual baseline, residual detection, diagnostics, findings and fixed-alarm evaluation | Implemented; regression values recorded in acceptance report |
| 3 — Application and workflow | API, UI, SQLite, role checks, bounded workflow and optional wording adapter | Implemented; integration tests pass |
| 4 — Validation and delivery | Full tests, evidence-based acceptance report, demo script, limitations and verification notes | Tests and Docker/HTTP startup checks pass; hosted CI and visual browser preview remain unverified |

The phases have been delivered in order. This validation pass did not regenerate existing reports or alter analytics configuration. Before any operational pilot, the next decision is whether to collect and govern a representative real-vessel dataset with engineering owners.

## 5. Workstream Ownership / RACI

No named project assignments were supplied. The following is a **proposed role-based RACI**, not a record of actual staffing. R = Responsible, A = Accountable, C = Consulted, I = Informed.

| Workstream / decision | POC sponsor | Data & analytics developer | Application developer | Chief Engineer / domain SME | Fleet office reviewer |
|---|---:|---:|---:|---:|---:|
| Scope and acceptance criteria | A | C | C | C | I |
| Synthetic data and assumptions | I | R | I | C | I |
| Detection and evaluation | I | R/A | C | C | I |
| API, UI, workflow, audit | I | C | R/A | C | I |
| Engineering validation of thresholds | I | C | I | R/A | I |
| Individual maintenance approval/rejection | I | I | I | R/A | I |
| Read-only findings review | I | I | I | C | R |

Project-wide acceptance is ultimately a sponsor decision; the table uses that role for scope accountability only. POC code does not simulate assigned staff beyond its demo user roles.

## 6. RAID Register

| Type | Item | Response / owner |
|---|---|---|
| Risk | Synthetic relationships and alarm limits may not represent engine behavior. | Do not use operationally; have marine-engineering SMEs validate assumptions and thresholds. Owner: Chief Engineer / future pilot sponsor. |
| Risk | Simplified OLS and tolerance/persistence rules may miss operating modes or create false alerts on real data. | Validate against labeled, representative telemetry and operating context before deployment. Owner: analytics and domain SME. |
| Assumption | All source inputs are synthetic because no actual dataset was supplied. | Preserve provenance and do not mix future real data silently. Owner: data steward. |
| Assumption | Demo users and mock maintenance/stock references are sufficient to demonstrate workflow. | Replace with approved identity and reference sources only in a separately scoped production project. Owner: application/security owner. |
| Issue | The in-app browser preview did not render the local Streamlit page during this validation. | Docker frontend is running and returns HTTP 200; Streamlit AppTest also renders the pages. Visual browser inspection remains unverified. |
| Dependency | GitHub Actions workflow exists, but no hosted run result was supplied or triggered. | Treat CI status as Not Verified until a run completes in GitHub. |
| Dependency | Real-data pilot depends on data access, privacy/security review, signal metadata, alarm ownership, and engineering labels. | Resolve before production design or performance claims. |

## 7. Test and Acceptance Strategy

The automated acceptance suite is `python3.11 -m unittest discover -s tests -v`. It covers generation schema/row counts/reproducibility and label separation; quality, context, persistence and alarm timing; role permissions and audit persistence; workflow routes and maintenance mapping; LLM-disabled, missing-key and provider-failure fallback; and Streamlit AppTest rendering of key screens and charts.

The report outputs are treated as the predictive regression baseline. Validation records SHA-1 checksums before/after the test run for `findings.json`, `evaluation.json`, `processing_summary.json`, `diagnostics.json`, and `residuals.csv.gz`; the four detection timestamps and alarm leads are also compared explicitly. Docker config parsing, actual service startup, API `/health`, `/docs`, browser-served Streamlit, and a hosted Actions run are tracked separately so configuration or in-process tests are not misreported as deployment verification.

## 8. POC-to-Production Roadmap

The following are **proposed enhancements**, not implemented commitments:

1. Obtain representative vessel telemetry, tag/alarm definitions, maintenance records, and quality metadata under agreed governance.
2. Have marine-engineering SMEs validate the healthy period, modes, thresholds, sensor limits, fault scenarios, and maintenance actions.
3. Run a time-separated offline evaluation with labeled incidents, missingness, sensor faults, operating transitions, false-alert rate, and lead-time uncertainty.
4. Define production identity, role provisioning, credential management, secure deployment, observability, backup/restore, retention, and audit controls.
5. Design and approve narrowly scoped vessel/PMS integrations with data ownership, failure modes, read-only pilot boundaries, and safety review.
6. Pilot in advisory/read-only mode with engineers; compare alerts to inspection outcomes and tune only through controlled change review.
7. Consider broader deployment only after acceptance thresholds, operational ownership, cybersecurity, and support responsibilities are approved.

No phase above changes the current advisory-only behavior or implies validated production readiness.
