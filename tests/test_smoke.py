r"""Headless smoke test — no GUI, no AI key, no network.

Run:  & "C:\Program Files\QGIS 3.40.13\bin\python-qgis-ltr.bat" tests\test_smoke.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qgis.core import (  # noqa: E402
    QgsApplication,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
)

app = QgsApplication([], False)
app.initQgis()

from naksha import agent, provider, tools  # noqa: E402

# 1) project_state sees a real (memory) layer with correct numbers
layer = QgsVectorLayer("Point?crs=EPSG:4326&field=name:string", "test_points", "memory")
assert layer.isValid()
feat = QgsFeature(layer.fields())
feat.setAttribute("name", "a")
feat.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(1, 2)))
assert layer.dataProvider().addFeatures([feat])[0]
QgsProject.instance().addMapLayer(layer, False)

state = tools.project_state()
assert "test_points" in state, state
assert "1 features" in state, state
assert "EPSG:4326" in state, state
assert "fields: name" in state, state

# 2) request payload has the right shape
payload = provider.build_payload([{"role": "user", "content": "hi"}], tools.openai_tool_specs())
assert payload["messages"][0]["content"] == "hi"
assert payload["tools"][0]["function"]["name"] == "project_state"
assert payload["tools"][0]["function"]["parameters"]["type"] == "object"

# 3) agent loop end-to-end with a fake provider: tool call -> tool result -> answer
calls = []


def fake_chat(messages, tool_specs):
    calls.append(list(messages))
    if len(calls) == 1:
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": "t1", "type": "function", "function": {"name": "project_state", "arguments": "{}"}}
            ],
        }
    last = messages[-1]
    assert last["role"] == "tool" and "test_points" in last["content"], last
    return {"role": "assistant", "content": "done"}


provider.chat = fake_chat
history = [{"role": "user", "content": "what is in my project?"}]
events = []
answer = agent.run_turn(history, lambda kind, text: events.append((kind, text)))
assert answer == "done", answer
assert len(calls) == 2
assert events == [("tool", "project_state")]
assert history[-1]["content"] == "done"  # turn persisted into history
assert any(m["role"] == "tool" for m in history)  # tool exchange persisted too

# 4) unknown tool degrades into a model-visible error, not a crash
assert tools.run_tool("nope", {}).startswith("error:")

# 5) plugin module imports cleanly (instantiation needs the real GUI)
import naksha.plugin  # noqa: E402, F401

# --- M2: the introspected tool engine ---
sys.path.append(r"C:\Program Files\QGIS 3.40.13\apps\qgis-ltr\python\plugins")
from processing.core.Processing import Processing  # noqa: E402

Processing.initialize()

# 6) catalogue: search finds native:buffer, describe exposes its real parameters
found = tools.run_tool("search_algorithms", {"query": "buffer"})
assert "native:buffer" in found, found
desc = tools.run_tool("describe_algorithm", {"algorithm_id": "native:buffer"})
for param in ("INPUT", "DISTANCE", "OUTPUT"):
    assert param in desc, desc

# 7) run a REAL buffer on the memory layer; output auto-added with a real count
before = len(QgsProject.instance().mapLayers())
result = tools.run_tool(
    "run_algorithm",
    {"algorithm_id": "native:buffer", "parameters": {"INPUT": "test_points", "DISTANCE": 0.1}},
)
assert "1 features" in result, result
assert "EPSG:4326" in result, result
assert len(QgsProject.instance().mapLayers()) == before + 1

# 8) project tools: query, style, layer resolution errors
q = tools.run_tool("query_features", {"layer_name": "test_points", "expression": "name = 'a'"})
assert q.startswith("1 features match"), q
assert "styled" in tools.run_tool("style_layer", {"layer_name": "test_points", "mode": "single", "color": "red"})
missing = tools.run_tool("query_features", {"layer_name": "ghost", "expression": "1"})
assert "no layer named 'ghost'" in missing and "test_points" in missing, missing

# 9) escape hatch
assert tools.run_tool("run_python", {"code": "result = 21 * 2"}) == "42"

# --- the subscription bridge: real HTTP against the live QTcpServer ---
import json  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
import urllib.error  # noqa: E402
import urllib.request  # noqa: E402

from naksha import bridge  # noqa: E402

srv = bridge.BridgeServer()
info = json.loads(bridge.DISCOVERY.read_text())
assert info["port"] == srv.port() and info["token"] == srv.token
base = f"http://127.0.0.1:{info['port']}"
results = {}


def client():
    def call(path, data=None, token=info["token"]):
        req = urllib.request.Request(
            base + path,
            data=json.dumps(data).encode() if data is not None else None,
            headers={"X-Naksha-Token": token, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())

    results["tools"] = call("/tools")
    results["call"] = call("/call", {"name": "project_state", "args": {}})
    try:
        call("/tools", token="wrong")
        results["bad_token"] = "allowed!"
    except urllib.error.HTTPError as e:
        results["bad_token"] = e.code


t = threading.Thread(target=client, daemon=True)
t.start()
deadline = time.time() + 15
while t.is_alive() and time.time() < deadline:
    app.processEvents()
    time.sleep(0.005)
assert not t.is_alive(), "bridge client timed out"
tool_names = {s["name"] for s in results["tools"]}
assert {"project_state", "run_algorithm", "search_algorithms"} <= tool_names, tool_names
assert "test_points" in results["call"]["result"], results["call"]
assert results["bad_token"] == 403, results["bad_token"]
srv.stop()
assert not bridge.DISCOVERY.exists()  # token file cleaned up

# --- M3: the trust loop ---
from naksha.task import MainThreadBridge  # noqa: E402

# 10) MainThreadBridge: cross-thread call runs on main thread, exceptions propagate
mtb = MainThreadBridge()
out = {}


def worker():
    out["value"] = mtb.call(lambda: tools.project_state()[:7])
    try:
        mtb.call(lambda: 1 / 0)
        out["exc"] = "not raised"
    except ZeroDivisionError:
        out["exc"] = "raised"


t2 = threading.Thread(target=worker, daemon=True)
t2.start()
deadline = time.time() + 15
while t2.is_alive() and time.time() < deadline:
    app.processEvents()
    time.sleep(0.005)
assert not t2.is_alive(), "bridge call timed out"
assert out["value"] == "project" and out["exc"] == "raised", out

# 11) ambient context is injected; a declined gate reaches the model verbatim
gate_calls = []


def fake_chat_gate(messages, tool_specs):
    gate_calls.append(1)
    if len(gate_calls) == 1:
        assert messages[1]["role"] == "system", messages[1]
        assert messages[1]["content"].startswith("Current project state:")
        assert "test_points" in messages[1]["content"]
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": "g1", "type": "function", "function": {"name": "save_project", "arguments": "{}"}}
            ],
        }
    assert "declined" in messages[-1]["content"], messages[-1]
    return {"role": "assistant", "content": "understood, not saving"}


provider.chat = fake_chat_gate
reply = agent.run_turn(
    [{"role": "user", "content": "save my project"}],
    gate=lambda n, a: None if n in tools.READ_ONLY else "error: the user declined this action",
)
assert reply == "understood, not saving", reply

# 12) cancellation aborts before any provider call
provider.chat = lambda m, t: (_ for _ in ()).throw(AssertionError("provider called despite cancel"))
assert agent.run_turn([{"role": "user", "content": "x"}], cancelled=lambda: True) == "(cancelled)"

# 13) healing: a CRS failure comes back with a plain-language next move
healed = tools.run_tool("run_python", {"code": "raise ValueError('CRS mismatch between layers')"})
assert "Hint" in healed and "reproject" in healed, healed

# 14) verify signal: a 0-feature output is flagged, not reported as success
empty = tools.run_tool(
    "run_algorithm",
    {"algorithm_id": "native:extractbyexpression",
     "parameters": {"INPUT": "test_points", "EXPRESSION": "name = 'zzz'"}},
)
assert "WARNING: 0 features" in empty, empty

app.exitQgis()
print("smoke: all green")
