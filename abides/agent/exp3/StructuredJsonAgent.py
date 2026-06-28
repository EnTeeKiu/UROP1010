import pandas as pd
import numpy as np
import os
import re
import json

from agent.TradingAgent import TradingAgent
from util.util import log_print
try:
    from openai import OpenAI
except ImportError:
    pass

# ============================================================
# StructuredJsonAgent — Exp 3, Structured-JSON arm (Option A)
# ============================================================
# Tests: Does forcing reasoning into strict JSON trade decision 
#        quality for parse reliability? (Tam et al. hypothesis)
# Mirrors R3: Exposure, Edge, Verify, Decision.
# ============================================================


class StructuredJsonAgent(TradingAgent):
    def __init__(self, id, name, type, symbol, starting_cash,
                 wake_up_freq='60s', q_max=10,
                 log_orders=True, random_state=None,
                 ollama_url='http://localhost:11434/v1',
                 model_name='gemma3:4b'):

        super().__init__(id, name, type, starting_cash=starting_cash, log_orders=log_orders, random_state=random_state)
        
        self.symbol = symbol
        self.wake_up_freq = wake_up_freq
        self.q_max = q_max

        # LLM specific
        self.ollama_url = ollama_url
        self.model_name = model_name
        
        # Metrics
        self.total_decisions = 0
        self.json_malformed_count = 0
        self.fence_stripped_count = 0
        self.hold_deliberate_count = 0
        self.hold_fallback_count = 0
        self.network_errors = 0
        self.truncated_count = 0
        self.tokens_out_list = []
        
        # New Tam-specific metrics
        self.reasoning_chars_list = []
        self.total_chars_list = []
        
        self.binding_match = 0
        self.binding_mismatch = 0
        self.binding_ambiguous = 0
        self.verify_cites_number = 0

        self.decision_log = []
        
        self.state = 'AWAITING_WAKEUP'
        
        try:
            self.client = OpenAI(base_url=self.ollama_url, api_key='ollama', timeout=60.0)
            self.use_openai = True
        except NameError:
            self.use_openai = False

    def kernelStarting(self, startTime):
        super().kernelStarting(startTime)

    def kernelStopping(self):
        super().kernelStopping()
        if hasattr(self, 'kernel') and hasattr(self.kernel, 'log_dir'):
            log_dir = self.kernel.log_dir
        else:
            log_dir = '.'
            
        os.makedirs(log_dir, exist_ok=True)
        df = pd.DataFrame(self.decision_log)
        if not df.empty:
            df.to_csv(os.path.join(log_dir, f"{self.name}_decision_log.csv"), index=False)

    def wakeup(self, currentTime):
        super().wakeup(currentTime)
        self.state = 'INACTIVE'

        if not self.mkt_open or not self.mkt_close:
            return
        else:
            if not getattr(self, 'trading', False):
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
            if self.mkt_closed:
                return
            self.make_llm_decision()
            self.state = 'AWAITING_WAKEUP'

    def cancelOrders(self):
        if not self.orders:
            return False
        for id, order in self.orders.items():
            self.cancelOrder(order)
        return True

    def getWakeFrequency(self):
        return pd.Timedelta(self.wake_up_freq)

    # ──────────────────────────────────────────────────────
    # Prompt Construction
    # ──────────────────────────────────────────────────────
    def get_prompt(self):
        bids = self.known_bids[self.symbol]
        asks = self.known_asks[self.symbol]

        top_bid = bids[0] if bids else (0, 0)
        top_ask = asks[0] if asks else (0, 0)

        bid, bid_sz = top_bid
        ask, ask_sz = top_ask
        last = self.last_trade.get(self.symbol, 0)
        pos = int(self.getHoldings(self.symbol) / 100)
        cash = self.holdings['CASH']
        mid = (bid + ask) // 2 if (bid and ask) else last

        # Keep state block identically frozen
        prompt  = "You are a trader. Maximize profit.\n"
        prompt += "All prices are in cents (e.g. 100000 = $1000.00).\n"
        prompt += (f"bid={bid} ({bid_sz}) ask={ask} ({ask_sz}) "
                   f"last={last} mid={mid} pos={pos:+d} cash={cash}\n")
                   
        self._last_state = {
            'bid': bid, 'ask': ask, 'last': last, 'mid': mid,
            'pos': pos, 'cash': cash
        }

        # JSON instruction
        prompt += "\n"
        prompt += "Respond with ONLY a valid JSON object, no other text, in exactly this form:\n"
        prompt += '{"exposure": "<one sentence>", "edge": "<one sentence>", "verify": "<one sentence>", "action": "BUY|SELL|HOLD", "price": <int cents>, "quantity": <int>}'

        return prompt

    # ──────────────────────────────────────────────────────
    # Binding & Field Quality
    # ──────────────────────────────────────────────────────
    def extract_conclusion_direction(self, conclusion_text):
        """Reusing base logic on 'edge' field to find direction"""
        if not conclusion_text:
            return 'AMBIGUOUS'
            
        text = conclusion_text.upper()
        clauses = re.split(r'[,.;:!?\n]|BUT|HOWEVER|ALTHOUGH|THOUGH', text)

        for clause in clauses:
            clause = clause.strip()
            if not clause: continue
            
            match = re.search(r'\b(BUY|SELL|HOLD)\b', clause)
            if match:
                action = match.group(1)
                negated = bool(re.search(r'\b(NOT|AVOID|DO NOT|DONT|DON\'T)\b', clause))
                if not negated:
                    return action
        return 'AMBIGUOUS'

    def check_verify_cites_number(self, verify_text, bid, ask, last, mid):
        """Dual-format word-boundary match on bid/ask/last/mid"""
        for cents_val in [bid, ask, last, mid]:
            if cents_val <= 0:
                continue
            
            # Cents (e.g. 100010)
            if re.search(r'\b' + str(cents_val) + r'\b', verify_text):
                return True
            
            # Dollars (e.g. 1000.10)
            dollar_str = f"{cents_val / 100:.2f}"
            if re.search(r'\b' + re.escape(dollar_str) + r'\b', verify_text):
                return True
                
            # Dollars truncated (e.g. 1000)
            dollar_int = str(cents_val // 100)
            if re.search(r'\b' + dollar_int + r'\b', verify_text):
                return True
        return False

    # ──────────────────────────────────────────────────────
    # Decision Loop
    # ──────────────────────────────────────────────────────
    def make_llm_decision(self):
        prompt = self.get_prompt()
        log_print("{} querying LLM at {}...", self.name, self.currentTime)
        self.total_decisions += 1

        decision_text = ""
        tokens_out = 0
        was_truncated = False

        # ── Step 1: Network call (NO CONSTRAINED DECODING) ──
        try:
            if self.use_openai:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=256,
                    temperature=0.1,
                )
                decision_text = response.choices[0].message.content.strip()
                if hasattr(response, 'usage') and response.usage:
                    tokens_out = response.usage.completion_tokens or 0
                else:
                    tokens_out = len(decision_text.split())
                finish = getattr(response.choices[0], 'finish_reason', None)
                if finish == 'length':
                    was_truncated = True
            else:
                import requests as req
                payload = {
                    "model": self.model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 256},
                }
                url = self.ollama_url.replace('/v1', '/api/chat')
                res = req.post(url, json=payload, timeout=60.0)
                res.raise_for_status()
                data = res.json()
                decision_text = data['message']['content'].strip()
                tokens_out = data.get('eval_count', len(decision_text.split()))
                if data.get('done_reason', 'unknown') == 'length':
                    was_truncated = True
        except Exception as e:
            self.network_errors += 1
            self.hold_fallback_count += 1
            log_print("{} Network/API error: {}", self.name, str(e))
            return

        self.tokens_out_list.append(tokens_out)
        self.total_chars_list.append(len(decision_text))
        if was_truncated:
            self.truncated_count += 1

        log_print("{} raw LLM output ({} tok, trunc={}): '{}'",
                  self.name, tokens_out, was_truncated, decision_text)

        # ── Step 2: Strict JSON Parse ──
        action = "HOLD"
        qty = 0
        price = 0
        fields = {'exposure': '', 'edge': '', 'verify': ''}
        fence_stripped = False

        try:
            text = decision_text.strip()
            if text.startswith('```'):
                text = re.sub(r'^```(?:json)?\s*', '', text)
                text = re.sub(r'\s*```$', '', text)
                fence_stripped = True
            
            if fence_stripped:
                self.fence_stripped_count += 1
                
            obj = json.loads(text)
            
            parsed_act = str(obj.get('action', '')).upper()
            if parsed_act not in ('BUY', 'SELL', 'HOLD'):
                raise ValueError(f"Invalid action: '{parsed_act}'")
            
            action = parsed_act
            
            if action in ('BUY', 'SELL'):
                if 'price' not in obj or 'quantity' not in obj:
                    raise ValueError(f"{action} missing price/quantity")
                try:
                    price = int(obj['price'])
                    qty = int(obj['quantity'])
                except (TypeError, ValueError):
                    raise ValueError(f"{action} non-integer price/qty")
                if price <= 0 or qty <= 0:
                    raise ValueError(f"{action} non-positive price={price} qty={qty}")
            else:
                self.hold_deliberate_count += 1
                price = int(obj.get('price', 0))
                qty = int(obj.get('quantity', 0))
                
            fields['exposure'] = str(obj.get('exposure', ''))
            fields['edge'] = str(obj.get('edge', ''))
            fields['verify'] = str(obj.get('verify', ''))
            
            reasoning_chars = len(fields['exposure']) + len(fields['edge']) + len(fields['verify'])
            self.reasoning_chars_list.append(reasoning_chars)

        except (ValueError, json.JSONDecodeError) as e:
            self.json_malformed_count += 1
            self.hold_fallback_count += 1
            log_print("{} JSON Malformed (fallback->HOLD): {}", self.name, str(e))
            action = "HOLD"
            qty = 0
            price = 0

        # ── Step 3: Metrics ──
        if action != "HOLD" or fields['verify']:  # Avoid metrics on pure empty fallback
            conclusion_dir = self.extract_conclusion_direction(fields['edge'])
            
            if conclusion_dir == 'AMBIGUOUS':
                self.binding_ambiguous += 1
                binding = None
            elif conclusion_dir == action:
                self.binding_match += 1
                binding = True
            else:
                self.binding_mismatch += 1
                binding = False
                
            cites_num = self.check_verify_cites_number(
                fields['verify'], 
                self._last_state['bid'], self._last_state['ask'], 
                self._last_state['last'], self._last_state['mid']
            )
            if cites_num:
                self.verify_cites_number += 1
                
            self.decision_log.append({
                'time': str(self.currentTime),
                'action': action,
                'price': price,
                'qty': qty,
                'tokens_out': tokens_out,
                'truncated': was_truncated,
                'conclusion_direction': conclusion_dir,
                'binding': binding,
                'cites_number': cites_num,
                'verify_snippet': fields['verify'][:100],
                'state_bid': self._last_state['bid'],
                'state_ask': self._last_state['ask'],
                'state_last': self._last_state['last'],
                'state_mid': self._last_state['mid'],
            })

        log_print("{} decides to {}: {} lots @ {} cents.",
                  self.name, action, qty, price)

        # ── Step 4: Execute order (byte-identical clamp to R3) ──
        if action == "HOLD":
            return

        if qty <= 0 or qty > self.q_max:
            log_print("{} Invalid quantity {}, skipping.", self.name, qty)
            return

        current_holdings = int(self.getHoldings(self.symbol) / 100)

        if action == "BUY":
            if current_holdings + qty > self.q_max:
                qty = self.q_max - current_holdings
                if qty <= 0:
                    return
            self.placeLimitOrder(self.symbol, qty * 100, True, price)
        elif action == "SELL":
            if current_holdings - qty < -self.q_max:
                qty = current_holdings + self.q_max
                if qty <= 0:
                    return
            self.placeLimitOrder(self.symbol, qty * 100, False, price)

    # ──────────────────────────────────────────────────────
    # Kernel Logging
    # ──────────────────────────────────────────────────────
    def get_log_events(self):
        events = super().get_log_events()
        
        events.append(('JSON_MALFORMED', f"{self.json_malformed_count}/{self.total_decisions}"))
        events.append(('FENCE_STRIPPED', f"{self.fence_stripped_count}/{self.total_decisions}"))
        events.append(('NETWORK_ERRORS', f"{self.network_errors}/{self.total_decisions}"))
        
        events.append(('HOLD_DELIBERATE', f"{self.hold_deliberate_count}/{self.total_decisions}"))
        events.append(('HOLD_FALLBACK', f"{self.hold_fallback_count}/{self.total_decisions}"))
        
        med_tok = int(np.median(self.tokens_out_list)) if self.tokens_out_list else 0
        mean_tok = np.mean(self.tokens_out_list) if self.tokens_out_list else 0
        events.append(('TOKENS_OUT_MEDIAN', str(med_tok)))
        events.append(('TOKENS_OUT_MEAN', str(mean_tok)))
        events.append(('TOKENS_TRUNCATED', f"{self.truncated_count}/{self.total_decisions}"))
        
        med_reas_chars = int(np.median(self.reasoning_chars_list)) if self.reasoning_chars_list else 0
        events.append(('REASONING_CHARS_MEDIAN', str(med_reas_chars)))
        
        bind_total = self.binding_match + self.binding_mismatch
        bind_rate = (self.binding_match / bind_total) * 100 if bind_total > 0 else 0
        events.append(('BINDING_RATE', f"{self.binding_match}/{bind_total} ({bind_rate:.0f}%)"))
        events.append(('BINDING_AMBIGUOUS', f"{self.binding_ambiguous}/{self.total_decisions}"))
        
        events.append(('VERIFY_CITES_NUMBER', f"{self.verify_cites_number}/{self.total_decisions}"))

        return events

    def get_log_df(self):
        df = pd.DataFrame(self.decision_log)
        if not df.empty:
            df.set_index('time', inplace=True)
        return df
