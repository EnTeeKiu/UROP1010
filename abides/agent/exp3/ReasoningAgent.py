import re
import json
import traceback
import pandas as pd
from agent.TradingAgent import TradingAgent
from util.util import log_print

try:
    from openai import OpenAI
except ImportError:
    import requests

class ReasoningAgent(TradingAgent):
    def __init__(self, id, name, type, symbol='IBM', starting_cash=100000, 
                 wake_up_freq='60s', q_max=10, log_orders=False, random_state=None,
                 ollama_url='http://localhost:11434/v1', model_name='gemma3:4b'):
                 
        super().__init__(id, name, type, starting_cash=starting_cash, log_orders=log_orders, random_state=random_state)
        
        self.symbol = symbol
        self.wake_up_freq = wake_up_freq
        self.q_max = q_max
        self.ollama_url = ollama_url
        self.model_name = model_name

        self.trading = False
        self.state = 'AWAITING_WAKEUP'
        
        try:
            self.client = OpenAI(
                base_url=self.ollama_url,
                api_key='ollama',
            )
            self.use_openai = True
        except NameError:
            self.use_openai = False
            
        self.parse_failures = 0
        self.total_decisions = 0

    def kernelStarting(self, startTime):
        super().kernelStarting(startTime)

    def kernelStopping(self):
        super().kernelStopping()
        
        H = int(round(self.getHoldings(self.symbol), -2) / 100)
        cash = self.holdings['CASH']
        final_price = self.last_trade.get(self.symbol, 0)
        surplus = cash - self.starting_cash + (H * 100 * final_price)
        
        self.logEvent('FINAL_VALUATION', surplus, True)
        self.logEvent('PARSE_FAILURES', f"{self.parse_failures}/{self.total_decisions}", True)
        
        log_print("{} final report. Holdings {}, end cash {}, start cash {}, final price {}, surplus {}",
                  self.name, H, cash, self.starting_cash, final_price, surplus)
        log_print("{} Parse Failures: {}/{}", self.name, self.parse_failures, self.total_decisions)

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

        delta_time = pd.Timedelta(self.wake_up_freq)
        self.setWakeup(currentTime + delta_time)

        self.cancelOrders()

        self.getCurrentSpread(self.symbol)
        self.state = 'AWAITING_SPREAD'

    def receiveMessage(self, currentTime, msg):
        super().receiveMessage(currentTime, msg)

        if self.state == 'AWAITING_SPREAD' and msg.body['msg'] == 'QUERY_SPREAD':
            if self.mkt_closed: return
            self.make_llm_decision()
            self.state = 'AWAITING_WAKEUP'

    def cancelOrders(self):
        if not self.orders: return False
        for id, order in self.orders.items():
            self.cancelOrder(order)
        return True

    def getWakeFrequency(self):
        return pd.Timedelta(self.wake_up_freq)

    def get_prompt(self):
        bids = self.known_bids[self.symbol]
        asks = self.known_asks[self.symbol]
        
        top_bid = bids[0] if bids else (0, 0)
        top_ask = asks[0] if asks else (0, 0)
        
        bid, bid_sz = top_bid
        ask, ask_ask = top_ask # bug fix wait ask_sz
        bid, bid_sz = top_bid
        ask, ask_sz = top_ask
        last = self.last_trade.get(self.symbol, 0)
        pos = int(self.getHoldings(self.symbol) / 100)
        cash = self.holdings['CASH']
        
        prompt = f"You are a trader. Maximize profit.\n"
        prompt += f"bid={bid} ({bid_sz}) ask={ask} ({ask_sz}) last={last}  pos={pos:+d} cash={cash}\n"
        prompt += f"Think step-by-step about what action to take. After your reasoning, reply with your final decision as ONLY one action line on the LAST line:\n"
        prompt += f"BUY <price> <qty> | SELL <price> <qty> | HOLD"
        
        return prompt

    def make_llm_decision(self):
        prompt = self.get_prompt()
        log_print("{} querying LLM at {}...", self.name, self.currentTime)
        self.total_decisions += 1
        
        decision_text = ""
        action = "HOLD"
        qty = 0
        price = 0
        
        try:
            if self.use_openai:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=150,
                    temperature=0.1
                )
                decision_text = response.choices[0].message.content.strip()
            else:
                import requests
                payload = {
                    "model": self.model_name,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 150
                    }
                }
                url = self.ollama_url.replace('/v1', '/api/chat')
                res = requests.post(url, json=payload, timeout=30)
                res.raise_for_status()
                decision_text = res.json()['message']['content'].strip()
                
            # Regex to find the last action line. We'll search for the last matching line.
            matches = list(re.finditer(r'(BUY|SELL|HOLD)(?:\s+(\d+)\s+(\d+))?', decision_text.upper()))
            if matches:
                # take the last one
                match = matches[-1]
                action = match.group(1)
                if action in ["BUY", "SELL"]:
                    if match.group(2) and match.group(3):
                        price = int(match.group(2))
                        qty = int(match.group(3))
                    else:
                        raise ValueError("Missing price/qty for BUY/SELL")
            else:
                raise ValueError("Regex no match")
                
        except Exception as e:
            self.parse_failures += 1
            log_print("{} Parse failure: {} (Output: '{}')", self.name, str(e), decision_text)
            action = "HOLD"
            qty = 0
            price = 0
            
        log_print("{} decides to {}: {} lots @ {} cents.", self.name, action, qty, price)
            
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
