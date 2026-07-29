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
# deliberately open-ended: anything quick.py recognises never reaches the model
history = [{"role": "user", "content": "find flood-exposed schools and make me a map"}]
events = []
answer = agent.run_turn(history, lambda kind, text: events.append((kind, text)))
assert answer == "done", answer
assert len(calls) == 2
assert events == [("tool", "project_state")]
assert history[-1]["content"] == "done"  # turn persisted into history
assert any(m["role"] == "tool" for m in history)  # tool exchange persisted too

# the instant path answers without the provider being consulted at all
calls.clear()
instant_history = [{"role": "user", "content": "what is in my project?"}]
seen = []
instant = agent.run_turn(instant_history, lambda kind, text: seen.append((kind, text)))
assert "test_points" in instant, instant
assert calls == [], "quick path must not call the model"
assert seen == [("quick", "project_state")], seen
assert agent.HISTORY[-1]["path"] == "instant"
assert agent.HISTORY[-1]["seconds"] < 1.0  # it is meant to feel immediate

# the approval gate still governs the instant path (it can write, too)
declined = agent.run_turn([{"role": "user", "content": "save project"}],
                          gate=lambda n, a: "error: the user declined this action")
assert "declined" in declined, declined

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
# a natural phrase must still find the tool: not every term will match
phrase = tools.run_tool("search_algorithms", {"query": "valid geometry check"})
assert "qgis:checkvalidity" in phrase, phrase
assert tools.run_tool("search_algorithms", {"query": "zzzznope"}).startswith("no algorithms")
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
# the exec() escape hatch is deliberately absent: bandit B102 is critical and not
# waivable, so shipping it would make the plugin unlistable
assert "run_python" not in tools.TOOLS
assert tools.run_tool("run_python", {"code": "1"}).startswith("error: unknown tool")

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

# a second instance's discovery file must survive the first one's shutdown
first = bridge.BridgeServer()
second = bridge.BridgeServer()  # replaces the discovery file with its own
first.stop()  # must NOT delete the file it no longer owns
assert bridge.DISCOVERY.exists(), "stale shutdown deleted the live instance's file"
assert json.loads(bridge.DISCOVERY.read_text())["token"] == second.token
second.stop()
assert not bridge.DISCOVERY.exists()

# --- MCP protocol (bridge.mcp is the single implementation both transports use) ---
srv2 = bridge.BridgeServer()
init = srv2.mcp({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                 "params": {"clientInfo": {"name": "smoke-client"}}})
assert init["result"]["protocolVersion"] == bridge.PROTOCOL, init
assert init["result"]["serverInfo"]["name"] == "naksha"
assert init["result"]["serverInfo"]["version"] != "0", "metadata.txt version not picked up"
assert srv2.client == "smoke-client"

