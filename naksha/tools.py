"""Naksha's hand-written project tools — the few things Processing doesn't cover.
Algorithm execution itself is introspected, see introspect.py."""

import os

from qgis.core import QgsProject


def _layer(name):
    """Resolve a project layer by exact name, or raise with the real names listed."""
    matches = QgsProject.instance().mapLayersByName(name)
    if not matches:
        names = ", ".join(l.name() for l in QgsProject.instance().mapLayers().values())
        raise ValueError(f"no layer named '{name}'. Layers: {names or '(none)'}")
    return matches[0]


def project_state(**_):
    """Compact snapshot of the open project, with CRS-mismatch flags."""
    proj = QgsProject.instance()
    proj_crs = proj.crs().authid()
    out = [f"project: {proj.fileName() or '(unsaved)'}   CRS: {proj_crs or '(none)'}"]
    layers = list(proj.mapLayers().values())
    out.append(f"layers ({len(layers)}):")
    for lyr in layers:
        crs = lyr.crs().authid()
        flag = "   <- CRS differs from project" if crs and proj_crs and crs != proj_crs else ""
        if hasattr(lyr, "featureCount"):
            fields = ", ".join(f.name() for f in lyr.fields())
            out.append(
                f"  [vector] {lyr.name()}   {lyr.featureCount()} features   {crs}   fields: {fields}{flag}"
            )
        elif hasattr(lyr, "width"):
            out.append(f"  [raster] {lyr.name()}   {lyr.width()}x{lyr.height()} px   {crs}{flag}")
        else:
            out.append(f"  [other ] {lyr.name()}   {crs}{flag}")
    return "\n".join(out)


def add_layer(path="", name="", **_):
    from qgis.core import QgsRasterLayer, QgsVectorLayer

    name = name or os.path.splitext(os.path.basename(path))[0]
    lyr = QgsVectorLayer(path, name, "ogr")
    if not lyr.isValid():
        lyr = QgsRasterLayer(path, name, "gdal")
    if not lyr.isValid():
        return f"error: could not load '{path}' as vector or raster"
    QgsProject.instance().addMapLayer(lyr)
    kind = f"{lyr.featureCount()} features" if hasattr(lyr, "featureCount") else "raster"
    return f"added '{name}' ({kind}, CRS {lyr.crs().authid()})"


def remove_layer(name="", **_):
    lyr = _layer(name)
    QgsProject.instance().removeMapLayer(lyr.id())
    return f"removed '{name}'"


def query_features(layer_name="", expression="", limit=10, **_):
    from qgis.core import QgsExpression, QgsFeatureRequest

    lyr = _layer(layer_name)
    exp = QgsExpression(expression)
    if exp.hasParserError():
        return f"error: bad expression: {exp.parserErrorString()}"
    count, samples = 0, []
    for f in lyr.getFeatures(QgsFeatureRequest(exp)):
        count += 1
        if len(samples) < int(limit):
            samples.append(dict(zip([fld.name() for fld in lyr.fields()], f.attributes())))
    return f"{count} features match on '{layer_name}'. First {len(samples)}: {samples}"


def style_layer(layer_name="", mode="single", color="", field="", **_):
    from qgis.core import QgsCategorizedSymbolRenderer, QgsRendererCategory, QgsSingleSymbolRenderer, QgsSymbol
    from qgis.PyQt.QtGui import QColor

    lyr = _layer(layer_name)
    if not hasattr(lyr, "renderer"):
        return f"error: '{layer_name}' is not a vector layer"
    if mode == "single":
        symbol = QgsSymbol.defaultSymbol(lyr.geometryType())
        if color:
            symbol.setColor(QColor(color))
        lyr.setRenderer(QgsSingleSymbolRenderer(symbol))
    elif mode == "categorized":
        if not field:
            return "error: categorized mode needs a field"
        idx = lyr.fields().indexOf(field)
        if idx < 0:
            return f"error: no field '{field}'. Fields: {[f.name() for f in lyr.fields()]}"
        values = sorted(lyr.uniqueValues(idx), key=str)
        categories = []
        for i, v in enumerate(values):
            symbol = QgsSymbol.defaultSymbol(lyr.geometryType())
            symbol.setColor(QColor.fromHsv(int(360 * i / max(len(values), 1)) % 360, 180, 220))
            categories.append(QgsRendererCategory(v, symbol, str(v)))
        lyr.setRenderer(QgsCategorizedSymbolRenderer(field, categories))
    else:
        # ponytail: graduated deferred — the classification API churned across 3.x
        return f"error: unknown mode '{mode}' (single | categorized)"
    lyr.triggerRepaint()
    return f"styled '{layer_name}' ({mode}{', by ' + field if field else ''})"


