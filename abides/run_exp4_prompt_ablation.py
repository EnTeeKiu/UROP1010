"""
Experiment 4 runner.

The file name follows the requested run_exp4_prompt_ablation entry point, but
Experiment 4 is implemented as the proposal's memory ablation. Prompt mode is
fixed to decision-only JSON with no reasoning field, so Exp 4 does not re-test
Exp 3's prompt variable.

Usage:
    python run_exp4_prompt_ablation.py
    python run_exp4_prompt_ablation.py --memory-mode last_5_events
    python run_exp4_prompt_ablation.py --model-name qwen2.5:3b
"""

import argparse
import os
import subprocess
import sys


MEMORY_MODES = (
    "no_history",
    "last_5_events",
    "last_20_events",
    "rolling_session_summary",
)


def run_command(cmd, cwd):
    print("Command: {}".format(" ".join(cmd)))
    print()
    return subprocess.run(cmd, cwd=cwd)


def run_arm(abides_dir, seed, memory_mode, ollama_url, model_name,
            skip_analysis, prompt_mode, memory_source, run_label):
    prefix = "exp4"
    if run_label:
        prefix = "{}_{}".format(prefix, run_label)
    log_dir = "{}_{}_seed{}".format(prefix, memory_mode, seed)

    print("=" * 72)
    print("Experiment 4: Memory Ablation")
    print("=" * 72)
    print("Seed: {}".format(seed))
    print("Memory mode: {}".format(memory_mode))
    print("Prompt mode: {}".format(prompt_mode))
    print("Memory source: {}".format(memory_source))
    print("Endpoint: {}".format(ollama_url))
    print("Model: {}".format(model_name))
    print("Log directory: log/{}".format(log_dir))
    print()

    sim_cmd = [
        sys.executable, "abides.py",
        "-c", "exp4_memory_ablation",
        "-s", str(seed),
        "-l", log_dir,
        "--memory-mode", memory_mode,
        "--prompt-mode", prompt_mode,
        "--memory-source", memory_source,
        "--ollama-url", ollama_url,
        "--model-name", model_name,
    ]

    print(">>> Step 1: Running ABIDES simulation...")
    result = run_command(sim_cmd, cwd=abides_dir)
    if result.returncode != 0:
        print("\nERROR: Simulation failed with code {}".format(
            result.returncode))
        return result.returncode

    if skip_analysis:
        print("\n>>> Analysis skipped.")
        return 0

    print("\n>>> Step 2: Running analysis...")
    analysis_log_dir = os.path.join("log", log_dir)
    analysis_cmd = [
        sys.executable, "analyze_exp1.py",
        analysis_log_dir,
    ]
    result = run_command(analysis_cmd, cwd=abides_dir)
    if result.returncode != 0:
        print("\nWARNING: Analysis script returned code {}".format(
            result.returncode))
    else:
        print("\n>>> Analysis completed.")

    print("=" * 72)
    print("Results are in: {}".format(analysis_log_dir))
    print("=" * 72)
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Run Experiment 4 memory ablation with fixed prompt mode.")
    parser.add_argument("--seed", type=int, default=12345,
                        help="Random seed")
    parser.add_argument("--memory-mode", default="all",
                        choices=("all",) + MEMORY_MODES,
                        help="Treatment arm to run")
    parser.add_argument("--prompt-mode", default="decision_only_json",
                        choices=("decision_only_json", "reasoning_json"),
                        help="Prompt/output mode for Exp 4")
    parser.add_argument("--memory-source", default="decisions_only",
                        choices=("decisions_only", "decisions_and_fills"),
                        help="Memory content source")
    parser.add_argument("--run-label", default="",
                        help="Optional label inserted into log directory names")
    parser.add_argument("--ollama-url", default="http://localhost:11434/v1",
                        help="OpenAI-compatible local LLM endpoint")
    parser.add_argument("--model-name", default="gemma3:4b",
                        help="Model name served by the endpoint")
    parser.add_argument("--skip-analysis", action="store_true",
                        help="Skip analyze_exp1.py after simulation")
    args = parser.parse_args()

    abides_dir = os.path.dirname(os.path.abspath(__file__))
    modes = MEMORY_MODES if args.memory_mode == "all" else (args.memory_mode,)

    for memory_mode in modes:
        code = run_arm(
            abides_dir=abides_dir,
            seed=args.seed,
            memory_mode=memory_mode,
            ollama_url=args.ollama_url,
            model_name=args.model_name,
            skip_analysis=args.skip_analysis,
            prompt_mode=args.prompt_mode,
            memory_source=args.memory_source,
            run_label=args.run_label,
        )
        if code != 0:
            sys.exit(code)


if __name__ == "__main__":
    main()
