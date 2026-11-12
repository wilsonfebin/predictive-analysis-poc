# AGENTS.md --- ThinkPalm Predictive Maintenance POC

## 1. Project mission

Build a small, runnable proof of concept for **Condition-Based
Predictive Maintenance (CBM) of one marine diesel generator**.

The system analyses one-minute telemetry for `DG-01` on `VESSEL-01`,
detects persistent deviations from expected operating behaviour,
distinguishes likely sensor faults from machinery findings, and presents
evidence-backed maintenance recommendations for human review.

This is a **predictive maintenance application with a bounded Agentic AI
workflow**. It is not an autonomous maintenance system or a general-purpose multi-agent platform.

The implementation must demonstrate:

1.  Context-aware expected-value modelling.
2.  Persistent drift detection and early warning.
3.  Deliberate handling of bad, missing, stale and implausible readings.
4.  Sensor-fault versus machinery-fault separation.
5.  Explainable findings and maintenance recommendations.
6.  Human approval and an auditable decision record.
7.  A reproducible evaluation against configured fixed alarm thresholds.

## 2. Source requirements and constraints

Use the supplied ThinkPalm POC brief as the functional source of truth.

Key requirements:

-   One asset: `DG-01` on `VESSEL-01`.
-   Approximately 36 sensor signals, sampled once per minute.
-   The reference dataset describes 30 days: 1--30 September 2026, or
    43,200 expected minute records.
-   Use generator load as a minimum operating-context variable. Use
    seawater temperature for cooling-related signals. Add other context
    variables only where justified by the signal.
-   Analyse only periods when the generator is running.
-   Respect record-quality flags and tag valid ranges.
-   Explicitly handle missing, stale, bad-quality and uncertain
    readings.
-   Select and document a defensible healthy training period.
-   Detect deviations that persist beyond configured tolerances.
-   Suppress findings caused by isolated spikes and normal load
    transitions.
-   Group related deviations into a finding with start time, affected
    system, actual-versus-expected evidence, severity and a concise
    explanation.
-   Suspected frozen, missing or implausible sensor behaviour must route
    to an instrument check. Do not create a machinery work order solely
    from a suspected sensor fault.
-   Compare first predictive detection time with the time a configured
    fixed threshold would have triggered.
-   Report false findings during healthy periods.
-   Only the Chief Engineer may approve or reject proposed maintenance
    jobs.
-   The Second Engineer may investigate but cannot approve jobs.
-   Fleet office access is read-only.
-   Record decision-maker, timestamp and rationale.
-   LLM use is optional. The application must run without an LLM and
    must not require paid services.
-   Do not connect to real vessel systems, ERP or PMS. Maintenance jobs
    and stock are mock/reference data.
-   No automatic maintenance execution.

**Dataset availability:** The CSV and JSON datasets referenced in the
brief were not supplied with the use-case document available for this
implementation. Therefore, Phase 1 must generate synthetic data matching
the required schema. Clearly label all generated data and evaluation
results as synthetic. Do not imply that synthetic results establish
real-world predictive performance.

## 3. Working principles

Follow these instructions throughout implementation:

-   Implement the project in the four phases below, in order.
-   Do not skip ahead to UI or agent orchestration before the predictive
    engine is working.
-   Keep the application as one small Python codebase with clear
    modules. Do not create microservices.
-   Prefer straightforward, readable code over abstractions that do not
    solve a current requirement.
-   Do not add Kafka, Redis, Kubernetes, cloud infrastructure, a message broker or distributed services.
-   Use SQLite for the POC. Do not introduce PostgreSQL unless
    explicitly requested.
-   Do not introduce multiple autonomous agents. Use one bounded
    LangGraph workflow in Phase 3 only if it adds clear value to
    conditional routing and human approval.
-   All detection, classification, severity and maintenance-routing
    decisions must be deterministic and testable. An LLM must not decide
    whether machinery is faulty.
-   The LLM may optionally turn already-computed evidence into
    plain-English wording. Provide a deterministic template fallback.
