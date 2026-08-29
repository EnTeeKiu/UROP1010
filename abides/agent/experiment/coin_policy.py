import numpy as np


class CoinPolicy:
    """
    Fair coin-flip policy for side selection.
    Chooses "BUY" with probability p_buy (default 0.5), else "SELL".
    Does not use state; interface takes state to match policy protocol.
    """

    def __init__(self, rng: np.random.RandomState, p_buy: float = 0.5):
        self.rng = rng
        self.p_buy = p_buy

    def choose_side(self, state: dict) -> str:
        return "BUY" if self.rng.random() < self.p_buy else "SELL"
