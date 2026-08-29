# UROP1010 Repository Overview

This repository contains the setup for the **UROP1010** project, which currently includes your documents and the `abides` Agent-Based Interactive Discrete Event Simulation environment.

## High-Level Directory Structure

- **`Documents/`**: Contains project documentation and notes (e.g., `local_llm_adjustments.md`).
- **`abides/`**: The core simulation environment submodule (an agent-based market simulator).

---

## The `abides` Simulation Environment

ABIDES is designed to support AI agent research in market applications. It is a message-based simulation modeled after NASDAQ's equity trading protocols (ITCH and OUCH). 

### Key Files in `abides/`

- **`abides.py`**: The main entry point script to run the simulation.
- **`Kernel.py`**: The core Discrete Event Simulation (DES) kernel that handles time progression and message passing between agents.
- **`requirements.txt` / `setup.py`**: Python dependencies and installation configuration.
- **`README.md`**: Official documentation and quickstart guide for ABIDES.

### Key Directories in `abides/`

#### 1. Core Simulation Components
- **`agent/`**: Contains all agent implementations. This includes the `ExchangeAgent` (which facilitates transactions) and various trading agents (e.g., Market Makers, Value Agents, Momentum Agents).
- **`message/`**: Defines the messages used for communication between agents and the exchange kernel (e.g., Order messages, Market Data messages).
- **`model/`**: Contains mathematical and environmental models, such as `LatencyModel.py`, which simulates network delays between agents.
- **`util/`**: Utility scripts, helper functions, formatters, cryptography, and oracle tools for the simulation.

#### 2. Configuration & Execution
- **`config/`**: Contains Python scripts defining different simulation scenarios and setups (e.g., parallel simulations, different agent compositions).
- **`scripts/`**: Shell scripts (`.sh`) designed to run specific predefined configurations and experiments.

#### 3. Analysis & Data
- **`cli/`**: Command Line Interface tools for plotting and analyzing simulation outputs (order books, midpoint prices, quotes).
- **`realism/`**: Tools and scripts dedicated to evaluating how realistic a simulation run is by comparing it against empirical "stylized facts" of real financial markets.
- **`data/`**: Stores background market data, such as historical trades and synthetic fundamental data used by agents during simulations.

#### 4. Additional Modules
- **`contributed_traders/`**: Sample or community-contributed trading agents (e.g., `SimpleAgent.py`).
- **`tests/`**: Automated tests and test data for verifying the simulation's integrity.

## Getting Started
To get started with `abides`, navigate into the directory and install the requirements:
```bash
cd abides
pip install -r requirements.txt
```