-   The core pipeline must work when no LLM credentials are configured,
    the provider is unavailable, or an LLM call fails.
-   Never invent sensor readings, alarm thresholds, fault evidence or
    maintenance inventory. Put simulation assumptions and configurable
    thresholds in explicit configuration/data files.
-   Keep ground-truth fault labels separate from telemetry features and
    never use them as model inputs.
-   Do not use future observations to predict or detect past events.
    Avoid data leakage in baseline training and evaluation.
-   Add tests for important logic as it is implemented. Do not defer all
    testing to the final phase.
-   Keep secrets in environment variables. Commit an `.env.example`,
    never real credentials.
-   Update the README with commands that work from a clean checkout.
-   Do not claim production readiness. Document limitations and what
    real-data validation remains necessary.
-   Before adding a dependency, check whether the standard library or an
    existing dependency is sufficient.
-   Do not change the required behaviour simply to make a test pass.
    Explain any change to assumptions or acceptance criteria.

## 4. Suggested lightweight technology choices

Use these unless a concrete implementation issue justifies a change:

  Area                    Choice
  ----------------------- --------------------------------------------------------
  Language                Python
  Data processing         Pandas, NumPy
  Expected-value models   Scikit-learn
  Statistical methods     SciPy and/or Statsmodels where useful
  API                     FastAPI
  UI                      Streamlit
  Charts                  Plotly
  Persistence             SQLite
  Tests                   Pytest
  Agent workflow          LangGraph, one bounded workflow
  LLM                     Optional provider adapter; no provider required to run

Keep dependencies and setup simple. The project should run locally
without paid services.

## 5. Four implementation phases

### Phase 1 --- Synthetic dataset generation and preparation

**Objective:** Produce reproducible synthetic inputs matching the POC's
stated data structure and operating characteristics.

Implement:

1.  A configurable synthetic data generator for 30 days of minute-level
    records.
2.  Approximately 36 sensor signals across operating context,
    lubrication, cooling/air, combustion (including 16 cylinder
    exhaust-temperature signals), and generator electrical measurements.
3.  `telemetry.csv` with timestamps, sensor values and record-quality
    information.
4.  `tags.csv` with tag identifiers, component, parameter, unit and
    valid minimum/maximum values.
5.  `context.csv` with ambient-air and seawater temperatures by minute,
    plus generator load where required by the telemetry schema.
6.  `maintenance_reference.json` with mock maintenance jobs, spare parts
    and stock availability.
7.  A separate ground-truth file describing injected fault type,
    affected sensor/system, fault onset, progression and configured
    fixed-alarm threshold.
8.  A data dictionary and documented simulation assumptions.

Include normal daily load variation, low measurement noise, gradual
fault scenarios, at least one sensor issue, missing readings, non-GOOD
quality records, isolated spikes and non-running periods.

Keep the generator deterministic through a configurable random seed.
Generate enough normal operating data to evaluate false findings
separately from injected fault periods.

Do not claim that the simulated sensor relationships or fault patterns
are validated marine-engineering models. Mark them as illustrative
assumptions requiring domain-expert validation.

**Deliverables:**

-   Synthetic input files.
-   Dataset generation script.
-   Separate ground-truth file.
-   Data dictionary and simulation assumptions.
-   Tests for row counts, timestamps, schema, reproducibility and
    injected scenarios.

**Exit criteria:**

-   The expected 43,200 minute timestamps are represented for the 30-day
    period, subject to any explicitly documented timestamp convention.
-   The schema is internally consistent and can be loaded by the
    application.
-   Ground-truth labels are separate from model input data.
-   Normal, faulty, missing, bad-quality and stopped-generator cases are
    present and reproducible.

### Phase 2 --- Deterministic predictive analytics and evaluation

**Objective:** Build and test the core capability that the POC is
primarily evaluating.

Implement the pipeline in this order:

1.  **Ingestion:** Load telemetry, tags and context; align timestamps
    and tag identifiers.
