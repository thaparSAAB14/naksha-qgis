import os


def _version():
    """Single source of truth: metadata.txt is what QGIS reads."""
    path = os.path.join(os.path.dirname(__file__), "metadata.txt")
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("version="):
                    return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return "0"


__version__ = _version()


def classFactory(iface):
    from .plugin import NakshaPlugin

    return NakshaPlugin(iface)
