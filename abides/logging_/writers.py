import os
import glob
import argparse
import pandas as pd
import numpy as np

from logging_.schema import (
    DECISIONS_SCHEMA, ORDERS_SCHEMA, TRADES_SCHEMA, BOOK_L1_SCHEMA, FUNDAMENTAL_SCHEMA, enforce_schema
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
    
    for idx, row in df_orders.iterrows():
        ev = row['Event']
        event_type = row['EventType']
        
        # Order Record
        status = event_type.split('_')[1]  # ACCEPTED, CANCELLED, EXECUTED
        
        # Some fields might be None or missing
        direction = "BUY" if ev.get('is_buy_order') else "SELL"
        
        records.append({
            'time': pd.to_datetime(ev.get('time_placed', idx)),
            'order_id': ev.get('order_id'),
            'agent_id': ev.get('agent_id'),
            'symbol': ev.get('symbol', 'JPM'),
            'direction': direction,
            'quantity': ev.get('quantity', 0),
            'price': ev.get('limit_price', 0),
            'status': status
        })
        
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

    df_o = pd.DataFrame(records)
    df_t = pd.DataFrame(trade_records)

    df_o = enforce_schema(df_o, ORDERS_SCHEMA)
    df_t = enforce_schema(df_t, TRADES_SCHEMA)

    return df_o, df_t


def extract_book_l1(log_dir: str):
    """
    Extracts L1 book state from ORDERBOOK_*.bz2.
    """
    book_files = glob.glob(os.path.join(log_dir, "ORDERBOOK_*_FREQ_s.bz2"))
    if not book_files:
        print("No ORDERBOOK log found.")
        return pd.DataFrame(columns=BOOK_L1_SCHEMA.keys())
        
    df_book = pd.read_pickle(book_files[0])
    
    # ABIDES orderbook logs are MultiIndex: (time, quote) -> Volume
    # We need to compute best bid, best ask per second.
    # But wait, ABIDES orderbook logs might just be all volumes at all price levels.
    # A faster proxy is to use EXCHANGE_AGENT BEST_BID / BEST_ASK events.
    # Let's use EXCHANGE_AGENT instead for exact L1 ticks.
    
    exch_path = os.path.join(log_dir, "EXCHANGE_AGENT.bz2")
    if not os.path.exists(exch_path):
        return pd.DataFrame(columns=BOOK_L1_SCHEMA.keys())
        
    df_exch = pd.read_pickle(exch_path)
    
    df_bba = df_exch[df_exch['EventType'].isin(['BEST_BID', 'BEST_ASK'])].copy()
    if len(df_bba) == 0:
        return pd.DataFrame(columns=BOOK_L1_SCHEMA.keys())
        
    records = []
    
    # Track current state
    current_bid = pd.NA
    current_bid_sz = pd.NA
    current_ask = pd.NA
    current_ask_sz = pd.NA
    
    for idx, row in df_bba.iterrows():
        ev = row['Event'] # e.g. "JPM,100000,34" or "JPM,No bids,0"
        
        parts = str(ev).split(',')
        if len(parts) >= 3:
            sym = parts[0]
            price_str = parts[1]
            sz_str = parts[2]
            
            if row['EventType'] == 'BEST_BID':
                if price_str == "No bids":
                    current_bid = pd.NA
                    current_bid_sz = 0
                else:
                    current_bid = int(price_str)
                    current_bid_sz = int(sz_str)
            else:
                if price_str == "No asks":
                    current_ask = pd.NA
                    current_ask_sz = 0
                else:
                    current_ask = int(price_str)
                    current_ask_sz = int(sz_str)
            
            mid = pd.NA
            if pd.notna(current_bid) and pd.notna(current_ask):
                mid = (current_bid + current_ask) / 2.0
                
            records.append({
                'time': pd.to_datetime(idx),
                'symbol': sym,
                'best_bid': current_bid,
                'best_bid_sz': current_bid_sz,
                'best_ask': current_ask,
                'best_ask_sz': current_ask_sz,
                'midpoint': mid
            })
            
    df = pd.DataFrame(records)
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
    if len(decisions_df) > 0:
        decisions_df.to_parquet(os.path.join(log_dir, "decisions.parquet"))
        print(f"  Wrote decisions.parquet ({len(decisions_df)} rows)")
        
    orders_df, trades_df = extract_exchange_events(log_dir)
    if len(orders_df) > 0:
        orders_df.to_parquet(os.path.join(log_dir, "orders.parquet"))
        print(f"  Wrote orders.parquet ({len(orders_df)} rows)")
    if len(trades_df) > 0:
        trades_df.to_parquet(os.path.join(log_dir, "trades.parquet"))
        print(f"  Wrote trades.parquet ({len(trades_df)} rows)")
        
    book_df = extract_book_l1(log_dir)
    if len(book_df) > 0:
        book_df.to_parquet(os.path.join(log_dir, "book_l1.parquet"))
        print(f"  Wrote book_l1.parquet ({len(book_df)} rows)")
        
    fund_df = extract_fundamental(log_dir)
    if len(fund_df) > 0:
        fund_df.to_parquet(os.path.join(log_dir, "fundamental.parquet"))
        print(f"  Wrote fundamental.parquet ({len(fund_df)} rows)")
        
    print("Done.")


if __name__ == "__main__":
    main()
