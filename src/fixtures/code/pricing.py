import json

PRICING = {
    "small": {"input": 0.25, "output": 1.25, "cache_read": 0.03},
    "large": {"input": 3.00, "output": 15.00, "cache_read": 0.30},
}

def cost_of(model: str, in_tokens: int, out_tokens: int, cached_tokens: int = 0) -> float:
    p = PRICING[model]
    paid_in = in_tokens - cached_tokens
    return (paid_in       * p["input"]      / 1_000_000
          + cached_tokens * p["cache_read"] / 1_000_000
          + out_tokens    * p["output"]     / 1_000_000)

def count_tokens(text) -> int:
    """Грубая оценка: 1 токен ≈ 4 символа. В проде — токенайзер провайдера."""
    if isinstance(text, str):
        return max(1, len(text) // 4)
    if isinstance(text, list):
        return sum(count_tokens(x) for x in text)
    if isinstance(text, dict):
        return count_tokens(json.dumps(text, ensure_ascii=False))
    return 1