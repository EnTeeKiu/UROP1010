# Adjustments for Local LLM Implementation

Based on the decision to use a local Large Language Model (LLM) on a 4GB VRAM GPU (RTX A2000), the following adjustments are made to the original research proposal. These changes ensure the experiments run efficiently and reliably without relying on commercial APIs.

## 1. Model Selection & Hardware Constraints

> [!IMPORTANT]
> The primary constraint is the **4GB VRAM limit**. We must ensure the model and context window fit entirely on the GPU to maintain high inference speeds.

*   **Chosen Model:** `Gemma 3 (4B) Instruct`
*   **Quantization:** 4-bit quantization (handled automatically via Ollama). This compresses the model to ~2.5GB - 2.8GB, leaving ~1.2GB of VRAM dedicated to the context window (system prompts, limit-order-book state, and memory).
*   **Eliminated Concerns:** API token costs and network latency (Experiment 6 will now strictly test *artificial* latency, rather than dealing with unpredictable API network latency).

## 2. Technical Stack Adjustments

*   **Inference Server:** We will use **Ollama** running locally to serve the model. It provides an OpenAI-compatible endpoint at `http://localhost:11434/v1`.
*   **Python Integration:** We will continue to use the standard `openai` Python package in the simulator, but redirect the `base_url` to the local Ollama server.
*   **Structured Output:** To guarantee valid JSON for trading decisions, we will rely on Ollama's native JSON Mode and/or constrained decoding libraries like `instructor`.

## 3. Experiment-Specific Adjustments

### Experiment 5 (Information-Access Ablation)
*   **Adjustment:** Since we have ~1.2GB of VRAM for context, we must be highly efficient with the Limit Order Book (LOB) text representation. We cannot pass an infinitely deep LOB. 
*   **Action:** The LOB will be truncated to the top 5 or 10 price levels and formatted as dense JSON or a compact Markdown table to minimize token usage.

### Experiment 8 (Communication / Collusion)
*   **Adjustment:** We cannot load two separate instances of the model simultaneously due to VRAM limits.
*   **Action:** We will run a single instance of `Gemma 3 (4B)` in Ollama. The simulator will simulate multi-agent communication sequentially. The ABIDES environment will query the model for Trader A (passing Trader A's prompt and memory), wait for the response, and then query the model for Trader B (passing Trader B's prompt and memory). 

## 4. Modified System Architecture

The python simulation loop will be adjusted as follows:

```python
from openai import OpenAI
import json

# Point to local Ollama instance
client = OpenAI(
    base_url='http://localhost:11434/v1',
    api_key='ollama', # required but ignored
)

def get_agent_decision(system_prompt, market_state):
    response = client.chat.completions.create(
        model="gemma3:4b", 
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": market_state}
        ],
        response_format={ "type": "json_object" } # Forces JSON output
    )
    return json.loads(response.choices[0].message.content)
```

## 5. Next Steps for Implementation

1.  **Install Ollama:** Set up Ollama on the local machine.
2.  **Pull the Model:** Run `ollama run gemma3:4b` to download and initialize the model.
3.  **Prompt Engineering Phase:** Test the model with mock ABIDES market data to verify it strictly adheres to the JSON schema before integrating it into the full simulator loop.
