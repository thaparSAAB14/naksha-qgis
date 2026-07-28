"""Naksha's tool layer. M1: project_state only; Processing introspection lands in M2."""

from qgis.core import QgsProject


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


TOOLS = {
    "project_state": {
        "description": "Snapshot of the current QGIS project: file, CRS, every layer with its "
        "type, feature count, fields, and any CRS mismatch.",
        "parameters": {"type": "object", "properties": {}},
        "func": project_state,
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


def run_tool(name, args):
    if name not in TOOLS:
        return f"error: unknown tool '{name}'"
    try:
        return str(TOOLS[name]["func"](**args))
    except Exception as e:  # result goes back to the model, which can react
        return f"error: {e}"