def zoom_to(layer_name="", **_):
    from qgis.utils import iface

    if iface is None:
        return "error: no map canvas (running headless)"
    lyr = _layer(layer_name)
    canvas = iface.mapCanvas()
    canvas.setExtent(canvas.mapSettings().layerExtentToOutputExtent(lyr, lyr.extent()))
    canvas.refresh()
    return f"zoomed to '{layer_name}'"


def layout_export(layout_name="", path="", **_):
    from qgis.core import QgsLayoutExporter

    layouts = QgsProject.instance().layoutManager().printLayouts()
    if not layouts:
        return "error: the project has no print layouts"
    if layout_name:
        # Falling back to layouts[0] on a name miss silently exported the WRONG
        # sheet - the worst possible failure, because the file looks fine.
        layout = next((l for l in layouts if l.name() == layout_name), None)
        if layout is None:
            names = ", ".join(repr(l.name()) for l in layouts)
            return f"error: no layout named '{layout_name}'. Layouts: {names}"
    else:
        layout = layouts[0]
    exporter = QgsLayoutExporter(layout)
    if path.lower().endswith(".pdf"):
        ok = exporter.exportToPdf(path, QgsLayoutExporter.PdfExportSettings())
    else:
        ok = exporter.exportToImage(path, QgsLayoutExporter.ImageExportSettings())
    if ok != QgsLayoutExporter.Success:
        return f"error: export failed (code {ok})"
    return f"exported layout '{layout.name()}' to {path}"


def save_project(path="", **_):
    proj = QgsProject.instance()
    ok = proj.write(path) if path else proj.write()
    return f"saved to {proj.fileName()}" if ok else "error: save failed (no path set?)"


def set_layer_display(layer_name="", visible=None, labels=None, **_):
    """Switch a layer on/off in the map, and turn its labels on/off.

    Both are layer *display* flags rather than style, so a .qml cannot set them -
    a layer can carry a perfectly good labelling definition and still draw nothing
    because labelsEnabled is false, or because the tree entry is unchecked.
    """
    layer = _layer(layer_name)
    done = []
    if visible is not None:
        node = QgsProject.instance().layerTreeRoot().findLayer(layer.id())
        if node is None:
            return f"error: '{layer_name}' is not in the layer tree"
        node.setItemVisibilityChecked(bool(visible))
        done.append(f"visible={bool(visible)}")
    if labels is not None:
        if not hasattr(layer, "setLabelsEnabled"):
            return f"error: '{layer_name}' is not a layer that can carry labels"
        layer.setLabelsEnabled(bool(labels))
        done.append(f"labels={bool(labels)}")
    layer.triggerRepaint()
    return f"{layer_name}: {', '.join(done)}" if done else "nothing to change"


def reload_plugin(**_):
    """Reload Naksha so newly added or edited tools appear, without restarting QGIS."""
    import qgis.utils
    from qgis.PyQt.QtCore import QTimer

    # Deferred on purpose: reloading unloads the bridge that is serving this very
    # request, so replying first is the difference between a clean answer and a
    # dead socket.
    QTimer.singleShot(400, lambda: qgis.utils.reloadPlugin("naksha"))
    return ("reload scheduled. The bridge stops and restarts on a NEW port within a "
            "couple of seconds - re-read ~/.naksha/bridge.json before the next call.")


# There is deliberately no run_python / exec escape hatch. Running model-authored
# Python inside QGIS is exactly the risk plugin review exists to catch (bandit B102,
# critical and not waivable), and the ~700 introspected Processing algorithms plus the
# project tools below cover the work. Humans who want raw PyQGIS already have QGIS's
# own Python Console.


def read_chat(**_):
    """Drain whatever the user typed into the Naksha panel since the last call."""
    from . import mailbox

    msgs = mailbox.take_user()
    if not msgs:
        return "(no new messages)"
    return "\n".join(f"[{i + 1}] {m['text']}" for i, m in enumerate(msgs))


def send_chat(text="", **_):
    """Put an answer back in the panel so the user never leaves QGIS."""
    from . import mailbox

    text = str(text).strip()
    if not text:
        return "error: nothing to send — pass the reply as 'text'"
    if mailbox.post_reply(text):
        return "shown in the Naksha panel"
    return "the Naksha panel is closed; held and shown when the user reopens it"


