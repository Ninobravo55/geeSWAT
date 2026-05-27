# -*- coding: utf-8 -*-
"""
geeswat_provider.py — geeSWAT
Proveedor de algoritmos Processing para geeSWAT.
"""
import os
from qgis.core import QgsProcessingProvider
from qgis.PyQt.QtGui import QIcon

from .Script.mde_descargar_mde import MDEDescargarMDE


class GeeSWATProvider(QgsProcessingProvider):
    """Agrupa todos los algoritmos de geeSWAT en el panel Processing."""

    def __init__(self):
        super().__init__()

    def id(self):
        return 'geeswat'

    def name(self):
        return 'geeSWAT'

    def longName(self):
        return 'geeSWAT — SWAT con Google Earth Engine'

    def icon(self):
        icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
        return QIcon(icon_path)

    def loadAlgorithms(self):
        self.addAlgorithm(MDEDescargarMDE())

    def supportedOutputRasterLayerExtensions(self):
        return ['tif']
