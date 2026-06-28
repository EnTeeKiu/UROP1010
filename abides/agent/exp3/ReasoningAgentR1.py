import re
from agent.exp3.ReasoningAgentBase import ReasoningAgentBase

# ============================================================
# ReasoningAgentR1 — Exp 3 Reasoning, Open CoT
# ============================================================
# Scaffold: bare "think step by step" instruction, no structure.
# Tests:    Does ANY reasoning fix Raw-arm failures?
# Gap:      Raw → R1 = adds reasoning (unstructured)
# ============================================================


class ReasoningAgentR1(ReasoningAgentBase):

    def get_scaffold(self):
        return "Think step by step before acting. Keep it brief (2-3 sentences).\n"

    def extract_conclusion_text(self, reasoning_text):
        """No scaffold tags — always use last sentence before action line."""
        sentences = re.split(r'[.!?]\s+', reasoning_text.strip())
        sentences = [s.strip() for s in sentences if s.strip()]
        if sentences:
            return sentences[-1], 'last_sentence'
        return reasoning_text, 'last_sentence'
