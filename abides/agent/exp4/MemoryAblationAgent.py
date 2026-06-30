import json
import os
import re

import pandas as pd

from agent.TradingAgent import TradingAgent
from util.util import log_print

try:
    from openai import OpenAI
except ImportError:
    import requests


class MemoryAblationAgent(TradingAgent):
    """
    Experiment 4 LLM agent.

    The prompt mode is fixed across all arms: a compact decision-only JSON
    prompt. The only treatment variable is the memory payload.
    """

    VALID_MEMORY_MODES = (
        "no_history",
        "last_5_events",
        "last_20_events",
        "rolling_session_summary",
    )
    VALID_PROMPT_MODES = (
        "decision_only_json",
        "reasoning_json",
    )
    VALID_MEMORY_SOURCES = (
        "decisions_only",
        "decisions_and_fills",
    )

    def __init__(self, id, name, type, symbol="IBM", starting_cash=100000,
                 wake_up_freq="60s", q_max=10, log_orders=False,
                 random_state=None, ollama_url="http://localhost:11434/v1",
                 model_name="gemma3:4b", memory_mode="no_history",
                 prompt_mode="decision_only_json",
                 memory_source="decisions_only"):

        super().__init__(id, name, type, starting_cash=starting_cash,
                         log_orders=log_orders, random_state=random_state)

        if memory_mode not in self.VALID_MEMORY_MODES:
            raise ValueError("Unknown memory_mode: {}".format(memory_mode))
        if prompt_mode not in self.VALID_PROMPT_MODES:
            raise ValueError("Unknown prompt_mode: {}".format(prompt_mode))
        if memory_source not in self.VALID_MEMORY_SOURCES:
            raise ValueError("Unknown memory_source: {}".format(memory_source))

        self.symbol = symbol
        self.wake_up_freq = wake_up_freq
        self.q_max = q_max
        self.ollama_url = ollama_url
        self.model_name = model_name
        self.memory_mode = memory_mode
        self.prompt_mode = prompt_mode
        self.memory_source = memory_source

        self.trading = False
        self.state = "AWAITING_WAKEUP"

        try:
            self.client = OpenAI(base_url=self.ollama_url, api_key="ollama",
                                 timeout=60.0)
            self.use_openai = True
        except NameError:
            self.use_openai = False

        self.total_decisions = 0
        self.json_malformed_count = 0
        self.network_errors = 0
        self.hold_deliberate_count = 0
        self.hold_fallback_count = 0
        self.truncated_count = 0
        self.tokens_out_list = []

        self.event_memory = []
        self.fill_memory = []
        self.decision_log = []

    def kernelStarting(self, startTime):
        super().kernelStarting(startTime)

    def kernelStopping(self):
        super().kernelStopping()

        holdings_shares = int(self.getHoldings(self.symbol))
        holdings_lots = holdings_shares / 100.0
        cash = self.holdings["CASH"]
        final_price = self.last_trade.get(self.symbol, 0)
        surplus = cash - self.starting_cash + (holdings_shares * final_price)

        self.logEvent("FINAL_VALUATION", surplus, True)
        self.logEvent("EXP4_MEMORY_MODE", self.memory_mode, True)
        self.logEvent("EXP4_PROMPT_MODE", self.prompt_mode, True)
        self.logEvent("EXP4_MEMORY_SOURCE", self.memory_source, True)
        self.logEvent("JSON_MALFORMED",
                      "{}/{}".format(self.json_malformed_count,
                                      self.total_decisions), True)
        self.logEvent("NETWORK_ERRORS",
                      "{}/{}".format(self.network_errors,
                                      self.total_decisions), True)
        self.logEvent("HOLD_DELIBERATE",
                      "{}/{}".format(self.hold_deliberate_count,
                                      self.total_decisions), True)
        self.logEvent("HOLD_FALLBACK",
                      "{}/{}".format(self.hold_fallback_count,
                                      self.total_decisions), True)

        if self.tokens_out_list:
            sorted_tokens = sorted(self.tokens_out_list)
            median_tokens = sorted_tokens[len(sorted_tokens) // 2]
            mean_tokens = sum(self.tokens_out_list) / len(self.tokens_out_list)
        else:
            median_tokens = 0
            mean_tokens = 0.0

        self.logEvent("TOKENS_OUT_MEDIAN", median_tokens, True)
        self.logEvent("TOKENS_OUT_MEAN", "{:.1f}".format(mean_tokens), True)
        self.logEvent("TOKENS_TRUNCATED",
                      "{}/{}".format(self.truncated_count,
                                      self.total_decisions), True)

        if hasattr(self, "kernel") and hasattr(self.kernel, "log_dir"):
            log_dir = self.kernel.log_dir
            if not os.path.isabs(log_dir) and not log_dir.startswith("log"):
                log_dir = os.path.join("log", log_dir)
        else:
            log_dir = "."
        os.makedirs(log_dir, exist_ok=True)

        df = pd.DataFrame(self.decision_log)
        if not df.empty:
            path = os.path.join(log_dir, "{}_decision_log.csv".format(self.name))
            df.to_csv(path, index=False)

        log_print("{} final report. Memory mode {}, holdings {}, end cash {}, "
                  "start cash {}, final price {}, surplus {}",
                  self.name, self.memory_mode, holdings_lots, cash,
                  self.starting_cash, final_price, surplus)

    def wakeup(self, currentTime):
        super().wakeup(currentTime)
        self.state = "INACTIVE"

        if not self.mkt_open or not self.mkt_close:
            return

        if not self.trading:
            self.trading = True
            log_print("{} is ready to start trading now.", self.name)

        if self.mkt_closed:
            return

        self.setWakeup(currentTime + pd.Timedelta(self.wake_up_freq))
        self.cancelOrders()
        self.getCurrentSpread(self.symbol)
        self.state = "AWAITING_SPREAD"

    def receiveMessage(self, currentTime, msg):
        super().receiveMessage(currentTime, msg)

        if self.state == "AWAITING_SPREAD" and msg.body["msg"] == "QUERY_SPREAD":
            if self.mkt_closed:
                return
            self.make_llm_decision()
            self.state = "AWAITING_WAKEUP"

    def cancelOrders(self):
        if not self.orders:
            return False
        for id, order in self.orders.items():
            self.cancelOrder(order)
        return True

    def getWakeFrequency(self):
        return pd.Timedelta(self.wake_up_freq)

    def snapshot_state(self):
        bids = self.known_bids[self.symbol]
        asks = self.known_asks[self.symbol]

        top_bid = bids[0] if bids else (0, 0)
        top_ask = asks[0] if asks else (0, 0)
        bid, bid_size = top_bid
        ask, ask_size = top_ask
        last = self.last_trade.get(self.symbol, 0)
        mid = (bid + ask) // 2 if bid and ask else last
        spread = ask - bid if bid and ask else 0

        return {
            "time": str(self.currentTime),
            "bid": int(bid),
            "bid_size": int(bid_size),
            "ask": int(ask),
            "ask_size": int(ask_size),
            "last": int(last),
            "mid": int(mid),
            "spread": int(spread),
            "position_lots": int(self.getHoldings(self.symbol) / 100),
            "cash": int(self.holdings["CASH"]),
        }

    def build_session_summary(self):
        if not self.event_memory:
            return {
                "events_seen": 0,
                "note": "No prior events.",
            }

        mids = [event["mid"] for event in self.event_memory if event["mid"] > 0]
        spreads = [event["spread"] for event in self.event_memory
                   if event["spread"] > 0]
        action_counts = {"BUY": 0, "SELL": 0, "HOLD": 0}
        for event in self.event_memory:
            action = event.get("action", "HOLD")
            if action in action_counts:
                action_counts[action] += 1

        last_event = self.event_memory[-1]
        summary = {
            "events_seen": len(self.event_memory),
            "action_counts": action_counts,
            "last_action": last_event.get("action", "HOLD"),
            "last_price": last_event.get("price", 0),
            "last_quantity": last_event.get("quantity", 0),
            "last_mid": last_event.get("mid", 0),
            "last_position_lots": last_event.get("position_lots", 0),
        }

        if mids:
            summary.update({
                "first_mid": mids[0],
                "min_mid": min(mids),
                "max_mid": max(mids),
                "mid_change": mids[-1] - mids[0],
            })
        if spreads:
            summary["avg_spread"] = int(round(sum(spreads) / len(spreads)))

        if self.memory_source == "decisions_and_fills":
            fills = self.fill_memory
            buy_fills = [fill for fill in fills if fill["action"] == "BUY"]
            sell_fills = [fill for fill in fills if fill["action"] == "SELL"]
            total_qty = sum(fill["quantity"] for fill in fills)
            if total_qty:
                avg_fill_price = int(round(
                    sum(fill["price"] * fill["quantity"] for fill in fills) / total_qty
                ))
            else:
                avg_fill_price = 0
            summary.update({
                "fills_seen": len(fills),
                "buy_fills": len(buy_fills),
                "sell_fills": len(sell_fills),
                "filled_quantity": total_qty,
                "avg_fill_price": avg_fill_price,
            })

        return summary

    def build_memory_payload(self):
        fills = []
        if self.memory_source == "decisions_and_fills":
            if self.memory_mode == "last_5_events":
                fills = self.fill_memory[-5:]
            elif self.memory_mode == "last_20_events":
                fills = self.fill_memory[-20:]
            elif self.memory_mode == "rolling_session_summary":
                fills = []

        if self.memory_mode == "no_history":
            return {
                "mode": self.memory_mode,
                "source": self.memory_source,
                "events": [],
                "fills": [],
                "summary": None,
            }

        if self.memory_mode == "last_5_events":
            events = self.event_memory[-5:]
            return {
                "mode": self.memory_mode,
                "source": self.memory_source,
                "events": events,
                "fills": fills,
                "summary": None,
            }

        if self.memory_mode == "last_20_events":
            events = self.event_memory[-20:]
            return {
                "mode": self.memory_mode,
                "source": self.memory_source,
                "events": events,
                "fills": fills,
                "summary": None,
            }

        return {
            "mode": self.memory_mode,
            "source": self.memory_source,
            "events": [],
            "fills": fills,
            "summary": self.build_session_summary(),
        }

    def get_system_prompt(self):
        base = (
            "You are a trading agent in an ABIDES continuous double auction. "
            "Use the current market state and the provided memory payload to "
            "maximize profit. Prices are in cents. You may hold at most 10 lots "
            "long or 10 lots short. "
        )
        if self.prompt_mode == "reasoning_json":
            return (
                base +
                "Reason briefly from the state and memory, then return only a "
                "valid JSON object with exactly these keys: "
                "{\"rationale\":\"<one short sentence>\","
                "\"action\":\"BUY|SELL|HOLD\",\"price\":<int cents>,"
                "\"quantity\":<int lots>}. For HOLD, use price=0 and quantity=0."
            )
        return (
            base +
            "Do not explain, justify, reason step by step, or include any "
            "reasoning fields. Return only a valid JSON object with exactly "
            "these keys: {\"action\":\"BUY|SELL|HOLD\",\"price\":<int cents>,"
            "\"quantity\":<int lots>}. For HOLD, use price=0 and quantity=0."
        )

    def get_user_payload(self, current_state, memory_payload):
        payload = {
            "experiment": "exp4_memory_ablation",
            "fixed_prompt_mode": self.prompt_mode,
            "current_state": current_state,
            "memory": memory_payload,
        }
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)

    def parse_decision(self, decision_text):
        text = decision_text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)

        obj = json.loads(text)
        if self.prompt_mode == "reasoning_json":
            expected_keys = {"rationale", "action", "price", "quantity"}
        else:
            expected_keys = {"action", "price", "quantity"}
        extra_keys = set(obj.keys()) - expected_keys
        missing_keys = expected_keys - set(obj.keys())
        if extra_keys or missing_keys:
            raise ValueError("Expected keys {}, got keys {}".format(
                sorted(expected_keys), sorted(obj.keys())))

        action = str(obj.get("action", "HOLD")).upper()
        if action not in ("BUY", "SELL", "HOLD"):
            raise ValueError("Invalid action: {}".format(action))

        if action == "HOLD":
            price = int(obj.get("price", 0))
            quantity = int(obj.get("quantity", 0))
            if price != 0 or quantity != 0:
                raise ValueError("HOLD must use price=0 and quantity=0")
            return action, 0, 0, str(obj.get("rationale", ""))

        price = int(obj.get("price", 0))
        quantity = int(obj.get("quantity", 0))
        if price <= 0 or quantity <= 0:
            raise ValueError("Non-positive price or quantity")

        return action, price, quantity, str(obj.get("rationale", ""))

    def query_llm(self, system_prompt, user_payload):
        if self.use_openai:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_payload},
                ],
                response_format={"type": "json_object"},
                max_tokens=160 if self.prompt_mode == "reasoning_json" else 64,
                temperature=0.1,
            )
            decision_text = response.choices[0].message.content.strip()
            tokens_out = len(decision_text.split())
            if hasattr(response, "usage") and response.usage:
                tokens_out = response.usage.completion_tokens or tokens_out
            finish_reason = getattr(response.choices[0], "finish_reason", None)
            return decision_text, tokens_out, finish_reason == "length"

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_payload},
            ],
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 160 if self.prompt_mode == "reasoning_json" else 64,
            },
        }
        url = self.ollama_url.replace("/v1", "/api/chat")
        res = requests.post(url, json=payload, timeout=60)
        res.raise_for_status()
        data = res.json()
        decision_text = data["message"]["content"].strip()
        tokens_out = data.get("eval_count", len(decision_text.split()))
        return decision_text, tokens_out, data.get("done_reason") == "length"

    def remember_event(self, state, action, price, quantity):
        event = {
            "time": state["time"],
            "bid": state["bid"],
            "ask": state["ask"],
            "last": state["last"],
            "mid": state["mid"],
            "spread": state["spread"],
            "position_lots": state["position_lots"],
            "action": action,
            "price": int(price),
            "quantity": int(quantity),
        }
        self.event_memory.append(event)
        if len(self.event_memory) > 200:
            self.event_memory.pop(0)

    def orderExecuted(self, order):
        super().orderExecuted(order)
        action = "BUY" if bool(order.is_buy_order) else "SELL"
        fill = {
            "time": str(self.currentTime),
            "action": action,
            "price": int(order.fill_price),
            "quantity": int(order.quantity),
            "order_id": int(order.order_id),
            "position_lots_after": int(self.getHoldings(self.symbol) / 100),
        }
        self.fill_memory.append(fill)
        if len(self.fill_memory) > 200:
            self.fill_memory.pop(0)

    def make_llm_decision(self):
        current_state = self.snapshot_state()
        memory_payload = self.build_memory_payload()
        system_prompt = self.get_system_prompt()
        user_payload = self.get_user_payload(current_state, memory_payload)

        log_print("{} querying LLM at {} with memory_mode={}...",
                  self.name, self.currentTime, self.memory_mode)
        self.total_decisions += 1

        decision_text = ""
        tokens_out = 0
        was_truncated = False
        action = "HOLD"
        price = 0
        quantity = 0
        rationale = ""
        error_note = ""

        try:
            decision_text, tokens_out, was_truncated = self.query_llm(
                system_prompt, user_payload)
            action, price, quantity, rationale = self.parse_decision(decision_text)
            if action == "HOLD":
                self.hold_deliberate_count += 1
        except Exception as e:
            if decision_text:
                self.json_malformed_count += 1
                error_note = "JSON/validation failure: {}".format(str(e))
                log_print("{} JSON/validation failure: {}", self.name, str(e))
            else:
                self.network_errors += 1
                error_note = "Network/API failure: {}".format(str(e))
                log_print("{} Network/API error: {}", self.name, str(e))
            self.hold_fallback_count += 1
            action = "HOLD"
            price = 0
            quantity = 0

        if tokens_out:
            self.tokens_out_list.append(tokens_out)
        if was_truncated:
            self.truncated_count += 1

        memory_chars = len(json.dumps(memory_payload, separators=(",", ":")))
        self.decision_log.append({
            "time": current_state["time"],
            "memory_mode": self.memory_mode,
            "prompt_mode": self.prompt_mode,
            "memory_source": self.memory_source,
            "memory_chars": memory_chars,
            "memory_events": len(memory_payload["events"]),
            "memory_fills": len(memory_payload["fills"]),
            "action": action,
            "price": price,
            "quantity": quantity,
            "rationale": rationale[:240],
            "error_note": error_note[:240],
            "tokens_out": tokens_out,
            "truncated": was_truncated,
            "raw_output": decision_text[:500],
            "state_bid": current_state["bid"],
            "state_ask": current_state["ask"],
            "state_last": current_state["last"],
            "state_mid": current_state["mid"],
            "state_position_lots": current_state["position_lots"],
        })

        self.remember_event(current_state, action, price, quantity)

        log_print("{} decides to {}: {} lots @ {} cents. Memory chars: {}",
                  self.name, action, quantity, price, memory_chars)

        if action == "HOLD":
            return

        if quantity <= 0 or quantity > self.q_max:
            log_print("{} Invalid quantity {}, skipping.", self.name, quantity)
            return

        current_holdings = int(self.getHoldings(self.symbol) / 100)

        if action == "BUY":
            if current_holdings + quantity > self.q_max:
                quantity = self.q_max - current_holdings
                if quantity <= 0:
                    return
            self.placeLimitOrder(self.symbol, quantity * 100, True, price)
        elif action == "SELL":
            if current_holdings - quantity < -self.q_max:
                quantity = current_holdings + self.q_max
                if quantity <= 0:
                    return
            self.placeLimitOrder(self.symbol, quantity * 100, False, price)
