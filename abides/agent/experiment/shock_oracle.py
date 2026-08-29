from util.oracle.SparseMeanRevertingOracle import SparseMeanRevertingOracle
from util.util import log_print
import pandas as pd


class ShockOracle(SparseMeanRevertingOracle):
    """
    Extends SparseMeanRevertingOracle to inject a deterministic, one-time jump 
    in both the fundamental value and the mean-reversion target (r_bar) at a specific time.
    """

    def __init__(self, mkt_open, mkt_close, symbols, shock_time: pd.Timestamp, shock_magnitude: int):
        super().__init__(mkt_open, mkt_close, symbols)
        self.shock_time = shock_time
        self.shock_magnitude = shock_magnitude
        
        # Track whether shock has been applied for each symbol
        self.shock_applied = {symbol: False for symbol in symbols}
        
        log_print("ShockOracle initialized. Shock scheduled at {} with magnitude {}", 
                  self.shock_time, self.shock_magnitude)

    def advance_fundamental_value_series(self, currentTime, symbol):
        # Check if we are crossing the shock boundary for the first time
        if not self.shock_applied[symbol] and currentTime >= self.shock_time:
            # 1. Advance the series to EXACTLY the shock_time using normal mechanics
            super().advance_fundamental_value_series(self.shock_time, symbol)
            
            # 2. Extract the value precisely at shock_time
            pt, pv = self.r[symbol]
            
            # 3. Apply the deterministic jump to the value
            new_pv = pv + self.shock_magnitude
            
            # 4. Shift the mean-reversion target so the OU process anchors to the new level
            self.symbols[symbol]['r_bar'] += self.shock_magnitude
            
            # 5. Overwrite the cached state to reflect the jump
            self.r[symbol] = (self.shock_time, new_pv)
            
            # 6. Log the exact jump moment to the fundamental log
            self.f_log[symbol].append({
                'FundamentalTime': self.shock_time, 
                'FundamentalValue': new_pv
            })
            
            self.shock_applied[symbol] = True
            log_print("ShockOracle applied {} cents shock to {} at {}. New fundamental: {}, New r_bar: {}",
                      self.shock_magnitude, symbol, self.shock_time, new_pv, self.symbols[symbol]['r_bar'])
            
        # 7. Proceed with normal advancement (either pre-shock, or post-shock from the new anchored level)
        return super().advance_fundamental_value_series(currentTime, symbol)
