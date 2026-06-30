# Experiment 4: Memory ablation with one fixed prompt mode.
#
# Treatment variable:
#   --memory-mode no_history | last_5_events | last_20_events |
#                 rolling_session_summary
#
# Held fixed relative to Experiment 3:
#   - 1 LLM trader + 9 traditional traders
#   - same market hours, symbol, oracle, latency setup, and cash
#   - one decision-only JSON prompt mode for every treatment arm
#   - temperature=0.1 and max_tokens=64 inside MemoryAblationAgent

import argparse
import datetime as dt
import sys

import numpy as np
import pandas as pd

from Kernel import Kernel
from agent.ExchangeAgent import ExchangeAgent
from agent.HeuristicBeliefLearningAgent import HeuristicBeliefLearningAgent
from agent.ValueAgent import ValueAgent
from agent.ZeroIntelligenceAgent import ZeroIntelligenceAgent
from agent.examples.MomentumAgent import MomentumAgent
from agent.exp4.MemoryAblationAgent import MemoryAblationAgent
from model.LatencyModel import LatencyModel
from util import util
from util.order import LimitOrder
from util.oracle.SparseMeanRevertingOracle import SparseMeanRevertingOracle


parser = argparse.ArgumentParser(
    description="Experiment 4: memory ablation with fixed no-reasoning prompt.")
parser.add_argument("-c", "--config", required=True,
                    help="Name of config file to execute")
parser.add_argument("-l", "--log_dir", default=None,
                    help="Log directory name")
parser.add_argument("-s", "--seed", type=int, default=12345,
                    help="numpy.random.seed()")
parser.add_argument("-v", "--verbose", action="store_true",
                    help="Maximum verbosity")
parser.add_argument("--config_help", action="store_true",
                    help="Print argument options for this config file")
parser.add_argument("--memory-mode", default="no_history",
                    choices=MemoryAblationAgent.VALID_MEMORY_MODES,
                    help="Memory payload treatment for the LLM agent")
parser.add_argument("--prompt-mode", default="decision_only_json",
                    choices=MemoryAblationAgent.VALID_PROMPT_MODES,
                    help="Prompt/output mode for the LLM agent")
parser.add_argument("--memory-source", default="decisions_only",
                    choices=MemoryAblationAgent.VALID_MEMORY_SOURCES,
                    help="Whether memory includes decisions only or decisions plus fills")
parser.add_argument("--ollama-url", default="http://localhost:11434/v1",
                    help="OpenAI-compatible local LLM endpoint")
parser.add_argument("--model-name", default="gemma3:4b",
                    help="Model name served by the local endpoint")

args, remaining_args = parser.parse_known_args()
if args.config_help:
    parser.print_help()
    sys.exit()

log_dir = args.log_dir
seed = args.seed
if not seed:
    seed = int(pd.Timestamp.now().timestamp() * 1000000) % (2 ** 32 - 1)
np.random.seed(seed)

util.silent_mode = not args.verbose
LimitOrder.silent_mode = not args.verbose

simulation_start_time = dt.datetime.now()
print("Simulation Start Time: {}".format(simulation_start_time))
print("Configuration seed: {}".format(seed))
print("Experiment 4 memory mode: {}".format(args.memory_mode))
print("Experiment 4 prompt mode: {}".format(args.prompt_mode))
print("Experiment 4 memory source: {}".format(args.memory_source))
print("LLM endpoint: {}".format(args.ollama_url))
print("LLM model: {}\n".format(args.model_name))

historical_date = pd.to_datetime("2019-06-28")
symbol = "JPM"
agent_count, agents, agent_types = 0, [], []
starting_cash = 10000000
mkt_open = historical_date + pd.to_timedelta("09:30:00")
mkt_close = historical_date + pd.to_timedelta("11:30:00")

symbols = {
    symbol: {
        "r_bar": 1e5,
        "kappa": 1.67e-12,
        "agent_kappa": 1.67e-15,
        "sigma_s": 0,
        "fund_vol": 1e-8,
        "megashock_lambda_a": 2.77778e-13,
        "megashock_mean": 1e3,
        "megashock_var": 5e4,
        "random_state": np.random.RandomState(
            seed=np.random.randint(low=0, high=2**31 - 1)),
    }
}

oracle = SparseMeanRevertingOracle(mkt_open, mkt_close, symbols)

agents.extend([ExchangeAgent(
    id=0, name="EXCHANGE_AGENT", type="ExchangeAgent",
    mkt_open=mkt_open, mkt_close=mkt_close, symbols=[symbol],
    log_orders=True, pipeline_delay=0, computation_delay=0,
    stream_history=10, book_freq="s",
    random_state=np.random.RandomState(
        seed=np.random.randint(low=0, high=2**31 - 1)))])
agent_types.extend(["ExchangeAgent"])
agent_count += 1

