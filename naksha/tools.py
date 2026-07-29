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
    layout = next((l for l in layouts if l.name() == layout_name), layouts[0])
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


# There is deliberately no run_python / exec escape hatch. Running model-authored
# Python inside QGIS is exactly the risk plugin review exists to catch (bandit B102,
# critical and not waivable), and the ~700 introspected Processing algorithms plus the
# project tools below cover the work. Humans who want raw PyQGIS already have QGIS's
# own Python Console.


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


READ_ONLY = {"project_state", "search_algorithms", "describe_algorithm", "query_features"}


def run_tool(name, args):
    if name not in TOOLS:
        return f"error: unknown tool '{name}'"
    try:
        return str(TOOLS[name]["func"](**args))
    except Exception as e:  # result goes back to the model, which can react
        return f"error: {e}{_hint(e)}"


from . import introspect  # noqa: E402  (no cycle: introspect never imports tools)

TOOLS.update(introspect.TOOLS)