_STR = {"type": "string"}
TOOLS = {
    "project_state": {
        "description": "Snapshot of the current QGIS project: file, CRS, every layer with its "
        "type, feature count, fields, and any CRS mismatch.",
        "parameters": {"type": "object", "properties": {}},
        "func": project_state,
    },
    "add_layer": {
        "description": "Load a vector or raster file into the project.",
        "parameters": {
            "type": "object",
            "properties": {"path": _STR, "name": {"type": "string", "description": "optional display name"}},
            "required": ["path"],
        },
        "func": add_layer,
    },
    "remove_layer": {
        "description": "Remove a layer from the project by name.",
        "parameters": {"type": "object", "properties": {"name": _STR}, "required": ["name"]},
        "func": remove_layer,
    },
    "query_features": {
        "description": "Count and sample features matching a QGIS expression, e.g. \"population > 1000\".",
        "parameters": {
            "type": "object",
            "properties": {"layer_name": _STR, "expression": _STR, "limit": {"type": "number"}},
            "required": ["layer_name", "expression"],
        },
        "func": query_features,
    },
    "style_layer": {
        "description": "Style a vector layer: mode 'single' (one color) or 'categorized' (by field).",
        "parameters": {
            "type": "object",
            "properties": {
                "layer_name": _STR,
                "mode": {"type": "string", "enum": ["single", "categorized"]},
                "color": {"type": "string", "description": "color name or #hex, for single mode"},
                "field": {"type": "string", "description": "attribute field, for categorized mode"},
            },
            "required": ["layer_name", "mode"],
        },
        "func": style_layer,
    },
    "zoom_to": {
        "description": "Zoom the map canvas to a layer's extent.",
        "parameters": {"type": "object", "properties": {"layer_name": _STR}, "required": ["layer_name"]},
        "func": zoom_to,
    },
    "layout_export": {
        "description": "Export a print layout to PNG or PDF (by file extension).",
        "parameters": {
            "type": "object",
            "properties": {"layout_name": {"type": "string", "description": "blank = first layout"}, "path": _STR},
            "required": ["path"],
        },
        "func": layout_export,
    },
    "save_project": {
        "description": "Save the project (optionally to a new .qgz path).",
        "parameters": {"type": "object", "properties": {"path": _STR}},
        "func": save_project,
    },
    "set_layer_display": {
        "description": "Show or hide a layer on the map, and enable or disable its labels. "
        "These are display flags a style file cannot set, so use this when a layer has "
        "styling or labelling that is not appearing.",
        "parameters": {
            "type": "object",
            "properties": {
                "layer_name": _STR,
                "visible": {"type": "boolean", "description": "tick/untick it in the layer list"},
                "labels": {"type": "boolean", "description": "draw its labels or not"},
            },
            "required": ["layer_name"],
        },
        "func": set_layer_display,
    },
    "reload_plugin": {
        "description": "Reload Naksha inside the running QGIS so tools added or changed "
        "on disk become available. Use when a tool you expect is reported unknown. The "
        "bridge restarts on a new port.",
        "parameters": {"type": "object", "properties": {}},
        "func": reload_plugin,
    },
    "create_layout": {
        "description": "Build a print layout: map at a fixed scale, legend limited to the "
        "layers you name (so basemaps stay out of it), bar scale, north arrow, title and a "
        "source statement. Rebuilds the layout if one of that name already exists.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "layout name"},
                "title": _STR,
                "subtitle": _STR,
                "sources": {"type": "string", "description": "data source / credit text"},
                "scale": {"type": "number", "description": "map scale denominator, e.g. 50000"},
                "legend_layers": {"type": "array", "items": _STR,
                                  "description": "layer names to show in the legend, in order"},
                "extent_layer": {"type": "string", "description": "layer to centre the map on"},
                "width": {"type": "number", "description": "page width in mm (default 420 = A3)"},
                "height": {"type": "number", "description": "page height in mm (default 297)"},
                "lock_layers": {"type": "array", "items": _STR,
                                "description": "layer names the map item is pinned to, "
                                "independent of live canvas visibility"},
                "picture_path": {"type": "string", "description": "absolute path to an "
                                 "image (PNG/SVG) to place in a full-width band below the "
                                 "map - for a figure that isn't a georeferenced layer"},
                "picture_height": {"type": "number", "description": "height of the picture "
                                   "band in mm (default 100)"},
                "elevation_lines_layer": {"type": "string", "description": "a line layer "
                                          "already in the project, one feature per "
                                          "cross-section - each gets a real native "
                                          "elevation profile panel stacked below the map"},
                "elevation_source_layers": {"type": "array", "items": _STR,
                                            "description": "raster/mesh layer names to draw "
                                            "elevation from in the profile panels"},
                "elevation_panel_height": {"type": "number", "description": "height per "
                                           "profile panel in mm (default 55)"},
                "map_enabled": {"type": "boolean", "description": "set False for a sheet "
                                "that is pure figure - no map, legend, scale bar or north "
                                "arrow - giving that whole area to picture_path or the "
                                "elevation panels instead (default True)"},
                "chart_layers": {"type": "array", "items": _STR,
                                 "description": "layer names to stack as plain map panels "
                                 "with a coordinate grid (chart axes) - for data that is "
                                 "itself an ordinary editable layer, e.g. a profile built "
                                 "as real polygons in a distance/elevation space"},
                "chart_panel_height": {"type": "number", "description": "height per chart "
                                       "panel in mm (default 55)"},
                "chart_x_max": {"type": "number", "description": "shared X-axis max across "
                                "all chart panels (default: the largest layer extent)"},
                "chart_y_max": {"type": "number", "description": "shared Y-axis max across "
                                "all chart panels (default: the largest layer extent)"},
                "chart_grid_x": {"type": "number", "description": "gridline spacing on X, "
                                 "in layer coordinate units (default 2000)"},
                "chart_grid_y": {"type": "number", "description": "gridline spacing on Y, "
                                 "in layer coordinate units (default 1000)"},
                "chart_vertical_exaggeration": {"type": "number", "description": "if the "
                                                "chart layer's Y coordinate is elevation*N "
                                                "(vertical exaggeration), pass N here to get "
                                                "an honest caption with the true spacing "
                                                "instead of a misleading raw axis label"},
            },
        },
        "func": None,  # bound below, so importing layout.py stays lazy
    },
}


