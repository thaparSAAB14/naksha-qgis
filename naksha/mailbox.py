"""Two-way chat relay between the Naksha panel and a connected AI app.

The bridge already lets an MCP client drive QGIS, but the traffic was one-way:
whatever the user typed into the dock went to Naksha's own provider, and a
connected Claude/ChatGPT session had no way to see it. So the user had to retype
their question in the other app and read the answer there — exactly the switching
this removes.

Here the dock drops user messages into `_inbox`, the AI drains it with the
`read_chat` tool, and answers come back through `send_chat` into `_replies`,
which the dock renders. Both halves buffer, so neither side has to be present
when the other speaks.

Everything runs on the Qt main thread: bridge requests are served on it, and the
local agent marshals through MainThreadBridge. No locking needed by construction.
"""

import time
from collections import deque

# Bounded so a panel left open for days, or an AI that never polls, cannot grow
# without limit. Oldest messages are dropped first.
_inbox = deque(maxlen=200)  # user -> AI
_replies = deque(maxlen=200)  # AI -> user, held until the dock is listening
_listeners = []  # callables the dock registers to receive replies live


def post_user(text):
    """Dock: the user said this and a connected app should answer it."""
    _inbox.append({"text": text, "at": time.time()})


def take_user():
    """AI: everything said since the last call. Draining is the delivery receipt,
    so a crashed client loses messages rather than replaying them forever."""
    out = list(_inbox)
    _inbox.clear()
    return out


def pending():
    return len(_inbox)


def post_reply(text):
    """AI: show this in the panel. Returns how many listeners took it; 0 means the
    dock is closed and the text is buffered for whenever it opens."""
    if _listeners:
        for fn in list(_listeners):
            fn(text)
        return len(_listeners)
    _replies.append({"text": text, "at": time.time()})
    return 0


def subscribe(fn):
    """Dock: receive replies. Anything buffered while closed is delivered now."""
    if fn not in _listeners:
        _listeners.append(fn)
    while _replies:
        fn(_replies.popleft()["text"])


def unsubscribe(fn):
    if fn in _listeners:
        _listeners.remove(fn)


def reset():
    """Tests only: forget every queued message and listener."""
    _inbox.clear()
    _replies.clear()
    _listeners.clear()


def demo():
    """Self-check: python naksha/mailbox.py"""
    reset()
    assert take_user() == []
    post_user("hello")
    post_user("second")
    got = take_user()
    assert [m["text"] for m in got] == ["hello", "second"], got
    assert take_user() == [], "draining must not replay"

    # no dock open: replies buffer instead of vanishing
    assert post_reply("held") == 0
    seen = []
    subscribe(seen.append)
    assert seen == ["held"], seen
    assert post_reply("live") == 1
    assert seen == ["held", "live"], seen

    # bound methods of the same list compare equal, so this does find the listener
    unsubscribe(seen.append)
    assert post_reply("after close") == 0, "unsubscribe left the listener attached"
    assert seen == ["held", "live"], "a removed listener still received a reply"
    subscribe(seen.append)  # reopening the dock drains what arrived meanwhile
    assert seen == ["held", "live", "after close"], seen
    reset()
    print("mailbox: ok")


if __name__ == "__main__":
    demo()
