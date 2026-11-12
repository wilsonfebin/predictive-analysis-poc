# Phase 4 Acceptance Report

**Project:** ThinkPalm Marine Diesel Generator Predictive Maintenance POC  
**Validation date:** 10 November 2026 (Asia/Kolkata)  
**Asset:** DG-01 / VESSEL-01  
**Data provenance:** Synthetic; not evidence of vessel performance  
**Recommendation:** **Ready for technical review and synthetic-data demonstration; not ready for operational deployment.**

## Acceptance checklist

| Area | Result | Evidence |
|---|---|---|
| Required synthetic inputs load and align | **Pass** | Current files: 43,200 telemetry rows, 43,200 context rows, 36 tag rows, five separate ground-truth scenarios; dataset tests verify row count, timestamps, schema, quality and label separation. |
| Predictive pipeline reproduces four machinery findings | **Pass** | `reports/findings.json` contains MACH-001 through MACH-004; `reports/evaluation.json` contains four machinery scenarios. Predictive regression tests passed. |
| Original detection times and fixed-alarm leads unchanged | **Pass** | Regression test asserts the four detection timestamps, fixed alarm crossings and lead minutes listed below. Output file checksums before and after the suite were unchanged. |
| Fixed alarm comparison | **Pass** | `reports/evaluation.json`; all four synthetic machinery scenarios detected before the configured running/GOOD-quality alarm crossings. |
| Frozen/missing sensor diagnostics kept separate | **Pass** | Evaluation records frozen-sensor detection at `2026-09-08T04:00:00Z`, instrument-check routing, and no machinery finding from that scenario. Sensor diagnostic tests pass. |
| Scenario-specific maintenance recommendation and parts | **Pass** | Workflow tests assert the action and mock part IDs for each of the four machinery signals; sensor faults route to instrument inspection with no parts/work order. |
| Overview, Sensor Monitoring and Findings render | **Pass** | `tests/test_ui.py` Streamlit AppTest exercises Overview, Sensor Monitoring, Findings, Maintenance Review and Audit History; chart content and range controls are asserted. Live Streamlit endpoint also returned HTTP 200. |
| Investigation workflow completes | **Pass** | `tests/test_api.py` exercises investigation and workflow endpoint; workflow tests cover machinery and sensor routes. |
| Chief Engineer can approve and reject | **Pass** | API integration test verifies Chief Engineer approval and rejection on separate findings. |
| Approval/rejection form enforces a nonblank rationale before sending | **Pass** | UI warns on empty or whitespace-only text and does not call the API; a valid rationale submits successfully. Verified by `test_maintenance_decision_requires_a_nonblank_rationale`. |
| Second Engineer cannot approve/reject | **Pass** | API integration test verifies both requests return HTTP 403. |
| Fleet Office is read-only | **Pass** | API integration test permits findings read and denies investigation and approval. Backend role dependencies enforce decisions for Chief Engineer only. |
| Decision audit includes actor, role, timestamp and rationale | **Pass** | `src/storage.py` persists all four fields. A separate TestClient check using a temporary SQLite file approved a finding and verified the returned audit event’s actor, role, rationale and UTC timestamp; the integration suite also verifies audit persistence across app reopen. |
| LangGraph and deterministic LLM-disabled path | **Pass** | `tests/test_workflow.py` executes the bounded workflow in disabled mode and validates route, explanation, recommendation, severity and human-review requirement. |
| Missing OpenAI key/provider failure fallback | **Pass** | Workflow tests verify both cases return deterministic template wording and preserve severity and recommendation. No live API request was made. |
| LLM cannot replace finding decision fields | **Pass** | Tests cover supported rewrite preserving severity/recommendation and rejection of unsupported numeric/factual claims. Workflow returns finding evidence/severity/recommendation separately from wording. |
| Full automated suite | **Pass** | `python3.11 -m unittest discover -s tests -v` — **23 tests passed**, 108.975 seconds. Warnings: LangGraph pending-deprecation notice and Streamlit AppTest bare-mode context notices; no failures. |
| Docker Compose build and both services start | **Pass** | `docker compose up --build -d` completed successfully; `docker compose ps` showed backend and frontend Up. `docker compose config --quiet` passed. Read-only live API calls to overview, sensors and findings returned 200 and reported DG-01, 36 sensors, 4 machinery findings and 3 sensor findings. |
| FastAPI health and OpenAPI documentation | **Pass** | Local HTTP checks: `/health` returned JSON status `ok`; `/docs` returned HTTP 200. |
| Streamlit service response | **Pass** | Local HTTP request to `http://127.0.0.1:8501/` returned HTTP 200; UI AppTest rendered the screens. |
| Visual browser smoke check | **Not Verified** | The in-app browser preview displayed `ERR_CONNECTION_REFUSED` for its local tab, even though host-side HTTP and AppTest checks passed. No screenshot/visual browser inspection is claimed. |
| GitHub Actions CI run | **Not Verified** | `.github/workflows/ci.yml` is present and configures tests plus Docker image build, but no hosted run result was available. |
| Live OpenAI provider request | **Not Verified / Not Required** | No external request was made; fake-client tests cover success rewrite, absent key and provider failure. |

