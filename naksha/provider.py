"""OpenAI-compatible chat client on QGIS's own network stack — no pip deps.

One adapter serves Ollama (default, free/offline), OpenAI, Groq, and any
other /chat/completions endpoint. Anthropic adapter lands in M3.
"""

import json

from qgis.core import QgsApplication, QgsBlockingNetworkRequest, QgsSettings
from qgis.PyQt.QtCore import QByteArray, QUrl
from qgis.PyQt.QtNetwork import QNetworkRequest

DEFAULTS = {
    "base_url": "http://localhost:11434/v1",  # Ollama
    "model": "qwen2.5:7b",  # known-good tool caller; any /chat/completions model works
}


def setting(key):
    return QgsSettings().value(f"naksha/{key}", DEFAULTS.get(key, ""))


def api_key():
    """Key from QGIS's encrypted store. Empty is fine — Ollama needs none."""
    try:
        return QgsApplication.authManager().authSetting("naksha/api_key", "", True) or ""
    except Exception:
        return ""


def build_payload(messages, tool_specs):
    payload = {"model": setting("model"), "messages": messages}
    if tool_specs:
        payload["tools"] = tool_specs
    return payload


def chat(messages, tool_specs):
    """One non-streaming /chat/completions call. Returns the assistant message dict."""
    req = QNetworkRequest(QUrl(str(setting("base_url")).rstrip("/") + "/chat/completions"))
    req.setHeader(QNetworkRequest.ContentTypeHeader, "application/json")
    key = api_key()
    if key:
        req.setRawHeader(b"Authorization", b"Bearer " + key.encode())
    body = QByteArray(json.dumps(build_payload(messages, tool_specs)).encode())
    blocking = QgsBlockingNetworkRequest()
    if blocking.post(req, body) != QgsBlockingNetworkRequest.NoError:
        raise RuntimeError(blocking.errorMessage() or "network request failed")
    reply = json.loads(bytes(blocking.reply().content()))
    if "error" in reply:
        raise RuntimeError(reply["error"].get("message", str(reply["error"])))
    return reply["choices"][0]["message"]
