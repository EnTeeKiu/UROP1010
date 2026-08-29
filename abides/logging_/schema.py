import pandas as pd

"""
Parquet schema definitions for output data.
By defining these explicitly, we ensure downstream analysis scripts
can rely on column presence and types.
"""

DECISIONS_SCHEMA = {
    'time': 'datetime64[ns]',
    'policy_side': 'string',
    'final_side': 'string',
    'limit_price': 'int64',
    'quantity': 'int64',
    'inventory': 'int64',
    'cash': 'int64',
    'llm_raw_output': 'string',
    'llm_valid': 'boolean',
    'llm_fallback_used': 'boolean',
    'llm_latency_ms': 'Int64',  # nullable int
    'llm_prompt': 'string'
}

ORDERS_SCHEMA = {
    'time': 'datetime64[ns]',
    'order_id': 'Int64',
    'agent_id': 'Int64',
    'symbol': 'string',
    'direction': 'string',  # "BUY" or "SELL"
    'quantity': 'int64',
    'price': 'int64',
    'status': 'string'  # "ACCEPTED", "CANCELLED", "EXECUTED"
}

TRADES_SCHEMA = {
    'time': 'datetime64[ns]',
    'trade_id': 'Int64',
    'order_id': 'Int64',
    'symbol': 'string',
    'price': 'int64',
    'quantity': 'int64',
    'buyer_id': 'Int64',
    'seller_id': 'Int64'
}

BOOK_L1_SCHEMA = {
    'time': 'datetime64[ns]',
    'symbol': 'string',
    'best_bid': 'Int64',
    'best_bid_sz': 'Int64',
    'best_ask': 'Int64',
    'best_ask_sz': 'Int64',
    'midpoint': 'Float64'
}

FUNDAMENTAL_SCHEMA = {
    'time': 'datetime64[ns]',
    'symbol': 'string',
    'value': 'int64'
}

def enforce_schema(df: pd.DataFrame, schema: dict) -> pd.DataFrame:
    """
    Ensures all columns in the schema exist. If missing, fills with NA.
    Casts to standard types.
    """
    for col, dtype in schema.items():
        if col not in df.columns:
            if dtype == 'datetime64[ns]':
                df[col] = pd.NaT
            else:
                df[col] = pd.NA
        df[col] = df[col].astype(dtype)
    
    # Return exactly the schema columns in the specified order
    return df[list(schema.keys())]
