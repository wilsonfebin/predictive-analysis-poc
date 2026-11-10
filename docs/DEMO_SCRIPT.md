# Interview Demonstration — DG-01 Predictive Maintenance POC

**Run time:** approximately 13 minutes  
**Dataset:** synthetic, 1–30 September 2026  
**Purpose:** demonstrate implemented behavior and its limits; do not present synthetic results as vessel performance.

## Preparation

1. From the repository root, follow the Python 3.11 setup in [`../README.md`](../README.md). Start FastAPI and Streamlit, or use Docker Compose where Docker is available.
2. Confirm the input files and reports exist. Do not rerun generation or analytics during the interview unless showing reproducibility; the checked-in report set is the reference for the values below.
3. Open `http://localhost:8501` and sign in with `chief` / `chief-demo`. These are local demonstration credentials only.
4. Keep `reports/evaluation.json` and `reports/findings.json` available for exact timestamps. The UI displays timestamps in IST; reports retain UTC.
5. If a service is unavailable, disclose it and use the committed report outputs. Do not imply that a live service was verified when it was not.

## Timed walkthrough

| Time | Segment | Demonstration and speaking points |
|---|---|---|
| 0:00–1:00 | Business objective | “This POC explores early warning for a single marine diesel generator. It combines expected sensor behavior, data-quality handling, persistent deviation evidence, and engineer review. The data is synthetic and advisory-only.” |
| 1:00–3:00 | Architecture and delivery | Show the repository/architecture in the delivery brief: deterministic generator and analytics reports; FastAPI; SQLite; Streamlit; one bounded conditional workflow. Point out that ground truth is held separately and optional LLM text does not determine severity, recommendation, or approval. |
| 3:00–5:00 | Sensor monitoring | Open Sensor Monitoring. Select Jacket Water Outlet and the 30-day range. Identify actual versus expected, residual/tolerance, quality strip, IST display, and run-start markers. Explain that invalid readings are excluded/marked, not treated as normal. |
| 5:00–7:00 | Findings and early warning | Open Findings and select MACH-002 (jacket-water cooling). Use the report values: detection `2026-09-13T03:50:00Z`, fixed alarm crossing `2026-09-24T12:44:00Z`, lead `16,374 minutes` (272 h 54 min). State explicitly that these are results from the illustrative synthetic benchmark. Optionally show the other three results from the table below. |
| 7:00–9:00 | Recommendation and investigation | Show MACH-002 evidence, recommendation “Inspect and clean cooling-water cooler,” and its mock parts. Run the investigation/workflow from the Finding or Maintenance Review interface. Explain that it looks up existing mock reference data and returns a proposed action for human review; it does not create a work order. |
| 9:00–11:00 | Human review and audit | As Chief Engineer, submit a decision only in a disposable local demonstration database, with a concise rationale. Show the decision status and audit history fields (actor, role, timestamp, rationale). If keeping the repository’s persisted SQLite state, do not overwrite an existing final decision; use a temporary `APP_DB_PATH` for the demonstration. |
| 11:00–12:00 | Workflow, RBAC and fallback | Show the workflow result in disabled mode. Explain sensor findings route to instrument inspection. Point to tests proving Second Engineer approval/rejection and Fleet Office mutation are denied, plus missing-key/provider-failure fallback. No live OpenAI request is required. |
| 12:00–13:00 | Limits and roadmap | Close with the limitations: no real vessel data, illustrative thresholds, mock inventory, demo Basic Auth, and no PMS/ERP integration. Production work would start with governed real telemetry and engineering validation, followed by identity/security and a read-only pilot. |

## Recorded synthetic early-warning results

These values are read from `reports/evaluation.json`; UTC is the report’s canonical timestamp convention. The table does not imply real-world accuracy.

| Scenario | Predictive detection (UTC) | Fixed alarm crossing (UTC) | Lead |
|---|---|---|---:|
| Jacket-water cooling (F-COOL-01) | 2026-09-13 03:50 | 2026-09-24 12:44 | 16,374 min / 272 h 54 min |
| Lube-oil pressure (F-LUBE-01) | 2026-09-17 13:27 | 2026-09-24 20:40 | 10,513 min / 175 h 13 min |
| Cylinder 7 exhaust (F-CYL-01) | 2026-09-20 15:01 | 2026-09-24 11:31 | 5,550 min / 92 h 30 min |
| Charge-air cooling (F-COOL-02) | 2026-09-21 15:01 | 2026-09-23 11:01 | 2,640 min / 44 h |

The frozen cooler differential-pressure sensor is separately diagnosed and routed to instrument inspection at `2026-09-08T04:00:00Z`; the scenario evaluation records no machinery finding from that sensor fault. Healthy-period, measured load-transition, isolated-spike, stopped-period, and poor-quality machinery-finding counts are all zero in the current synthetic evaluation.

## Presentation safeguards

- Call all observations and results synthetic, including the early-warning numbers.
- Distinguish predictive residual tolerance from configured fixed alarm thresholds.
- Describe LangGraph as one bounded workflow, not multiple autonomous agents.
- The LLM is optional explanation wording only; disabled mode is the baseline.
- Do not call recommendations approved maintenance instructions or imply any automated execution.