2.  **Data quality:** Apply record-quality flags and tag valid ranges.
    Represent missing, stale, bad-quality and uncertain readings
    explicitly. Do not silently convert invalid readings into normal
    observations.
3.  **Running-state filter:** Analyse only confirmed generator-running
    periods. Make the running-state rule explicit and configurable.
4.  **Healthy baseline selection:** Select and document a defensible
    healthy training period. Do not train on injected fault periods or
    use ground-truth labels as model features.
5.  **Expected behaviour:** Train a simple context-aware regression
    model for each applicable signal. Start with a straightforward
    Scikit-learn model. Use generator load at minimum and seawater
    temperature for cooling-related signals. Avoid deep learning unless
    evidence demonstrates a need.
6.  **Residuals:** Calculate actual minus expected values for valid
    observations.
7.  **Persistent drift:** Apply configurable residual tolerances,
    rolling persistence and data-availability rules. EWMA or CUSUM may
    be used where justified, but do not add multiple detectors without a
    demonstrated benefit. Isolated spikes and normal load transitions
    must not create persistent findings.
8.  **Sensor diagnostics:** Detect missing, frozen, out-of-range and
    implausible sensor behaviour using deterministic rules and temporal
    evidence. A constant value alone must not automatically prove a
    sensor fault.
9.  **Fault correlation:** Group related deviations by system and time.
    Keep the grouping rules transparent and configurable.
10. **Finding generation:** Produce a structured finding with
    identifier, asset, system, affected signals, start/detection times,
    severity, actual and expected values, residuals, persistence
    evidence, data-quality context and finding type.
11. **Maintenance mapping:** For machinery findings only, map to
    relevant mock maintenance jobs and check mock spare-part
    availability. Sensor findings route to an instrument check, not a
    machinery work order.
12. **Evaluation:** Compare first predictive detection time with
    configured fixed-threshold alarm time. Calculate lead time. Report
    false findings during known healthy periods and results for each
    injected scenario.

The operational fixed alarm thresholds must be configured separately
from tag valid minimum/maximum ranges. Do not treat a valid measurement
boundary as an alarm threshold. Since the original alarm configuration
is not supplied, document that simulated thresholds are assumptions.

**Deliverables:**

-   Runnable deterministic analytics pipeline.
-   Configurable baseline and detection settings.
-   Structured findings.
-   Sensor-versus-machinery routing.
-   Evaluation report with per-fault detection time, fixed-alarm time,
    lead time and healthy-period false findings.
-   Pytest coverage for data handling, baseline estimation, persistence
    detection, sensor diagnostics, routing and evaluation.

**Exit criteria:**

-   The pipeline runs without an LLM.
-   Bad or missing data does not become an anomaly by default.
-   Non-running periods are excluded.
-   Load transitions and isolated spikes do not produce persistent
    findings in the test scenarios.
-   Sensor faults cannot independently create machinery work orders.
-   Evaluation outputs are reproducible and explicitly labelled
    synthetic.
-   Baseline and drift-detection tests pass.

### Phase 3 --- Application UI and bounded Agentic AI workflow

**Objective:** Make the working analytics usable by the specified
engineering and shore users, and demonstrate a modest, controlled
Agentic AI capability.

Build the UI in this phase, after Phase 2 exposes stable finding and
telemetry structures.

**UI screens:**

1.  **Generator Overview**
    -   Generator running/stopped state.
    -   Current load and selected operating indicators.
    -   Overall findings summary.
    -   Active findings and data-quality status.
2.  **Sensor Monitoring**
    -   Actual versus expected readings.
    -   Time-series trend and anomaly markers.
    -   Relevant operating context.
    -   Clear indication of invalid or missing data.
3.  **Findings**
    -   Finding type and severity.
    -   Affected system and signals.
    -   Start time and first detection time.
    -   Evidence, explanation and recommended next action.
    -   Maintenance job and spare-part availability where applicable.
4.  **Maintenance Review**
    -   Proposed action.
    -   Approve/reject controls for Chief Engineer only.
    -   Decision rationale and history.

**Backend and access:**