listed = srv2.mcp({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
names = {t["name"] for t in listed}
assert {"project_state", "run_algorithm", "search_algorithms"} <= names, names
assert all("inputSchema" in t for t in listed), "MCP requires inputSchema, not parameters"

called = srv2.mcp({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                   "params": {"name": "project_state", "arguments": {}}})["result"]
assert "test_points" in called["content"][0]["text"], called
assert called["isError"] is False

# a failing tool reports through content so the model can react, not as an RPC error
bad = srv2.mcp({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                "params": {"name": "nope", "arguments": {}}})["result"]
assert bad["isError"] is True and bad["content"][0]["text"].startswith("error:")

assert srv2.mcp({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
assert srv2.mcp({"jsonrpc": "2.0", "id": 5, "method": "bogus"})["error"]["code"] == -32601
assert srv2.last_seen == 0.0  # mcp() itself is transport-agnostic; _route stamps last_seen
srv2.stop()

# --- connect.py: it writes OTHER apps' config files, so prove it never clobbers them ---
import shutil  # noqa: E402
import tempfile  # noqa: E402
from pathlib import Path  # noqa: E402

from naksha import connect  # noqa: E402

tmp = Path(tempfile.mkdtemp(prefix="naksha_connect_"))
cfg = tmp / "claude_desktop_config.json"
ORIGINAL = {
    "mcpServers": {"someone-else": {"command": "node", "args": ["their-server.js"]}},
    "unrelatedSetting": {"theme": "dark", "nested": [1, 2, 3]},
}
cfg.write_text(json.dumps(ORIGINAL, indent=2), encoding="utf-8")
connect.CLIENTS = {"test-app": ("Test App", cfg, "mcpServers")}

assert connect.status() == [("test-app", "Test App", True, False)], connect.status()
connect.connect("test-app")

after = json.loads(cfg.read_text(encoding="utf-8"))
assert after["mcpServers"]["someone-else"] == ORIGINAL["mcpServers"]["someone-else"], "clobbered another server!"
assert after["unrelatedSetting"] == ORIGINAL["unrelatedSetting"], "clobbered unrelated settings!"
assert after["mcpServers"]["naksha"]["command"].lower().endswith("python.exe")
assert after["mcpServers"]["naksha"]["args"][0].endswith("mcp_server.py")
assert Path(str(cfg) + ".bak").exists(), "no backup written before modifying someone's config"
assert connect.status()[0][3] is True  # now reports connected

connect.disconnect("test-app")
restored = json.loads(cfg.read_text(encoding="utf-8"))
assert restored == ORIGINAL, f"disconnect did not restore the file: {restored}"
assert connect.disconnect("test-app").endswith("was not connected.")

# malformed config must be refused, never overwritten
bad = tmp / "bad.json"
bad.write_text("{ this is not json", encoding="utf-8")
connect.CLIENTS = {"bad-app": ("Bad App", bad, "mcpServers")}
try:
    connect.connect("bad-app")
    raise AssertionError("should have refused malformed JSON")
except ValueError as e:
    assert "not valid JSON" in str(e), e
assert bad.read_text(encoding="utf-8") == "{ this is not json", "overwrote a file it could not parse"

# VS Code keys its servers under "servers", not "mcpServers"
vs = tmp / "vscode.json"
vs.write_text(json.dumps({"servers": {"other": {"command": "x"}}}), encoding="utf-8")
connect.CLIENTS = {"vscode": ("VS Code", vs, "servers")}
connect.connect("vscode")
vsdata = json.loads(vs.read_text(encoding="utf-8"))
assert "naksha" in vsdata["servers"] and "other" in vsdata["servers"], vsdata
assert "mcpServers" not in vsdata, "wrote the wrong key for this client"

# a client whose config dir does not exist is simply not offered
connect.CLIENTS = {"ghost": ("Ghost", tmp / "nope" / "deep" / "x.json", "mcpServers")}
assert connect.status() == [("ghost", "Ghost", False, False)]

# the Claude connector bundle must match the MCPB spec or it silently fails to install
import zipfile  # noqa: E402

bundle = connect.build_connector(tmp)
assert bundle.name == "naksha-connector.mcpb"
with zipfile.ZipFile(bundle) as z:
    assert "manifest.json" in z.namelist() and "server/mcp_server.py" in z.namelist(), z.namelist()
    man = json.loads(z.read("manifest.json"))
for required in ("manifest_version", "name", "version", "description", "author", "server"):
    assert required in man, f"manifest missing required field {required}"
assert man["author"]["name"], "author.name is required by the spec"
assert man["server"]["type"] == "python"
assert man["server"]["entry_point"] == "server/mcp_server.py"
assert man["server"]["mcp_config"]["args"] == ["${__dirname}/server/mcp_server.py"]
assert Path(man["server"]["mcp_config"]["command"]).exists(), "manifest names a python that isn't there"

shutil.rmtree(tmp, ignore_errors=True)

# --- quick.py: the no-AI path. 'test_points' is in the project with a 'name' field ---
from naksha import quick  # noqa: E402

assert quick.parse("what's in my project") == ("project_state", {})
assert quick.parse("Style Test_Points by name") == (
    "style_layer", {"layer_name": "test_points", "mode": "categorized", "field": "name"})
assert quick.parse("colour test_points red") == (
    "style_layer", {"layer_name": "test_points", "mode": "single", "color": "red"})
assert quick.parse("buffer test_points by 2 km") == (
    "run_algorithm", {"algorithm_id": "native:buffer",
                      "parameters": {"INPUT": "test_points", "DISTANCE": 2000.0}})
assert quick.parse("zoom to test_points")[0] == "zoom_to"
assert quick.parse("how many features in test_points")[0] == "query_features"
assert quick.parse("save project") == ("save_project", {})

# partial names resolve, unknown things defer to the AI rather than guessing
assert quick.parse("zoom to points")[1]["layer_name"] == "test_points"
assert quick.parse("colour ghost_layer red") is None
assert quick.parse("style test_points by nosuchfield") is None
assert quick.parse("find flood-exposed schools and make me a map") is None
assert quick.parse("") is None
assert quick.parse("buffer test_points by 2 parsecs") is None

# and it actually executes, with no provider configured at all
assert "test_points" in quick.run("what's in my project")
assert "styled" in quick.run("colour test_points blue")

# --- model discovery (real network path) ---
# This regressed silently once: QgsBlockingNetworkRequest has no setTimeout(),
# so calling it raised AttributeError inside models(), which swallowed the
# exception and returned [] — every model list was empty and nobody noticed.
provider.invalidate()
assert provider.models("http://127.0.0.1:9/v1", "", timeout_ms=800) == [], \
    "a dead endpoint must degrade to an empty list, not raise"

_live = provider.models("https://openrouter.ai/api/v1", "", timeout_ms=15000)
if _live:
    assert len(_live) > 20, f"expected a real OpenAI-compatible catalogue, got {_live[:3]}"
    provider.models("https://openrouter.ai/api/v1", "sk-other", timeout_ms=800)
    assert len(provider._probe_cache) >= 2, "cache must be keyed on the API key too"
else:
    print("smoke: skipped live model-discovery check (no network)")
provider.invalidate()

# --- provider resolution + settings round-trip ---
from qgis.core import QgsSettings  # noqa: E402

QgsSettings().setValue("naksha/provider", "")
QgsSettings().setValue("naksha/base_url", "")
QgsSettings().setValue("naksha/model", "")
provider.invalidate()
provider.models = lambda *a, **k: []                 # nothing local
provider.api_key = lambda: ""                        # no key
assert provider.resolve()[0] == "none", provider.resolve()
assert provider.detect()[0][2] is False              # ollama reported not ready

provider.api_key = lambda: "sk-test"                 # a key beats nothing
assert provider.resolve()[0] == "groq", provider.resolve()
provider.models = lambda *a, **k: ["qwen2.5:7b"]
assert provider.resolve()[0] == "groq", "a stored key should win over local by default"

provider.api_key = lambda: ""                        # ollama alone is still usable
assert provider.resolve()[0] == "ollama", provider.resolve()

QgsSettings().setValue("naksha/provider", "openai")  # explicit choice needs to be ready
provider.api_key = lambda: "sk-test"
assert provider.resolve()[0] == "openai", provider.resolve()
QgsSettings().setValue("naksha/provider", "")

# a live bridge client shows up as a source
class _FakeBridge:
    last_seen = time.time()
    client = "Claude Code"

assert any(s[0] == "bridge" for s in provider.detect(_FakeBridge())), provider.detect(_FakeBridge())

# settings persist through QgsSettings, and agent honours max_steps
QgsSettings().setValue("naksha/max_steps", 7)
assert agent.max_steps() == 7
QgsSettings().setValue("naksha/max_steps", 25)
assert agent.system_prompt().startswith("You are Naksha")

# every new module must import cleanly inside QGIS
import naksha.connect, naksha.panels, naksha.settings  # noqa: E402, F401

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
    [{"role": "user", "content": "tidy up my project however you think best"}],
    gate=lambda n, a: None if n in tools.READ_ONLY else "error: the user declined this action",
)
assert reply == "understood, not saving", reply

# 12) cancellation aborts before any provider call (and before the quick path)
provider.chat = lambda m, t: (_ for _ in ()).throw(AssertionError("provider called despite cancel"))
assert agent.run_turn([{"role": "user", "content": "x"}], cancelled=lambda: True) == "(cancelled)"
# a cancelled turn must not fire the instant path either - it can write to the project
assert agent.run_turn([{"role": "user", "content": "save project"}],
                      cancelled=lambda: True) == "(cancelled)"

# 13) healing: a CRS failure comes back with a plain-language next move
assert "reproject" in tools._hint(ValueError("CRS mismatch between layers"))
assert "fixgeometries" in tools._hint(RuntimeError("invalid geometry at feature 3"))
assert tools._hint(RuntimeError("something unrecognised")) == ""
# and a raising tool comes back as a model-readable error, never an exception
healed = tools.run_tool("remove_layer", {"name": "no_such_layer"})
assert healed.startswith("error: no layer named"), healed
assert "test_points" in healed, "the error should list the real layer names"

# 14) verify signal: a 0-feature output is flagged, not reported as success
empty = tools.run_tool(
    "run_algorithm",
    {"algorithm_id": "native:extractbyexpression",
     "parameters": {"INPUT": "test_points", "EXPRESSION": "name = 'zzz'"}},
)
assert "WARNING: 0 features" in empty, empty

app.exitQgis()
print("smoke: all green")
