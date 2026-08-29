"""
run_matrix.py
=============
Orchestrator script that loops over seeds and cells to run the full
experimental matrix (or a subset of it).

Usage:
    python run_matrix.py --phase pilot          # 3 seeds × 10 cells = 30 runs
    python run_matrix.py --phase final          # 30 seeds × 10 cells = 300 runs
    python run_matrix.py --seeds 1001 1002 --cells C1-N C2-N   # custom subset

After all simulations complete, the script automatically invokes the
Parquet log extractor on each run directory.
"""

import argparse
import subprocess
import sys
import os
import time
import json

# ── Experiment Design Constants ──────────────────────────────────────────────

CELLS = [
    "C1-N", "C2-N", "C3-N", "C4-N", "C5-N",
    "C1-S", "C2-S", "C3-S", "C4-S", "C5-S",
]

PILOT_SEEDS  = [1001, 1002, 1003]
FINAL_SEEDS  = list(range(1001, 1031))  # 1001..1030 inclusive → 30 seeds


def run_single_cell(cell: str, seed: int, verbose: bool = False):
    """Runs a single cell simulation via run_cell.py as a subprocess."""
    cmd = [sys.executable, "run_cell.py", "--cell", cell, "--seed", str(seed)]
    if verbose:
        cmd.append("-v")

    t0 = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__)))
    elapsed = time.time() - t0

    success = result.returncode == 0

    if not success:
        print(f"  ✗ {cell} seed={seed} FAILED in {elapsed:.1f}s")
        print(f"    STDERR: {result.stderr[-500:]}")
    else:
        print(f"  ✓ {cell} seed={seed} OK in {elapsed:.1f}s")

    return {
        "cell": cell,
        "seed": seed,
        "success": success,
        "elapsed_s": round(elapsed, 2),
        "stdout_tail": result.stdout[-200:] if result.stdout else "",
        "stderr_tail": result.stderr[-200:] if result.stderr else ""
    }


def extract_logs(cell: str, seed: int):
    """Runs the Parquet log extractor on a completed run directory."""
    log_dir = os.path.join("output", "raw", cell, str(seed))
    if not os.path.isdir(log_dir):
        print(f"  ⚠ Log dir not found for {cell}/{seed}, skipping extraction.")
        return False

    cmd = [sys.executable, "-m", "logging_.writers", log_dir]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__)))

    if result.returncode != 0:
        print(f"  ⚠ Extraction failed for {cell}/{seed}: {result.stderr[-300:]}")
        return False
    else:
        print(f"  📦 Extracted parquet for {cell}/{seed}")
        return True


def main():
    parser = argparse.ArgumentParser(description="Run the experimental matrix.")
    parser.add_argument("--phase", choices=["pilot", "final"], default=None,
                        help="Run a predefined phase: 'pilot' (3 seeds) or 'final' (30 seeds).")
    parser.add_argument("--seeds", type=int, nargs="+", default=None,
                        help="Custom list of seeds to run.")
    parser.add_argument("--cells", type=str, nargs="+", default=None,
                        help="Custom list of cells to run (e.g. C1-N C2-S).")
    parser.add_argument("--skip-extract", action="store_true",
                        help="Skip parquet extraction after simulation.")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose simulation output.")
    args = parser.parse_args()

    # Determine seeds
    if args.phase == "pilot":
        seeds = PILOT_SEEDS
    elif args.phase == "final":
        seeds = FINAL_SEEDS
    elif args.seeds:
        seeds = args.seeds
    else:
        seeds = PILOT_SEEDS
        print("No phase or seeds specified, defaulting to pilot seeds.")

    # Determine cells
    cells = args.cells if args.cells else CELLS

    total_runs = len(seeds) * len(cells)
    print("=" * 70)
    print(f"EXPERIMENT MATRIX: {len(cells)} cells × {len(seeds)} seeds = {total_runs} runs")
    print(f"  Cells: {', '.join(cells)}")
    print(f"  Seeds: {seeds}")
    print("=" * 70)

    results = []
    completed = 0
    failed = 0

    for seed in seeds:
        print(f"\n── Seed {seed} ──")
        for cell in cells:
            completed += 1
            print(f"\n[{completed}/{total_runs}] Running {cell} / seed={seed}...")
            r = run_single_cell(cell, seed, verbose=args.verbose)
            results.append(r)

            if r["success"] and not args.skip_extract:
                extract_logs(cell, seed)
            elif not r["success"]:
                failed += 1

    # Summary
    print("\n" + "=" * 70)
    print(f"MATRIX COMPLETE: {completed - failed}/{total_runs} succeeded, {failed} failed.")
    print("=" * 70)

    # Write summary JSON
    summary_dir = os.path.join("output", "results")
    os.makedirs(summary_dir, exist_ok=True)
    phase_label = args.phase or "custom"
    summary_path = os.path.join(summary_dir, f"matrix_summary_{phase_label}.json")

    with open(summary_path, "w") as f:
        json.dump({
            "phase": phase_label,
            "total_runs": total_runs,
            "succeeded": completed - failed,
            "failed": failed,
            "seeds": seeds,
            "cells": cells,
            "runs": results
        }, f, indent=2)

    print(f"Summary written to: {summary_path}")

    if failed > 0:
        print(f"\n⚠ {failed} runs failed. Check stderr output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
