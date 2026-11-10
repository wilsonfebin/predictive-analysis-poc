# Predictive Results & Chart Calculation Audit

**Audit date:** 2026-11-08  
**Data provenance:** Synthetic; telemetry spans 2026-09-01 00:00 UTC through 2026-09-30 23:59 UTC.  
**Scope:** Read-only review of source, configuration, inputs, existing reports, dashboard/API calculations, and tests. No source, configuration, telemetry, existing result, or database was changed. A deterministic pipeline replay wrote only to a temporary directory, which was removed automatically.

## 1. Executive Summary

1. **Jacket-water expected-value model:** No material in-sample healthy-baseline bias was found. An independent OLS fit using the configured healthy period, load, and seawater temperature matches the stored residuals to within 0.0000005 °C for 39,566 valid running observations. The rising 15–24 °C gap later in September is a genuine injected synthetic degradation relative to the baseline expectation, not a chart arithmetic error. A small number of chart markers represent starts of contiguous tolerance-exceeding runs, not every violating observation or the finding’s detection time. This marker meaning is not obvious from the legend.
2. **Detection times and lead times:** All four machinery detection timestamps, all four fixed-alarm crossing timestamps, and lead times were independently recalculated from telemetry and configuration. They match the persisted evaluation exactly. Crossings were after onset, during running state, and GOOD quality; all timestamps are UTC. The frozen sensor was marked STALE and routed to an instrument check without a machinery finding.
3. **Four machinery findings:** They represent four distinct injected scenarios and four distinct affected signals. MACH-002 (jacket-water outlet) and MACH-003 (charge-air temperature) are separate cooling events, beginning 8 days 13 hours apart. They are not duplicate findings. However, both receive the same cooling-water-cooler work recommendation and spares; that recommendation is not sufficiently specific for the charge-air scenario.

**Overall conclusion:** The current synthetic residual calculations, persistence detection times, alarm crossings, and lead-time arithmetic are reproducible. No healthy-period false machinery finding was found. The principal calculation/integrity defect is severity being assigned from later event evidence and then represented as if it applied at first detection: all four are stored High, while the configured rule would classify each Medium at its first detection. The main chart issue is marker semantics and the display of BAD_SPIKE values on the same vertical scale; the latter can compress the valid trend. The audit report does not authorize implementation changes.

## 2. Audit Scope

Reviewed `AGENTS.md`, `config/detection.json`, synthetic telemetry/context/tags/ground truth, maintenance reference, `src/predictive.py`, `src/api.py`, `app/streamlit_app.py`, all existing `reports/*.json` and `reports/residuals.csv.gz`, and the existing tests. The report’s source references below use UTC and unrounded CSV/report values except where values are explicitly rounded for readability.

Reproducibility methods:

- Independently fit jacket-water OLS with NumPy least-squares on running, GOOD, in-range data from the configured 1–6 September training period, using load and seawater temperature.
- Recomputed residuals as actual minus expected, and compared them by timestamp with the stored compressed residual file.
- Independently replayed the persistence window and alarm predicates against aligned telemetry/context rows.
- Ran `run_pipeline` against the existing inputs/configuration with output directed to a temporary directory. Existing findings and scenario results compared exactly equal to the committed report artifacts.
- Ran `python3.11 -m unittest discover -s tests -v`: **19 tests passed**. Existing Streamlit AppTest `ScriptRunContext` warnings appeared in test mode; no test failed.

## 3. Jacket-water Model and Residual Analysis

**Sensor:** `jacket_water_outlet_c`, tag `JW_OUT`; description “Jacket water outlet temperature”; system `cooling`; unit `degC`; valid range 0–130 °C; criticality `high`.

The baseline model is OLS with intercept, generator load, and seawater temperature. Independent fit coefficients were approximately `[28.0477981, 0.3999372, 0.9983056]`. The training set contained 7,914 running, GOOD, in-range observations. Training RMSE was 0.08562 °C; configured tolerance is `max(1 °C, 4 × RMSE) = 1 °C`.

On the candidate healthy training observations:

| Statistic | Result |
|---|---:|
| Actual mean | 71.49303 °C |
| Expected mean | 71.49303 °C |
| Residual mean | approximately 0.00000 °C |
| Residual median | 0.00026 °C |
| Residual standard deviation | 0.08562 °C |
| Residual minimum / maximum | −0.32434 / +0.29715 °C |
| Absolute residuals above 1 °C | 0 of 7,914 |

