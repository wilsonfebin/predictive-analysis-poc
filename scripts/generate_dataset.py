#!/usr/bin/env python3
"""Generate the clearly synthetic DG-01 Phase 1 reference dataset."""
import argparse
import csv
import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

VESSEL, GENERATOR = "VESSEL-01", "DG-01"
START = datetime(2026, 9, 1, tzinfo=timezone.utc)
MINUTES = 30 * 24 * 60


def tag(tag_id, name, description, system, unit, low, high, behaviour, criticality="medium"):
    return dict(tag_id=tag_id, signal_name=name, description=description,
                equipment_system=system, unit=unit, valid_min=low, valid_max=high,
                expected_operating_behaviour=behaviour, criticality=criticality)


def make_tags():
    tags = [
        tag("ENG_SPEED", "engine_speed_rpm", "Engine rotational speed", "operating_context", "rpm", 0, 1200, "Near rated speed while running; zero while stopped", "high"),
        tag("GEN_LOAD", "generator_load_pct", "Generator electrical load", "operating_context", "%", 0, 110, "Daily demand variation; zero while stopped", "high"),
        tag("LO_PRESS", "lube_oil_pressure_bar", "Main lube oil pressure", "lubrication", "bar", 0, 10, "Rises with running state and modestly with load", "high"),
        tag("LO_TEMP", "lube_oil_temperature_c", "Lube oil temperature", "lubrication", "degC", -10, 150, "Load and ambient dependent", "high"),
        tag("LO_LEVEL", "lube_oil_level_pct", "Sump level indication", "lubrication", "%", 0, 100, "Slowly varying level", "medium"),
        tag("LO_FILTER", "lube_filter_dp_bar", "Lube filter differential pressure", "lubrication", "bar", 0, 3, "Small load dependence", "medium"),
        tag("JW_OUT", "jacket_water_outlet_c", "Jacket water outlet temperature", "cooling", "degC", 0, 130, "Load and seawater temperature dependent", "high"),
        tag("JW_PRESS", "jacket_water_pressure_bar", "Jacket water pressure", "cooling", "bar", 0, 10, "Rises with load while running", "high"),
        tag("SW_IN", "seawater_inlet_c", "Seawater inlet temperature", "cooling", "degC", -5, 50, "Environmental context dependent", "medium"),
        tag("SW_DP", "cooler_seawater_dp_bar", "Illustrative cooler seawater differential pressure", "cooling", "bar", 0, 5, "Near nominal; degradation scenario reduces heat transfer", "medium"),
        tag("AIR_P", "charge_air_pressure_bar", "Charge air pressure", "air_intake_exhaust", "bar", 0, 8, "Increases with load", "high"),
        tag("AIR_T", "charge_air_temperature_c", "Charge air temperature", "cooling", "degC", -10, 120, "Load, ambient and cooler condition dependent", "medium"),
        tag("EXH_OUT", "exhaust_receiver_temp_c", "Exhaust receiver temperature", "air_intake_exhaust", "degC", 0, 800, "Increases with load", "high"),
        tag("TURBO", "turbo_speed_rpm", "Turbocharger speed", "air_intake_exhaust", "rpm", 0, 60000, "Increases with load", "medium"),
        tag("FUEL_P", "fuel_supply_pressure_bar", "Fuel supply pressure", "combustion", "bar", 0, 20, "Stable while running", "medium"),
    ]
    for cyl in range(1, 17):
        tags.append(tag("CYL{:02d}_EGT".format(cyl), "cylinder_{:02d}_exhaust_temp_c".format(cyl),
                        "Cylinder {:02d} exhaust gas temperature".format(cyl), "combustion", "degC", 0, 900,
                        "Load dependent; small cylinder-to-cylinder variation", "high"))
    tags += [
        tag("GEN_VOLT", "generator_voltage_v", "Generator terminal voltage", "generator_electrical", "V", 0, 600, "Regulated near nominal while online", "high"),
        tag("GEN_CURR", "generator_current_a", "Generator current", "generator_electrical", "A", 0, 3000, "Proportional to load", "high"),
        tag("GEN_FREQ", "generator_frequency_hz", "Generator frequency", "generator_electrical", "Hz", 0, 100, "Regulated near nominal while online", "high"),
        tag("GEN_PF", "generator_power_factor", "Generator power factor", "generator_electrical", "ratio", 0, 1, "Moderately stable under load", "medium"),
        tag("GEN_KW", "generator_active_power_kw", "Generator active power", "generator_electrical", "kW", 0, 2500, "Proportional to load", "high"),
    ]
    assert len(tags) == 36
    return tags


