"""Talking to an AI, and working out which one is even available.

One OpenAI-compatible adapter serves Ollama, Groq, OpenAI and anything else
exposing /chat/completions. No pip deps: everything rides QGIS's own network
stack, which also inherits the user's proxy and SSL configuration.
"""

import json
import time

from qgis.core import QgsApplication, QgsBlockingNetworkRequest, QgsSettings
from qgis.PyQt.QtCore import QByteArray, QUrl
from qgis.PyQt.QtNetwork import QNetworkRequest

# id -> (label, base_url, default model, needs a key)
PRESETS = {
    "ollama": ("Ollama (local, free)", "http://localhost:11434/v1", "", False),
    "groq": ("Groq", "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile", True),
    "openai": ("OpenAI", "https://api.openai.com/v1", "gpt-4o-mini", True),
    "custom": ("Custom endpoint", "", "", True),
}
DEFAULTS = {"base_url": PRESETS["ollama"][1], "model": "qwen2.5:7b"}

_probe_cache = (0.0, [])  # (checked_at, models) - ponytail: 30 s TTL, good enough for a UI


def setting(key, default=None):
    return QgsSettings().value(f"naksha/{key}", DEFAULTS.get(key, default if default is not None else ""))


def api_key():
    """Key from QGIS's encrypted store. Empty is fine — Ollama needs none."""
    try:
        return QgsApplication.authManager().authSetting("naksha/api_key", "", True) or ""
    except Exception:
        return ""


def set_api_key(value):
    QgsApplication.authManager().storeAuthSetting("naksha/api_key", value or "", True)
    invalidate()


def invalidate():
    global _probe_cache
    _probe_cache = (0.0, [])


def ollama_models(timeout_ms=1200):
    """Model names from a local Ollama, or [] if it isn't running. Cached briefly so
    repainting the UI doesn't hammer it."""
    global _probe_cache
    checked, cached = _probe_cache
    if time.time() - checked < 30:
        return cached
    models = []
    try:
        base = str(setting("base_url") or DEFAULTS["base_url"])
        host = base.rsplit("/v1", 1)[0] if "/v1" in base else "http://localhost:11434"
        req = QNetworkRequest(QUrl(host.rstrip("/") + "/api/tags"))
        blocking = QgsBlockingNetworkRequest()
        blocking.setTimeout(timeout_ms)
        if blocking.get(req) == QgsBlockingNetworkRequest.NoError:
            payload = json.loads(bytes(blocking.reply().content()))
            models = [m["name"] for m in payload.get("models", []) if m.get("name")]
    except Exception:
        models = []
    _probe_cache = (time.time(), models)
    return models


def detect(bridge=None):
    """What can answer a question right now: [(id, label, ready, detail)]."""
    found = []
    local = ollama_models()
    found.append(("ollama", "Ollama (local, free)", bool(local),
                  f"{len(local)} model{'s' if len(local) != 1 else ''} installed" if local
                  else "not running — install from ollama.com"))
    chosen = str(setting("provider") or "")
    cloud_id = chosen if chosen in PRESETS and chosen != "ollama" else "groq"
    label = PRESETS[cloud_id][0]
    has_key = bool(api_key())
    found.append((cloud_id, label, has_key, "API key stored" if has_key else "no API key yet"))
    if bridge is not None and getattr(bridge, "last_seen", 0):
        idle = time.time() - bridge.last_seen
        if idle < 300:
            who = bridge.client or "an MCP app"
            found.append(("bridge", f"MCP · {who}", True, f"active {int(idle)}s ago"))
    return found


def resolve(bridge=None):
    """(id, label, ready, detail) for the source we will actually use.

    Explicit user choice wins; otherwise prefer a cloud key (fast, reliable tool
    calling) over local Ollama, and report honestly when nothing is configured.
    """
    sources = {s[0]: s for s in detect(bridge)}
    chosen = str(setting("provider") or "")
    if chosen and chosen in sources and sources[chosen][2]:
        return sources[chosen]
    for candidate in list(sources):
        if candidate not in ("ollama", "bridge") and sources[candidate][2]:
            return sources[candidate]
    if sources.get("ollama", (None, None, False))[2]:
        return sources["ollama"]
    return ("none", "Not configured", False, "add an API key or install Ollama")


def active_model():
    explicit = str(setting("model") or "")
    if explicit:
        return explicit
    source = resolve()[0]
    if source == "ollama":
        local = ollama_models()
        return local[0] if local else ""
    return PRESETS.get(source, ("", "", "", False))[2]


def active_base_url():
    explicit = str(setting("base_url") or "")
    if explicit:
        return explicit
    return PRESETS.get(resolve()[0], ("", DEFAULTS["base_url"], "", False))[1]


def build_payload(messages, tool_specs):
    payload = {"model": active_model(), "messages": messages}
    if tool_specs:
        payload["tools"] = tool_specs
    return payload


def chat(messages, tool_specs):
    """One non-streaming /chat/completions call. Returns the assistant message dict."""
    req = QNetworkRequest(QUrl(active_base_url().rstrip("/") + "/chat/completions"))
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


def test_connection():
    """Cheap round trip for the settings dialog. Returns (ok, plain-language message)."""
    try:
        msg = chat([{"role": "user", "content": "Reply with the single word: ready"}], None)
        return True, f"Working — {active_model() or 'model'} replied: {(msg.get('content') or '').strip()[:60]}"
    except Exception as e:
        text = str(e)
        if "authentication" in text.lower() or "401" in text:
            return False, "The endpoint rejected the API key. Check the key and try again."
        if "refused" in text.lower():
            return False, "Nothing answered at that address. Is Ollama running, or the URL right?"
        return False, text[:200]
