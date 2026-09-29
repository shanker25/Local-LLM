"""Context-window trimming for JARVIS.

Pure functions, no I/O, no mutation of inputs.
"""

from __future__ import annotations


def trim(messages: list[dict], system_prompt: str, max_messages: int) -> list[dict]:
    """Return a new list: [system_message] + last `max_messages` non-system.

    - Always preserves the system prompt at index 0.
    - Keeps only the latest non-system messages.
    - Does not mutate `messages`.
    - If max_messages <= 0, returns just the system message.
    """
    system_message = {"role": "system", "content": system_prompt}

    if max_messages <= 0:
        return [system_message]

    non_system = [m for m in messages if m.get("role") != "system"]
    tail = non_system[-max_messages:] if len(non_system) > max_messages else non_system

    # Copy dicts so callers can't mutate our output's inner values.
    return [system_message] + [dict(m) for m in tail]