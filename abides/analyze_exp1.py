"""
Experiment 1: Baseline Market Analysis
=======================================
Reads ABIDES simulation output and generates key metrics:
  1. Bid-Ask Spread over time
  2. Cumulative Trading Volume
  3. Price Discovery (mid-price vs fundamental value)
  4. Per-agent P&L summary

Usage:
    python analyze_exp1.py <log_directory>

Example:
    python analyze_exp1.py log/exp1_seed12345
"""

import sys
import os
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for saving to file
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


def load_exchange_log(log_dir):
    """Load the Exchange Agent log from the output directory."""
    exchange_file = None
    for f in os.listdir(log_dir):
        if f.startswith('EXCHANGE') and f.endswith('.bz2'):
            exchange_file = os.path.join(log_dir, f)
            break
    if exchange_file is None:
        raise FileNotFoundError("Exchange agent log not found in {}".format(log_dir))
    print("Loading exchange log: {}".format(exchange_file))
    df = pd.read_pickle(exchange_file, compression='bz2')
    return df


def load_summary_log(log_dir):
    """Load the summary log containing per-agent final valuations."""
    summary_file = os.path.join(log_dir, 'summary_log.bz2')
    if not os.path.exists(summary_file):
        raise FileNotFoundError("Summary log not found: {}".format(summary_file))
    print("Loading summary log: {}".format(summary_file))
    df = pd.read_pickle(summary_file, compression='bz2')
    return df


def load_fundamental(log_dir, symbol='JPM'):
    """Load the fundamental value series logged by the oracle."""
    fund_file = os.path.join(log_dir, 'fundamental_{}.bz2'.format(symbol))
    if not os.path.exists(fund_file):
        print("WARNING: Fundamental value log not found: {}".format(fund_file))
        return None
    print("Loading fundamental values: {}".format(fund_file))
    df = pd.read_pickle(fund_file, compression='bz2')
    return df


def load_orderbook(log_dir, symbol='JPM'):
    """Load order book snapshots if available."""
    for f in os.listdir(log_dir):
        if f.startswith('ORDERBOOK_{}'.format(symbol)) and f.endswith('.bz2'):
            ob_file = os.path.join(log_dir, f)
            print("Loading order book snapshots: {}".format(ob_file))
            df = pd.read_pickle(ob_file, compression='bz2')
            return df
    print("WARNING: Order book snapshot log not found in {}".format(log_dir))
    return None


def extract_spreads_from_exchange_log(exchange_df):
    """
    Extract bid-ask spreads from the exchange log.
    The exchange log contains events like BEST_BID and BEST_ASK.
    """
    df = exchange_df.copy()
    df['Timestamp'] = df.index

    # Filter to bid/ask events
    df_bid = df[df['EventType'] == 'BEST_BID'].copy()
    df_ask = df[df['EventType'] == 'BEST_ASK'].copy()

    if df_bid.empty or df_ask.empty:
        return None, None, None

    # Parse the event string: "symbol,price,volume"
    try:
        df_bid['price'] = df_bid['Event'].apply(
            lambda x: float(str(x).split(',')[1].replace('$', '')))
        df_ask['price'] = df_ask['Event'].apply(
            lambda x: float(str(x).split(',')[1].replace('$', '')))
    except (IndexError, ValueError):
        # Try direct numeric interpretation
        try:
            df_bid['price'] = pd.to_numeric(df_bid['Event'], errors='coerce')
            df_ask['price'] = pd.to_numeric(df_ask['Event'], errors='coerce')
        except Exception:
            return None, None, None

    # Merge on time
    bids = df_bid[['price']].rename(columns={'price': 'bid'})
    asks = df_ask[['price']].rename(columns={'price': 'ask'})

    merged = bids.join(asks, how='outer')
    merged = merged.ffill().dropna()
    merged['spread'] = merged['ask'] - merged['bid']
    merged['midpoint'] = (merged['bid'] + merged['ask']) / 2.0

    return merged['spread'], merged['midpoint'], merged


def extract_volume_from_exchange_log(exchange_df):
    """Extract cumulative volume from ORDER_EXECUTED events."""
    df = exchange_df.copy()
    executed = df[df['EventType'] == 'ORDER_EXECUTED']

    if executed.empty:
        return None

    # Try to extract quantity from executed orders
    volumes = []
    timestamps = []
    for idx, row in executed.iterrows():
        event = row['Event']
        if isinstance(event, dict) and 'quantity' in event:
            volumes.append(event['quantity'])
            timestamps.append(idx)
        elif isinstance(event, str):
            # Try to parse
            volumes.append(1)  # Default unit volume
            timestamps.append(idx)

    if not volumes:
        return None

    vol_series = pd.Series(volumes, index=timestamps)
    cum_vol = vol_series.cumsum()
    return cum_vol


