import subprocess
import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description='Run Experiment 3: Structured-JSON')
    parser.add_argument('--seed', type=int, default=12345, help='Random seed')
    args = parser.parse_args()

    cmd = [
        sys.executable, 'abides.py',
        '-c', 'exp3_structured_json',
        '-l', f'exp3_structured_json_seed{args.seed}',
        '-s', str(args.seed)
    ]
    
    print(f"Running command: {' '.join(cmd)}")
    subprocess.run(cmd)

if __name__ == "__main__":
    main()