-   Expose only the API endpoints needed by the UI.
-   Enforce role permissions in the backend, not only by hiding UI
    controls.
-   Chief Engineer: view, investigate, approve and reject.
-   Second Engineer: view and investigate; cannot approve or reject.
-   Fleet Office: read-only.
-   Persist findings, recommendations and decisions in SQLite.
-   Record decision-maker, timestamp and rationale.

**Bounded LangGraph workflow:**

Use one small workflow only if it provides clear value:

1.  Load an already-generated finding.
2.  Route sensor findings to an instrument-check path.
3.  Route machinery findings to maintenance-reference lookup.
4.  Retrieve relevant mock spare-part information.
5.  Generate a concise explanation from computed evidence.
6.  Validate the explanation against the evidence.
7.  Present the proposed action for human review.
8.  Record the human decision and audit event.

The LLM is optional and only supports wording. Use a deterministic
template when no model is configured or when the model call fails.
Validate generated text so unsupported numbers or factual claims are not
displayed as verified evidence. The workflow must not autonomously
approve or execute maintenance.

Do not create separate autonomous Telemetry, Machinery and Maintenance
agents. Deterministic Python modules are services/tools, not agents.
Describe the implementation accurately as a bounded workflow with
optional LLM-assisted explanation.

**Deliverables:**

-   Streamlit UI.
-   Minimal FastAPI backend.
-   SQLite persistence.
-   Backend-enforced role permissions.
-   One bounded LangGraph workflow, if used.
-   LLM-free template fallback.
-   Human approval and audit history.

**Exit criteria:**

-   A user can follow a finding from evidence through recommendation to
    review.
-   The application works without LLM credentials and without paid
    services.
-   Second Engineer and Fleet Office cannot approve or reject through
    direct API calls.
-   Sensor findings do not produce machinery work orders.
-   Every decision records the actor, timestamp and rationale.

### Phase 4 --- Validation, documentation and demonstration

**Objective:** Verify the acceptance criteria and make the POC easy to
run, inspect and explain.

Implement:

1.  Run all automated tests from a clean environment.
2.  Run end-to-end scenarios for each injected fault.
3.  Verify early-warning calculations against configured fixed
    thresholds.
4.  Review false findings during healthy periods.
5.  Verify data-quality and generator-running-state handling.
6.  Verify sensor-versus-machinery routing.
7.  Verify role permissions and audit records.
8.  Verify complete operation with the LLM disabled.
9.  Fix defects and document known limitations.
10. Prepare a short demonstration using clearly labelled synthetic data.

**Deliverables:**

-   Complete runnable source repository.
-   README with environment setup, data generation, application startup
    and test commands.
-   Technical note describing data treatment, healthy baseline
    selection, detection logic, assumptions and limitations.
-   Findings and evaluation report.
-   Automated test results.
-   Short demonstration script or walkthrough.

**Exit criteria:**

-   A reviewer can reproduce the dataset, run the application and
    execute tests using the README.
-   Mandatory POC requirements are mapped to implementation and test
    evidence.
-   All reported metrics identify whether they come from synthetic data.
-   Limitations and assumptions are explicit.
-   No claim of real-world predictive accuracy is made without real
    telemetry validation.

## 6. Suggested repository structure

Keep the structure compact. Adjust names only when the implementation
makes a clear case for doing so.

``` text
project/
├── AGENTS.md
├── README.md
├── requirements.txt
├── .env.example
├── config/
│   └── settings.yaml
├── data/
│   ├── synthetic/
│   └── ground_truth/
├── scripts/
│   └── generate_dataset.py
├── src/
│   ├── data/
│   │   ├── ingestion.py
│   │   └── validation.py
│   ├── analytics/
│   │   ├── baseline.py
│   │   ├── residuals.py
│   │   ├── drift.py
│   │   ├── sensor_diagnostics.py
│   │   └── findings.py
│   ├── maintenance/
│   │   └── recommendations.py
│   ├── workflow/
│   │   └── graph.py
│   ├── api/
│   │   └── main.py
│   └── storage/
│       └── repository.py
├── app/
│   └── streamlit_app.py
├── tests/
│   ├── test_data_quality.py
│   ├── test_baseline.py
│   ├── test_drift.py
│   ├── test_sensor_diagnostics.py
│   ├── test_findings.py
│   ├── test_evaluation.py
│   └── test_permissions.py
└── reports/
```

