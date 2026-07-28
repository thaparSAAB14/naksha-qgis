"""The agent turn: bounded tool-call loop. Plan/verify/self-heal lands in M3."""

import json

from . import provider, tools

SYSTEM = (
    "You are Naksha, an AI agent living inside QGIS. Use your tools to inspect and "
    "operate on the user's open project. Be concise. Report real numbers (feature "
    "counts, CRS codes), never a bare 'done'."
)

MAX_STEPS = 10  # ponytail: flat step cap; per-step retry budget arrives with self-heal in M3


def run_turn(history, on_event=lambda kind, text: None):
    """Run one user turn. `history` is the chat so far (no system message), mutated
    in place so tool exchanges persist as context. Returns the final assistant text."""
    msgs = [{"role": "system", "content": SYSTEM}] + history
    for _ in range(MAX_STEPS):
        msg = provider.chat(msgs, tools.openai_tool_specs())
        msgs.append(msg)
        calls = msg.get("tool_calls") or []
        if not calls:
            history[:] = msgs[1:]
            return msg.get("content") or ""
        for call in calls:
            name = call["function"]["name"]
            try:
                args = json.loads(call["function"].get("arguments") or "{}")
            except ValueError:
                args = {}
            on_event("tool", name)
            result = tools.run_tool(name, args)
            msgs.append({"role": "tool", "tool_call_id": call.get("id", ""), "content": result})
    history[:] = msgs[1:]
    return "(stopped: reached the step limit)"