## Predictive regression comparison

The run used the existing committed synthetic reports and did not invoke the data generator or predictive pipeline. The full test suite passed the regression assertions. SHA-1 checksums of `reports/findings.json`, `evaluation.json`, `processing_summary.json`, `diagnostics.json`, and `residuals.csv.gz` were identical before and after the test run, showing that validation did not rewrite those artifacts.

| Scenario | Predictive detection (UTC) | Fixed alarm crossing (UTC) | Lead time |
|---|---|---|---:|
| Jacket-water cooling — F-COOL-01 | 2026-09-13 03:50 | 2026-09-24 12:44 | 16,374 min (272 h 54 min) |
| Lube-oil pressure — F-LUBE-01 | 2026-09-17 13:27 | 2026-09-24 20:40 | 10,513 min (175 h 13 min) |
| Cylinder 7 exhaust — F-CYL-01 | 2026-09-20 15:01 | 2026-09-24 11:31 | 5,550 min (92 h 30 min) |
| Charge-air cooling — F-COOL-02 | 2026-09-21 15:01 | 2026-09-23 11:01 | 2,640 min (44 h) |

Current evaluation reports zero healthy-period machinery findings, zero in the measured healthy load-transition checks, zero tied to isolated spikes, zero on stopped periods, and zero at poor-quality detection timestamps. These are synthetic counts and limited to the checks represented by the configured evaluation.

## RBAC, workflow and audit evidence

The API tests use a temporary SQLite database. They verify that Second Engineer approve/reject requests return 403; Fleet Office can read findings but cannot investigate or approve; Chief Engineer decisions succeed; and audit events survive an API app reopen. A separate temporary-database API check confirmed an approval audit event returned actor `chief`, role `Chief Engineer`, the submitted rationale, and an ISO-8601 UTC `created_at`. Workflow tests verify scenario-specific machinery maintenance references, instrument inspection routing for sensor faults, and no work-order creation.

## Documentation and delivery status

- `README.md`: project description, architecture, setup, startup, URLs, Docker Compose, test command, demo users/RBAC and LLM configuration.
- `docs/POC_DELIVERY_BRIEF.md`: charter, traceability, architecture, delivery plan, role-based proposed RACI, RAID register, test strategy, and proposed production roadmap.
- `docs/DEMO_SCRIPT.md`: 13-minute interview walkthrough with actual synthetic outputs and safeguards.
- `docs/SYNTHETIC_DATA_ASSUMPTIONS.md` and `docs/DATA_DICTIONARY.md`: input semantics, simulation assumptions and limitations.
- Existing predictive and chart audit reports remain unchanged.

## Known limitations

- All telemetry, fault labels, alarm crossings, lead times and maintenance stock are synthetic illustrative assumptions. They do not establish real-world predictive accuracy.
- The ordinary least-squares models, healthy interval, tolerances, persistence settings, fixed alarm thresholds and fault progression need marine-engineering review and real-data validation.
- The scenario and signal set is limited; the healthy false-finding metrics do not estimate fleet-wide or long-term alert rates.
- No vessel, PMS, ERP or live inventory integrations exist; recommendations use mock/reference data and no work order is executed.
- Demo Basic Auth credentials and local SQLite are not production identity, access governance, scaling, backup, or cybersecurity controls.
- Hosted GitHub Actions status and visual in-browser rendering remain unverified; the browser tool could not render the local tab. Docker Compose build/start, service HTTP checks, AppTest and all automated tests did pass.

## Readiness recommendation

Proceed with technical review and a clearly labelled synthetic demonstration. Do not use outputs for maintenance decisions on a live vessel. Before operational evaluation, obtain governed representative telemetry, validate thresholds and findings with marine engineers, and separately design production identity/security and approved read-only integrations. No commit, push, or predictive-output regeneration was performed as part of this validation.
