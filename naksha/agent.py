"""The agent turn: an instant path for recognised commands, otherwise a bounded
tool-call loop with ambient context, an approval gate, and cooperative cancellation.
Runs on a worker thread via task.py — everything touching QGIS goes through `main`."""

import json
import time
from collections import deque

from . import provider, quick, tools

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
HISTORY = deque(maxlen=20)  # turn records for the developer panel; in memory only


def system_prompt():
    return str(provider.setting("system_prompt", "") or SYSTEM)


def max_steps():
    try:
        return int(provider.setting("max_steps", MAX_STEPS) or MAX_STEPS)
    except (TypeError, ValueError):
        return MAX_STEPS


def run_turn(history, on_event=lambda kind, text: None, main=None, cancelled=None, gate=None):
    """Run one user turn. `history` is the chat so far (no system messages), mutated
    in place so tool exchanges persist as context.

    main(fn)          -> run fn on the Qt main thread (default: call directly)
    cancelled()       -> True aborts between steps
    gate(name, args)  -> error string to block a tool call, or None to allow
    """
    main = main or (lambda fn: fn())
    cancelled = cancelled or (lambda: False)
    if cancelled():  # checked before the instant path too, which can write
        return "(cancelled)"
    started = time.time()
    record = {"asked": history[-1]["content"] if history else "", "calls": [], "path": "ai"}

    # Recognised commands never reach a model: instant, offline, and impossible to
    # hallucinate. Unrecognised input returns None and carries on below.
    asked = history[-1]["content"] if history and history[-1].get("role") == "user" else ""
    hit = main(lambda: quick.parse(asked))
    if hit:
        name, args = hit
        on_event("quick", name)
        blocked = gate(name, args) if gate else None
        answer = blocked or main(lambda: tools.run_tool(name, args))
        history.append({"role": "assistant", "content": answer})
        record.update(path="instant", calls=[name], seconds=round(time.time() - started, 3),
                      answer=answer)
        HISTORY.append(record)
        return answer

    context = {"role": "system", "content": "Current project state:\n" + main(tools.project_state)}
    msgs = [{"role": "system", "content": system_prompt()}, context] + history

    def finish(text):
        history[:] = msgs[2:]
        record.update(seconds=round(time.time() - started, 3), answer=text, messages=msgs)
        HISTORY.append(record)
        return text

    for _ in range(max_steps()):
        if cancelled():
            return finish("(cancelled)")
        msg = provider.chat(msgs, tools.openai_tool_specs())
        record.setdefault("raw", []).append(msg)
        if msg.get("usage"):
            record["usage"] = msg["usage"]
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
            record["calls"].append(name)
            result = (gate(name, args) if gate else None) or main(lambda: tools.run_tool(name, args))
            msgs.append({"role": "tool", "tool_call_id": call.get("id", ""), "content": result})
    return finish("(stopped: reached the step limit)")
