import json
import time
import requests
import numpy as np
from util.util import log_print
from agent.experiment.prompt_template import SYSTEM_PROMPT, build_user_prompt

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


class LLMPolicy:
    """
    LLM policy for side selection (BUY or SELL).
    Queries local Ollama. On parse failure or timeout, falls back to a coin flip.
    """

    def __init__(self, rng_fallback: np.random.RandomState, 
                 model: str = 'gemma3:4b', 
                 server_url: str = 'http://localhost:11434/v1',
                 temperature: float = 0.0, 
                 max_tokens: int = 200,
                 p_buy_fallback: float = 0.5):
        self.rng_fallback = rng_fallback
        self.model = model
        self.server_url = server_url
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.p_buy_fallback = p_buy_fallback
        
        self.use_openai = OpenAI is not None
        if self.use_openai:
            # The SDK retries twice by default. The experiment protocol permits one
            # model call per wake-up, so retries must be disabled explicitly.
            self.client = OpenAI(
                base_url=self.server_url,
                api_key='ollama',
                max_retries=0,
                timeout=30.0,
            )

    def choose_side(self, state: dict) -> str:
        user_prompt = build_user_prompt(state)
        
        fallback_used = False
        valid = True
        parsed_side = None
        raw_output = ""
        latency_ms = 0
        timed_out = False
        tokens_in = None
        tokens_out = None
        
        start_t = time.time()
        
        try:
            if self.use_openai:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={"type": "json_object"},
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    timeout=30.0
                )
                raw_output = response.choices[0].message.content
                usage = getattr(response, "usage", None)
                if usage is not None:
                    tokens_in = getattr(usage, "prompt_tokens", None)
                    tokens_out = getattr(usage, "completion_tokens", None)
                decision = self._parse_json(raw_output)
            else:
                # Fallback to requests if openai not installed
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    "format": "json",
                    "stream": False,
                    "options": {
                        "temperature": self.temperature,
                        "num_predict": self.max_tokens
                    }
                }
                url = self.server_url.replace('/v1', '/api/chat')
                res = requests.post(url, json=payload, timeout=30.0)
                res.raise_for_status()
                response_json = res.json()
                raw_output = response_json['message']['content']
                tokens_in = response_json.get('prompt_eval_count')
                tokens_out = response_json.get('eval_count')
                decision = self._parse_json(raw_output)
                
            parsed_side = decision.get("side", None)
            if parsed_side not in ["BUY", "SELL"]:
                valid = False
                fallback_used = True
                
        except Exception as e:
            log_print("LLMPolicy query failed: {}", str(e))
            valid = False
            fallback_used = True
            timed_out = self._is_timeout(e)

        latency_ms = int((time.time() - start_t) * 1000)
            
        if fallback_used:
            parsed_side = "BUY" if self.rng_fallback.random() < self.p_buy_fallback else "SELL"
            
        # Log this decision detail somewhere if possible, but the wrapper is what writes to file.
        # We can attach these metadata directly to the state or return a tuple.
        # To strictly match choose_side(state) -> str, we will just return the string.
        # But wait! Section 7 schema requires logging raw_output, valid, fallback_used, latency.
        # Let's attach them to the `state` dict which is mutable, so the wrapper can extract and log them.
        state['llm_raw_output'] = raw_output
        state['llm_valid'] = valid
        state['llm_fallback_used'] = fallback_used
        state['llm_latency_ms'] = latency_ms
        state['llm_timeout'] = timed_out
        state['llm_tokens_in'] = tokens_in
        state['llm_tokens_out'] = tokens_out
        state['llm_prompt'] = user_prompt
        
        return parsed_side

    @staticmethod
    def _parse_json(raw_output: str) -> dict:
        """Parse a JSON-only response, allowing one surrounding Markdown fence."""
        text = (raw_output or "").strip()
        if text.startswith("```") and text.endswith("```"):
            lines = text.splitlines()
            if len(lines) >= 3:
                text = "\n".join(lines[1:-1]).strip()
        decision = json.loads(text)
        if not isinstance(decision, dict):
            raise ValueError("LLM response must be a JSON object")
        return decision

    @staticmethod
    def _is_timeout(exc: Exception) -> bool:
        """Recognize timeout exceptions from requests and OpenAI/httpx clients."""
        current = exc
        seen = set()
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            if isinstance(current, requests.exceptions.Timeout):
                return True
            if "timeout" in current.__class__.__name__.lower():
                return True
            current = getattr(current, "__cause__", None) or getattr(current, "__context__", None)
        return False
