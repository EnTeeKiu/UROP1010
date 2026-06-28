import re
from agent.exp3.ReasoningAgentBase import ReasoningAgentBase

# ============================================================
# ReasoningAgentR3 — Exp 3 Reasoning, Structured + [VERIFY]
# ============================================================
# Scaffold: [EXPOSURE] / [EDGE] / [VERIFY] / [DECISION]
# Tests:    Does citing specific state evidence improve quality?
# Gap:      R2 → R3 = adds evidence-grounding step
#
# [VERIFY] is directionally neutral: "what specific number
# confirms the direction and price I am considering?" validates
# any direction equally. It is NOT skepticism or anti-trade.
#
# Writeup label: "evidence-grounding" (not "self-critique").
# ============================================================


class ReasoningAgentR3(ReasoningAgentBase):

    def get_scaffold(self):
        scaffold  = "Think step by step (one sentence each):\n"
        scaffold += "  [EXPOSURE]   How large is my position? Am I over-concentrated on one side?\n"
        scaffold += "  [EDGE]       Is there profit available? (buying below mid or selling above mid)\n"
        scaffold += "  [VERIFY]     What specific number in the state confirms the direction and price I am considering?\n"
        scaffold += "  [DECISION]   Weigh all three, then choose.\n"
        return scaffold

    def extract_conclusion_text(self, reasoning_text):
        """Try [DECISION] tag; fall back to last sentence (patch #3)."""
        decision_match = re.search(
            r'\[DECISION\]\s*(.*)',
            reasoning_text,
            re.IGNORECASE | re.DOTALL,
        )
        if decision_match:
            return decision_match.group(1).strip(), 'decision_tag'

        # Fallback: last sentence
        sentences = re.split(r'[.!?]\s+', reasoning_text.strip())
        sentences = [s.strip() for s in sentences if s.strip()]
        if sentences:
            return sentences[-1], 'last_sentence_fallback'
        return reasoning_text, 'last_sentence_fallback'
