"""
run_cell.py
===========
Executes a single experiment cell for a specific seed.

Usage:
    python run_cell.py --cell C2-N --seed 1001
    python run_cell.py --cell C1 --regime N --seed 1001
"""

import argparse
import datetime as dt
import json
import os
import sys
import numpy as np
import pandas as pd

from agent.experiment.build_config import build_experiment_config
from util import util
from util.order import LimitOrder


def main():
    parser = argparse.ArgumentParser(description='Run a single cell/regime/seed simulation.')
    parser.add_argument('--cell', required=True,
                        help='Cell ID, e.g. C2-N or C2 (if --regime specified)')
    parser.add_argument('--regime', default=None,
                        help='Regime: N (Normal) or S (Shock). Inferred from --cell if formatted as C2-N.')
    parser.add_argument('--seed', type=int, default=1001,
                        help='Master random seed (default: 1001)')
    parser.add_argument('--config-dir', default=None,
                        help='Path to config directory')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Verbose output')

    args = parser.parse_args()

    cell_raw = args.cell.upper()
    if '-' in cell_raw:
        cell_id, regime = cell_raw.split('-', 1)
    else:
        cell_id = cell_raw
        regime = args.regime.upper() if args.regime else 'N'

    seed = args.seed

    print("=" * 60)
    print(f"Running Cell: {cell_id} | Regime: {regime} | Seed: {seed}")
    print("=" * 60)

    # Set up global random seed and verbosity
    np.random.seed(seed)
    util.silent_mode = not args.verbose
    LimitOrder.silent_mode = not args.verbose

    sim_start = dt.datetime.now()

    # Build simulation configuration
    env = build_experiment_config(cell_id, regime, seed, config_dir=args.config_dir)

    log_dir = env['log_dir']
    os.makedirs(log_dir, exist_ok=True)

    print(f"Log directory: {log_dir}")
    print(f"Agents count: {len(env['agents'])}")
    print("Starting ABIDES runner...")
    print("-" * 60)

    # Run Kernel
    kernel = env['kernel']
    kernel.runner(
        agents=env['agents'],
        startTime=env['kernel_start_time'],
        stopTime=env['kernel_stop_time'],
        agentLatencyModel=env['latency_model'],
        defaultComputationDelay=50,
        oracle=env['oracle'],
        log_dir=log_dir
    )

    sim_end = dt.datetime.now()
    elapsed_s = (sim_end - sim_start).total_seconds()

    print("-" * 60)
    print(f"Simulation Finished cleanly in {elapsed_s:.2f} seconds.")
    print(f"Results written to: {log_dir}")

    # Write run manifest
    manifest = {
        'cell_id': cell_id,
        'regime': regime,
        'cell_full': f"{cell_id}-{regime}",
        'seed': seed,
        'agent_count': len(env['agents']),
        'wall_clock_seconds': elapsed_s,
        'simulation_start': str(sim_start),
        'simulation_end': str(sim_end)
    }

    manifest_path = os.path.join(log_dir, "run_manifest.json")
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    print(f"Manifest written to: {manifest_path}")
    print("=" * 60)


if __name__ == '__main__':
    main()
