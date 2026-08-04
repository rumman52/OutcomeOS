from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol


class LLM(Protocol):
    def complete(self, prompt: str) -> str: ...


@dataclass
class DeterministicLLM:
    responses: dict[str, str]

    def complete(self, prompt: str) -> str:
        return next(
            (value for key, value in self.responses.items() if key in prompt),
            '{"action":"handoff","reason":"unknown"}',
        )


def answer(question: str, tenant: str, documents: list[dict[str, str]], llm: LLM) -> dict[str, str]:
    safe_docs = [d["text"] for d in documents if d["tenant"] == tenant]
    lowered = question.lower()
    if any(x in lowered for x in ("ignore previous", "system prompt")):
        return {"action": "handoff", "reason": "prompt_injection"}
    if any(x in lowered for x in ("idiot", "stupid")):
        return {"action": "handoff", "reason": "abusive_content"}
    raw = llm.complete(f"CONTEXT={safe_docs}\nQUESTION={question}")
    try:
        result = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"action": "handoff", "reason": "malformed_tool_output"}
    if result.get("action") == "answer" and result.get("evidence") not in safe_docs:
        return {"action": "handoff", "reason": "ungrounded"}
    return {str(k): str(v) for k, v in result.items()}