def fault_scenarios():
    return [
        dict(scenario_id="F-COOL-01", category="machinery", system="cooling", affected_signals=["jacket_water_outlet_c"], onset="2026-09-12T06:00:00Z", progression="Linear +0.0009 degC per minute while running", alarm=dict(signal="jacket_water_outlet_c", operator=">=", value=96, unit="degC"), expected_detection="Persistent positive residual; illustrative fixed alarm at 96 degC"),
        dict(scenario_id="F-LUBE-01", category="machinery", system="lubrication", affected_signals=["lube_oil_pressure_bar"], onset="2026-09-17T00:00:00Z", progression="Linear -0.00012 bar per running minute", alarm=dict(signal="lube_oil_pressure_bar", operator="<=", value=3.2, unit="bar"), expected_detection="Persistent negative residual; illustrative fixed alarm at 3.2 bar"),
        dict(scenario_id="F-CYL-01", category="machinery", system="combustion", affected_signals=["cylinder_07_exhaust_temp_c"], onset="2026-09-20T12:00:00Z", progression="Linear +0.025 degC per elapsed minute after onset", alarm=dict(signal="cylinder_07_exhaust_temp_c", operator=">=", value=560, unit="degC"), expected_detection="Persistent imbalance relative to other cylinders; illustrative fixed alarm at 560 degC"),
        dict(scenario_id="F-SENSOR-01", category="sensor_fault", system="cooling", affected_signals=["cooler_seawater_dp_bar"], onset="2026-09-08T03:00:00Z", progression="Sensor value freezes at its onset reading; quality marked STALE after 60 minutes", alarm=None, expected_detection="Instrument check candidate from frozen/stale diagnostic; constant value alone is not proof"),
        dict(scenario_id="F-COOL-02", category="machinery", system="cooling", affected_signals=["charge_air_temperature_c"], onset="2026-09-19T00:00:00Z", progression="Linear +0.0010 degC per elapsed minute after onset", alarm=dict(signal="charge_air_temperature_c", operator=">=", value=68, unit="degC"), expected_detection="Persistent positive residual; illustrative fixed alarm at 68 degC"),
    ]


