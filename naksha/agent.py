"""The agent turn: bounded tool-call loop with ambient context, an approval
gate, and cooperative cancellation. Runs on a worker thread via task.py —
everything touching QGIS goes through `main`."""

import json

from . import provider, tools

SYSTEM = (
    "You are Naksha, an AI agent living inside QGIS. Use your tools to inspect and "
    "operate on the user's open project. For GIS operations discover at runtime: "
    "search_algorithms -> describe_algorithm -> run_algorithm (outputs become "
    "temporary layers unless a path is given). For a multi-step goal, state a brief "
    "numbered plan first, then execute it step by step. After any operation that "
    "produces data, verify it: a 0-feature output, an empty extent, or a lost CRS "
    "means something went wrong — diagnose, fix, and say what you corrected and why. "
    "Be concise. Report real numbers (feature counts, CRS codes), never a bare 'done'."
)

MAX_STEPS = 25


def run_turn(history, on_event=lambda kind, text: None, main=None, cancelled=None, gate=None):
    """Run one user turn. `history` is the chat so far (no system messages),
    mutated in place so tool exchanges persist as context.

    main(fn)          -> run fn on the Qt main thread (default: call directly)
    cancelled()       -> True aborts between steps
    gate(name, args)  -> error string to block a tool call, or None to allow
    """
    main = main or (lambda fn: fn())
    cancelled = cancelled or (lambda: False)
    context = {"role": "system", "content": "Current project state:\n" + main(tools.project_state)}
    msgs = [{"role": "system", "content": SYSTEM}, context] + history

    def finish(text):
        history[:] = msgs[2:]
        return text

    for _ in range(MAX_STEPS):
        if cancelled():
            return finish("(cancelled)")
        msg = provider.chat(msgs, tools.openai_tool_specs())
        msgs.append(msg)
        calls = msg.get("tool_calls") or []
        if not calls:
            return finish(msg.get("content") or "")
        for call in calls:
            name = call["function"]["name"]
            try:
                args = json.loads(call["function"].get("arguments") or "{}")
            except ValueError:
                args = {}
            on_event("tool", name)
            result = (gate(name, args) if gate else None) or main(lambda: tools.run_tool(name, args))
            msgs.append({"role": "tool", "tool_call_id": call.get("id", ""), "content": result})
    return finish("(stopped: reached the step limit)")
