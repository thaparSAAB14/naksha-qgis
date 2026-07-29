"""Commands that need no AI at all.

Symbology, buffers and zooms are structured requests — a language model adds latency
and a chance of hallucination without adding capability. These patterns run instantly,
offline, with no key and no model installed. Anything unrecognised returns None and
falls through to the agent loop untouched.
"""

import difflib
import re

from qgis.core import QgsProject

from . import tools

COLOURS = {
    "red", "blue", "green", "yellow", "orange", "purple", "black", "white", "grey",
    "gray", "brown", "pink", "cyan", "magenta", "teal", "navy",
}


def _layers():
    return [layer.name() for layer in QgsProject.instance().mapLayers().values()]


def _match(name, choices):
    """Resolve a spoken layer/field name. Returns None when it is not clearly one thing —
    ambiguity is the agent's problem to solve, not ours to guess at."""
    if not name:
        return None
    name = name.strip().strip("'\"")
    lowered = {c.lower(): c for c in choices}
    if name.lower() in lowered:
        return lowered[name.lower()]
    contains = [c for c in choices if name.lower() in c.lower()]
    if len(contains) == 1:
        return contains[0]
    close = difflib.get_close_matches(name.lower(), list(lowered), n=2, cutoff=0.75)
    if len(close) == 1:
        return lowered[close[0]]
    return None


def _fields(layer_name):
    layers = QgsProject.instance().mapLayersByName(layer_name)
    if not layers or not hasattr(layers[0], "fields"):
        return []
    return [f.name() for f in layers[0].fields()]


def _style_by(text):
    m = re.match(r"^(?:colou?r|style|symbolise|symbolize)\s+(.+?)\s+by\s+(.+?)$", text)
    if not m:
        return None
    layer = _match(m.group(1), _layers())
    if not layer:
        return None
    field = _match(m.group(2), _fields(layer))
    if not field:
        return None
    return "style_layer", {"layer_name": layer, "mode": "categorized", "field": field}


def _style_single(text):
    m = re.match(r"^(?:colou?r|style|make)\s+(.+?)\s+([a-z]+)$", text)
    if not m or m.group(2) not in COLOURS:
        return None
    layer = _match(m.group(1), _layers())
    if not layer:
        return None
    return "style_layer", {"layer_name": layer, "mode": "single", "color": m.group(2)}


def _buffer(text):
    m = re.match(r"^buffer\s+(.+?)\s+(?:by\s+)?([\d.]+)\s*(m|metres|meters|km)\b", text)
    if not m:
        return None
    layer = _match(m.group(1), _layers())
    if not layer:
        return None
    distance = float(m.group(2)) * (1000 if m.group(3) == "km" else 1)
    return "run_algorithm", {"algorithm_id": "native:buffer",
                             "parameters": {"INPUT": layer, "DISTANCE": distance}}


def _zoom(text):
    m = re.match(r"^zoom\s+(?:to|on)\s+(.+)$", text)
    if not m:
        return None
    layer = _match(m.group(1), _layers())
    return ("zoom_to", {"layer_name": layer}) if layer else None


def _count(text):
    m = re.match(r"^(?:how many|count)\s+(?:features\s+(?:in|on)\s+)?(.+?)(?:\s+features)?$", text)
    if not m:
        return None
    layer = _match(m.group(1), _layers())
    return ("query_features", {"layer_name": layer, "expression": "TRUE", "limit": 1}) if layer else None


def _state(text):
    if re.match(r"^(?:what(?:'s| is) in (?:my |the )?project|project state|list layers|"
                r"what layers|show layers)\b", text):
        return "project_state", {}
    return None


def _save(text):
    return ("save_project", {}) if re.match(r"^save(?: the| my)? project$", text) else None


MATCHERS = (_state, _style_by, _style_single, _buffer, _zoom, _count, _save)


def parse(text):
    """(tool_name, args) for a recognised command, else None."""
    cleaned = re.sub(r"\s+", " ", (text or "").strip().lower()).rstrip(".!?")
    if not cleaned:
        return None
    for matcher in MATCHERS:
        try:
            hit = matcher(cleaned)
        except Exception:
            hit = None  # a parser must never break the chat
        if hit:
            return hit
    return None


def run(text):
    """Execute a recognised command. Returns the result text, or None to defer to the AI."""
    hit = parse(text)
    if not hit:
        return None
    name, args = hit
    return tools.run_tool(name, args)
