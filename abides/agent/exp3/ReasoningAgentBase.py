import re
import os
import pandas as pd
from agent.TradingAgent import TradingAgent
from util.util import log_print

try:
    from openai import OpenAI
except ImportError:
    import requests

# ============================================================
# ReasoningAgentBase — Shared logic for Exp 3 Reasoning arms
# ============================================================
# Subclasses override:
#   get_scaffold()               → the reasoning instruction block
#   extract_conclusion_text()    → the section to classify for binding
#
# Frozen parameters (equal across R1/R2/R3):
#   max_tokens   = 256 (equal cap; tokens_out logged per decision)
#   temperature  = 0.1
#   prompt state = identical to Minimal-Raw (bid/ask/last/mid/pos/cash)
#   action grammar = identical to Minimal-Raw
#   parser       = bottom-up scan for last valid action line
#
# Metrics logged at kernel stop:
#   PARSE_FAILURES, NETWORK_ERRORS, HOLD_DELIBERATE, HOLD_FALLBACK
#   TOKENS_OUT_MEDIAN, TOKENS_OUT_MEAN, TOKENS_TRUNCATED
#   BINDING_RATE, BINDING_AMBIGUOUS
#   CONCLUSION_FROM_TAG, CONCLUSION_FROM_FALLBACK
# ============================================================


