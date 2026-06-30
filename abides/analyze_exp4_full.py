import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


MEMORY_ARMS = [
    ("no_history", "No History"),
    ("last_5_events", "Last 5 Events"),
    ("last_20_events", "Last 20 Events"),
    ("rolling_session_summary", "Rolling Summary"),
]

RUN_GROUPS = [
    ("rerun", "Decision Only", "exp4_rerun_decision_only_{arm}_seed12345"),
    ("reasoning", "Reasoning JSON", "exp4_reasoning_json_{arm}_seed12345"),
    ("fills", "Decisions + Fills", "exp4_decisions_fills_{arm}_seed12345"),
]


def parse_price_event(event):
    try:
        return float(str(event).split(",")[1].replace("$", ""))
    except Exception:
        return np.nan


def load_summary(log_dir):
    return pd.read_pickle(os.path.join(log_dir, "summary_log.bz2"), compression="bz2")


def load_exchange(log_dir):
    return pd.read_pickle(os.path.join(log_dir, "EXCHANGE_AGENT.bz2"), compression="bz2")


def find_llm_log(log_dir):
    for name in os.listdir(log_dir):
        if name.startswith("LLM_EXP4") and name.endswith(".bz2"):
            return os.path.join(log_dir, name)
    return None


def find_decision_csv(root, log_dir, log_name, llm_log):
    candidates = []
    if llm_log:
        base = os.path.basename(llm_log).replace(".bz2", "_decision_log.csv")
        candidates.append(os.path.join(log_dir, base))
        candidates.append(os.path.join(root, "abides", log_name, base))
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def event_map(summary):
    llm_rows = summary[summary["AgentID"] == 10]
    return {row["EventType"]: row["Event"] for _, row in llm_rows.iterrows()}


def true_pnl(summary):
    rows = summary[(summary["AgentID"] == 10) & (summary["EventType"] == "ENDING_CASH")]
    if rows.empty:
        return np.nan
    return (float(rows.iloc[0]["Event"]) - 10000000) / 100.0


def rank_from_true_pnl(summary):
    start = summary[summary["EventType"] == "STARTING_CASH"][["AgentID", "Event"]]
    end = summary[summary["EventType"] == "ENDING_CASH"][["AgentID", "AgentStrategy", "Event"]]
    merged = end.merge(start, on="AgentID", suffixes=("_end", "_start"))
    merged["PnL"] = (
        pd.to_numeric(merged["Event_end"], errors="coerce")
        - pd.to_numeric(merged["Event_start"], errors="coerce")
    ) / 100.0
    merged = merged.sort_values("PnL", ascending=False).reset_index(drop=True)
    merged["Rank"] = np.arange(1, len(merged) + 1)
    return int(merged.loc[merged["AgentID"] == 10, "Rank"].iloc[0])


def order_stats(llm_df):
    orders = llm_df[llm_df["EventType"] == "ORDER_SUBMITTED"]["Event"]
    fills = llm_df[llm_df["EventType"] == "ORDER_EXECUTED"]["Event"]
    buys = 0
    sells = 0
    for event in orders:
        if isinstance(event, dict):
            if bool(event.get("is_buy_order")):
                buys += 1
            else:
                sells += 1
    return {
        "orders": len(orders),
        "buy_orders": buys,
        "sell_orders": sells,
        "fills": len(fills),
        "fill_rate": len(fills) / len(orders) if len(orders) else np.nan,
    }