Residual means were also close to zero across the observed load bands (20–40%: +0.0004 °C; 40–60%: −0.0013 °C; 60–80%: +0.0014 °C) and seawater bands (24–26 °C: +0.0002 °C; 26–28 °C: −0.0001 °C). There were no baseline samples in the other specified bins. This is an **in-sample** baseline check; it does not establish out-of-sample or real-engine accuracy.

For the 39,566 GOOD jacket-water residual records in the stored file, the independent residual comparison has correlation 0.9999999999999996, mean absolute difference 0.000000249 °C, and maximum absolute difference 0.000000500 °C. The small difference is consistent with stored residual rounding to six decimals.

Post-onset behavior is a progressive synthetic drift. Daily running/GOOD means show actual versus expected / mean residual:

| Date | Actual mean °C | Expected mean °C | Residual mean °C | p95 residual °C | Samples > +1 °C |
|---|---:|---:|---:|---:|---:|
| Sep 7 | 69.711 | 69.713 | −0.002 | 0.142 | 0 / 1,319 |
| Sep 11 | 72.187 | 72.190 | −0.003 | 0.144 | 0 / 1,319 |
| Sep 12 | 72.672 | 72.273 | +0.399 | 0.918 | 21 / 1,319 |
| Sep 13 | 73.626 | 71.956 | +1.670 | 2.210 | 1,310 / 1,319 |
| Sep 20 | 82.863 | 72.118 | +10.744 | 11.296 | 1,319 / 1,319 |
| Sep 24 | 86.097 | 70.168 | +15.929 | 16.482 | 1,319 / 1,319 |
| Sep 30 | 96.141 | 72.439 | +23.702 | 24.267 | 1,319 / 1,319 |

These table counts use valid running records, and “> +1 °C” follows the configured positive residual tolerance. **Conclusion:** no material healthy in-sample bias; a real synthetic injected deviation is present after onset. The displayed growing gap is consistent with the stored model output.

## 4. Healthy Baseline Assessment

The configured baseline is 2026-09-01 00:00 UTC inclusive to 2026-09-07 00:00 UTC exclusive. The 8,640 timestamps contain 720 stopped minutes and 7,920 running minutes. For jacket water, 7,914 samples remain after GOOD-quality and valid-range filtering.

Across all telemetry signals in those six calendar days there are 29 non-GOOD sensor cells: 9 lube-pressure MISSING, 7 jacket-water BAD_SPIKE, 5 fuel-pressure UNCERTAIN, and 8 generator-frequency BAD_QUALITY. These are quality records, not machinery findings. The baseline fit and detector filter running state and each signal’s quality/range separately.

No machinery finding starts in the healthy period; the persisted report and independent source inspection both yield **0 false machinery findings**. The recurring lube-pressure missing records produce one sensor diagnostic summary across the whole dataset, whose first missing timestamp is in the baseline. This is not a machinery false positive. Healthy-period count: one diagnostic type is represented (missing lube pressure); there are no frozen/stale sensor findings in this interval.

The stopped-state filter excludes 720 complete timestamp rows in this baseline. This overlaps, rather than adds to, the 29 raw non-GOOD sensor cells. The stored evaluation also reports 36 healthy 30-minute running load transitions of at least 10 percentage points and zero machinery findings from those transitions. Isolated spikes also yield zero machinery findings.

## 5. Persistence Detection Verification

Configuration: 180 running-minute history window, 120 residual-tolerance exceedances required; unit floors and `4 × baseline RMSE` are applied per signal. Only running GOOD and in-range samples contribute as qualifying residuals; a bad/missing running observation appends a non-qualifying slot. Stopped observations are skipped, so persistence is measured in running observations, not wall-clock minutes. This is explicit in the implementation and configuration.

Independent replay found the same first detection for every machinery finding. At each detection there were exactly 120 qualifying observations in the window. The first residual crossing can predate the first persistent event; for charge air, the initial crossing on Sep 20 was not itself persistent, and persistent evidence began Sep 21.

MACH-001 and MACH-003 both detected at 15:01 UTC on consecutive dates. The exact minute is not timestamp rounding: each is the first row where its directional count reached 120 in the 180-running-observation history. Both occur during the generator’s daily running period (daily 00:00–01:59 stoppage is documented). MACH-001 first crossed at 12:42 and became persistent at 15:01 the same day. MACH-003 had an earlier isolated crossing at Sep 20 12:09; the first qualifying run associated with its persistent detection starts Sep 21 12:20, with detection at 15:01. Thus the repeated clock time is explained by persistence accumulation during the operating schedule and the fault signals’ threshold history, not evidence of a duplicate event.

