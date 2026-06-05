import argparse
import subprocess
import sys
import os

def main():
    parser = argparse.ArgumentParser(description='Run Experiment 3: Structured LLM Agent')
    parser.add_argument('--seed', type=int, default=12345, help='Random seed')
    args = parser.parse_args()

    seed = args.seed
    log_dir = f"exp3_structured_seed{seed}"

    print("=" * 60)
    print("Experiment 3: Structured LLM Baseline")
    print("=" * 60)
    print(f"Seed: {seed}")
    print(f"Log directory: log/{log_dir}")
    print()

    print(">>> Step 1: Running ABIDES simulation...")
    sim_cmd = [
        sys.executable, "abides.py",
        "-c", "exp3_structured",
        "-s", str(seed),
        "-l", log_dir
    ]
    
    result = subprocess.run(sim_cmd, cwd=os.path.dirname(os.path.abspath(__file__)))
    if result.returncode != 0:
        print(f"\nERROR: Simulation failed with code {result.returncode}")
        sys.exit(1)

    print("\n>>> Simulation completed successfully!")
    print("\n>>> Step 2: Running analysis...")
    
    analysis_log_dir = os.path.join("log", log_dir)
    analysis_cmd = [
        sys.executable, "analyze_exp1.py",
        analysis_log_dir
    ]
    
    result = subprocess.run(analysis_cmd, cwd=os.path.dirname(os.path.abspath(__file__)))
    if result.returncode != 0:
        print(f"\nWARNING: Analysis script returned code {result.returncode}")
    else:
        print("\n>>> Analysis completed!")
        
    print("=" * 60)
    print(f"Results are in: {analysis_log_dir}")
    print("=" * 60)

if __name__ == '__main__':
    main()
