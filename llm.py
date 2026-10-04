"""Optional Claude wrapper. Returns None when no API key is available (agents then use templates)."""
import config as cfg


def complete(system: str, prompt: str, api_key: str | None = None) -> str | None:
    key = api_key or cfg.ANTHROPIC_API_KEY
    if not key:
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(model=cfg.CLAUDE_MODEL, max_tokens=cfg.LLM_MAX_TOKENS,
                                     system=system,
                                     messages=[{"role": "user", "content": prompt}])
        return "".join(b.text for b in msg.content if b.type == "text")
    except Exception as e:  # noqa: BLE001
        return f"(LLM call failed: {e})"