def generate(out_dir, seed=20260901):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    tags = make_tags()
    by_name = {t["signal_name"]: t for t in tags}
    scenario = fault_scenarios()
    onset = {f["scenario_id"]: datetime.fromisoformat(f["onset"].replace("Z", "+00:00")) for f in scenario}
    frozen_value = None
    telemetry_path, context_path = out / "telemetry.csv", out / "context.csv"
    signals = [t["signal_name"] for t in tags]
    with telemetry_path.open("w", newline="") as tf, context_path.open("w", newline="") as cf:
        tw, cw = csv.writer(tf), csv.writer(cf)
        tw.writerow(["timestamp", "vessel_id", "generator_id"] + signals + ["quality_" + s for s in signals])
        cw.writerow(["timestamp", "vessel_id", "generator_id", "generator_running", "generator_load_pct", "engine_speed_rpm", "ambient_air_temp_c", "seawater_temp_c"])
        for i in range(MINUTES):
            ts = START + timedelta(minutes=i)
            minute_day = ts.hour * 60 + ts.minute
            # Daily demand cycle plus a smooth intraday variation; 00:00-01:59 each day is stopped.
            running = not (minute_day < 120)
            daily = 0.42 + 0.20 * math.sin(2 * math.pi * (minute_day - 360) / 1440)
            variation = 0.05 * math.sin(2 * math.pi * i / 310) + 0.025 * math.sin(2 * math.pi * i / 73)
            load = max(0.18, min(0.88, daily + variation)) if running else 0.0
            ambient = 27 + 3.5 * math.sin(2 * math.pi * (minute_day - 420) / 1440) + rng.gauss(0, .18)
            sea = 25.5 + 1.4 * math.sin(2 * math.pi * i / (1440 * 9)) + rng.gauss(0, .12)
            speed = 750 + rng.gauss(0, 1.2) if running else 0.0
            idx = {"F-COOL-01": i - int((onset["F-COOL-01"]-START).total_seconds()/60), "F-LUBE-01": i - int((onset["F-LUBE-01"]-START).total_seconds()/60), "F-CYL-01": i - int((onset["F-CYL-01"]-START).total_seconds()/60), "F-COOL-02": i - int((onset["F-COOL-02"]-START).total_seconds()/60)}
            warmup = 1.0 if running else 0.0
            vals = {
                "engine_speed_rpm": speed, "generator_load_pct": load*100,
                "lube_oil_pressure_bar": (4.5 + .35*load if running else 0) - max(0,idx["F-LUBE-01"])*.00012 if running else 0,
                "lube_oil_temperature_c": (58 + 27*load + .18*(ambient-27)) if running else ambient,
                "lube_oil_level_pct": 78 + .15*math.sin(i/600),
                "lube_filter_dp_bar": (.28 + .25*load) if running else 0,
                "jacket_water_outlet_c": (sea + 28 + 40*load + max(0,idx["F-COOL-01"])*.0009) if running else sea,
                "jacket_water_pressure_bar": (2.1 + .9*load) if running else 0,
                "seawater_inlet_c": sea,
                "cooler_seawater_dp_bar": (.75 + .08*load) if running else 0,
                "charge_air_pressure_bar": (0.35 + 2.5*load) if running else 0,
                "charge_air_temperature_c": (ambient + 13 + 28*load + max(0,idx["F-COOL-02"])*.001) if running else ambient,
                "exhaust_receiver_temp_c": (180 + 350*load) if running else ambient,
                "turbo_speed_rpm": (9000 + 29000*load) if running else 0,
                "fuel_supply_pressure_bar": (6.0 + .4*load) if running else 0,
                "generator_voltage_v": (440 + rng.gauss(0, .5)) if running else 0,
                "generator_current_a": (load*1350) if running else 0,
                "generator_frequency_hz": (50 + rng.gauss(0, .025)) if running else 0,
                "generator_power_factor": (.84 + .04*load) if running else 0,
                "generator_active_power_kw": (load*1500) if running else 0,
            }
            for c in range(1, 17):
                vals["cylinder_{:02d}_exhaust_temp_c".format(c)] = (190 + 345*load + (c-8.5)*.55 + (max(0,idx["F-CYL-01"])*.025 if c == 7 else 0)) if running else ambient
            # Small measurement noise, scaled by signal. Context signals receive low noise too.
            for s in signals:
                if s not in ("engine_speed_rpm", "generator_load_pct", "seawater_inlet_c", "lube_oil_level_pct", "generator_voltage_v", "generator_frequency_hz"):
                    vals[s] += rng.gauss(0, max(.015, abs(vals[s])*.0012))
            if i >= int((onset["F-SENSOR-01"]-START).total_seconds()/60):
                if frozen_value is None:
                    frozen_value = vals["cooler_seawater_dp_bar"]
                vals["cooler_seawater_dp_bar"] = frozen_value
            qualities = {s: "GOOD" for s in signals}
            # Deterministic quality events distributed across the healthy period and fault periods.
            if i % 997 == 211:
                s = "lube_oil_pressure_bar"; vals[s] = ""; qualities[s] = "MISSING"
            if i % 1237 == 509:
                s = "jacket_water_outlet_c"; vals[s] = float(vals[s]) + 35; qualities[s] = "BAD_SPIKE"
            if i % 1103 == 641:
                s = "generator_frequency_hz"; qualities[s] = "BAD_QUALITY"
            if i % 1601 == 801:
                s = "fuel_supply_pressure_bar"; qualities[s] = "UNCERTAIN"
            if ts >= onset["F-SENSOR-01"] + timedelta(minutes=60):
                qualities["cooler_seawater_dp_bar"] = "STALE"
            tw.writerow([ts.strftime("%Y-%m-%dT%H:%M:%SZ"), VESSEL, GENERATOR] + [vals[s] for s in signals] + [qualities[s] for s in signals])
            cw.writerow([ts.strftime("%Y-%m-%dT%H:%M:%SZ"), VESSEL, GENERATOR, str(running).lower(), round(load*100, 3), round(speed, 3), round(ambient, 3), round(sea, 3)])
    with (out / "tags.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(tags[0])); w.writeheader(); w.writerows(tags)
    (out / "ground_truth.json").write_text(json.dumps({"provenance":"synthetic","timezone":"UTC","seed":seed,"period":{"start":"2026-09-01T00:00:00Z","end_exclusive":"2026-10-01T00:00:00Z","sampling_minutes":1,"expected_rows":MINUTES},"healthy_training_period":{"start":"2026-09-01T00:00:00Z","end_exclusive":"2026-09-07T00:00:00Z","selection":"Before the earliest injected fault onset; exclude all non-GOOD records and verify valid ranges before model fitting.","limitations":"Contains ordinary stopped periods and periodic quality events; running state and quality filters remain necessary."},"fault_scenarios":scenario,"data_quality_events":{"missing":"Periodic lube-oil pressure values are blank with MISSING status.","isolated_spikes":"Periodic jacket-water outlet outliers marked BAD_SPIKE.","bad_quality":"Periodic generator-frequency records marked BAD_QUALITY.","uncertain":"Periodic fuel-pressure readings marked UNCERTAIN.","stale":"Frozen cooler differential-pressure signal marked STALE after 60 minutes.","implausible":"The marked BAD_SPIKE values are intentionally outside typical behaviour but remain within tag range; tag-range violations are not separately injected."},"disclaimer":"All telemetry and thresholds are illustrative synthetic data, not validated marine-engineering models."}, indent=2)+"\n")
    (out / "maintenance_reference.json").write_text(json.dumps({"provenance":"synthetic mock reference data","asset":"DG-01","systems":[{"system":"cooling","fault_categories":["high_temperature","cooler_degradation"],"inspection_actions":["Check cooling-water flow and cooler condition","Inspect seawater-side strainer and heat-transfer surfaces"],"maintenance_actions":[{"action_id":"MA-COOL-01","description":"Inspect and clean cooling-water cooler","spares":["GASKET-COOL-01","FILTER-SW-01"]}]},{"system":"lubrication","fault_categories":["low_pressure"],"inspection_actions":["Verify pressure with an independent gauge","Inspect filters and pump condition"],"maintenance_actions":[{"action_id":"MA-LUBE-01","description":"Inspect lubrication circuit and renew filter if required","spares":["FILTER-LO-01"]}]},{"system":"combustion","fault_categories":["cylinder_temperature_imbalance"],"inspection_actions":["Compare cylinder exhaust temperatures and inspect the affected cylinder"],"maintenance_actions":[{"action_id":"MA-COMB-01","description":"Inspect cylinder combustion condition","spares":["INJECTOR-SEAL-01"]}]},{"system":"instrumentation","fault_categories":["frozen","missing","stale","implausible"],"inspection_actions":["Check transmitter, wiring and signal freshness; compare with an independent measurement"],"maintenance_actions":[]}],"inventory":[{"part_id":"GASKET-COOL-01","description":"Cooler gasket set","quantity_available":2},{"part_id":"FILTER-SW-01","description":"Seawater filter element","quantity_available":4},{"part_id":"FILTER-LO-01","description":"Lube oil filter element","quantity_available":3},{"part_id":"INJECTOR-SEAL-01","description":"Injector seal kit","quantity_available":1}]}, indent=2)+"\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20260901, help="reproducible random seed")
    parser.add_argument("--output-dir", default="data", help="directory for generated CSV and JSON files")
    args = parser.parse_args()
    generate(args.output_dir, args.seed)
