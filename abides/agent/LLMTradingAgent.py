from agent.TradingAgent import TradingAgent
from util.util import log_print

import numpy as np
import pandas as pd
import json
import traceback

try:
    from openai import OpenAI
except ImportError:
    # Fallback to requests if openai isn't installed
    import requests

class LLMTradingAgent(TradingAgent):
    """
    An agent that uses a local LLM via Ollama to make trading decisions.
    It receives the top of the limit order book and its own holdings,
    then returns a JSON payload deciding whether to BUY, SELL, or HOLD.
    """
    def __init__(self, id, name, type, symbol='IBM', starting_cash=100000, 
                 wake_up_freq='60s', q_max=10, log_orders=False, random_state=None,
                 ollama_url='http://localhost:11434/v1', model_name='gemma3:4b'):

        # Base class init
        super().__init__(id, name, type, starting_cash=starting_cash, log_orders=log_orders, random_state=random_state)

        self.symbol = symbol
        self.wake_up_freq = wake_up_freq
        self.q_max = q_max
        
        self.ollama_url = ollama_url
        self.model_name = model_name

        self.trading = False
        self.state = 'AWAITING_WAKEUP'
        
        # Memory of last 5 decisions
        self.memory = []

        # Try setting up OpenAI client
        try:
            self.client = OpenAI(
                base_url=self.ollama_url,
                api_key='ollama', # required but ignored
            )
            self.use_openai = True
        except NameError:
            self.use_openai = False
            # Will use requests instead

    def kernelStarting(self, startTime):
        super().kernelStarting(startTime)

    def kernelStopping(self):
        super().kernelStopping()
        
        # Print end of day valuation
        H = int(round(self.getHoldings(self.symbol), -2) / 100)
        cash = self.holdings['CASH']
        
        # For simplicity in baseline, we just look at Mark to Market value using last trade price
        final_price = self.last_trade.get(self.symbol, 0)
        surplus = cash - self.starting_cash + (H * 100 * final_price)
        
        self.logEvent('FINAL_VALUATION', surplus, True)
        log_print("{} final report. Holdings {}, end cash {}, start cash {}, final price {}, surplus {}",
                  self.name, H, cash, self.starting_cash, final_price, surplus)

    def wakeup(self, currentTime):
        super().wakeup(currentTime)
        self.state = 'INACTIVE'

        if not self.mkt_open or not self.mkt_close:
            return
        else:
            if not self.trading:
                self.trading = True
                log_print("{} is ready to start trading now.", self.name)

        if self.mkt_closed:
            return

        # Schedule next wakeup
        delta_time = pd.Timedelta(self.wake_up_freq)
        self.setWakeup(currentTime + delta_time)

        # Cancel open orders
        self.cancelOrders()

        # Get current spread to make a decision
        self.getCurrentSpread(self.symbol)
        self.state = 'AWAITING_SPREAD'

    def receiveMessage(self, currentTime, msg):
        super().receiveMessage(currentTime, msg)

        if self.state == 'AWAITING_SPREAD' and msg.body['msg'] == 'QUERY_SPREAD':
            if self.mkt_closed: return
            
            # Now we have the book and can make a decision
            self.make_llm_decision()
            self.state = 'AWAITING_WAKEUP'

    def cancelOrders(self):
        if not self.orders: return False
        for id, order in self.orders.items():
            self.cancelOrder(order)
        return True

    def getWakeFrequency(self):
        return pd.Timedelta(self.wake_up_freq)

    def format_market_state(self):
        # Build prompt state
        bids = self.known_bids[self.symbol]
        asks = self.known_asks[self.symbol]
        
        # Top 5 bids and asks
        top_bids = bids[:5] if bids else []
        top_asks = asks[:5] if asks else []

        state_str = f"Time: {self.currentTime}\n"
        state_str += f"Last Traded Price: {self.last_trade.get(self.symbol, 'None')}\n\n"
        
        state_str += "Limit Order Book (Top 5):\n"
        state_str += "| Action | Price | Volume |\n"
        state_str += "|---|---|---|\n"
        
        for price, vol in reversed(top_asks):
            state_str += f"| ASK | {price} | {vol} |\n"
            
        for price, vol in top_bids:
            state_str += f"| BID | {price} | {vol} |\n"
            
        state_str += f"\nAgent Portfolio:\n"
        state_str += f"- Cash: {self.holdings['CASH']}\n"
        current_holdings = int(self.getHoldings(self.symbol) / 100)
        state_str += f"- Stock Holdings: {current_holdings} lots (1 lot = 100 shares)\n"
        
        if self.memory:
            state_str += "\nRecent Actions (Memory):\n"
            for m in self.memory[-5:]:
                state_str += f"- {m}\n"
                
        return state_str

    def get_system_prompt(self):
        return """You are a rational trading agent operating in a financial market simulation. 
You will be provided with the current Limit Order Book, the last traded price, and your current portfolio. 
Prices are in cents (e.g. 100000 = $1000.00).

Your goal is to maximize your profit. 
You must analyze the order book and decide whether to BUY, SELL, or HOLD.
- If you BUY, you place a bid limit order.
- If you SELL, you place an ask limit order.
- If you HOLD, you do nothing this turn.

You can hold a maximum of 10 lots long or 10 lots short. Do not exceed this limit.
If you decide to trade, you must provide a limit price and a quantity (in lots of 100 shares, between 1 and 10).

You must respond ONLY with a JSON object in the following format:
{
  "action": "BUY" | "SELL" | "HOLD",
  "quantity": <integer 1 to 10, or 0 if HOLD>,
  "price": <integer price in cents, or 0 if HOLD>,
  "reasoning": "<brief explanation of your logic>"
}"""

    def make_llm_decision(self):
        market_state = self.format_market_state()
        system_prompt = self.get_system_prompt()
        
        log_print("{} querying LLM at {}...", self.name, self.currentTime)
        
        decision = {"action": "HOLD", "quantity": 0, "price": 0, "reasoning": "Fallback/Error"}
        
        try:
            if self.use_openai:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": market_state}
                    ],
                    response_format={"type": "json_object"},
                    max_tokens=150,
                    temperature=0.1 # low temp for more deterministic trading
                )
                decision_text = response.choices[0].message.content
                decision = json.loads(decision_text)
            else:
                import requests
                # Fallback to requests if openai not installed
                payload = {
                    "model": self.model_name,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": market_state}
                    ],
                    "format": "json",
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 150
                    }
                }
                url = self.ollama_url.replace('/v1', '/api/chat')
                res = requests.post(url, json=payload, timeout=30)
                res.raise_for_status()
                decision_text = res.json()['message']['content']
                decision = json.loads(decision_text)
                
        except Exception as e:
            log_print("{} LLM query failed: {}", self.name, str(e))
            traceback.print_exc()
            
        action = decision.get("action", "HOLD")
        qty = decision.get("quantity", 0)
        price = decision.get("price", 0)
        reasoning = decision.get("reasoning", "")
        
        log_print("{} decides to {}: {} lots @ {} cents. Reason: {}", self.name, action, qty, price, reasoning)
        
        self.memory.append(f"{self.currentTime}: {action} {qty} lots @ {price}")
        if len(self.memory) > 5:
            self.memory.pop(0)
            
        if action == "HOLD":
            return
            
        if qty <= 0 or qty > self.q_max:
            log_print("{} Invalid quantity {}, skipping order.", self.name, qty)
            return
            
        current_holdings = int(self.getHoldings(self.symbol) / 100)
        
        if action == "BUY":
            if current_holdings + qty > self.q_max:
                qty = self.q_max - current_holdings
                if qty <= 0: return
            self.placeLimitOrder(self.symbol, qty * 100, True, price)
        elif action == "SELL":
            if current_holdings - qty < -self.q_max:
                qty = current_holdings + self.q_max
                if qty <= 0: return
            self.placeLimitOrder(self.symbol, qty * 100, False, price)
