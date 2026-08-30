"""Strict technical-pilot validation for the fixed-wrapper experiment.

Unlike the original checker, missing cells or files are failures. The gates here
implement the validation requirements in ``ANTIGRAVITY_BLUEPRINT.md`` and emit a
machine-readable report alongside the console summary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Iterable

import numpy as np
import pandas as pd

from analysis.metrics import (
    depth_at_touch_tw,
    midpoint_error_tw,
    quoted_spread_tw,
    recovery_time_s,
)


PILOT_SEEDS = [1001, 1002, 1003]
FINAL_SEEDS = list(range(2001, 2031))
CELLS = [f"C{number}-{regime}" for regime in ("N", "S") for number in range(1, 6)]
WRAPPER_CELLS = {
    "C2-N": 60, "C3-N": 60, "C4-N": 300, "C5-N": 300,
    "C2-S": 60, "C3-S": 60, "C4-S": 300, "C5-S": 300,
}
MECHANICAL_PAIRS = [
    ("C3-N", "C2-N", 60),
    ("C5-N", "C4-N", 300),
    ("C3-S", "C2-S", 60),
    ("C5-S", "C4-S", 300),
]
REGIME_GROUPS = {
    "N": ["C1-N", "C2-N", "C3-N", "C4-N", "C5-N"],
    "S": ["C1-S", "C2-S", "C3-S", "C4-S", "C5-S"],
}
LLM_CELLS = ["C3-N", "C5-N", "C3-S", "C5-S"]
REQUIRED_PARQUETS = [
    "decisions.parquet", "orders.parquet", "trades.parquet",
    "book_l1.parquet", "fundamental.parquet", "agent_state.parquet",
    "treatment_requests.parquet",
]


@dataclass
class ValidationResult:
    gate_name: str
    checks: list[tuple[str, bool, str]] = field(default_factory=list)

    def add(self, description: str, passed: bool, detail: str = "") -> None:
        self.checks.append((description, bool(passed), detail))

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(passed for _, passed, _ in self.checks)

    @property
    def pass_count(self) -> int:
        return sum(passed for _, passed, _ in self.checks)

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"Gate: {self.gate_name} - {status} ({self.pass_count}/{len(self.checks)})"


def _run_dir(log_root: str, cell: str, seed: int) -> str:
    return os.path.join(log_root, cell, str(seed))


def _load_parquet(path: str) -> pd.DataFrame:
    if not os.path.isfile(path):
        raise FileNotFoundError(2, "Parquet output not found", path)
    return pd.read_parquet(path)


def _frame_hash(frame: pd.DataFrame, columns: Iterable[str]) -> str:
    """Stable SHA-256 for selected, sorted dataframe columns."""
    columns = list(columns)
    normalized = frame[columns].copy()
    for column in columns:
        if pd.api.types.is_datetime64_any_dtype(normalized[column]):
            normalized[column] = normalized[column].astype("int64")
    normalized = normalized.sort_values(columns, kind="mergesort").reset_index(drop=True)
    hashed = pd.util.hash_pandas_object(normalized, index=False).values.tobytes()
    return hashlib.sha256(hashed).hexdigest()


def gate_output_completeness(log_root: str, seeds: list[int]) -> ValidationResult:
    result = ValidationResult("Gate 0: Output Completeness")
    for seed in seeds:
        for cell in CELLS:
            directory = _run_dir(log_root, cell, seed)
            manifest_path = os.path.join(directory, "run_manifest.json")
            missing = [name for name in REQUIRED_PARQUETS if not os.path.isfile(os.path.join(directory, name))]
            result.add(
                f"{cell} seed={seed}: required outputs",
                os.path.isfile(manifest_path) and not missing,
                f"manifest={os.path.isfile(manifest_path)}, missing={missing}",
            )
            if os.path.isfile(manifest_path):
                with open(manifest_path, "r", encoding="utf-8") as handle:
                    manifest = json.load(handle)
                identity_ok = manifest.get("cell_full") == cell and manifest.get("seed") == seed
                result.add(
                    f"{cell} seed={seed}: manifest identity",
                    identity_ok,
                    f"cell_full={manifest.get('cell_full')}, seed={manifest.get('seed')}",
                )
    return result


def _wrapper_cell_checks(result: ValidationResult, log_root: str, cell: str, seed: int, interval_s: int) -> None:
    directory = _run_dir(log_root, cell, seed)
    try:
        decisions = _load_parquet(os.path.join(directory, "decisions.parquet"))
        requests = _load_parquet(os.path.join(directory, "treatment_requests.parquet"))
    except FileNotFoundError as exc:
        result.add(f"{cell} seed={seed}: wrapper audit", False, f"missing {os.path.basename(exc.filename)}")
        return

    essential = {
        "time", "final_side", "limit_price", "snapshot_best_bid",
        "snapshot_best_ask", "quantity",
    }
    result.add(
        f"{cell} seed={seed}: decision data present",
        not decisions.empty and essential.issubset(decisions.columns),
        f"rows={len(decisions)}, missing_columns={sorted(essential - set(decisions.columns))}",
    )
    if decisions.empty or not essential.issubset(decisions.columns):
        return

    times = pd.to_datetime(decisions["time"]).sort_values().reset_index(drop=True)
    deltas = times.diff().dropna().dt.total_seconds()
    cadence_ok = not deltas.empty and bool(np.isclose(deltas, interval_s, atol=1e-6).all())
    result.add(
        f"{cell} seed={seed}: fixed {interval_s}s cadence",
        cadence_ok,
        f"decisions={len(times)}, unique_deltas={sorted(deltas.unique().tolist())[:5]}",
    )

    quantities_ok = bool((pd.to_numeric(decisions["quantity"]) == 100).all())
    sides_ok = bool(decisions["final_side"].isin(["BUY", "SELL"]).all())
    expected_price = np.where(
        decisions["final_side"].eq("BUY"),
        decisions["snapshot_best_bid"].fillna(100000),
        decisions["snapshot_best_ask"].fillna(100000),
    )
    placement_ok = bool(np.array_equal(pd.to_numeric(decisions["limit_price"]).to_numpy(), expected_price))
    result.add(f"{cell} seed={seed}: fixed lot size", quantities_ok, "required quantity=100")
    result.add(f"{cell} seed={seed}: valid final sides", sides_ok, "allowed=BUY,SELL")
    result.add(f"{cell} seed={seed}: at-touch placement", placement_ok, "BUY=best bid, SELL=best ask")

    submissions = requests[requests["event_type"] == "ORDER_SUBMITTED"].copy()
    submissions = submissions.sort_values(["time", "order_id"]).reset_index(drop=True)
    decisions_sorted = decisions.sort_values("time").reset_index(drop=True)
    submission_ok = len(submissions) == len(decisions_sorted)
    detail = f"submissions={len(submissions)}, decisions={len(decisions_sorted)}"
    if submission_ok:
        submission_ok = bool(
            np.array_equal(submissions["direction"].astype(str), decisions_sorted["final_side"].astype(str))
            and np.array_equal(pd.to_numeric(submissions["quantity"]), pd.to_numeric(decisions_sorted["quantity"]))
            and np.array_equal(pd.to_numeric(submissions["price"]), pd.to_numeric(decisions_sorted["limit_price"]))
        )
        detail += ", chronological side/size/price match=" + str(submission_ok)
    result.add(f"{cell} seed={seed}: forced submission per wake", submission_ok, detail)

    cancellations = requests[requests["event_type"] == "CANCEL_SUBMITTED"].copy()
    submitted_ids = set(submissions["order_id"].dropna().astype(int))
    cancelled_ids = cancellations["order_id"].dropna().astype(int)
    max_per_wake = int(cancellations.groupby("time").size().max()) if not cancellations.empty else 0
    cancellation_contract_ok = bool(
        set(cancelled_ids).issubset(submitted_ids)
        and not cancelled_ids.duplicated().any()
        and max_per_wake <= 1
        and len(cancellations) <= len(submissions)
    )
    result.add(
        f"{cell} seed={seed}: cancel-all request contract",
        cancellation_contract_ok,
        f"cancellations={len(cancellations)}, max_per_wake={max_per_wake}, "
        f"all target prior unique submissions={set(cancelled_ids).issubset(submitted_ids)}",
    )


def gate_mechanics_identity(log_root: str, seeds: list[int]) -> ValidationResult:
    result = ValidationResult("Gate 1: Mechanics-Identity Audit")
    for seed in seeds:
        for cell, interval_s in WRAPPER_CELLS.items():
            _wrapper_cell_checks(result, log_root, cell, seed, interval_s)

        for treatment, control, _ in MECHANICAL_PAIRS:
            try:
                t_dec = _load_parquet(os.path.join(_run_dir(log_root, treatment, seed), "decisions.parquet"))
                c_dec = _load_parquet(os.path.join(_run_dir(log_root, control, seed), "decisions.parquet"))
                t_ord = _load_parquet(os.path.join(_run_dir(log_root, treatment, seed), "orders.parquet"))
                c_ord = _load_parquet(os.path.join(_run_dir(log_root, control, seed), "orders.parquet"))
                t_req = _load_parquet(os.path.join(_run_dir(log_root, treatment, seed), "treatment_requests.parquet"))
                c_req = _load_parquet(os.path.join(_run_dir(log_root, control, seed), "treatment_requests.parquet"))
            except FileNotFoundError as exc:
                result.add(f"{treatment} vs {control} seed={seed}: identity", False, str(exc))
                continue

            t_times = pd.to_datetime(t_dec["time"]).sort_values().reset_index(drop=True)
            c_times = pd.to_datetime(c_dec["time"]).sort_values().reset_index(drop=True)
            if len(t_times) == len(c_times):
                schedule_delta_ns = np.abs((t_times - c_times).astype("timedelta64[ns]").astype("int64"))
                schedule_ok = bool((schedule_delta_ns <= 1_000).all())
                max_schedule_delta_ns = int(schedule_delta_ns.max()) if len(schedule_delta_ns) else 0
            else:
                schedule_ok = False
                max_schedule_delta_ns = -1
            t_submit = t_req[t_req["event_type"] == "ORDER_SUBMITTED"]
            c_submit = c_req[c_req["event_type"] == "ORDER_SUBMITTED"]
            submissions_ok = len(t_submit) == len(c_submit)
            t_cancel = t_req[t_req["event_type"] == "CANCEL_SUBMITTED"]
            c_cancel = c_req[c_req["event_type"] == "CANCEL_SUBMITTED"]
            result.add(
                f"{treatment} vs {control} seed={seed}: wake count/schedule",
                schedule_ok,
                f"treatment={len(t_dec)}, control={len(c_dec)}, max_delta_ns={max_schedule_delta_ns}",
            )
            result.add(
                f"{treatment} vs {control} seed={seed}: submission count",
                submissions_ok,
                f"treatment={len(t_submit)}, control={len(c_submit)}",
            )
    return result


def _background_prefix_hash(orders: pd.DataFrame, cutoff: pd.Timestamp) -> tuple[str, int]:
    background = orders[
        orders["agent_id"].between(1, 9, inclusive="both")
        & (pd.to_datetime(orders["time"]) < cutoff)
    ].copy()
    columns = ["time", "order_id", "agent_id", "direction", "quantity", "price", "status"]
    return _frame_hash(background, columns), len(background)


def gate_pairing_audit(log_root: str, seeds: list[int]) -> ValidationResult:
    result = ValidationResult("Gate 2: Pairing Audit")
    for seed in seeds:
        for regime, cells in REGIME_GROUPS.items():
            fundamentals = {}
            orders_by_cell = {}
            first_treatment_events = {}
            missing = []
            for cell in cells:
                directory = _run_dir(log_root, cell, seed)
                try:
                    fund = _load_parquet(os.path.join(directory, "fundamental.parquet"))
                    orders = _load_parquet(os.path.join(directory, "orders.parquet"))
                except FileNotFoundError:
                    missing.append(cell)
                    continue
                fundamentals[cell] = (_frame_hash(fund, ["time", "symbol", "value"]), len(fund))
                orders_by_cell[cell] = orders
                treatment = orders[(orders["agent_id"] == 10) & (orders["status"] == "ACCEPTED")]
                if not treatment.empty:
                    first_treatment_events[cell] = pd.to_datetime(treatment["time"]).min()

            if missing or len(fundamentals) != len(cells):
                result.add(
                    f"Regime {regime} seed={seed}: exact fundamental path",
                    False,
                    f"missing cells={missing}",
                )
                continue

            unique_fund_hashes = {item[0] for item in fundamentals.values()}
            result.add(
                f"Regime {regime} seed={seed}: exact fundamental path",
                len(unique_fund_hashes) == 1,
                "rows/hashes=" + str({cell: (count, digest[:10]) for cell, (digest, count) in fundamentals.items()}),
            )

            if len(first_treatment_events) != len(cells):
                result.add(
                    f"Regime {regime} seed={seed}: background stream before treatment",
                    False,
                    f"missing first treatment event={sorted(set(cells) - set(first_treatment_events))}",
                )
            else:
                cutoff = min(first_treatment_events.values())
                hashes = {cell: _background_prefix_hash(orders_by_cell[cell], cutoff) for cell in cells}
                result.add(
                    f"Regime {regime} seed={seed}: background stream before first treatment action",
                    len({digest for digest, _ in hashes.values()}) == 1,
                    f"cutoff={cutoff}, rows/hashes=" + str({cell: (n, h[:10]) for cell, (h, n) in hashes.items()}),
                )

            wrapper_cells = cells[1:]
            wrapper_first = {
                cell: first_treatment_events[cell]
                for cell in wrapper_cells if cell in first_treatment_events
            }
            if len(wrapper_first) == len(wrapper_cells):
                cutoff = min(wrapper_first.values())
                hashes = {cell: _background_prefix_hash(orders_by_cell[cell], cutoff) for cell in wrapper_cells}
                result.add(
                    f"Regime {regime} seed={seed}: wrapper-arm background stream through warmup",
                    len({digest for digest, _ in hashes.values()}) == 1,
                    f"cutoff={cutoff}, rows/hashes=" + str({cell: (n, h[:10]) for cell, (h, n) in hashes.items()}),
                )
    return result


def gate_market_data_integrity(log_root: str, seeds: list[int]) -> ValidationResult:
    result = ValidationResult("Gate 3: Market-Data Integrity")
    for seed in seeds:
        for cell in CELLS:
            path = os.path.join(_run_dir(log_root, cell, seed), "book_l1.parquet")
            try:
                book = _load_parquet(path)
            except FileNotFoundError as exc:
                result.add(f"{cell} seed={seed}: L1 integrity", False, str(exc))
                continue
            two_sided = book.dropna(subset=["best_bid", "best_ask"])
            crossed = two_sided[two_sided["best_bid"] > two_sided["best_ask"]]
            midpoint_expected = (two_sided["best_bid"] + two_sided["best_ask"]) / 2.0
            midpoint_ok = np.allclose(two_sided["midpoint"].astype(float), midpoint_expected.astype(float))
            times = pd.to_datetime(book["time"])
            result.add(
                f"{cell} seed={seed}: non-crossed, ordered L1 snapshots",
                not book.empty and crossed.empty and times.is_monotonic_increasing and times.is_unique,
                f"rows={len(book)}, two_sided={len(two_sided)}, crossed={len(crossed)}, "
                f"ordered={times.is_monotonic_increasing}, unique={times.is_unique}",
            )
            result.add(
                f"{cell} seed={seed}: midpoint arithmetic",
                midpoint_ok,
                "midpoint must equal (best_bid + best_ask) / 2",
            )
    return result


def gate_metric_sanity() -> ValidationResult:
    result = ValidationResult("Gate 4: Metric Sanity")
    base = pd.Timestamp("2019-06-28 10:00:00")
    end = base + pd.Timedelta(minutes=4)
    times = [base, base + pd.Timedelta(minutes=1), base + pd.Timedelta(minutes=3), end]
    book = pd.DataFrame({
        "time": times,
        "best_bid": [99, 99, 98, 98],
        "best_ask": [101, 103, 104, 104],
        "best_bid_sz": [10, 20, 30, 30],
        "best_ask_sz": [20, 30, 40, 40],
        "midpoint": [100, 102, 101, 101],
    })
    fundamental = pd.DataFrame({"time": [base, end], "value": [100, 100]})
    observed = {
        "midpoint_error_tw": midpoint_error_tw(book, fundamental, start=base, end=end),
        "quoted_spread_tw": quoted_spread_tw(book, start=base, end=end),
        "depth_at_touch_tw": depth_at_touch_tw(book, start=base, end=end),
    }
    expected = {"midpoint_error_tw": 1.25, "quoted_spread_tw": 4.0, "depth_at_touch_tw": 50.0}
    for name, expected_value in expected.items():
        result.add(
            f"hand-calculated {name}",
            np.isclose(observed[name], expected_value),
            f"observed={observed[name]}, expected={expected_value}",
        )

    shock = pd.Timestamp("2019-06-28 12:30:00")
    recovery = recovery_time_s(
        [shock, shock + pd.Timedelta(seconds=30), shock + pd.Timedelta(seconds=90)],
        [90, 99.5, 100.0],
        shock_time=shock,
        new_fundamental=100,
        threshold=1,
        hold_s=60,
    )
    result.add("hand-calculated recovery_time_s", recovery == 30.0, f"observed={recovery}, expected=30.0")
    return result


def gate_order_lifecycle(log_root: str, seeds: list[int]) -> ValidationResult:
    result = ValidationResult("Gate 5: Order Lifecycle Integrity")
    for seed in seeds:
        for cell in CELLS:
            directory = _run_dir(log_root, cell, seed)
            try:
                orders = _load_parquet(os.path.join(directory, "orders.parquet"))
                state = _load_parquet(os.path.join(directory, "agent_state.parquet"))
            except FileNotFoundError as exc:
                result.add(f"{cell} seed={seed}: lifecycle", False, str(exc))
                continue
            if orders.empty:
                result.add(f"{cell} seed={seed}: lifecycle", False, "orders.parquet is empty")
                continue

            accepted = set(orders.loc[orders["status"] == "ACCEPTED", "order_id"].dropna().astype(int))
            resolved = set(orders.loc[orders["status"].isin(["EXECUTED", "CANCELLED", "EXPIRED"]), "order_id"].dropna().astype(int))
            unresolved = sorted(accepted - resolved)
            result.add(
                f"{cell} seed={seed}: all accepted orders terminal",
                not unresolved,
                f"accepted={len(accepted)}, resolved={len(resolved)}, unresolved={len(unresolved)}",
            )

            treatment_exec = orders[(orders["agent_id"] == 10) & (orders["status"] == "EXECUTED")]
            signed_fill = np.where(
                treatment_exec["direction"].eq("BUY"),
                treatment_exec["quantity"],
                -treatment_exec["quantity"],
            ).sum()
            final_inventory = int(state["inventory"].iloc[-1]) if not state.empty else 0
            result.add(
                f"{cell} seed={seed}: treatment fills reconcile with inventory",
                int(signed_fill) == final_inventory,
                f"signed fills={int(signed_fill)}, final inventory={final_inventory}",
            )
    return result


def gate_llm_health(log_root: str, seeds: list[int]) -> ValidationResult:
    result = ValidationResult("Gate 6: LLM Health")
    required = {"llm_valid", "llm_fallback_used", "llm_timeout", "llm_latency_ms"}
    for seed in seeds:
        for cell in LLM_CELLS:
            path = os.path.join(_run_dir(log_root, cell, seed), "decisions.parquet")
            try:
                decisions = _load_parquet(path)
            except FileNotFoundError:
                result.add(f"{cell} seed={seed}: diagnostics", False, "decisions.parquet missing")
                continue
            missing = required - set(decisions.columns)
            diagnostics_ok = not decisions.empty and not missing and decisions[list(required)].notna().all().all()
            result.add(
                f"{cell} seed={seed}: complete diagnostics",
                diagnostics_ok,
                f"rows={len(decisions)}, missing_columns={sorted(missing)}",
            )
            if not diagnostics_ok:
                continue
            fallbacks = decisions["llm_fallback_used"].astype(bool)
            valid = decisions["llm_valid"].astype(bool)
            timeouts = decisions["llm_timeout"].astype(bool)
            fallback_rate = float(fallbacks.mean())
            timeout_rate = float(timeouts.mean())
            result.add(
                f"{cell} seed={seed}: invalid/fallback rate < 10%",
                fallback_rate < 0.10,
                f"rate={fallback_rate:.2%} ({fallbacks.sum()}/{len(decisions)})",
            )
            result.add(
                f"{cell} seed={seed}: timeout rate < 1%",
                timeout_rate < 0.01,
                f"rate={timeout_rate:.2%} ({timeouts.sum()}/{len(decisions)})",
            )
            result.add(
                f"{cell} seed={seed}: validity/fallback consistency",
                bool((valid == ~fallbacks).all() and (timeouts <= fallbacks).all()),
                "valid must be inverse of fallback; every timeout must fall back",
            )
    return result


def validate(log_root: str, seeds: list[int]) -> list[ValidationResult]:
    return [
        gate_output_completeness(log_root, seeds),
        gate_mechanics_identity(log_root, seeds),
        gate_pairing_audit(log_root, seeds),
        gate_market_data_integrity(log_root, seeds),
        gate_metric_sanity(),
        gate_order_lifecycle(log_root, seeds),
        gate_llm_health(log_root, seeds),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate fixed-wrapper experiment outputs")
    parser.add_argument("--phase", choices=["pilot", "final"], default=None)
    parser.add_argument("--log-root", default="output/raw")
    parser.add_argument("--seeds", type=int, nargs="+")
    args = parser.parse_args()
    seeds = PILOT_SEEDS if args.phase == "pilot" else FINAL_SEEDS if args.phase == "final" else (args.seeds or PILOT_SEEDS)

    print("=" * 72)
    print("STRICT EXPERIMENT VALIDATION")
    print(f"  Log root: {args.log_root}")
    print(f"  Seeds: {seeds}")
    print("=" * 72)

    gates = validate(args.log_root, seeds)
    for gate in gates:
        print(f"\n{gate.summary()}")
        for description, passed, detail in gate.checks:
            print(f"  {'PASS' if passed else 'FAIL'} {description}")
            if detail:
                print(f"       {detail}")

    all_passed = all(gate.passed for gate in gates)
    phase_label = args.phase or "custom"
    report_dir = os.path.join("output", "results")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, f"validation_report_{phase_label}.json")
    payload = {
        "phase": phase_label,
        "seeds": seeds,
        "all_passed": all_passed,
        "gates": [
            {
                "name": gate.gate_name,
                "passed": gate.passed,
                "pass_count": gate.pass_count,
                "total_checks": len(gate.checks),
                "checks": [
                    {"description": desc, "passed": passed, "detail": detail}
                    for desc, passed, detail in gate.checks
                ],
            }
            for gate in gates
        ],
    }
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    print("\n" + "=" * 72)
    print("ALL GATES PASSED" if all_passed else "ONE OR MORE GATES FAILED")
    print(f"Report: {report_path}")
    print("=" * 72)
    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