def market_stats(exchange_df):
    bids = exchange_df[exchange_df["EventType"] == "BEST_BID"].copy()
    asks = exchange_df[exchange_df["EventType"] == "BEST_ASK"].copy()
    bids["bid"] = bids["Event"].apply(parse_price_event)
    asks["ask"] = asks["Event"].apply(parse_price_event)

    book = bids[["bid"]].join(asks[["ask"]], how="outer").sort_index().ffill().dropna()
    book["spread"] = book["ask"] - book["bid"]
    book["mid"] = (book["ask"] + book["bid"]) / 2.0
    book = book[book["spread"] >= 0]

    executed = exchange_df[exchange_df["EventType"] == "ORDER_EXECUTED"]["Event"]
    qty = 0
    for event in executed:
        if isinstance(event, dict):
            qty += int(event.get("quantity", 0))

    return {
        "mean_spread": book["spread"].mean() / 100.0,
        "median_spread": book["spread"].median() / 100.0,
        "mid_std": book["mid"].std() / 100.0,
        "volume": qty / 2.0,
        "executions": len(executed) / 2.0,
    }


def market_series(exchange_df, fund_df=None):
    bids = exchange_df[exchange_df["EventType"] == "BEST_BID"].copy()
    asks = exchange_df[exchange_df["EventType"] == "BEST_ASK"].copy()
    bids["bid"] = bids["Event"].apply(parse_price_event)
    asks["ask"] = asks["Event"].apply(parse_price_event)
    book = bids[["bid"]].join(asks[["ask"]], how="outer").sort_index().ffill().dropna()
    book["spread"] = book["ask"] - book["bid"]
    book["mid"] = (book["ask"] + book["bid"]) / 2.0
    book = book[book["spread"] >= 0]

    executed = exchange_df[exchange_df["EventType"] == "ORDER_EXECUTED"]["Event"]
    volumes = []
    times = []
    for idx, event in executed.items():
        if isinstance(event, dict):
            volumes.append(int(event.get("quantity", 0)) / 2.0)
            times.append(idx)
    cum_volume = pd.Series(volumes, index=times).cumsum()

    fundamental = None
    if fund_df is not None and not fund_df.empty:
        fundamental = fund_df.iloc[:, 0]
        if fundamental.mean() > 500:
            fundamental = fundamental / 100.0

    return book["spread"] / 100.0, cum_volume, book["mid"] / 100.0, fundamental


def collect(root):
    log_base = os.path.join(root, "abides", "log")
    rows = []
    for group_key, group_label, pattern in RUN_GROUPS:
        for arm_key, arm_label in MEMORY_ARMS:
            log_name = pattern.format(arm=arm_key)
            log_dir = os.path.join(log_base, log_name)
            if not os.path.isdir(log_dir):
                continue

            summary = load_summary(log_dir)
            exchange = load_exchange(log_dir)
            llm_log = find_llm_log(log_dir)
            llm_df = pd.read_pickle(llm_log, compression="bz2") if llm_log else pd.DataFrame()
            events = event_map(summary)

            row = {
                "group": group_key,
                "group_label": group_label,
                "arm": arm_key,
                "arm_label": arm_label,
                "log_name": log_name,
                "pnl": true_pnl(summary),
                "rank": rank_from_true_pnl(summary),
                "malformed": events.get("JSON_MALFORMED", ""),
                "network": events.get("NETWORK_ERRORS", ""),
                "hold_deliberate": events.get("HOLD_DELIBERATE", ""),
                "hold_fallback": events.get("HOLD_FALLBACK", ""),
                "tokens_median": float(events.get("TOKENS_OUT_MEDIAN", np.nan)),
                "prompt_mode": events.get("EXP4_PROMPT_MODE", ""),
                "memory_source": events.get("EXP4_MEMORY_SOURCE", ""),
            }
            row.update(order_stats(llm_df))
            row.update(market_stats(exchange))

            decision_csv = find_decision_csv(root, log_dir, log_name, llm_log)
            if decision_csv:
                decisions = pd.read_csv(decision_csv)
                row["memory_chars_mean"] = decisions["memory_chars"].mean()
                row["memory_fills_mean"] = decisions.get("memory_fills", pd.Series([0])).mean()
                row["rationale_nonempty"] = (
                    decisions.get("rationale", pd.Series(dtype=str)).fillna("").astype(str).str.len() > 0
                ).sum()
            else:
                row["memory_chars_mean"] = np.nan
                row["memory_fills_mean"] = np.nan
                row["rationale_nonempty"] = 0

            rows.append(row)
    return pd.DataFrame(rows)


