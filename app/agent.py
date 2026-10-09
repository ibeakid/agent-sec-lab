"""Tool-use loop."""

from app.llm import get_backend
from app.tools import TOOL_SCHEMAS, run_tool

MAX_STEPS = 5


def run_agent(system_prompt: str, user_text: str, backend=None) -> dict:
    backend = backend or get_backend()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]
    trace = []
    for _ in range(MAX_STEPS):
        msg = backend.chat(messages, TOOL_SCHEMAS)
        messages.append(msg)
        calls = msg.get("tool_calls") or []
        if not calls:
            return {"reply": msg.get("content", ""), "tool_calls": trace}
        for call in calls:
            name = call["function"]["name"]
            args = call["function"]["arguments"]
            # VULN (LLM06 excessive agency): every tool call runs with no
            # allowlist, argument validation, or human approval.
            result = run_tool(name, args)
            trace.append({"tool": name, "args": args, "result": result})
            messages.append({"role": "tool", "content": result, "tool_name": name})
    return {"reply": "step limit reached", "tool_calls": trace}
