"""The core bet: tools are introspected from Processing, never hand-written.

Every QgsProcessingAlgorithm describes itself, so the catalogue is generated.
~1000 algorithms can't fit in a prompt — the agent discovers at runtime via
search_algorithms -> describe_algorithm -> run_algorithm.
"""

from qgis.core import QgsApplication, QgsMapLayer, QgsProcessingParameterDefinition

_NUMERIC = {"number", "distance", "scale", "duration"}
_SINKS = {"sink", "vectorDestination", "rasterDestination", "fileDestination"}


def _params(alg):
    """Visible parameter definitions of an algorithm."""
    return [
        p
        for p in alg.parameterDefinitions()
        if not (p.flags() & QgsProcessingParameterDefinition.FlagHidden)
    ]


def search_algorithms(query="", **_):
    """Rank by how many query terms match, so a natural phrase still finds things.
    Requiring every term (the obvious implementation) makes 'valid geometry check'
    miss qgis:checkvalidity, which is exactly how a model phrases a search."""
    terms = query.lower().split()
    hits = []
    for alg in QgsApplication.processingRegistry().algorithms():
        hay = f"{alg.id()} {alg.displayName()} {' '.join(alg.tags())}".lower()
        score = sum(t in hay for t in terms)
        if score:
            hits.append((-score, alg.id(), f"{alg.id()} — {alg.displayName()}"))
    if not hits:
        return f"no algorithms match '{query}'"
    hits.sort()
    shown = [h[2] for h in hits[:30]]
    more = f"\n… and {len(hits) - 30} more; refine the query" if len(hits) > 30 else ""
    return "\n".join(shown) + more


def describe_algorithm(algorithm_id="", **_):
    alg = QgsApplication.processingRegistry().algorithmById(algorithm_id)
    if alg is None:
        return f"error: no algorithm '{algorithm_id}' — try search_algorithms"
    out = [f"{alg.id()} — {alg.displayName()}", (alg.shortHelpString() or "").strip()[:600], "parameters:"]
    for p in _params(alg):
        opt = " (optional)" if p.flags() & QgsProcessingParameterDefinition.FlagOptional else ""
        default = f"  default={p.defaultValue()!r}" if p.defaultValue() is not None else ""
        enum = f"  options={p.options()}" if hasattr(p, "options") and p.type() == "enum" else ""
        out.append(f"  {p.name()} [{p.type()}]{opt}: {p.description()}{default}{enum}")
    out.append("Layer parameters accept a layer name from the project or a file path. "
               "Output parameters default to a temporary layer if omitted.")
    return "\n".join(out)


def run_algorithm(algorithm_id="", parameters=None, **_):
    import processing  # deferred: needs Processing initialized (plugin load / test setup)
    from qgis.core import QgsProject

    alg = QgsApplication.processingRegistry().algorithmById(algorithm_id)
    if alg is None:
        return f"error: no algorithm '{algorithm_id}' — try search_algorithms"
    params = dict(parameters or {})
    for p in _params(alg):
        required = not (p.flags() & QgsProcessingParameterDefinition.FlagOptional)
        if p.type() in _SINKS and p.name() not in params and required:
            params[p.name()] = "TEMPORARY_OUTPUT"
    result = processing.run(algorithm_id, params)

    short = algorithm_id.split(":")[-1]
    out = [f"{algorithm_id} finished:"]
    for key, val in result.items():
        if isinstance(val, QgsMapLayer):
            val.setName(f"{short}_{key.lower()}")
            QgsProject.instance().addMapLayer(val)
            if hasattr(val, "featureCount"):
                n = val.featureCount()
                warn = "  WARNING: 0 features — verify inputs (CRS mismatch? wrong filter?)" if n == 0 else ""
                out.append(f"  {key}: layer '{val.name()}' added — "
                           f"{n} features, CRS {val.crs().authid()}{warn}")
            else:
                out.append(f"  {key}: layer '{val.name()}' added — CRS {val.crs().authid()}")
        else:
            out.append(f"  {key}: {val!r}")
    return "\n".join(out)


TOOLS = {
    "search_algorithms": {
        "description": "Search every installed Processing algorithm by keyword, best matches "
        "first. Returns 'id — name' lines. Always the first step before running one.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "keywords, e.g. 'buffer' or 'clip raster'"}},
            "required": ["query"],
        },
        "func": search_algorithms,
    },
    "describe_algorithm": {
        "description": "Full parameter list, types, defaults and help for one algorithm id.",
        "parameters": {
            "type": "object",
            "properties": {"algorithm_id": {"type": "string", "description": "e.g. 'native:buffer'"}},
            "required": ["algorithm_id"],
        },
        "func": describe_algorithm,
    },
    "run_algorithm": {
        "description": "Execute a Processing algorithm. Layer params take a project layer "
        "name or file path; omitted outputs become temporary layers, which are added to the "
        "project and reported with real feature counts.",
        "parameters": {
            "type": "object",
            "properties": {
                "algorithm_id": {"type": "string"},
                "parameters": {"type": "object", "description": "algorithm parameters by name"},
            },
            "required": ["algorithm_id"],
        },
        "func": run_algorithm,
    },
}
