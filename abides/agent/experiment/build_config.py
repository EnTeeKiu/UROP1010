import os
import sys
import datetime as dt
import numpy as np
import pandas as pd

from Kernel import Kernel
from util import util
from model.LatencyModel import LatencyModel
from util.oracle.SparseMeanRevertingOracle import SparseMeanRevertingOracle

from agent.ExchangeAgent import ExchangeAgent
from agent.ZeroIntelligenceAgent import ZeroIntelligenceAgent
from agent.HeuristicBeliefLearningAgent import HeuristicBeliefLearningAgent
from agent.ValueAgent import ValueAgent
from agent.examples.MomentumAgent import MomentumAgent

from agent.experiment.seeds import make_seeds
from agent.experiment.fixed_wrapper import FixedWrapperAgent
from agent.experiment.coin_policy import CoinPolicy


def load_yaml_config(path):
    try:
        import yaml
        with open(path, 'r') as f:
            return yaml.safe_load(f)
    except Exception:
        # Simple fallback parser for experiment.yaml if PyYAML is not installed
        cfg = {
            'symbol': 'JPM',
            'starting_cash': 10000000,
            'r_bar': 100000,
            'kappa': 1.67e-12,
            'agent_kappa': 1.67e-15,
            'sigma_s': 0,
            'fund_vol': 1e-8,
            'megashock_lambda_a': 2.77778e-13,
            'megashock_mean': 1e3,
            'megashock_var': 5e4,
            'lot_size': 100,
            'q_max': 10,
            'p_buy': 0.5,
            'open': '09:30:00',
            'close': '16:00:00',
            'warmup_min': 30
        }
        return cfg


