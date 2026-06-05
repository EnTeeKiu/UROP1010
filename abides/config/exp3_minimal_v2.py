# Experiment 3: Minimal LLM Baseline — Version 2
# ============================================================
# Identical structure to exp3_minimal.py, but uses MinimalAgentV2.
# Changes vs. V1:
#   1. HOLD reframing in prompt
#   2. Mid-price signal added to prompt
#   4. max_tokens raised: 24 → 32
#   5. Temperature raised: 0.1 → 0.4

import argparse
import numpy as np
import pandas as pd
import sys
import datetime as dt

from Kernel import Kernel
from util import util
from util.order import LimitOrder
from util.oracle.SparseMeanRevertingOracle import SparseMeanRevertingOracle
from model.LatencyModel import LatencyModel

from agent.ExchangeAgent import ExchangeAgent
from agent.ZeroIntelligenceAgent import ZeroIntelligenceAgent
from agent.HeuristicBeliefLearningAgent import HeuristicBeliefLearningAgent
from agent.ValueAgent import ValueAgent
from agent.examples.MomentumAgent import MomentumAgent
from agent.exp3.MinimalAgentV2 import MinimalAgentV2

########################################################################################################################
############################################### GENERAL CONFIG #########################################################

parser = argparse.ArgumentParser(description='Experiment 3: Minimal Baseline V2')
parser.add_argument('-c', '--config', required=True, help='Name of config file to execute')
parser.add_argument('-l', '--log_dir', default=None, help='Log directory name')
parser.add_argument('-s', '--seed', type=int, default=12345, help='numpy.random.seed()')
parser.add_argument('-v', '--verbose', action='store_true', help='Maximum verbosity!')
parser.add_argument('--config_help', action='store_true', help='Print argument options for this config file')

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

historical_date = pd.to_datetime('2019-06-28')
symbol = 'JPM'
agent_count, agents, agent_types = 0, [], []
starting_cash = 10000000  # Cash in cents ($100,000)
mkt_open = historical_date + pd.to_timedelta('09:30:00')
mkt_close = historical_date + pd.to_timedelta('11:30:00')

symbols = {symbol: {'r_bar': 1e5, 'kappa': 1.67e-12, 'agent_kappa': 1.67e-15, 'sigma_s': 0,
                    'fund_vol': 1e-8, 'megashock_lambda_a': 2.77778e-13, 'megashock_mean': 1e3,
                    'megashock_var': 5e4, 'random_state': np.random.RandomState(seed=np.random.randint(low=0, high=2**31 - 1))}}

oracle = SparseMeanRevertingOracle(mkt_open, mkt_close, symbols)

# 1) Exchange Agent (id=0)
agents.extend([ExchangeAgent(id=0, name="EXCHANGE_AGENT", type="ExchangeAgent", mkt_open=mkt_open, mkt_close=mkt_close, symbols=[symbol], log_orders=True, pipeline_delay=0, computation_delay=0, stream_history=10, book_freq='s', random_state=np.random.RandomState(seed=np.random.randint(low=0, high=2**31 - 1)))])
agent_types.extend(["ExchangeAgent"])
agent_count += 1

# 2) 3 Zero Intelligence (ZIC) Agents
num_zi_agents = 3
agents.extend([ZeroIntelligenceAgent(id=j, name="ZI_AGENT_{}".format(j), type="ZeroIntelligenceAgent", symbol=symbol, starting_cash=starting_cash, sigma_n=10000, sigma_s=symbols[symbol]['fund_vol'], kappa=symbols[symbol]['agent_kappa'], r_bar=symbols[symbol]['r_bar'], q_max=10, sigma_pv=5e4, R_min=0, R_max=250, eta=1, lambda_a=1e-12, log_orders=True, random_state=np.random.RandomState(seed=np.random.randint(low=0, high=2**31 - 1))) for j in range(agent_count, agent_count + num_zi_agents)])
agent_types.extend(["ZeroIntelligenceAgent"] * num_zi_agents)
agent_count += num_zi_agents