num_zi_agents = 3
agents.extend([ZeroIntelligenceAgent(
    id=j, name="ZI_AGENT_{}".format(j), type="ZeroIntelligenceAgent",
    symbol=symbol, starting_cash=starting_cash,
    sigma_n=10000, sigma_s=symbols[symbol]["fund_vol"],
    kappa=symbols[symbol]["agent_kappa"], r_bar=symbols[symbol]["r_bar"],
    q_max=10, sigma_pv=5e4, R_min=0, R_max=250, eta=1,
    lambda_a=1e-12, log_orders=True,
    random_state=np.random.RandomState(
        seed=np.random.randint(low=0, high=2**31 - 1)))
    for j in range(agent_count, agent_count + num_zi_agents)])
agent_types.extend(["ZeroIntelligenceAgent"] * num_zi_agents)
agent_count += num_zi_agents

num_hbl_agents = 3
agents.extend([HeuristicBeliefLearningAgent(
    id=j, name="HBL_AGENT_{}".format(j), type="HeuristicBeliefLearningAgent",
    symbol=symbol, starting_cash=starting_cash,
    sigma_n=10000, sigma_s=symbols[symbol]["fund_vol"],
    kappa=symbols[symbol]["agent_kappa"], r_bar=symbols[symbol]["r_bar"],
    q_max=10, sigma_pv=5e4, R_min=0, R_max=250, eta=1,
    lambda_a=1e-12, L=2, log_orders=True,
    random_state=np.random.RandomState(
        seed=np.random.randint(low=0, high=2**31 - 1)))
    for j in range(agent_count, agent_count + num_hbl_agents)])
agent_types.extend(["HeuristicBeliefLearningAgent"] * num_hbl_agents)
agent_count += num_hbl_agents

num_value_agents = 2
agents.extend([ValueAgent(
    id=j, name="VALUE_AGENT_{}".format(j), type="ValueAgent",
    symbol=symbol, starting_cash=starting_cash,
    sigma_n=10000, sigma_s=symbols[symbol]["fund_vol"],
    kappa=symbols[symbol]["agent_kappa"], r_bar=symbols[symbol]["r_bar"],
    lambda_a=1e-12, log_orders=True,
    random_state=np.random.RandomState(
        seed=np.random.randint(low=0, high=2**31 - 1)))
    for j in range(agent_count, agent_count + num_value_agents)])
agent_types.extend(["ValueAgent"] * num_value_agents)
agent_count += num_value_agents

num_momentum_agents = 1
agents.extend([MomentumAgent(
    id=j, name="MOMENTUM_AGENT_{}".format(j), type="MomentumAgent",
    symbol=symbol, starting_cash=starting_cash,
    min_size=1, max_size=10, wake_up_freq="60s", subscribe=True,
    log_orders=True,
    random_state=np.random.RandomState(
        seed=np.random.randint(low=0, high=2**31 - 1)))
    for j in range(agent_count, agent_count + num_momentum_agents)])
agent_types.extend(["MomentumAgent"] * num_momentum_agents)
agent_count += num_momentum_agents

num_llm_agents = 1
agents.extend([MemoryAblationAgent(
    id=j, name="LLM_EXP4_{}_{}".format(args.memory_mode.upper(), j),
    type="MemoryAblationAgent",
    symbol=symbol, starting_cash=starting_cash,
    wake_up_freq="60s", q_max=10, log_orders=True,
    ollama_url=args.ollama_url, model_name=args.model_name,
    memory_mode=args.memory_mode,
    prompt_mode=args.prompt_mode,
    memory_source=args.memory_source,
    random_state=np.random.RandomState(
        seed=np.random.randint(low=0, high=2**31 - 1)))
    for j in range(agent_count, agent_count + num_llm_agents)])
agent_types.extend(["MemoryAblationAgent"] * num_llm_agents)
agent_count += num_llm_agents

kernel = Kernel("Exp4 Memory Ablation Kernel",
                random_state=np.random.RandomState(
                    seed=np.random.randint(low=0, high=2**31 - 1)))
kernelStartTime = historical_date
kernelStopTime = mkt_close + pd.to_timedelta("00:01:00")
defaultComputationDelay = 50

latency_rstate = np.random.RandomState(
    seed=np.random.randint(low=0, high=2**31 - 1))
pairwise_distances = util.generate_uniform_random_pairwise_dist_on_line(
    0.0, 3866660, agent_count, random_state=latency_rstate)
pairwise_latencies = util.meters_to_light_ns(pairwise_distances)
latency_model = LatencyModel(
    latency_model="deterministic", random_state=latency_rstate,
    kwargs={"connected": True, "min_latency": pairwise_latencies})

kernel.runner(
    agents=agents,
    startTime=kernelStartTime,
    stopTime=kernelStopTime,
    agentLatencyModel=latency_model,
    defaultComputationDelay=defaultComputationDelay,
    oracle=oracle,
    log_dir=args.log_dir)

simulation_end_time = dt.datetime.now()
print("Simulation End Time: {}".format(simulation_end_time))
print("Time taken to run simulation: {}".format(
    simulation_end_time - simulation_start_time))