Do not create empty modules merely to match this tree. Add files when
their functionality is implemented.

## 7. Cross-cutting quality requirements

### Data and model integrity

-   Use explicit timestamps and a consistent timezone convention.
    Document it.
-   Preserve raw input data; do not overwrite source CSVs during
    processing.
-   Keep data-quality status separate from anomaly status.
-   Do not interpret unavailable data as normal data.
-   Do not train or evaluate using future information.
-   Store model settings and simulation settings so runs can be
    reproduced.
-   Make tolerances, persistence windows and alarm thresholds
    configurable rather than scattering constants through code.

### Finding integrity

Each finding should include enough structured evidence to reproduce its
explanation. At minimum:

-   Finding ID and asset ID.
-   Finding category: sensor or machinery.
-   Affected system and signal(s).
-   Start time and first detection time.
-   Actual value, expected value and residual where applicable.
-   Persistence window and valid-observation count.
-   Severity and the rule that assigned it.
-   Data-quality context.
-   Recommended next action.
-   Synthetic/real data provenance.

### Security and governance

-   Enforce permissions server-side.
-   Do not expose approval endpoints to unauthorized roles.
-   Do not allow an LLM to approve, reject or execute maintenance.
-   Record approval/rejection rationale and actor.
-   Do not commit credentials or sensitive data.
-   Keep the application advisory-only.

### Testing

Prefer tests of behaviour and acceptance criteria over tests that merely
mirror implementation details. Include:

-   Good, bad, missing, stale and out-of-range readings.
-   Generator running and stopped periods.
-   Normal load transitions.
-   Isolated spikes.
-   Persistent gradual drift.
-   Frozen sensors.
-   Sensor-to-instrument-check routing.
-   Machinery-to-maintenance routing.
-   Fixed-alarm comparison and lead-time calculation.
-   Healthy-period false findings.
-   Role-based approval restrictions.
-   LLM disabled and LLM failure paths.

## 8. How Codex should work

At the start of each phase:

1.  Inspect the existing repository and current implementation.
2.  Identify what is already complete; do not recreate working
    functionality.
3.  State the phase tasks and any assumptions.
4.  Implement only that phase's scope.
5.  Run relevant tests and fix failures.
6.  Update README and project notes where needed.
7.  Summarize changed files, commands run, test results, known issues
    and the next phase.

Do not start the next phase automatically unless explicitly asked. Keep
each change small enough to review.

If a requirement is ambiguous, prefer the simplest safe interpretation
and document it. Ask for clarification only when the ambiguity blocks
implementation or could change safety, data integrity or acceptance
behaviour.

## 9. Definition of done

The POC is complete when:

-   All four phases have been implemented.
-   The synthetic dataset is reproducible and clearly labelled.
-   The deterministic predictive pipeline works without an LLM.
-   Persistent deviations are detected with data-quality and
    running-state rules applied.
-   Sensor faults are separated from machinery findings.
-   Findings include explainable, reproducible evidence.
-   Fixed-alarm lead time and healthy-period false findings are
    reported.
-   Maintenance recommendations use the supplied mock reference data.
-   Chief Engineer approval/rejection is enforced and audited.
-   Second Engineer is unable to approve/reject.
-   Fleet Office is read-only.
-   The UI supports overview, sensor monitoring, findings and
    maintenance review.
-   Automated tests pass and the README enables a clean local run.
-   Assumptions, synthetic-data limitations and outstanding real-data
    validation are documented.

**Final guiding principle:** Build the smallest reliable solution that
satisfies the ThinkPalm POC. Prioritize predictive detection, data
quality, evaluation and safe human review. Add Agentic AI only where it
provides a clear workflow benefit.