class ReasoningAgentBase(TradingAgent):

    def __init__(self, id, name, type, symbol='IBM', starting_cash=100000,
                 wake_up_freq='60s', q_max=10, log_orders=False, random_state=None,
                 ollama_url='http://localhost:11434/v1', model_name='gemma3:4b'):

        super().__init__(id, name, type, starting_cash=starting_cash,
                         log_orders=log_orders, random_state=random_state)

        self.symbol = symbol
        self.wake_up_freq = wake_up_freq
        self.q_max = q_max
        self.ollama_url = ollama_url
        self.model_name = model_name

        self.trading = False
        self.state = 'AWAITING_WAKEUP'

        try:
            self.client = OpenAI(base_url=self.ollama_url, api_key='ollama', timeout=60.0)
            self.use_openai = True
        except NameError:
            self.use_openai = False

        # ── Decision counters ──
        self.total_decisions = 0
        self.parse_failures = 0
        self.network_errors = 0
        self.hold_deliberate_count = 0
        self.hold_fallback_count = 0

        # ── Token tracking ──
        self.tokens_out_list = []
        self.truncated_count = 0

        # ── Binding rate ──
        self.binding_match = 0
        self.binding_mismatch = 0
        self.binding_ambiguous = 0

        # ── Conclusion source (patch #3) ──
        self.conclusion_from_tag = 0
        self.conclusion_from_fallback = 0

        # ── Per-decision log for manual inspection ──
        self.decision_log = []

    # ──────────────────────────────────────────────────────
    # Subclass hooks
    # ──────────────────────────────────────────────────────

    def get_scaffold(self):
        """Override: return the reasoning scaffold string."""
        raise NotImplementedError

    def extract_conclusion_text(self, reasoning_text):
        """
        Override: extract the conclusion section for binding classification.
        Returns (conclusion_text: str, source: str).
        source is 'decision_tag', 'last_sentence_fallback', or 'last_sentence'.
        """
        raise NotImplementedError

    # ──────────────────────────────────────────────────────
    # Kernel lifecycle
    # ──────────────────────────────────────────────────────

    def kernelStarting(self, startTime):
        super().kernelStarting(startTime)

    def kernelStopping(self):
        super().kernelStopping()

        H = int(round(self.getHoldings(self.symbol), -2) / 100)
        cash = self.holdings['CASH']
        final_price = self.last_trade.get(self.symbol, 0)
        surplus = cash - self.starting_cash + (H * 100 * final_price)

        self.logEvent('FINAL_VALUATION', surplus, True)
        self.logEvent('PARSE_FAILURES',
                      f"{self.parse_failures}/{self.total_decisions}", True)
        self.logEvent('NETWORK_ERRORS',
                      f"{self.network_errors}/{self.total_decisions}", True)
        self.logEvent('HOLD_DELIBERATE',
                      f"{self.hold_deliberate_count}/{self.total_decisions}", True)
        self.logEvent('HOLD_FALLBACK',
                      f"{self.hold_fallback_count}/{self.total_decisions}", True)

        # Tokens
        if self.tokens_out_list:
            sorted_tok = sorted(self.tokens_out_list)
            median_tok = sorted_tok[len(sorted_tok) // 2]
            mean_tok = sum(self.tokens_out_list) / len(self.tokens_out_list)
        else:
            median_tok = 0
            mean_tok = 0.0
        self.logEvent('TOKENS_OUT_MEDIAN', median_tok, True)
        self.logEvent('TOKENS_OUT_MEAN', f"{mean_tok:.1f}", True)
        self.logEvent('TOKENS_TRUNCATED',
                      f"{self.truncated_count}/{self.total_decisions}", True)

        # Binding
        total_classifiable = self.binding_match + self.binding_mismatch
        if total_classifiable > 0:
            rate_str = (f"{self.binding_match}/{total_classifiable} "
                        f"({100 * self.binding_match / total_classifiable:.0f}%)")
        else:
            rate_str = "0/0 (N/A)"
        self.logEvent('BINDING_RATE', rate_str, True)
        self.logEvent('BINDING_AMBIGUOUS',
                      f"{self.binding_ambiguous}/{self.total_decisions}", True)

        # Conclusion source
        self.logEvent('CONCLUSION_FROM_TAG',
                      f"{self.conclusion_from_tag}/{self.total_decisions}", True)
        self.logEvent('CONCLUSION_FROM_FALLBACK',
                      f"{self.conclusion_from_fallback}/{self.total_decisions}", True)

        log_print("{} final report. Holdings {}, end cash {}, start cash {}, "
                  "final price {}, surplus {}",
                  self.name, H, cash, self.starting_cash, final_price, surplus)
        log_print("{} Parse Failures: {}/{} | Network Errors: {}/{}",
                  self.name, self.parse_failures, self.total_decisions,
                  self.network_errors, self.total_decisions)
        log_print("{} HOLD — deliberate: {}/{} | fallback: {}/{}",
                  self.name,
                  self.hold_deliberate_count, self.total_decisions,
                  self.hold_fallback_count, self.total_decisions)
        
        if hasattr(self, 'kernel') and hasattr(self.kernel, 'log_dir'):
            log_dir = self.kernel.log_dir
        else:
            log_dir = '.'
            
        os.makedirs(log_dir, exist_ok=True)
        df = pd.DataFrame(self.decision_log)
        if not df.empty:
            df.to_csv(os.path.join(log_dir, f"{self.name}_decision_log.csv"), index=False)

        log_print("{} Binding: {}/{} match, {} ambiguous | Tokens median: {}",
                  self.name, self.binding_match, total_classifiable,
                  self.binding_ambiguous, median_tok)

    # ──────────────────────────────────────────────────────
    # Message loop (identical to Minimal-Raw)
    # ──────────────────────────────────────────────────────

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

        self.setWakeup(currentTime + pd.Timedelta(self.wake_up_freq))
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
    # Prompt construction
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

        # State block — identical to Minimal-Raw
        prompt  = "You are a trader. Maximize profit.\n"
        prompt += "All prices are in cents (e.g. 100000 = $1000.00).\n"
        prompt += (f"bid={bid} ({bid_sz}) ask={ask} ({ask_sz}) "
                   f"last={last} mid={mid} pos={pos:+d} cash={cash}\n")
                   
        self._last_state = {
            'bid': bid, 'ask': ask, 'last': last, 'mid': mid,
            'pos': pos, 'cash': cash
        }

        # Scaffold — injected by subclass
        prompt += "\n"
        prompt += self.get_scaffold()
        prompt += "\n"

        # Action grammar — identical to Minimal-Raw
        prompt += "Put your final answer on the LAST LINE ONLY, exactly as:\n"
        prompt += "BUY <price_cents> <qty> | SELL <price_cents> <qty> | HOLD"

        return prompt

    # ──────────────────────────────────────────────────────
    # Binding: conclusion-direction extraction
    # ──────────────────────────────────────────────────────

    def extract_conclusion_direction(self, conclusion_text):
        """
        Position-order scan with clause-boundary negation guard.
        Returns 'BUY', 'SELL', 'HOLD', or 'AMBIGUOUS'.

        Patch #1: scan by text position, not hardcoded list order.
        Patch #2: cut prefix at nearest clause boundary, not fixed chars.
        """
        text = conclusion_text.upper()
        negation_words = [
            'NOT ', 'NO ', "DON'T ", "AVOID ", "INSTEAD OF ",
            "RATHER THAN ", "SHOULDN'T ", "WON'T ",
        ]

        # Find all occurrences, sorted by position in text
        positions = []
        for action in ['BUY', 'SELL', 'HOLD']:
            pos = text.find(action)
            if pos >= 0:
                positions.append((pos, action))
        positions.sort(key=lambda x: x[0])

        # Walk left-to-right, return first non-negated
        for pos, action in positions:
            prefix_start = max(0, pos - 30)
            raw_prefix = text[prefix_start:pos]

            # Cut at last clause boundary (patch #2)
            for boundary in ['. ', '; ', ', ']:
                bnd_pos = raw_prefix.rfind(boundary)
                if bnd_pos >= 0:
                    raw_prefix = raw_prefix[bnd_pos + len(boundary):]
                    break

            negated = any(neg in raw_prefix for neg in negation_words)
            if not negated:
                return action

        return 'AMBIGUOUS'

    # ──────────────────────────────────────────────────────
    # Core decision loop
    # ──────────────────────────────────────────────────────

    def make_llm_decision(self):
        prompt = self.get_prompt()
        log_print("{} querying LLM at {}...", self.name, self.currentTime)
        self.total_decisions += 1

        decision_text = ""
        tokens_out = 0
        was_truncated = False

        # ── Step 1: Network call ──
        try:
            if self.use_openai:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=256,
                    temperature=0.1,
                )
                decision_text = response.choices[0].message.content.strip()
                # Token tracking
                if hasattr(response, 'usage') and response.usage:
                    tokens_out = response.usage.completion_tokens or 0
                else:
                    tokens_out = len(decision_text.split())
                # Truncation check via finish_reason
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
                res = req.post(url, json=payload, timeout=60)
                res.raise_for_status()
                data = res.json()
                decision_text = data['message']['content'].strip()
                tokens_out = data.get('eval_count', len(decision_text.split()))
                done_reason = data.get('done_reason', 'unknown')
                if done_reason == 'length':
                    was_truncated = True
        except Exception as e:
            self.network_errors += 1
            self.hold_fallback_count += 1
            log_print("{} Network/API error: {}", self.name, str(e))
            return

        self.tokens_out_list.append(tokens_out)
        if was_truncated:
            self.truncated_count += 1

        log_print("{} raw LLM output ({} tok, trunc={}): '{}'",
                  self.name, tokens_out, was_truncated, decision_text)

        # ── Step 2: Parse action (bottom-up, last valid line) ──
        action = "HOLD"
        qty = 0
        price = 0
        reasoning_text = ""

        try:
            lines = decision_text.strip().split('\n')
            action_match = None
            action_line_idx = None

            for i in range(len(lines) - 1, -1, -1):
                m = re.search(
                    r'(BUY|SELL|HOLD)(?:\s+(\d+)\s+(\d+))?',
                    lines[i].upper(),
                )
                if m:
                    action_match = m
                    action_line_idx = i
                    break

            if action_match:
                action = action_match.group(1)
                if action in ("BUY", "SELL"):
                    if action_match.group(2) and action_match.group(3):
                        price = int(action_match.group(2))
                        qty = int(action_match.group(3))
                    else:
                        raise ValueError("Missing price/qty for BUY/SELL")

                # Everything above the action line is reasoning
                if action_line_idx is not None and action_line_idx > 0:
                    reasoning_text = '\n'.join(lines[:action_line_idx])

                if action == "HOLD":
                    self.hold_deliberate_count += 1
            else:
                raise ValueError(
                    f"No valid action line found. Raw: '{decision_text}'")

        except ValueError as e:
            self.parse_failures += 1
            self.hold_fallback_count += 1
            log_print("{} Parse failure (fallback->HOLD): {}", self.name, str(e))
            action = "HOLD"
            qty = 0
            price = 0

        # ── Step 3: Binding rate measurement ──
        if reasoning_text:
            conclusion_text, conclusion_source = \
                self.extract_conclusion_text(reasoning_text)

            if conclusion_source == 'decision_tag':
                self.conclusion_from_tag += 1
            else:
                self.conclusion_from_fallback += 1

            if conclusion_text:
                conclusion_dir = self.extract_conclusion_direction(conclusion_text)
            else:
                conclusion_dir = 'AMBIGUOUS'

            if conclusion_dir == 'AMBIGUOUS':
                self.binding_ambiguous += 1
                binding = None
            elif conclusion_dir == action:
                self.binding_match += 1
                binding = True
            else:
                self.binding_mismatch += 1
                binding = False

            log_print(
                "{} Conclusion[{}]: '{}' -> dir={} | act={} | bind={}",
                self.name, conclusion_source,
                (conclusion_text[:80] if conclusion_text else ''),
                conclusion_dir, action, binding,
            )

            self.decision_log.append({
                'time': str(self.currentTime),
                'action': action,
                'price': price,
                'qty': qty,
                'tokens_out': tokens_out,
                'truncated': was_truncated,
                'conclusion_source': conclusion_source,
                'conclusion_direction': conclusion_dir,
                'binding': binding,
                'reasoning_snippet': reasoning_text[:300],
                'state_bid': getattr(self, '_last_state', {}).get('bid', 0),
                'state_ask': getattr(self, '_last_state', {}).get('ask', 0),
                'state_last': getattr(self, '_last_state', {}).get('last', 0),
                'state_mid': getattr(self, '_last_state', {}).get('mid', 0),
            })

        log_print("{} decides to {}: {} lots @ {} cents.",
                  self.name, action, qty, price)

        # ── Step 4: Execute order ──
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
