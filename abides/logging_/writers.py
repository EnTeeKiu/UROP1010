import os
import glob
import argparse
import pandas as pd
import numpy as np

from logging_.schema import (
    DECISIONS_SCHEMA, ORDERS_SCHEMA, TRADES_SCHEMA, BOOK_L1_SCHEMA,
    FUNDAMENTAL_SCHEMA, AGENT_STATE_SCHEMA, TREATMENT_REQUESTS_SCHEMA,
    enforce_schema
)
from util.util import log_print


def extract_decisions(log_dir: str):
    """
    Finds the treatment agent log and extracts WRAPPER_DECISION events.
    Returns DataFrame matching DECISIONS_SCHEMA.
    """
    # Treatment agent is always id 10
    treatment_files = glob.glob(os.path.join(log_dir, "*_10.bz2"))
    if not treatment_files:
        print("No treatment agent log found.")
        return pd.DataFrame(columns=DECISIONS_SCHEMA.keys())

    file_path = treatment_files[0]
    df_agent = pd.read_pickle(file_path)

    # Filter for WRAPPER_DECISION
    df_dec = df_agent[df_agent['EventType'] == 'WRAPPER_DECISION'].copy()
    
    if len(df_dec) == 0:
        return pd.DataFrame(columns=DECISIONS_SCHEMA.keys())

    # The Event column contains the dictionary payload
    records = list(df_dec['Event'].values)
    df = pd.DataFrame(records)
    
    # Time is already in df from the index of df_agent if we reset it, or in the dict
    if 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'])

    df = enforce_schema(df, DECISIONS_SCHEMA)
    return df


def extract_exchange_events(log_dir: str):
    """
    Extracts orders and trades from EXCHANGE_AGENT.bz2.
    Returns (orders_df, trades_df).
    """
    exch_path = os.path.join(log_dir, "EXCHANGE_AGENT.bz2")
    if not os.path.exists(exch_path):
        print("EXCHANGE_AGENT.bz2 not found.")
        return pd.DataFrame(columns=ORDERS_SCHEMA.keys()), pd.DataFrame(columns=TRADES_SCHEMA.keys())

    df_exch = pd.read_pickle(exch_path)
    
    # Filter for order events
    order_events = ['ORDER_ACCEPTED', 'ORDER_CANCELLED', 'ORDER_EXECUTED']
    df_orders = df_exch[df_exch['EventType'].isin(order_events)].copy()
    
    if len(df_orders) == 0:
        return pd.DataFrame(columns=ORDERS_SCHEMA.keys()), pd.DataFrame(columns=TRADES_SCHEMA.keys())
    
    records = []
    trade_records = []
    open_orders = {}
    
    for idx, row in df_orders.iterrows():
        ev = row['Event']
        event_type = row['EventType']
        
        # Order Record
        status = event_type.split('_')[1]  # ACCEPTED, CANCELLED, EXECUTED
        
        # Some fields might be None or missing
        direction = "BUY" if ev.get('is_buy_order') else "SELL"
        
        records.append({
            # ``idx`` is when the exchange emitted this lifecycle event.  Keeping
            # placement time separate is essential for ordering/cancellation audits.
            'time': pd.to_datetime(idx),
            'time_placed': pd.to_datetime(ev.get('time_placed', idx)),
            'order_id': ev.get('order_id'),
            'agent_id': ev.get('agent_id'),
            'symbol': ev.get('symbol', 'JPM'),
            'direction': direction,
            'quantity': ev.get('quantity', 0),
            'price': ev.get('limit_price', 0),
            'status': status
        })

        order_id = ev.get('order_id')
        if order_id is not None:
            if status == 'ACCEPTED':
                open_orders[order_id] = {
                    'time_placed': pd.to_datetime(ev.get('time_placed', idx)),
                    'agent_id': ev.get('agent_id'),
                    'symbol': ev.get('symbol', 'JPM'),
                    'direction': direction,
                    'quantity': int(ev.get('quantity', 0)),
                    'price': ev.get('limit_price', 0),
                }
            elif status == 'EXECUTED' and order_id in open_orders:
                open_orders[order_id]['quantity'] = max(
                    0, open_orders[order_id]['quantity'] - int(ev.get('quantity', 0))
                )
                if open_orders[order_id]['quantity'] == 0:
                    del open_orders[order_id]
            elif status == 'CANCELLED':
                open_orders.pop(order_id, None)
        
        # Trade Record (from ORDER_EXECUTED)
        if event_type == 'ORDER_EXECUTED':
            trade_records.append({
                'time': pd.to_datetime(idx),
                'trade_id': ev.get('order_id'),  # ABIDES doesn't emit global trade IDs easily; use order_id as proxy for the leg
                'order_id': ev.get('order_id'),
                'symbol': ev.get('symbol', 'JPM'),
                'price': ev.get('fill_price', 0),
                'quantity': ev.get('quantity', 0),
                'buyer_id': ev.get('agent_id') if ev.get('is_buy_order') else pd.NA,
                'seller_id': ev.get('agent_id') if not ev.get('is_buy_order') else pd.NA
            })

    # ABIDES leaves resting orders in the book when the session closes. Record
    # their remaining quantity as explicitly expired so every lifecycle terminates.
    expiry_time = pd.to_datetime(df_exch.index.max())
    for order_id, order in open_orders.items():
        if order['quantity'] <= 0:
            continue
        records.append({
            'time': expiry_time,
            'time_placed': order['time_placed'],
            'order_id': order_id,
            'agent_id': order['agent_id'],
            'symbol': order['symbol'],
            'direction': order['direction'],
            'quantity': order['quantity'],
            'price': order['price'],
            'status': 'EXPIRED',
        })

    df_o = pd.DataFrame(records)
    df_t = pd.DataFrame(trade_records)

    df_o = enforce_schema(df_o, ORDERS_SCHEMA)
    df_t = enforce_schema(df_t, TRADES_SCHEMA)

    return df_o, df_t


