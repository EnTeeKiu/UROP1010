import re
from agent.exp3.ReasoningAgentBase import ReasoningAgentBase

# ============================================================
# ReasoningAgentR2 — Exp 3 Reasoning, Structured 3-Check CoT
# ============================================================
# Scaffold: [EXPOSURE] / [EDGE] / [DECISION]
# Tests:    Does guided structure improve over free-form thinking?
# Gap:      R1 → R2 = adds structure to reasoning
#
# Note: [EDGE] is phrased as a question ("is there profit
# available?"), NOT a heuristic ("buy below mid"). The model
# evaluates; it is not instructed.
# ============================================================


class ReasoningAgentR2(ReasoningAgentBase):

    def get_scaffold(self):
        scaffold  = "Think step by step before acting (one sentence each):\n"
        scaffold += "  [EXPOSURE]  How large is my position? Am I over-concentrated on one side?\n"
        scaffold += "  [EDGE]      Is there profit available? (buying below mid or selling above mid)\n"
        scaffold += "  [DECISION]  Weigh exposure against edge, then choose.\n"
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
