# -*- coding: utf-8 -*-
def classFactory(iface):
    try:
        from .plugin import GeeSWATPlugin
        return GeeSWATPlugin(iface)
    except Exception as e:
        from qgis.PyQt.QtWidgets import QMessageBox
        QMessageBox.critical(
            None,
            'geeSWAT — Error de carga',
            f'Error al cargar el plugin:\n\n{str(e)}\n\n'
            'Solución: Desinstala el plugin, cierra QGIS completamente, '
            'vuelve a abrirlo e instala de nuevo desde el ZIP.'
        )
        raise
