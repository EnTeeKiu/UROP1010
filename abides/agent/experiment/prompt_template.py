SYSTEM_PROMPT = """You are a trading agent. You will receive market state.
Your ONLY job: decide whether to BUY or SELL.
All prices are in cents (100000 = $1000.00).

Respond with ONLY a JSON object: {"side": "BUY"} or {"side": "SELL"}
No other text."""

def build_user_prompt(state: dict) -> str:
    """
    Constructs the prompt string from the state snapshot dictionary.
    """
    return f"bid={state['best_bid']} ({state['best_bid_sz']}) " \
           f"ask={state['best_ask']} ({state['best_ask_sz']}) " \
           f"mid={state['midpoint']} last={state['last_trade']} " \
           f"pos={state['inventory']} cash={state['cash']}"
