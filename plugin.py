# -*- coding: utf-8 -*-
"""
plugin.py — geeSWAT
Punto de entrada principal del plugin: registra el menú en QGIS
y el proveedor de algoritmos Processing.
"""
import os
from qgis.PyQt.QtWidgets import QAction, QMenu, QMessageBox
from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsApplication

from .geeswat_provider import GeeSWATProvider


class GeeSWATPlugin:
    """Plugin principal de geeSWAT."""

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.provider = None
        self.menu = None
        self.actions = []

    # ──────────────────────────────────────────────────────────────────────────
    # QGIS lifecycle
    # ──────────────────────────────────────────────────────────────────────────
    def initGui(self):
        """Registra el proveedor Processing y construye el menú."""
        # Processing provider
        self.provider = GeeSWATProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

        # Icono principal
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        icon_main = QIcon(icon_path)

        # Menú raíz
        self.menu = QMenu('geeSWAT', self.iface.mainWindow())
        self.menu.setIcon(icon_main)
        self.iface.pluginMenu().addMenu(self.menu)

        # ── Acción principal: abrir geeSWAT ───────────────────────────────────
        action_config = QAction(icon_main, 'geeSWAT 1.2', self.iface.mainWindow())
        action_config.setToolTip(
            'geeSWAT 1.2 — SWAT con Google Earth Engine\n'
            'AOI | DEM | SOIL | Proyección del proyecto')
        action_config.triggered.connect(self._abrir_config)
        self.menu.addAction(action_config)
        self.actions.append(action_config)

        # Botón también en la barra de herramientas de QGIS
        self.iface.addToolBarIcon(action_config)

        self.menu.addSeparator()

        # ── Instalar dependencias ─────────────────────────────────────────
        action_deps = QAction(
            QIcon(os.path.join(self.plugin_dir, 'Icons', 'dep.png')),
            'Instalar dependencias de Python...',
            self.iface.mainWindow()
        )
        action_deps.triggered.connect(self._check_dependencies)
        self.menu.addAction(action_deps)
        self.actions.append(action_deps)

        # ── Diálogo persistente (se crea al primer uso) ─────────────────────
        self._dialog = None

    def unload(self):
        """Desregistra el plugin."""
        if self.provider:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None
        if self.menu:
            self.iface.pluginMenu().removeAction(self.menu.menuAction())
            self.menu = None
        for action in self.actions:
            self.iface.removeToolBarIcon(action)
        self.actions.clear()
        if self._dialog:
            self._dialog.close()
            self._dialog = None

    # ──────────────────────────────────────────────────────────────────────────
    # Slots
    # ──────────────────────────────────────────────────────────────────────────
    def _abrir_config(self):
        """Abre el diálogo principal (pestaña Config GEE)."""
        if self._dialog is None:
            from .geeswat_dialog import GeeSWATDialog
            self._dialog = GeeSWATDialog(self.iface)
        self._dialog.show()
        self._dialog.raise_()
        self._dialog.activateWindow()



    # ──────────────────────────────────────────────────────────────────────────
    # Dependencias
    # ──────────────────────────────────────────────────────────────────────────
    def _check_dependencies(self):
        missing = []
        try:
            import ee  # noqa: F401
        except ImportError:
            missing.append('earthengine-api')
        try:
            import requests  # noqa: F401
        except ImportError:
            missing.append('requests')

        if missing:
            msg = QMessageBox(self.iface.mainWindow())
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle('geeSWAT — Instalar Dependencias')
            msg.setText(
                f'Faltan las siguientes bibliotecas de Python:\n\n'
                f'{chr(10).join("  • " + m for m in missing)}\n\n'
                '¿Desea intentar instalarlas ahora?\n'
                '(QGIS se congelará brevemente mientras descarga los archivos.)'
            )
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            if msg.exec_() == QMessageBox.Yes:
                self._install_dependencies(missing)
        else:
            QMessageBox.information(
                self.iface.mainWindow(),
                'geeSWAT — Dependencias',
                'Todas las dependencias necesarias ya están instaladas.'
            )

    def _install_dependencies(self, missing):
        import sys
        import subprocess  # nosec
        import tempfile

        osgeo4w_root = os.environ.get('OSGEO4W_ROOT')
        if os.name == 'nt' and osgeo4w_root:
            bat_path = os.path.join(osgeo4w_root, 'OSGeo4W.bat')
            deps = ' '.join(missing)
            script = (
                '@echo off\ncolor 0A\n'
                'echo ============================================================\n'
                'echo Instalando dependencias de geeSWAT...\n'
                'echo ============================================================\n'
                f'call "{bat_path}" python -m pip install {deps}\n'
                'echo.\necho Instalacion completada. Reinicia QGIS.\npause\n'
            )
            tmp = os.path.join(tempfile.gettempdir(), 'install_geeswat_deps.bat')
            with open(tmp, 'w') as f:
                f.write(script)
            subprocess.Popen(['cmd.exe', '/c', 'start', 'cmd.exe', '/c', tmp])  # nosec
            QMessageBox.information(
                self.iface.mainWindow(), 'geeSWAT — Instalando',
                'Se ha abierto una ventana de terminal.\n'
                'Espera a que termine y luego REINICIA QGIS.'
            )
        else:
            try:
                python_exe = sys.executable
                subprocess.check_call([python_exe, '-m', 'pip', 'install', *missing])  # nosec
                QMessageBox.information(
                    self.iface.mainWindow(), 'geeSWAT — Éxito',
                    'Dependencias instaladas. Reinicia QGIS.'
                )
            except Exception as ex:
                QMessageBox.critical(
                    self.iface.mainWindow(), 'geeSWAT — Error',
                    f'Instalación automática fallida.\n\n'
                    f'Instala manualmente en OSGeo4W Shell:\n'
                    f'python -m pip install {" ".join(missing)}\n\n'
                    f'Detalle: {str(ex)}'
                )
