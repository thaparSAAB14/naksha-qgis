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

app.exitQgis()
print("smoke: all green")