| Finding | Onset | First residual crossing | First persistent window evidence | First detection | Load / seawater at detection |
|---|---|---|---|---|---|
| MACH-001 · cylinder 07 | Sep 20 12:00 | Sep 20 12:42 | Sep 20 12:42 | Sep 20 15:01 | 62.272% / 26.712 °C |
| MACH-002 · jacket water | Sep 12 06:00 | Sep 12 19:43 | Sep 12 22:55 | Sep 13 03:50 | 29.864% / 26.925 °C |
| MACH-003 · charge air | Sep 19 00:00 | Sep 20 12:09 (initial crossing, not persistent) | Sep 21 12:20 | Sep 21 15:01 | 49.532% / 26.748 °C |
| MACH-004 · lube pressure | Sep 17 00:00 | Sep 17 05:59 | Sep 17 10:32 | Sep 17 13:27 | 56.129% / 24.249 °C |

All dates/times in this table are 2026 UTC. Sensor-fault verification: `F-SENSOR-01` freezes at Sep 8 03:00; the 60-running-minute flatline candidate ends at 04:00 with constant value 0.774498 bar; quality becomes STALE at 04:00. The diagnostic routes to `instrument_inspection`; evaluation confirms no machinery finding.

## 6. Fixed Alarm and Lead-Time Verification

The independent alarm scan started at each ground-truth onset and required running state, GOOD quality, then applied the configured `>=`/`<=` predicate to raw telemetry. Every alarm crossing was after onset and passed both state/quality checks. Detection and alarm timestamps are UTC; elapsed minutes were calculated as `(alarm − detection).total_seconds() / 60`.

| Scenario / finding | Detection UTC | Alarm crossing UTC | Threshold value at crossing | Recomputed lead | Stored lead |
|---|---|---|---:|---:|---:|
| F-CYL-01 / MACH-001 | Sep 20 15:01 | Sep 24 11:31 | 560.620 °C ≥ 560 | 5,550 min | 5,550 min |
| F-COOL-01 / MACH-002 | Sep 13 03:50 | Sep 24 12:44 | 96.261 °C ≥ 96 | 16,374 min | 16,374 min |
| F-COOL-02 / MACH-003 | Sep 21 15:01 | Sep 23 11:01 | 68.074 °C ≥ 68 | 2,640 min | 2,640 min |
| F-LUBE-01 / MACH-004 | Sep 17 13:27 | Sep 24 20:40 | 3.193 bar ≤ 3.2 | 10,513 min | 10,513 min |

The stored pipeline replay exactly matched both `findings.json` and `evaluation.json`. No stopped-state zero, missing value, non-GOOD value, or pre-onset alarm crossing was used. These are synthetic threshold comparisons, not validated engineering alarm settings.

## 7. Suspicious Timestamp Investigation

The Sep 20 and Sep 21 15:01 detections are both exact first-passage times to the 120-observation persistence count. The associated sensor, fault onset, actual/expected relationship, and qualifying sequence differ. Both occur during a common daily running schedule. The timing is therefore a reproducible consequence of the persistence/window plus schedule and signal trajectories; there is no evidence of rounding or event duplication. The earlier Sep 20 charge-air residual crossing was transient and did not start the detected persistent event.

## 8. Finding Grouping Assessment

The four machinery findings map one-to-one to four distinct synthetic fault scenarios and affected signals:

- MACH-001: F-CYL-01, `cylinder_07_exhaust_temp_c`, combustion, Sep 20.
- MACH-002: F-COOL-01, `jacket_water_outlet_c`, cooling, Sep 12.
- MACH-003: F-COOL-02, `charge_air_temperature_c`, cooling, Sep 21.
- MACH-004: F-LUBE-01, `lube_oil_pressure_bar`, lubrication, Sep 17.

MACH-002 and MACH-003 are independent events: different sensor IDs and ground-truth scenario IDs, different residual trajectories and onset times, and start times more than eight days apart. They are not duplicates and were not merged by the 60-minute same-system grouping rule.

**Mapping caveat:** Both cooling findings receive “Inspect and clean cooling-water cooler” with seawater-side spares from the single generic cooling maintenance action. This is plausible for jacket-water cooling, but does not specifically describe the charge-air cooler or its inspection. Ground truth and tag classification are consistently `cooling`; the gap is maintenance-reference specificity, not predictive classification. The grouping implementation could merge independent same-system events whose starts are within 60 minutes because it groups by system/start proximity rather than scenario/component identity; that did not occur in this dataset.

## 9. Severity Assessment

The configured rule assigns High when maximum absolute residual/tolerance ratio is at least 4, or when a high-criticality sensor has at least 240 qualifying observations. It assigns Medium at ratio at least 2 or for medium/high criticality. The detector calls this rule once using `all_points` accumulated through the end of the detected event; the resulting single severity is stored on the finding. It does not save an escalation history.