# 3) 3 Heuristic Belief Learning Agents
num_hbl_agents = 3
agents.extend([HeuristicBeliefLearningAgent(id=j, name="HBL_AGENT_{}".format(j), type="HeuristicBeliefLearningAgent", symbol=symbol, starting_cash=starting_cash, sigma_n=10000, sigma_s=symbols[symbol]['fund_vol'], kappa=symbols[symbol]['agent_kappa'], r_bar=symbols[symbol]['r_bar'], q_max=10, sigma_pv=5e4, R_min=0, R_max=250, eta=1, lambda_a=1e-12, L=2, log_orders=True, random_state=np.random.RandomState(seed=np.random.randint(low=0, high=2**31 - 1))) for j in range(agent_count, agent_count + num_hbl_agents)])
agent_types.extend(["HeuristicBeliefLearningAgent"] * num_hbl_agents)
agent_count += num_hbl_agents

# 4) 2 Value Agents
num_value_agents = 2
agents.extend([ValueAgent(id=j, name="VALUE_AGENT_{}".format(j), type="ValueAgent", symbol=symbol, starting_cash=starting_cash, sigma_n=10000, sigma_s=symbols[symbol]['fund_vol'], kappa=symbols[symbol]['agent_kappa'], r_bar=symbols[symbol]['r_bar'], lambda_a=1e-12, log_orders=True, random_state=np.random.RandomState(seed=np.random.randint(low=0, high=2**31 - 1))) for j in range(agent_count, agent_count + num_value_agents)])
agent_types.extend(["ValueAgent"] * num_value_agents)
agent_count += num_value_agents

# 5) 1 Momentum Agent
num_momentum_agents = 1
agents.extend([MomentumAgent(id=j, name="MOMENTUM_AGENT_{}".format(j), type="MomentumAgent", symbol=symbol, starting_cash=starting_cash, min_size=1, max_size=10, wake_up_freq='60s', subscribe=True, log_orders=True, random_state=np.random.RandomState(seed=np.random.randint(low=0, high=2**31 - 1))) for j in range(agent_count, agent_count + num_momentum_agents)])
agent_types.extend(["MomentumAgent"] * num_momentum_agents)
agent_count += num_momentum_agents

# 6) 1 Minimal LLM Agent V2
num_llm_agents = 1
agents.extend([MinimalAgentV2(id=j, name="LLM_MINIMAL_V2_{}".format(j), type="MinimalAgentV2", symbol=symbol, starting_cash=starting_cash, wake_up_freq='60s', q_max=10, log_orders=True, ollama_url='http://localhost:11434/v1', model_name='gemma3:4b', random_state=np.random.RandomState(seed=np.random.randint(low=0, high=2**31 - 1))) for j in range(agent_count, agent_count + num_llm_agents)])
agent_types.extend(["MinimalAgentV2"] * num_llm_agents)
agent_count += num_llm_agents

kernel = Kernel("Exp3 Minimal V2 Kernel", random_state=np.random.RandomState(seed=np.random.randint(low=0, high=2**31 - 1)))
kernelStartTime = historical_date
kernelStopTime = mkt_close + pd.to_timedelta('00:01:00')
defaultComputationDelay = 50

latency_rstate = np.random.RandomState(seed=np.random.randint(low=0, high=2**31 - 1))
pairwise_distances = util.generate_uniform_random_pairwise_dist_on_line(0.0, 3866660, agent_count, random_state=latency_rstate)
pairwise_latencies = util.meters_to_light_ns(pairwise_distances)
latency_model = LatencyModel(latency_model='deterministic', random_state=latency_rstate, kwargs={'connected': True, 'min_latency': pairwise_latencies})

kernel.runner(agents=agents, startTime=kernelStartTime, stopTime=kernelStopTime, agentLatencyModel=latency_model, defaultComputationDelay=defaultComputationDelay, oracle=oracle, log_dir=args.log_dir)