def extract_agent_state(log_dir: str):
    """Extract treatment-agent inventory and cash after every fill."""
    treatment_files = glob.glob(os.path.join(log_dir, "*_10.bz2"))
    if not treatment_files:
        return pd.DataFrame(columns=AGENT_STATE_SCHEMA.keys())

    df_agent = pd.read_pickle(treatment_files[0])
    state_rows = df_agent[df_agent['EventType'] == 'HOLDINGS_UPDATED']
    records = []
    for idx, row in state_rows.iterrows():
        holdings = row['Event']
        if not isinstance(holdings, dict):
            continue
        records.append({
            'time': pd.to_datetime(idx),
            'agent_id': 10,
            'inventory': holdings.get('JPM', 0),
            'cash': holdings.get('CASH', 0),
        })
    return enforce_schema(pd.DataFrame(records), AGENT_STATE_SCHEMA)


def extract_treatment_requests(log_dir: str):
    """Extract the wrapper's actual submit and cancel requests before exchange handling."""
    treatment_files = glob.glob(os.path.join(log_dir, "*_10.bz2"))
    if not treatment_files:
        return pd.DataFrame(columns=TREATMENT_REQUESTS_SCHEMA.keys())

    df_agent = pd.read_pickle(treatment_files[0])
    request_rows = df_agent[df_agent['EventType'].isin(['ORDER_SUBMITTED', 'CANCEL_SUBMITTED'])]
    records = []
    for idx, row in request_rows.iterrows():
        order = row['Event']
        if not isinstance(order, dict):
            continue
        records.append({
            'time': pd.to_datetime(idx),
            'order_id': order.get('order_id'),
            'event_type': row['EventType'],
            'direction': 'BUY' if order.get('is_buy_order') else 'SELL',
            'quantity': order.get('quantity', 0),
            'price': order.get('limit_price', 0),
        })
    return enforce_schema(pd.DataFrame(records), TREATMENT_REQUESTS_SCHEMA)


