# Synthetic data dictionary

Every generated file is synthetic. Timestamps are UTC, inclusive from 2026-09-01 00:00 through 2026-09-30 23:59 (43,200 one-minute rows). Regenerate with `python3 scripts/generate_dataset.py --seed 20260901`.

## Files

- `data/telemetry.csv`: one asset row per minute; 36 measurement columns, each paired with `quality_<signal>` (`GOOD`, `MISSING`, `BAD_SPIKE`, `BAD_QUALITY`, `UNCERTAIN`, or `STALE`). Missing measurements are blank.
- `data/context.csv`: timestamp-aligned running state, load, speed, ambient-air temperature and seawater temperature. `generator_running` is lowercase Boolean text; load is percent.
- `data/tags.csv`: signal identifier, name, description, system, unit, illustrative valid measurement range, expected behaviour and criticality. These valid ranges are not operational alarm limits.
- `data/maintenance_reference.json`: mock system actions and spare-part availability; no external inventory connection.
- `data/ground_truth.json`: synthetic scenario labels, onset, progression, illustrative fixed alarm settings, data-quality notes and baseline selection. Keep this file out of model inputs.

## Signals (36)

| System | Signals | Units |
|---|---|---|
| Operating context | engine speed; generator load | rpm; % |
| Lubrication | oil pressure, oil temperature, sump level, filter differential pressure | bar, degC, %, bar |
| Cooling | jacket-water outlet temperature, jacket-water pressure, seawater inlet temperature, cooler seawater differential pressure, charge-air temperature | degC, bar, degC, bar, degC |
| Air intake/exhaust | charge-air pressure, exhaust receiver temperature, turbo speed | bar, degC, rpm |
| Combustion | fuel supply pressure, 16 cylinder exhaust temperatures | bar, degC each |
| Generator electrical | voltage, current, frequency, power factor, active power | V, A, Hz, ratio, kW |

Full per-signal descriptions and valid ranges are in `data/tags.csv`.

## Quality interpretation

Quality is independent of anomaly state. `GOOD` is the only ordinary valid status. `MISSING` has no value; `STALE` is a frozen signal labelled stale after an hour; `BAD_SPIKE` and `BAD_QUALITY` mark suspect readings; `UNCERTAIN` is retained but not asserted as valid. This Phase 1 generator records status; downstream handling belongs to Phase 2.