def _create_layout(**kwargs):
    from .layout import create_layout

    return create_layout(**kwargs)


TOOLS["create_layout"]["func"] = _create_layout

# Appended rather than declared inline so project_state stays the first tool a model
# sees — it is the one that orients it, and ordering is the only nudge we get.
TOOLS["read_chat"] = {
    "description": "Read what the user has typed into the Naksha chat panel inside QGIS and "
    "not yet had answered. Returns '(no new messages)' when nothing is waiting — it never "
    "blocks, so poll it every few seconds while you are working with this user. Reading a "
    "message marks it delivered, so each one arrives once. Answer with send_chat rather than "
    "in your own window: the point is that the user never has to switch away from QGIS.",
    "parameters": {"type": "object", "properties": {}},
    "func": read_chat,
}
TOOLS["send_chat"] = {
    "description": "Show a message to the user in the Naksha chat panel inside QGIS. Use it "
    "for every reply to something read_chat gave you, and for progress notes during long "
    "jobs, so the user can follow along without leaving the map.",
    "parameters": {
        "type": "object",
        "properties": {"text": {"type": "string", "description": "what the user should read"}},
        "required": ["text"],
    },
    "func": send_chat,
}


def openai_tool_specs():
    return [
        {
            "type": "function",
            "function": {"name": name, "description": t["description"], "parameters": t["parameters"]},
        }
        for name, t in TOOLS.items()
    ]


# self-heal seeds: translate common failures into a plain-language next move
_HINTS = (
    ("crs", "the layers are probably in different CRSs — reproject with native:reprojectlayer first"),
    ("projection", "the layers are probably in different CRSs — reproject with native:reprojectlayer first"),
    ("geometry", "run native:fixgeometries on the input, then retry"),
    ("lock", "the file is locked by another program — write to a new output path"),
    ("in use", "the file is locked by another program — write to a new output path"),
    ("field", "check the real field names via project_state before retrying"),
    ("permission", "no write access there — use a different folder or TEMPORARY_OUTPUT"),
)


def _hint(err):
    low = str(err).lower()
    for needle, hint in _HINTS:
        if needle in low:
            return f"  Hint: {hint}"
    return ""


# read_chat/send_chat touch the chat panel, never the project, so they are never
# worth an approval prompt — gating them would stall the relay on every reply.
READ_ONLY = {"project_state", "search_algorithms", "describe_algorithm", "query_features",
             "read_chat", "send_chat"}


def run_tool(name, args):
    if name not in TOOLS:
        # A stale plugin is the usual cause: the tool exists on disk but this QGIS
        # loaded before it was written. Say so rather than just denying the name.
        return (f"error: unknown tool '{name}'. Available: {', '.join(sorted(TOOLS))}."
                f" If you expected a newer tool, this QGIS may be running older code"
                f" - call reload_plugin.")
    try:
        return str(TOOLS[name]["func"](**args))
    except Exception as e:  # result goes back to the model, which can react
        return f"error: {e}{_hint(e)}"


from . import introspect  # noqa: E402  (no cycle: introspect never imports tools)

TOOLS.update(introspect.TOOLS)
