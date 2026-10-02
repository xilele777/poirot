"""Interpret explicit tool failure envelopes without scanning successful evidence."""

from __future__ import annotations

import json

from langchain_core.messages import ToolMessage


def tool_error_text(message: ToolMessage) -> str | None:
    content = message.content
    text = content if isinstance(content, str) else "".join(
        part if isinstance(part, str) else str(part.get("text", ""))
        for part in content if isinstance(part, (str, dict))
    )
    if message.status == "error":
        return text or "Tool failed"
    try:
        payload = json.loads(text)
    except (ValueError, TypeError):
        return None
    if isinstance(payload, dict):
        if payload.get("error"):
            return str(payload["error"])
        if payload.get("isError") is True or payload.get("status") == "error":
            return str(payload.get("message") or text)
    return None