At first detection each finding has 120 qualifying observations and maximum ratio below 4; the rule therefore gives **Medium at first detection for all four**. At the dataset end, the final rolling evidence window exceeds ratio 4 for every sensor, which explains the stored High values:

| Finding | Criticality | Max ratio at first detection | Rule at first detection | End-window max ratio | Stored severity |
|---|---|---:|---|---:|---|
| MACH-001 | High | 2.976 | Medium | 230.659 | High |
| MACH-002 | High | 1.468 | Medium | 24.575 | High |
| MACH-003 | Medium | 1.623 | Medium | 5.021 | High |
| MACH-004 | High | 1.574 | Medium | 30.565 | High |

This is a verified look-ahead/classification-timing defect if severity is presented as severity **at first detection**: the full-interval later residuals influence the finding’s single stored severity. The implementation has no explicit severity progression record. High at the end of the synthetic month follows the configured rule; High at the original detection time does not.

## 10. Dashboard Chart Calculation Assessment

**Actual:** the dashboard uses the actual values returned from the existing residual history API, and the current chart code plots the actual line only for `quality_status == GOOD`. Non-GOOD values are plotted separately as quality-excluded markers. **Expected and residual tolerance:** the endpoint reads `reports/residuals.csv.gz`, whose expected/residual values come from the same baseline model and tolerance used by Phase 2. The chart does not independently recalculate model values or tolerance.

The endpoint’s per-row `anomaly` flag is `abs(normalised_deviation) >= 1`; this marks a residual-tolerance exceedance, not a persistent finding. The current Streamlit plot marks the start of each contiguous GOOD-quality exceedance run, rather than every violating sample. Purple vertical finding markers use stored finding timestamps. Therefore, a few red markers over a continuous high-residual period are not evidence that only a few readings exceeded tolerance; the rendered marker semantics are run starts. The legend says “Residual tolerance exceeded” but does not say “run starts,” which can reasonably be read as individual violations.

The endpoint currently returns all finding markers for a sensor, even when they are outside the requested time range. Current Streamlit chart code filters marker timestamps to the plotted data range and constrains the x-axis to that data range. Thus the source-level UI should not expand the seven-day x-axis for an old finding marker; the screenshot’s Sep 15–30 span is consistent with an older/stale running container or code version, not the current checked-in chart range. A runtime container was not available in this audit to confirm its image version.

## 11. Data Quality and False Finding Assessment

Jacket-water tag maximum is 130 °C. The raw telemetry has 35 `BAD_SPIKE` flags total, 34 while running; two jacket-water raw values exceed the 130 °C tag maximum, with an overall raw maximum of 140.265 °C. Both are marked BAD_SPIKE and excluded from residual/model scoring because quality is checked before range. The two values remain in raw telemetry. Current chart code displays non-GOOD raw values as separate quality markers, so they can still extend the chart y-axis and visually compress the valid 60–105 °C trend. They are not connected into the GOOD actual line.

Other raw non-GOOD counts across the 30-day file are: lube pressure MISSING 44; cooler seawater differential pressure STALE 32,880 (of which 30,240 running records are counted in diagnostics); fuel pressure UNCERTAIN 27; and generator frequency BAD_QUALITY 39. Differences between raw quality totals and diagnostics reflect running-state filtering. During the candidate baseline, the 29 flagged cells listed in Section 4 produce no machinery findings. Stored evaluation counts are zero for healthy-period machinery findings, healthy load-transition findings, isolated-spike findings, stopped-period findings, and poor-quality machinery findings.

Sensor selection and the sensor y-axis title use raw snake-case signal IDs; the sensor metadata already includes an engineering description. A user-friendly label could be derived from description plus unit. The Findings table has no blank records in the six current findings, and its displayed default order follows report order/IDs, not detection timestamp or severity; users may sort interactively, but the code defines no initial chronological/severity sort. “Findings by System” counts all categories together: cooling 3 (two machinery plus one sensor), lubrication 2 (one machinery plus one sensor), combustion 1. It is not machinery-only.

## 12. Timestamp and Historical Data Assessment

Telemetry and context align exactly from 2026-09-01 00:00:00 UTC through 2026-09-30 23:59:00 UTC, one-minute cadence. Ground truth, findings, residuals, alarms, and evaluation use UTC `Z` values. The last telemetry and context row is Sep 30 23:59 UTC. The overview’s “Latest analytics” value is derived from the processing-summary file modification time, 2026-11-08 11:08:40 UTC; the summary itself has no explicit `processed_at` field. The last load/state KPI comes from the Sep 30 final context row, not current vessel telemetry. “Current Load” and “RUNNING” can therefore sound live even though this is historical synthetic data. The page does label the dataset synthetic/advisory, but those two KPI labels should be understood as the last recorded historical values.

