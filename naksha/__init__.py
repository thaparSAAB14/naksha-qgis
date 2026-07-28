def classFactory(iface):
    from .plugin import NakshaPlugin

    return NakshaPlugin(iface)