def analyze_pnl(summary_df):
    """Analyze per-agent P&L from summary log."""
    # Filter to FINAL_CASH_POSITION or ENDING_CASH events
    final_cash = summary_df[summary_df['EventType'] == 'ENDING_CASH'].copy()
    starting_cash = summary_df[summary_df['EventType'] == 'STARTING_CASH'].copy()

    if final_cash.empty or starting_cash.empty:
        return None

    results = []
    for agent_id in final_cash['AgentID'].unique():
        agent_final = final_cash[final_cash['AgentID'] == agent_id]
        agent_start = starting_cash[starting_cash['AgentID'] == agent_id]
        if not agent_final.empty and not agent_start.empty:
            strategy = agent_final['AgentStrategy'].values[0]
            end_val = float(agent_final['Event'].values[0])
            start_val = float(agent_start['Event'].values[0])
            pnl = end_val - start_val
            results.append({
                'AgentID': agent_id,
                'Strategy': strategy,
                'StartingCash': start_val / 100,  # Convert cents to dollars
                'EndingCash': end_val / 100,
                'PnL_dollars': pnl / 100
            })

    if results:
        return pd.DataFrame(results)
    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_exp1.py <log_directory>")
        print("Example: python analyze_exp1.py log/exp1_seed12345")
        sys.exit(1)

    log_dir = sys.argv[1]

    if not os.path.isdir(log_dir):
        print("ERROR: Directory not found: {}".format(log_dir))
        sys.exit(1)

    print("=" * 60)
    print("Experiment 1: Baseline Market Analysis")
    print("=" * 60)
    print("Log directory: {}".format(log_dir))
    print()

    # List all files in the log directory for debugging
    print("Files in log directory:")
    for f in sorted(os.listdir(log_dir)):
        size = os.path.getsize(os.path.join(log_dir, f))
        print("  {} ({:,.0f} bytes)".format(f, size))
    print()

    # ──────────────────────────────────────────────────────────────
    # Load data
    # ──────────────────────────────────────────────────────────────
    try:
        exchange_df = load_exchange_log(log_dir)
        print("  Exchange log shape: {}".format(exchange_df.shape))
        print("  Exchange log columns: {}".format(list(exchange_df.columns)))
        print("  Exchange log EventTypes: {}".format(
            exchange_df['EventType'].unique() if 'EventType' in exchange_df.columns else 'N/A'))
        print()
    except FileNotFoundError as e:
        print("ERROR: {}".format(e))
        exchange_df = None

    try:
        summary_df = load_summary_log(log_dir)
        print("  Summary log shape: {}".format(summary_df.shape))
        print()
    except FileNotFoundError as e:
        print("ERROR: {}".format(e))
        summary_df = None

    fund_df = load_fundamental(log_dir)
    if fund_df is not None:
        print("  Fundamental log shape: {}".format(fund_df.shape))
        print()

    # ──────────────────────────────────────────────────────────────
    # Analysis
    # ──────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(3, 1, figsize=(14, 12), sharex=False)
    
    if "exp3_minimal_v2" in log_dir:
        exp_name = "Experiment 3: Minimal V2"
        img_name_prefix = "exp3_minimal_v2"
    elif "exp3_minimal" in log_dir:
        exp_name = "Experiment 3: Minimal Baseline"
        img_name_prefix = "exp3_minimal"
    elif "exp3_reasoning" in log_dir:
        exp_name = "Experiment 3: Reasoning Baseline"
        img_name_prefix = "exp3_reasoning"
    elif "exp3_structured" in log_dir:
        exp_name = "Experiment 3: Structured Baseline"
        img_name_prefix = "exp3_structured"
    elif "exp2" in log_dir:
        exp_name = "Experiment 2: LLM Market Baseline Reproduction"
        img_name_prefix = "exp2_llm_baseline"
    else:
        exp_name = "Experiment 1: Baseline Market Reproduction"
        img_name_prefix = "exp1_baseline"
        
    fig.suptitle(exp_name, fontsize=16, fontweight='bold')

    has_plot = False

    # Panel 1: Bid-Ask Spread
    if exchange_df is not None:
        spread, midpoint, merged = extract_spreads_from_exchange_log(exchange_df)
        if spread is not None and not spread.empty:
            # Convert from cents to dollars for readability
            spread_dollars = spread / 100.0
            spread_dollars.plot(ax=axes[0], color='steelblue', linewidth=0.5, alpha=0.7)
            # Add rolling mean
            rolling_spread = spread_dollars.rolling(window=min(100, len(spread_dollars))).mean()
            rolling_spread.plot(ax=axes[0], color='darkred', linewidth=2, label='Rolling Mean')
            axes[0].set_title('Bid-Ask Spread Over Time')
            axes[0].set_ylabel('Spread ($)')
            axes[0].legend(['Raw Spread', 'Rolling Mean (100)'])
            axes[0].grid(True, alpha=0.3)
            has_plot = True

            print("SPREAD STATISTICS:")
            print("  Mean spread: ${:.4f}".format(spread_dollars.mean()))
            print("  Median spread: ${:.4f}".format(spread_dollars.median()))
            print("  Std spread: ${:.4f}".format(spread_dollars.std()))
            print()
        else:
            axes[0].text(0.5, 0.5, 'No bid-ask spread data available',
                        transform=axes[0].transAxes, ha='center', va='center', fontsize=14)
            axes[0].set_title('Bid-Ask Spread Over Time')

    # Panel 2: Cumulative Volume
    if exchange_df is not None:
        cum_vol = extract_volume_from_exchange_log(exchange_df)
        if cum_vol is not None and not cum_vol.empty:
            cum_vol.plot(ax=axes[1], color='forestgreen', linewidth=1.5)
            axes[1].set_title('Cumulative Trading Volume')
            axes[1].set_ylabel('Shares')
            axes[1].grid(True, alpha=0.3)
            has_plot = True

            print("VOLUME STATISTICS:")
            print("  Total volume: {:,} shares".format(int(cum_vol.iloc[-1])))
            print("  Number of executions: {:,}".format(len(cum_vol)))
            print()
        else:
            axes[1].text(0.5, 0.5, 'No volume data available',
                        transform=axes[1].transAxes, ha='center', va='center', fontsize=14)
            axes[1].set_title('Cumulative Trading Volume')

    # Panel 3: Price Discovery (midpoint vs fundamental)
    if exchange_df is not None and midpoint is not None and not midpoint.empty:
        mid_dollars = midpoint / 100.0
        mid_dollars.plot(ax=axes[2], color='steelblue', linewidth=0.8, alpha=0.8, label='Mid-Price')
        if fund_df is not None and not fund_df.empty:
            fund_series = fund_df.iloc[:, 0] / 100.0 if fund_df.iloc[:, 0].mean() > 500 else fund_df.iloc[:, 0]
            fund_series.plot(ax=axes[2], color='darkorange', linewidth=1.5, alpha=0.9, label='Fundamental Value')
        axes[2].set_title('Price Discovery: Mid-Price vs Fundamental')
        axes[2].set_ylabel('Price ($)')
        axes[2].legend()
        axes[2].grid(True, alpha=0.3)
        has_plot = True

        print("PRICE DISCOVERY STATISTICS:")
        print("  Mean mid-price: ${:.2f}".format(mid_dollars.mean()))
        print("  Final mid-price: ${:.2f}".format(mid_dollars.iloc[-1]))
        print("  Mid-price std: ${:.4f}".format(mid_dollars.std()))
        print()
    else:
        axes[2].text(0.5, 0.5, 'No price data available',
                    transform=axes[2].transAxes, ha='center', va='center', fontsize=14)
        axes[2].set_title('Price Discovery')

    plt.tight_layout()

    # Save figure
    img_name = f"{img_name_prefix}_analysis.png"
    output_file = os.path.join(log_dir, img_name)
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print("Analysis figure saved to: {}".format(output_file))
    print()

    # ──────────────────────────────────────────────────────────────
    # P&L Summary
    # ──────────────────────────────────────────────────────────────
    if summary_df is not None:
        pnl_df = analyze_pnl(summary_df)
        if pnl_df is not None:
            print("=" * 60)
            print("AGENT P&L SUMMARY")
            print("=" * 60)
            print(pnl_df.to_string(index=False))
            print()

            # Group by strategy
            grouped = pnl_df.groupby('Strategy')['PnL_dollars'].agg(['mean', 'sum', 'count'])
            print("P&L BY STRATEGY:")
            print(grouped.to_string())
            print()

    print("=" * 60)
    print("Analysis complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()