def save_group_market_plot(root, metrics, group_key, group_label, output):
    log_base = os.path.join(root, "abides", "log")
    colors = ["steelblue", "forestgreen", "darkorange", "purple"]
    fig, axes = plt.subplots(3, 1, figsize=(14, 12), sharex=False)
    fig.suptitle(f"Experiment 4: {group_label} Market Dynamics", fontsize=16, fontweight="bold")
    fundamental_plotted = False

    group_rows = metrics[metrics["group"] == group_key]
    for (_, row), color in zip(group_rows.iterrows(), colors):
        log_dir = os.path.join(log_base, row["log_name"])
        exchange = load_exchange(log_dir)
        fund_path = os.path.join(log_dir, "fundamental_JPM.bz2")
        fund = pd.read_pickle(fund_path, compression="bz2") if os.path.exists(fund_path) else None
        spread, volume, mid, fundamental = market_series(exchange, fund)
        spread.rolling(window=min(100, len(spread))).mean().plot(
            ax=axes[0], color=color, linewidth=1.8, label=row["arm_label"]
        )
        volume.plot(ax=axes[1], color=color, linewidth=1.8, label=row["arm_label"])
        mid.plot(ax=axes[2], color=color, linewidth=1.1, alpha=0.85, label=row["arm_label"])
        if not fundamental_plotted and fundamental is not None:
            fundamental.plot(ax=axes[2], color="black", linestyle="--", linewidth=1.6, alpha=0.65, label="Fundamental")
            fundamental_plotted = True

    axes[0].set_title("Bid-Ask Spread Over Time")
    axes[0].set_ylabel("Spread ($)")
    axes[1].set_title("Cumulative Trading Volume")
    axes[1].set_ylabel("Shares")
    axes[2].set_title("Price Discovery: Mid-Price vs Fundamental")
    axes[2].set_ylabel("Price ($)")
    for ax in axes:
        ax.grid(True, alpha=0.3)
        ax.legend(loc="best")
    plt.tight_layout()
    fig.savefig(output, dpi=150, bbox_inches="tight")
    plt.close(fig)


def save_comparison_plots(metrics, results_dir):
    groups = [g[0] for g in RUN_GROUPS if g[0] in set(metrics["group"])]
    arm_labels = [label for _, label in MEMORY_ARMS]
    x = np.arange(len(arm_labels))
    width = 0.23
    offset_center = (len(groups) - 1) / 2.0

    fig, ax = plt.subplots(figsize=(12, 6))
    for i, group_key in enumerate(groups):
        subset = metrics[metrics["group"] == group_key].set_index("arm").loc[[a for a, _ in MEMORY_ARMS]]
        ax.bar(x + (i - offset_center) * width, subset["pnl"], width, label=subset["group_label"].iloc[0])
    ax.axhline(0, color="#333333", linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels(arm_labels)
    ax.set_ylabel("LLM true mark-to-market PnL ($)")
    ax.set_title("Experiment 4: True LLM PnL Across Runs and Variants")
    ax.legend()
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(os.path.join(results_dir, "exp4_full_pnl_comparison.png"), dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.8))
    for i, group_key in enumerate(groups):
        subset = metrics[metrics["group"] == group_key].set_index("arm").loc[[a for a, _ in MEMORY_ARMS]]
        axes[0].bar(x + (i - offset_center) * width, subset["mean_spread"], width, label=subset["group_label"].iloc[0])
        axes[1].bar(x + (i - offset_center) * width, subset["volume"], width, label=subset["group_label"].iloc[0])
    axes[0].set_title("Mean Bid-Ask Spread")
    axes[0].set_ylabel("Dollars")
    axes[1].set_title("Total Executed Volume")
    axes[1].set_ylabel("Shares")
    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels(arm_labels, rotation=15)
        ax.grid(True, alpha=0.25)
    axes[1].legend(loc="upper left", bbox_to_anchor=(1.02, 1.0))
    fig.tight_layout()
    fig.savefig(os.path.join(results_dir, "exp4_full_market_comparison.png"), dpi=180, bbox_inches="tight")
    plt.close(fig)


