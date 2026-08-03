"""Talking to an AI, and working out which one is even available.

One OpenAI-compatible adapter serves Ollama, OpenRouter, Groq, OpenAI and
anything else exposing /chat/completions. No pip deps: everything rides QGIS's
own network stack, which also inherits the user's proxy and SSL configuration.

Model discovery uses the same standard: GET {base_url}/models. That one request
covers every provider above, so a custom endpoint needs no special support - if
it answers, it works.
"""

import json
import time

from qgis.core import (
    QgsApplication,
    QgsBlockingNetworkRequest,
    QgsMessageLog,
    QgsSettings,
)
from qgis.PyQt.QtCore import QByteArray, QUrl
from qgis.PyQt.QtNetwork import QNetworkRequest

# id -> (label, base_url, default model, needs a key)
# No default model for OpenRouter/custom on purpose: the catalogue is fetched
# from the endpoint, so hardcoding one would only go stale.
PRESETS = {
    "ollama": ("Ollama (local, free)", "http://localhost:11434/v1", "", False),
    "openrouter": ("OpenRouter", "https://openrouter.ai/api/v1", "", True),
    "groq": ("Groq", "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile", True),
    "openai": ("OpenAI", "https://api.openai.com/v1", "gpt-4o-mini", True),
    "custom": ("Custom endpoint", "", "", True),
}
DEFAULTS = {"base_url": PRESETS["ollama"][1], "model": "qwen2.5:7b"}

# (base_url, key) -> (checked_at, [model ids]). Keyed on both so switching
# endpoint or pasting a new key refetches instead of showing the old list.
_probe_cache = {}  # ponytail: 30 s TTL, good enough for a settings dialog
# An endpoint that answered nothing is remembered for longer: resolve() runs on
# every turn and always probes the optional local Ollama, so a 30 s memory means
# a blocking re-probe (and a log line) every few turns on machines without it.
# invalidate() still fires whenever the user changes provider, URL or key.
_TTL_OK, _TTL_DEAD = 30, 300


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
    _probe_cache.clear()


def models(base_url=None, key=None, timeout_ms=4000):
    """Model ids this endpoint offers for this key, or [] if it did not answer.

    `GET {base_url}/models` is the OpenAI-compatible standard, so the same
    request serves OpenRouter, OpenAI, Groq and Ollama. Both response shapes
    are accepted: `data[].id` (OpenAI-compatible) and `models[].name` (Ollama's
    native listing), which keeps this working without knowing the provider.
    """
    base = (active_base_url() if base_url is None else base_url).rstrip("/")
    if not base:
        return []
    key = api_key() if key is None else key
    cached = _probe_cache.get((base, key))
    if cached and time.time() - cached[0] < (_TTL_OK if cached[1] else _TTL_DEAD):
        return cached[1]
    found = []
    try:
        req = QNetworkRequest(QUrl(base + "/models"))
        # Timeout lives on the request: QgsBlockingNetworkRequest has no
        # setTimeout(), and calling one silently cost us every model list.
        req.setTransferTimeout(timeout_ms)
        if key:
            req.setRawHeader(b"Authorization", b"Bearer " + key.encode())
        blocking = QgsBlockingNetworkRequest()
        if blocking.get(req) == QgsBlockingNetworkRequest.NoError:
            body = bytes(blocking.reply().content())
            # A refused connection can still come back NoError with an empty body
            # (Ollama not installed is the everyday case). That is an answer of
            # "no models", not a fault — parsing it only produced a JSON error in
            # the log that named neither the cause nor the cure.
            payload = json.loads(body) if body else {}
            entries = payload.get("data") or payload.get("models") or []
            found = sorted(
                str(m.get("id") or m.get("name"))
                for m in entries
                if isinstance(m, dict) and (m.get("id") or m.get("name"))
            )
    except Exception as e:
        # Never let a bad endpoint break the settings dialog, but say why in the
        # log — swallowing this silently is exactly how the bug above survived.
        QgsMessageLog.logMessage(f"model list from {base} failed: {e}", "Naksha")
        found = []
    _probe_cache[(base, key)] = (time.time(), found)
    return found


def detect(bridge=None):
    """What can answer a question right now: [(id, label, ready, detail)]."""
    found = []
    local = models(PRESETS["ollama"][1], "", timeout_ms=1200)
    found.append(("ollama", PRESETS["ollama"][0], bool(local),
                  f"{len(local)} model{'s' if len(local) != 1 else ''} installed" if local
                  else "not running — install from ollama.com"))

    chosen = str(setting("provider") or "")
    url = str(setting("base_url") or "")
    if chosen in PRESETS and chosen != "ollama":
        cloud_id = chosen
    else:
        cloud_id = "custom" if url and url != PRESETS["ollama"][1] else "groq"
    label = PRESETS[cloud_id][0]
    # Deliberately cheap: resolve() runs on every turn, so readiness is "a key
    # exists", not a network probe. The settings dialog does the real probe via
    # models() and reports what the endpoint actually answered.
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
    preset = PRESETS.get(resolve()[0], ("", "", "", False))[2]
    if preset:
        return preset
    available = models()  # Ollama, OpenRouter, custom: ask the endpoint
    return available[0] if available else ""


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
    req.setTransferTimeout(120000)  # a hung endpoint must not wedge the turn
    key = api_key()
    if key:
        req.setRawHeader(b"Authorization", b"Bearer " + key.encode())
    # OpenRouter uses these for attribution; harmless everywhere else.
    req.setRawHeader(b"HTTP-Referer", b"https://github.com/thaparSAAB14/naksha-qgis")
    req.setRawHeader(b"X-Title", b"Naksha for QGIS")
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
