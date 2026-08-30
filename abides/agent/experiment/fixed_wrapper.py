from agent.TradingAgent import TradingAgent
from util.util import log_print
import pandas as pd


class FixedWrapperAgent(TradingAgent):
    """
    FixedWrapperAgent controls all execution mechanics for treatment agents.
    Both LLM and Coin control arms share this identical wrapper class.
    The injectable `policy` controls ONLY the side choice ("BUY" or "SELL").
    """

    def __init__(self, id, name, type, symbol='JPM', starting_cash=10000000,
                 policy=None, wake_interval_s=60, lot_size=100, q_max=10,
                 r_bar=100000, warmup_end=None, log_orders=True, random_state=None):
        super().__init__(id, name, type, starting_cash=starting_cash,
                         log_orders=log_orders, random_state=random_state)
        self.symbol = symbol
        self.policy = policy
        self.wake_interval_s = wake_interval_s
        self.lot_size = lot_size
        self.q_max = q_max
        self.r_bar = r_bar
        self.warmup_end = warmup_end

        self.trading = False
        self.state = 'AWAITING_WAKEUP'

    def getWakeFrequency(self):
        return pd.Timedelta(seconds=self.wake_interval_s)

    def wakeup(self, currentTime):
        super().wakeup(currentTime)
        self.state = 'INACTIVE'

        if not self.mkt_open or not self.mkt_close:
            return
        if not self.trading:
            self.trading = True
            log_print("{} is ready to start trading.", self.name)

        if self.mkt_closed:
            return

        # Schedule next wakeup
        delta_time = pd.Timedelta(seconds=self.wake_interval_s)
        self.setWakeup(currentTime + delta_time)

        # Skip during warmup period
        if self.warmup_end is not None and currentTime < self.warmup_end:
            return

        # Cancel all open resting orders
        self.cancelOrders()

        # Query spread to obtain current L1 order book
        self.getCurrentSpread(self.symbol)
        self.state = 'AWAITING_SPREAD'

    def receiveMessage(self, currentTime, msg):
        super().receiveMessage(currentTime, msg)

        if self.state == 'AWAITING_SPREAD' and msg.body['msg'] == 'QUERY_SPREAD':
            if self.mkt_closed:
                return
            self.execute_decision_cycle()
            self.state = 'AWAITING_WAKEUP'

    def cancelOrders(self):
        if not self.orders:
            return False
        for id_, order in list(self.orders.items()):
            self.cancelOrder(order)
        return True

    def execute_decision_cycle(self):
        bids = self.known_bids.get(self.symbol, [])
        asks = self.known_asks.get(self.symbol, [])

        bid, ask, midpoint = self.getKnownBidAskMidpoint(self.symbol)
        bid_sz = bids[0][1] if bids else 0
        ask_sz = asks[0][1] if asks else 0
        last = self.last_trade.get(self.symbol, self.r_bar)

        holdings = int(self.getHoldings(self.symbol) / self.lot_size)
        cash = self.holdings['CASH']
        mid_or_last = midpoint if midpoint is not None else last
        pnl_marked = cash - self.starting_cash + (holdings * self.lot_size * mid_or_last)

        time_elapsed_s = int((self.currentTime - self.mkt_open).total_seconds()) if self.mkt_open else 0

        # Snapshot state S_t for policy
        state_snapshot = {
            "best_bid": bid if bid is not None else self.r_bar,
            "best_bid_sz": bid_sz,
            "best_ask": ask if ask is not None else self.r_bar,
            "best_ask_sz": ask_sz,
            "midpoint": mid_or_last,
            "last_trade": last,
            "inventory": holdings,
            "cash": cash,
            "pnl_marked": pnl_marked,
            "time_elapsed_s": time_elapsed_s
        }

        # Query side choice from injectable policy
        chosen_side = self.policy.choose_side(state_snapshot)

        # Enforce position limits
        side = chosen_side
        if holdings >= self.q_max:
            side = "SELL"
            log_print("{} position limit long (+{}), overriding side to SELL.", self.name, holdings)
        elif holdings <= -self.q_max:
            side = "BUY"
            log_print("{} position limit short ({}), overriding side to BUY.", self.name, holdings)

        # Determine price according to placement rule (at_touch: join best bid for BUY, join best ask for SELL)
        if side == "BUY":
            limit_price = bid if bid is not None else self.r_bar
            is_buy = True
        else:
            limit_price = ask if ask is not None else self.r_bar
            is_buy = False

        # Submit limit order (lot_size shares)
        self.placeLimitOrder(self.symbol, self.lot_size, is_buy, limit_price)

        log_print("{} executed wrapper cycle: policy_side={}, final_side={}, price={}, qty={}",
                  self.name, chosen_side, side, limit_price, self.lot_size)

        log_payload = {
            "time": str(self.currentTime),
            "policy_side": chosen_side,
            "final_side": side,
            "limit_price": limit_price,
            "snapshot_best_bid": bid,
            "snapshot_best_ask": ask,
            "quantity": self.lot_size,
            "inventory": holdings,
            "cash": cash
        }
        
        # Merge any LLM diagnostics attached to state by LLMPolicy
        if 'llm_raw_output' in state_snapshot:
            log_payload['llm_raw_output'] = state_snapshot['llm_raw_output']
            log_payload['llm_valid'] = state_snapshot['llm_valid']
            log_payload['llm_fallback_used'] = state_snapshot['llm_fallback_used']
            log_payload['llm_latency_ms'] = state_snapshot['llm_latency_ms']
            log_payload['llm_timeout'] = state_snapshot['llm_timeout']
            log_payload['llm_tokens_in'] = state_snapshot['llm_tokens_in']
            log_payload['llm_tokens_out'] = state_snapshot['llm_tokens_out']
            log_payload['llm_prompt'] = state_snapshot['llm_prompt']

        self.logEvent("WRAPPER_DECISION", log_payload)