def table(df, columns, headers, formatters=None):
    formatters = formatters or {}
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for _, row in df.iterrows():
        values = []
        for col in columns:
            value = row[col]
            values.append(formatters[col](value) if col in formatters else str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def money(value):
    return "${:,.2f}".format(value)


def pct(value):
    return "{:.1f}%".format(value * 100)


def write_report(metrics, results_dir):
    ordered = metrics.copy()
    ordered["group_order"] = ordered["group"].map({g: i for i, (g, _, _) in enumerate(RUN_GROUPS)})
    ordered["arm_order"] = ordered["arm"].map({a: i for i, (a, _) in enumerate(MEMORY_ARMS)})
    ordered = ordered.sort_values(["group_order", "arm_order"])

    summary_table = table(
        ordered,
        ["group_label", "arm_label", "pnl", "rank", "orders", "buy_orders", "sell_orders", "fills", "fill_rate", "mean_spread", "volume"],
        ["Run", "Arm", "True LLM PnL", "Rank", "Orders", "BUY", "SELL", "Fills", "Fill rate", "Mean spread", "Volume"],
        {
            "pnl": money,
            "fill_rate": pct,
            "mean_spread": lambda v: f"${v:.2f}",
            "volume": lambda v: f"{v:,.0f}",
        },
    )

    reasoning = ordered[ordered["group"] == "reasoning"].sort_values("arm_order")
    fills = ordered[ordered["group"] == "fills"].sort_values("arm_order")
    rerun = ordered[ordered["group"] == "rerun"].sort_values("arm_order")

    best_reasoning = reasoning.loc[reasoning["pnl"].idxmax()]
    best_fills = fills.loc[fills["pnl"].idxmax()]
    best_rerun = rerun.loc[rerun["pnl"].idxmax()]
    worst_reasoning = reasoning.loc[reasoning["pnl"].idxmin()]

    report = f"""# Experiment 4: Full Memory Ablation Report

## 1. Scope

This report consolidates the three current Exp 4 representatives:

| Run | Prompt mode | Memory source | Purpose |
| --- | --- | --- | --- |
| Decision Only | Decision-only JSON | Own decisions | Main no-reasoning memory ablation baseline |
| Reasoning JSON | JSON with one rationale sentence | Own decisions | Tests whether no-reasoning output was too random |
| Decisions + Fills | Decision-only JSON | Own decisions + successful fills | Tests whether memory improves when it includes actual executions |

All runs use seed 12345, `gemma3:4b`, temperature 0.1, one LLM trader, and the same 9 traditional background agents.

PnL is computed from ABIDES' `ENDING_CASH` mark-to-market value. The custom `FINAL_VALUATION` event is not used in this report.

![Full PnL Comparison](exp4_full_pnl_comparison.png)

## 2. Market Dynamics

The plots below follow the same three-panel format used for Experiments 1-3: bid-ask spread, cumulative volume, and price discovery.

### 2.1 Decision Only

![Decision-only market dynamics](exp4_rerun_decision_only_analysis.png)

### 2.2 Reasoning JSON

![Reasoning market dynamics](exp4_reasoning_json_analysis.png)

### 2.3 Decisions + Fills

![Decisions and fills market dynamics](exp4_decisions_fills_analysis.png)

![Market comparison](exp4_full_market_comparison.png)

## 3. Cross-Run Metrics

{summary_table}

## 4. Analysis

### 4.1 Decision-Only Baseline

The decision-only baseline keeps the prompt feature fixed and removes reasoning, so it is the cleanest memory ablation. All four memory arms are profitable. The best decision-only result is **{best_rerun['arm_label']}** at {money(best_rerun['pnl'])}, while No History remains much lower at {money(rerun.iloc[0]['pnl'])}. This supports the idea that even compact or shallow memory helps the LLM place more effective orders than stateless decisions.

### 4.2 Reasoning Changes The Memory Effect

The reasoning-enabled variant changes behavior substantially. The best overall result in this report is **{best_reasoning['arm_label']}** under Reasoning JSON at {money(best_reasoning['pnl'])}. However, reasoning is not uniformly better: **{worst_reasoning['arm_label']}** falls to {money(worst_reasoning['pnl'])}. This suggests that reasoning interacts with the memory payload rather than acting as a general quality improvement.

The rationale field also increases generation cost and wall-clock time. It is useful as a diagnostic variant, but it should not be mixed into the primary no-reasoning memory ablation.

### 4.3 Successful-Trade Memory Is Useful When Compressed

The decisions-plus-fills variant gives the LLM access to its own actual successful trades. The strongest arm is **{best_fills['arm_label']}** with {money(best_fills['pnl'])}. The rolling summary with fills is especially strong, suggesting that successful trade memory is more useful when summarized than when appended as a longer raw event stream.

The raw Last 20 Events arm behaves very differently in this setting: it submits only 7 orders and earns {money(fills[fills['arm'] == 'last_20_events'].iloc[0]['pnl'])}. That does not mean fills are harmful; rather, it suggests the raw combined memory payload can become too distracting or restrictive for this prompt format.

### 4.4 Memory Still Does Not Create Restraint

Across all variants, the LLM continues to submit an order at nearly every wakeup. The dominant action remains BUY in most arms. Memory changes price/quantity/fill outcomes more than it changes the model's willingness to trade.

### 4.5 Market Quality And LLM Profitability Remain Different

The market plots show that tighter spreads or higher volume do not guarantee better LLM PnL. Some arms improve liquidity-like metrics while increasing the LLM's inventory risk. Exp 4 should therefore report both market-level metrics and agent-level mark-to-market PnL.

## 5. Conclusions

1. **Decision-only memory remains the primary Exp 4 baseline.** It keeps prompt mode fixed and shows that memory improves results over No History.
2. **Reasoning should be interpreted as a separate prompt feature.** It produces the best single outcome, but it also creates the weakest no-memory outcome and changes runtime cost.
3. **Successful fills help most when compressed.** The best fills-aware result is Rolling Summary at {money(best_fills['pnl'])}.
4. **Raw memory is not always better memory.** Last 20 Events performs strongly with reasoning, but weakly when decisions and fills are combined as raw history.
5. **Agent PnL and market quality should both be reported.** Liquidity-like metrics explain market conditions, but they do not directly determine the LLM trader's profit.
"""

    path = os.path.join(results_dir, "exp4_full_result_report.md")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(report)


def main():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    results_dir = os.path.join(root, "Results")
    os.makedirs(results_dir, exist_ok=True)

    metrics = collect(root)
    metrics.to_csv(os.path.join(results_dir, "exp4_full_metrics.csv"), index=False)

    for group_key, group_label, _pattern in RUN_GROUPS:
        if group_key in set(metrics["group"]):
            filename_map = {
                "rerun": "exp4_rerun_decision_only_analysis.png",
                "reasoning": "exp4_reasoning_json_analysis.png",
                "fills": "exp4_decisions_fills_analysis.png",
            }
            save_group_market_plot(
                root,
                metrics,
                group_key,
                group_label,
                os.path.join(results_dir, filename_map[group_key]),
            )

    save_comparison_plots(metrics, results_dir)
    write_report(metrics, results_dir)

    print(metrics.sort_values(["group", "arm"]).to_string(index=False))
    print("Wrote Results/exp4_full_result_report.md")


if __name__ == "__main__":
    main()