def extract_book_l1(log_dir: str):
    """
    Extracts one-second L1 state from the complete ORDERBOOK snapshot log.

    Negative volume denotes bids and positive volume denotes asks.  Using the
    snapshot is essential: Exchange BEST_BID/BEST_ASK events do not emit an
    explicit update when one side becomes empty, so event reconstruction can
    retain a stale quote and even manufacture a crossed book.
    """
    book_files = glob.glob(os.path.join(log_dir, "ORDERBOOK_*_FREQ_s.bz2"))
    if not book_files:
        print("No ORDERBOOK log found.")
        return pd.DataFrame(columns=BOOK_L1_SCHEMA.keys())

    raw = pd.read_pickle(book_files[0]).reset_index()
    raw['time'] = pd.to_datetime(raw['time'])
    raw['quote'] = pd.to_numeric(raw['quote'])
    raw['Volume'] = pd.to_numeric(raw['Volume'])
    times = pd.DataFrame({'time': raw['time'].drop_duplicates().sort_values()})

    bids = raw[raw['Volume'] < 0].sort_values(['time', 'quote'])
    bids = bids.groupby('time', sort=False).tail(1)[['time', 'quote', 'Volume']]
    bids = bids.rename(columns={'quote': 'best_bid', 'Volume': 'best_bid_sz'})
    bids['best_bid_sz'] = -bids['best_bid_sz']

    asks = raw[raw['Volume'] > 0].sort_values(['time', 'quote'])
    asks = asks.groupby('time', sort=False).head(1)[['time', 'quote', 'Volume']]
    asks = asks.rename(columns={'quote': 'best_ask', 'Volume': 'best_ask_sz'})

    df = times.merge(bids, on='time', how='left').merge(asks, on='time', how='left')
    df['symbol'] = 'JPM'
    df['midpoint'] = (df['best_bid'] + df['best_ask']) / 2.0
    df = enforce_schema(df, BOOK_L1_SCHEMA)
    return df


def extract_fundamental(log_dir: str):
    """
    Extracts fundamental values from fundamental_*.bz2.
    """
    fund_files = glob.glob(os.path.join(log_dir, "fundamental_*.bz2"))
    if not fund_files:
        print("No fundamental log found.")
        return pd.DataFrame(columns=FUNDAMENTAL_SCHEMA.keys())
        
    df_fund = pd.read_pickle(fund_files[0])
    
    df = pd.DataFrame({
        'time': pd.to_datetime(df_fund.index),
        'symbol': 'JPM', # Hardcoded for this experiment
        'value': df_fund['FundamentalValue']
    })
    
    df = enforce_schema(df, FUNDAMENTAL_SCHEMA)
    return df


def main():
    parser = argparse.ArgumentParser(description="Extract ABIDES bz2 logs to Parquet formats")
    parser.add_argument("log_dir", type=str, help="Path to the simulation log directory (e.g. output/raw/C2-N/1001)")
    args = parser.parse_args()
    
    log_dir = args.log_dir
    print(f"Extracting logs in {log_dir}...")
    
    decisions_df = extract_decisions(log_dir)
    decisions_df.to_parquet(os.path.join(log_dir, "decisions.parquet"))
    print(f"  Wrote decisions.parquet ({len(decisions_df)} rows)")
        
    orders_df, trades_df = extract_exchange_events(log_dir)
    orders_df.to_parquet(os.path.join(log_dir, "orders.parquet"))
    print(f"  Wrote orders.parquet ({len(orders_df)} rows)")
    trades_df.to_parquet(os.path.join(log_dir, "trades.parquet"))
    print(f"  Wrote trades.parquet ({len(trades_df)} rows)")
        
    book_df = extract_book_l1(log_dir)
    book_df.to_parquet(os.path.join(log_dir, "book_l1.parquet"))
    print(f"  Wrote book_l1.parquet ({len(book_df)} rows)")
        
    fund_df = extract_fundamental(log_dir)
    fund_df.to_parquet(os.path.join(log_dir, "fundamental.parquet"))
    print(f"  Wrote fundamental.parquet ({len(fund_df)} rows)")

    state_df = extract_agent_state(log_dir)
    state_df.to_parquet(os.path.join(log_dir, "agent_state.parquet"))
    print(f"  Wrote agent_state.parquet ({len(state_df)} rows)")

    requests_df = extract_treatment_requests(log_dir)
    requests_df.to_parquet(os.path.join(log_dir, "treatment_requests.parquet"))
    print(f"  Wrote treatment_requests.parquet ({len(requests_df)} rows)")
        
    print("Done.")


if __name__ == "__main__":
    main()
