"""LLM backends: Ollama for real runs, a scripted mock for tests/CI.

Both return an Ollama-style message dict: {"role", "content", "tool_calls"?}.
"""

import os
import re

import httpx


class OllamaBackend:
    def __init__(self) -> None:
        self.url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        self.model = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")

    def chat(self, messages: list[dict], tools: list[dict]) -> dict:
        resp = httpx.post(
            f"{self.url}/api/chat",
            json={"model": self.model, "messages": messages, "tools": tools, "stream": False},
            timeout=300,
        )
        resp.raise_for_status()
        return resp.json()["message"]


class MockBackend:
    """Deterministic stand-in: maps "<tool> <arg>" in the last user message to a tool call."""

    PATTERN = re.compile(r"\b(read|query|calc|fetch)\s+(.+)", re.IGNORECASE)
    TOOL_FOR = {
        "read": ("read_file", "path"),
        "query": ("query_db", "name"),
        "calc": ("calculate", "expr"),
        "fetch": ("fetch_url", "url"),
    }

    def chat(self, messages: list[dict], tools: list[dict]) -> dict:
        last = messages[-1]
        if last["role"] == "tool":
            return {"role": "assistant", "content": f"Tool result:\n{last['content']}"}
        match = self.PATTERN.search(last["content"])
        if not match:
            return {"role": "assistant", "content": "mock: no tool needed"}
        tool, param = self.TOOL_FOR[match.group(1).lower()]
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {"name": tool, "arguments": {param: match.group(2).strip()}}}],
        }


def get_backend():
    if os.environ.get("LLM_BACKEND", "ollama") == "mock":
        return MockBackend()
    return OllamaBackend()