def build_experiment_config(cell_id: str, regime: str, master_seed: int,
                            config_dir: str = None):
    """
    Constructs the kernel, agent population, oracle, latency model, and log directory
    for a given cell_id ("C1".."C5"), regime ("N" or "S"), and master_seed.
    """
    if config_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_dir = os.path.join(base_dir, "config")

    exp_cfg_path = os.path.join(config_dir, "experiment.yaml")

    # Historical date anchor for ABIDES
    historical_date = pd.to_datetime('2019-06-28')
    symbol = 'JPM'
    starting_cash = 10000000  # $100,000 in cents

    mkt_open = historical_date + pd.to_timedelta('09:30:00')
    mkt_close = historical_date + pd.to_timedelta('16:00:00')
    warmup_end = mkt_open + pd.to_timedelta('30min')

    r_bar = 100000  # $1,000 in cents

    # Derive deterministic seeds
    seeds = make_seeds(master_seed, cell_id)

    # 1. Oracle Configuration
    symbols = {
        symbol: {
            'r_bar': r_bar,
            'kappa': 1.67e-12,
            'agent_kappa': 1.67e-15,
            'sigma_s': 0,
            'fund_vol': 1e-8,
            'megashock_lambda_a': 2.77778e-13,
            'megashock_mean': 1e3,
            'megashock_var': 5e4,
            'random_state': np.random.RandomState(seeds['oracle'])
        }
    }

    if regime == "S":
        try:
            from agent.experiment.shock_oracle import ShockOracle
            shock_cfg_path = os.path.join(config_dir, "shock.yaml")
            shock_time = historical_date + pd.to_timedelta('12:30:00')
            shock_magnitude = 8000  # 8000 cents ($80)
            oracle = ShockOracle(mkt_open, mkt_close, symbols,
                                 shock_time=shock_time, shock_magnitude=shock_magnitude)
        except ImportError:
            oracle = SparseMeanRevertingOracle(mkt_open, mkt_close, symbols)
    else:
        oracle = SparseMeanRevertingOracle(mkt_open, mkt_close, symbols)

    # 2. Exchange Agent (id=0)
    agent_count = 0
    agents = []
    agent_types = []

    exchange_rng = np.random.RandomState(seeds['exchange'])
    agents.append(ExchangeAgent(
        id=0,
        name="EXCHANGE_AGENT",
        type="ExchangeAgent",
        mkt_open=mkt_open,
        mkt_close=mkt_close,
        symbols=[symbol],
        log_orders=True,
        pipeline_delay=0,
        computation_delay=0,
        stream_history=10,
        book_freq='s',
        random_state=exchange_rng
    ))
    agent_types.append("ExchangeAgent")
    agent_count += 1

    # 3. Background Agents (ids 1-9) — Shared seed across conditions
    bg_rng = np.random.RandomState(seeds['background'])

    # 3 ZI agents (ids 1-3)
    for j in range(3):
        agents.append(ZeroIntelligenceAgent(
            id=agent_count,
            name=f"ZI_AGENT_{j+1}",
            type="ZeroIntelligenceAgent",
            symbol=symbol,
            starting_cash=starting_cash,
            sigma_n=10000,
            sigma_s=symbols[symbol]['fund_vol'],
            kappa=symbols[symbol]['agent_kappa'],
            r_bar=r_bar,
            q_max=10,
            sigma_pv=5e4,
            R_min=0,
            R_max=250,
            eta=1,
            lambda_a=1e-12,
            log_orders=True,
            random_state=np.random.RandomState(bg_rng.randint(0, 2**31 - 1))
        ))
        agent_types.append("ZeroIntelligenceAgent")
        agent_count += 1

    # 3 HBL agents (ids 4-6)
    for j in range(3):
        agents.append(HeuristicBeliefLearningAgent(
            id=agent_count,
            name=f"HBL_AGENT_{j+1}",
            type="HeuristicBeliefLearningAgent",
            symbol=symbol,
            starting_cash=starting_cash,
            sigma_n=10000,
            sigma_s=symbols[symbol]['fund_vol'],
            kappa=symbols[symbol]['agent_kappa'],
            r_bar=r_bar,
            q_max=10,
            sigma_pv=5e4,
            R_min=0,
            R_max=250,
            eta=1,
            lambda_a=1e-12,
            L=2,
            log_orders=True,
            random_state=np.random.RandomState(bg_rng.randint(0, 2**31 - 1))
        ))
        agent_types.append("HeuristicBeliefLearningAgent")
        agent_count += 1

    # 2 Value agents (ids 7-8)
    for j in range(2):
        agents.append(ValueAgent(
            id=agent_count,
            name=f"VALUE_AGENT_{j+1}",
            type="ValueAgent",
            symbol=symbol,
            starting_cash=starting_cash,
            sigma_n=10000,
            sigma_s=symbols[symbol]['fund_vol'],
            kappa=symbols[symbol]['agent_kappa'],
            r_bar=r_bar,
            lambda_a=1e-12,
            log_orders=True,
            random_state=np.random.RandomState(bg_rng.randint(0, 2**31 - 1))
        ))
        agent_types.append("ValueAgent")
        agent_count += 1

    # 1 Momentum agent (id 9)
    agents.append(MomentumAgent(
        id=agent_count,
        name="MOMENTUM_AGENT_1",
        type="MomentumAgent",
        symbol=symbol,
        starting_cash=starting_cash,
        min_size=1,
        max_size=10,
        wake_up_freq='60s',
        subscribe=True,
        log_orders=True,
        random_state=np.random.RandomState(bg_rng.randint(0, 2**31 - 1))
    ))
    agent_types.append("MomentumAgent")
    agent_count += 1

    # 4. Treatment Agent (id 10) — Differs by cell_id
    policy_rng = np.random.RandomState(seeds['policy'])

    if cell_id == "C1":
        # Stock ZeroIntelligenceAgent, no wrapper, native Poisson arrival
        treatment = ZeroIntelligenceAgent(
            id=agent_count,
            name="ZI_TREATMENT_10",
            type="ZeroIntelligenceAgent",
            symbol=symbol,
            starting_cash=starting_cash,
            sigma_n=10000,
            sigma_s=symbols[symbol]['fund_vol'],
            kappa=symbols[symbol]['agent_kappa'],
            r_bar=r_bar,
            q_max=10,
            sigma_pv=5e4,
            R_min=0,
            R_max=250,
            eta=1,
            lambda_a=1e-12,
            log_orders=True,
            random_state=policy_rng
        )
    elif cell_id == "C2":
        policy = CoinPolicy(rng=policy_rng, p_buy=0.5)
        treatment = FixedWrapperAgent(
            id=agent_count,
            name="COIN_60s_10",
            type="CoinControl60",
            symbol=symbol,
            starting_cash=starting_cash,
            policy=policy,
            wake_interval_s=60,
            lot_size=100,
            q_max=10,
            r_bar=r_bar,
            warmup_end=warmup_end,
            log_orders=True,
            random_state=policy_rng
        )
    elif cell_id == "C3":
        try:
            from agent.experiment.llm_policy import LLMPolicy
            policy = LLMPolicy(rng_fallback=policy_rng)
        except ImportError:
            policy = CoinPolicy(rng=policy_rng, p_buy=0.5)
        treatment = FixedWrapperAgent(
            id=agent_count,
            name="LLM_60s_10",
            type="LLMPolicy60",
            symbol=symbol,
            starting_cash=starting_cash,
            policy=policy,
            wake_interval_s=60,
            lot_size=100,
            q_max=10,
            r_bar=r_bar,
            warmup_end=warmup_end,
            log_orders=True,
            random_state=policy_rng
        )
    elif cell_id == "C4":
        policy = CoinPolicy(rng=policy_rng, p_buy=0.5)
        treatment = FixedWrapperAgent(
            id=agent_count,
            name="COIN_300s_10",
            type="CoinControl300",
            symbol=symbol,
            starting_cash=starting_cash,
            policy=policy,
            wake_interval_s=300,
            lot_size=100,
            q_max=10,
            r_bar=r_bar,
            warmup_end=warmup_end,
            log_orders=True,
            random_state=policy_rng
        )
    elif cell_id == "C5":
        try:
            from agent.experiment.llm_policy import LLMPolicy
            policy = LLMPolicy(rng_fallback=policy_rng)
        except ImportError:
            policy = CoinPolicy(rng=policy_rng, p_buy=0.5)
        treatment = FixedWrapperAgent(
            id=agent_count,
            name="LLM_300s_10",
            type="LLMPolicy300",
            symbol=symbol,
            starting_cash=starting_cash,
            policy=policy,
            wake_interval_s=300,
            lot_size=100,
            q_max=10,
            r_bar=r_bar,
            warmup_end=warmup_end,
            log_orders=True,
            random_state=policy_rng
        )
    else:
        raise ValueError(f"Unknown cell_id: {cell_id}")

    agents.append(treatment)
    agent_types.append(treatment.type)
    agent_count += 1

    # 5. Latency Model
    latency_rstate = np.random.RandomState(seeds['latency'])
    nyc_to_seattle_meters = 3866660
    pairwise_distances = util.generate_uniform_random_pairwise_dist_on_line(
        0.0, nyc_to_seattle_meters, agent_count, random_state=latency_rstate)
    pairwise_latencies = util.meters_to_light_ns(pairwise_distances)
    model_args = {'connected': True, 'min_latency': pairwise_latencies}
    latency_model = LatencyModel(latency_model='deterministic',
                                 random_state=latency_rstate,
                                 kwargs=model_args)

    # 6. Kernel
    kernel = Kernel("Experiment_Kernel",
                    random_state=np.random.RandomState(seeds['market']))

    kernel_start_time = historical_date
    kernel_stop_time = mkt_close + pd.to_timedelta('00:01:00')

    # Log directory setup
    base_output = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    log_dir = os.path.join(base_output, "output", "raw", f"{cell_id}-{regime}", str(master_seed))

    return {
        'kernel': kernel,
        'agents': agents,
        'oracle': oracle,
        'latency_model': latency_model,
        'kernel_start_time': kernel_start_time,
        'kernel_stop_time': kernel_stop_time,
        'log_dir': log_dir
    }