## 13. Defects Identified

| Priority | Finding | Evidence / observed behavior | Expected behavior |
|---|---|---|---|
| **MEDIUM** | Severity timing leakage, all four machinery findings | Every detection-time classification is Medium; stored value is High due end-window residual ratios (2.976–230.659). | Severity attached to first detection should use only information available then; any later escalation should be timestamped separately. |
| **MEDIUM** | Quality-excluded spikes share the sensor chart y-axis | Two jacket values exceed the 130 °C tag range (max 140.265 °C); they are preserved as quality markers but can compress the valid trend. | Keep invalid values accessible while preventing them from dominating the valid-series scale or clearly separate the quality view. |
| **MEDIUM** | Charge-air finding uses nonspecific cooling-water maintenance action | MACH-003 maps to charge-air temperature but recommends cleaning the cooling-water cooler and seawater-side parts. | Provide an action/reference appropriate to the charge-air cooler, or explicitly mark the generic mapping as such. |
| **LOW** | Sparse red marker meaning is unclear | Markers represent starts of contiguous tolerance-exceeding runs, not every tolerance failure or finding detection. | Label run starts distinctly and retain the separate finding-detection marker semantics. |
| **LOW** | Historical final state is labeled “Current” | Load and running status come from Sep 30 23:59 data; processing time is Nov 8. | Label these as latest recorded historical telemetry and show the observation timestamp. |
| **LOW** | Findings-by-system combines machinery and sensor diagnostics; default table order is not chronological | Current category mix yields cooling 3, lubrication 2, combustion 1; table follows report order. | Separate category counts or label total findings; choose an explicit initial sort. |
| **INFORMATIONAL** | API includes out-of-window finding markers in history responses | Endpoint returns sensor-related finding timestamps without filtering to requested start/end; current UI filters them before plotting. | Filter at API boundary as well if other clients consume this endpoint. |
| **INFORMATIONAL** | Grouping is system/time based | Same-system events within a 60-minute start gap could merge, even if independent; no such pair exists here. | Consider component/scenario identity in future grouping design if close independent events are introduced. |

No jacket-water model/residual arithmetic defect, no lead-time arithmetic defect, no duplicate MACH-002/MACH-003 finding, and no healthy-period false machinery finding were identified.

## 14. Recommended Corrections

In implementation order, subject to approval:

1. Calculate and store severity using evidence available at the detection timestamp; if later evidence raises severity, record an explicit escalation time and prior/new levels.
2. Keep BAD_SPIKE values visible but prevent quality-excluded points from setting the primary GOOD-trend y-axis; provide a clear way to inspect their raw value, quality flag, and timestamp.
3. Add a charge-air-specific mock maintenance action/spares reference and verify the scenario-to-reference mapping.
4. Clarify anomaly-run-start versus persistent-finding marker labels; filter finding markers in the API response as well as the UI.
5. Label the overview state/load as latest recorded values and show the source observation timestamp; make the analytics timestamp an explicit processing field rather than relying only on file mtime.
6. Separate machinery and sensor diagnostic totals in the system summary and set a deliberate default sort for findings.

These are recommendations only; no correction was applied in this audit.

## 15. Overall Audit Conclusion

The jacket-water expected model is not detectably biased on its configured healthy training sample; the later actual/expected gap is caused by the injected synthetic cooling degradation. Stored residual calculations reproduce independently. The visible sparse red markers summarize tolerance-exceedance run starts, not all violating observations, so the marker count is a chart communication choice rather than evidence of a calculation mismatch. BAD_SPIKE values remain visible and excluded from scoring, though they can distort the shared y-axis.

All four machinery detection times, all four fixed alarm crossings, and all lead-time minute counts are reproducible from the supplied synthetic telemetry. The two consecutive 15:01 detections follow distinct sensor trajectories and persistent-window accumulation during the daily operating schedule. There are four independent machinery scenarios, not four copies of one event; the two cooling findings are distinct jacket-water and charge-air events. No healthy-period false machinery findings are present.

The principal predictive integrity issue is retroactive High severity based on later evidence, where every finding would be Medium at first detection. The main maintenance mapping issue is charge-air’s generic cooling-water-cooler recommendation. The application remains a synthetic POC; none of these metrics establish real-vessel predictive performance.
