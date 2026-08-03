"""Composing a print layout.

Running an algorithm is only half of GIS work; the other half is the sheet somebody
prints. QGIS exposes the whole layout API, so the agent can build a real map -
fixed scale, a legend restricted to the layers that matter, bar scale, north arrow,
title and a source statement - rather than leaving the user to place items by hand.
"""

from qgis.core import (
    QgsLayerTreeGroup,
    QgsLayerTreeLayer,
    QgsLayoutItemLabel,
    QgsLayoutItemLegend,
    QgsLayoutItemMap,
    QgsLayoutItemPicture,
    QgsLayoutItemScaleBar,
    QgsLayoutMeasurement,
    QgsLayoutPoint,
    QgsLayoutSize,
    QgsPrintLayout,
    QgsProject,
    QgsTextFormat,
    QgsUnitTypes,
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QFont

MM = QgsUnitTypes.LayoutMillimeters


def _prune(group, keep_ids):
    """Drop every legend node whose layer was not asked for, groups included.

    This is what keeps basemaps out of the legend: a legend built from the layer
    tree otherwise lists every visible raster, which on a printed sheet is noise
    at best and a licensing claim at worst.
    """
    for node in list(group.children()):
        if isinstance(node, QgsLayerTreeGroup):
            _prune(node, keep_ids)
            if not node.children():
                group.removeChildNode(node)
        elif isinstance(node, QgsLayerTreeLayer):
            if node.layer() is None or node.layer().id() not in keep_ids:
                group.removeChildNode(node)


def _text_format(size, bold=False, colour="#1a1a1a"):
    """QgsTextFormat, not the deprecated setFont/setFontColor pair - and it takes a
    float point size, which QFont's constructor does not."""
    font = QFont("Segoe UI")
    font.setBold(bold)
    fmt = QgsTextFormat()
    fmt.setFont(font)
    fmt.setSize(float(size))
    fmt.setSizeUnit(QgsUnitTypes.RenderPoints)
    fmt.setColor(QColor(colour))
    return fmt


def _label(layout, text, x, y, width, height, size, bold=False, colour="#1a1a1a"):
    item = QgsLayoutItemLabel(layout)
    item.setText(text)
    item.setTextFormat(_text_format(size, bold, colour))
    layout.addLayoutItem(item)
    item.attemptMove(QgsLayoutPoint(x, y, MM))
    item.attemptResize(QgsLayoutSize(width, height, MM))
    return item


def create_layout(name="Naksha map", title="", subtitle="", sources="", scale=50000,
                  legend_layers=None, extent_layer="", width=420, height=297, **_):
    """Build (or rebuild) a print layout and return a description of it."""
    proj = QgsProject.instance()
    manager = proj.layoutManager()
    for old in [lay for lay in manager.printLayouts() if lay.name() == name]:
        manager.removeLayout(old)  # rebuild in place rather than pile up duplicates

    layout = QgsPrintLayout(proj)
    layout.initializeDefaults()
    layout.setName(name)
    layout.pageCollection().page(0).setPageSize(QgsLayoutSize(width, height, MM))

    margin = 12.0
    legend_w = 62.0
    header = 20.0 if title else margin
    map_w = width - legend_w - margin * 3
    map_h = height - header - margin * 2

    # --- map ---------------------------------------------------------------
    map_item = QgsLayoutItemMap(layout)
    map_item.setRect(0, 0, map_w, map_h)  # must exist before it can be moved
    layout.addLayoutItem(map_item)
    map_item.attemptMove(QgsLayoutPoint(margin, header + 4, MM))
    map_item.attemptResize(QgsLayoutSize(map_w, map_h, MM))

    target = proj.mapLayersByName(extent_layer)
    if target:
        extent = target[0].extent()
        # A single point, or one feature, has zero width - zooming to that leaves the
        # map with no scale at all (0.0) and setScale then has nothing to work from.
        if extent.isEmpty() or extent.width() <= 0 or extent.height() <= 0:
            extent.grow(max(extent.width(), extent.height(), 1.0))
        map_item.zoomToExtent(extent)
    map_item.setScale(float(scale))  # fixed scale is the point; set it last
    map_item.setFrameEnabled(True)
    map_item.setFrameStrokeWidth(QgsLayoutMeasurement(0.3, MM))

    # --- legend ------------------------------------------------------------
    legend = QgsLayoutItemLegend(layout)
    legend.setLinkedMap(map_item)
    legend.setTitle("Legend")
    layout.addLayoutItem(legend)
    wanted = []
    for wanted_name in (legend_layers or []):
        wanted.extend(proj.mapLayersByName(wanted_name))
    if wanted:
        legend.setAutoUpdateModel(False)
        _prune(legend.model().rootGroup(), {lyr.id() for lyr in wanted})
    legend.setResizeToContents(True)
    legend.attemptMove(QgsLayoutPoint(margin * 2 + map_w, header + 4, MM))
    legend.attemptResize(QgsLayoutSize(legend_w, map_h * 0.7, MM))

    # --- title block -------------------------------------------------------
    if title:
        _label(layout, title, margin, margin * 0.5, map_w, 9, 16, bold=True)
    if subtitle:
        _label(layout, subtitle, margin, margin * 0.5 + 9, map_w, 6, 9, colour="#555555")

    # --- bar scale ---------------------------------------------------------
    bar = QgsLayoutItemScaleBar(layout)
    bar.setStyle("Single Box")
    bar.setLinkedMap(map_item)
    bar.applyDefaultSize(QgsUnitTypes.DistanceKilometers)
    bar.setTextFormat(_text_format(7))
    layout.addLayoutItem(bar)
    bar.attemptMove(QgsLayoutPoint(margin + 2, header + map_h - 10, MM))

    # --- north arrow (QGIS ships the SVG; skip quietly if the theme lacks it)
    from qgis.core import QgsApplication

    for svg_dir in QgsApplication.svgPaths():
        candidate = f"{svg_dir}/arrows/NorthArrow_02.svg".replace("//", "/")
        picture = QgsLayoutItemPicture(layout)
        picture.setPicturePath(candidate)
        if picture.mode() != QgsLayoutItemPicture.FormatUnknown:
            layout.addLayoutItem(picture)
            picture.attemptMove(QgsLayoutPoint(margin + map_w - 16, header + 8, MM))
            picture.attemptResize(QgsLayoutSize(12, 12, MM))
            break

    # --- scale statement and sources ---------------------------------------
    _label(layout, f"Scale 1:{int(scale):,}".replace(",", " "),
           margin * 2 + map_w, header + 4 + map_h * 0.7 + 4, legend_w, 5, 8, bold=True)
    if sources:
        _label(layout, sources, margin * 2 + map_w,
               header + 4 + map_h * 0.7 + 11, legend_w, map_h * 0.3 - 12, 6.5,
               colour="#555555")

    manager.addLayout(layout)
    shown = [n.layer().name() for n in legend.model().rootGroup().findLayers() if n.layer()]
    lines = [f"layout '{name}' created: {width}x{height} mm, map at 1:{int(scale):,}",
             f"  legend lists {len(shown)}: {', '.join(shown) or '(all layers)'}"]
    missing = [lyr.name() for lyr in wanted if lyr.name() not in shown]
    if missing:
        # A legend is built from the layer tree, so a layer that was loaded without
        # being added to it can never appear. Say so instead of returning a blank box.
        lines.append(f"  WARNING: not in the legend (absent from the layer tree): "
                     f"{', '.join(missing)}")
    lines.append(f"  open it with Project > Layouts > {name}")
    return "\n".join(lines)
