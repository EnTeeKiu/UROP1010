"""
Experiment 1: Run Script
=========================
Convenience script to run the Experiment 1 baseline simulation and analysis.

Usage:
    python run_exp1.py [--seed SEED]

Example:
    python run_exp1.py --seed 12345
"""

import argparse
import subprocess
import sys
import os


def main():
    parser = argparse.ArgumentParser(description='Run Experiment 1: Baseline Market Reproduction')
    parser.add_argument('--seed', type=int, default=12345, help='Random seed (default: 12345)')
    args = parser.parse_args()

    seed = args.seed
    log_dir = "exp1_seed{}".format(seed)

    print("=" * 60)
    print("Experiment 1: Baseline Market Reproduction")
    print("=" * 60)
    print("Seed: {}".format(seed))
    print("Log directory: log/{}".format(log_dir))
    print()

    # Step 1: Run the simulation
    print(">>> Step 1: Running ABIDES simulation...")
    print("-" * 60)

    sim_cmd = [
        sys.executable, "abides.py",
        "-c", "exp1_baseline",
        "-s", str(seed),
        "-l", log_dir
    ]

    print("Command: {}".format(' '.join(sim_cmd)))
    print()

    result = subprocess.run(sim_cmd, cwd=os.path.dirname(os.path.abspath(__file__)))

    if result.returncode != 0:
        print("\nERROR: Simulation failed with return code {}".format(result.returncode))
        sys.exit(1)

    print()
    print(">>> Simulation completed successfully!")
    print()

    # Step 2: Run the analysis
    print(">>> Step 2: Running analysis...")
    print("-" * 60)

    analysis_log_dir = os.path.join("log", log_dir)
    analysis_cmd = [
        sys.executable, "analyze_exp1.py",
        analysis_log_dir
    ]

    print("Command: {}".format(' '.join(analysis_cmd)))
    print()

    result = subprocess.run(analysis_cmd, cwd=os.path.dirname(os.path.abspath(__file__)))

    if result.returncode != 0:
        print("\nWARNING: Analysis script returned code {}".format(result.returncode))
    else:
        print()
        print(">>> Analysis completed!")

    print()
    print("=" * 60)
    print("Results are in: {}".format(analysis_log_dir))
    print("=" * 60)


if __name__ == '__main__':
    main()
