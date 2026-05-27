# -*- coding: utf-8 -*-
"""
geeswat_dialog.py — geeSWAT v1.1.0
Diálogo principal: Config GEE · Seleccionar AOI · MDE
La descarga del MDE corre en un QThread para no bloquear QGIS.
"""
import os
import math
import time
import datetime

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QLineEdit, QPushButton, QProgressBar,
    QFileDialog, QMessageBox,
    QGroupBox, QGridLayout, QScrollArea, QFrame,
    QComboBox, QSpinBox, QSplitter, QSizePolicy, QTextEdit
)
from qgis.PyQt.QtCore import Qt, QSettings, QTimer, QUrl, QThread, pyqtSignal
from qgis.PyQt.QtGui import (
    QFont, QDesktopServices, QPixmap, QColor,
    QPainter, QBrush, QPen, QPainterPath, QPolygon
)
from qgis.PyQt.QtCore import QPoint

from qgis.core import (
    QgsProject, QgsVectorLayer, QgsRasterLayer,
    QgsGeometry, QgsPointXY,
    QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsDistanceArea, QgsWkbTypes
)
from qgis.gui import QgsMapToolEmitPoint, QgsRubberBand

try:
    import ee
    EE_DISPONIBLE = True
except ImportError:
    EE_DISPONIBLE = False

# ── Paleta geeSWAT ────────────────────────────────────────────────────────────
AZUL     = '#0D47A1'
AZUL_M   = '#1565C0'
AZUL_C   = '#E3F2FD'
AZUL_OS  = '#0A2F6E'
VERDE    = '#1B5E20'
VERDE_M  = '#2E7D32'
VERDE_C  = '#E8F5E9'
NARANJA  = '#E65100'
NARANJA_C= '#FFF3E0'
ROJO     = '#C62828'
ROJO_C   = '#FFEBEE'
GRIS     = '#37474F'
GRIS_C   = '#ECEFF1'
GRIS_OS  = '#263238'
CYAN     = '#006064'
CYAN_C   = '#E0F7FA'

# ── Catálogo DEMs (igual que el algoritmo Processing) ────────────────────────
GEE_DEMS = [
    {'label': 'SRTM GL1 — 30 m global (NASA/USGS)',
     'collection': 'USGS/SRTMGL1_003', 'band': 'elevation',
     'scale': 30, 'tipo': 'Image', 'dtype': 'Int16',
     'desc': 'SRTM 1 arc-sec. Global 56S-60N. Datum EGM96.'},
    {'label': 'Copernicus DEM GLO-30 — 30 m global',
     'collection': 'COPERNICUS/DEM/GLO30', 'band': 'DEM',
     'scale': 30, 'tipo': 'ImageCollection', 'dtype': 'Float32',
     'desc': 'TanDEM-X. Cobertura global. Alta precisión.'},
    {'label': 'NASADEM — 30 m global (NASA)',
     'collection': 'NASA/NASADEM_HGT/001', 'band': 'elevation',
     'scale': 30, 'tipo': 'Image', 'dtype': 'Int16',
     'desc': 'SRTM reprocesado con ASTER/ICESat. Global.'},
    {'label': 'ALOS AW3D30 — 30 m global (JAXA)',
     'collection': 'JAXA/ALOS/AW3D30/V3_2', 'band': 'DSM',
     'scale': 30, 'tipo': 'ImageCollection', 'dtype': 'Float32',
     'desc': 'DSM global de ALOS PRISM. JAXA.'},
    {'label': 'MERIT DEM — 90 m global (corregido)',
     'collection': 'MERIT/DEM/v1_0_3', 'band': 'dem',
     'scale': 90, 'tipo': 'Image', 'dtype': 'Float32',
     'desc': 'SRTM/AW3D30 corregido por vegetación y speckle. Ideal SWAT.'},
    {'label': 'SRTM 90 m (CGIAR-CSI v4)',
     'collection': 'CGIAR/SRTM90_V4', 'band': 'elevation',
     'scale': 90, 'tipo': 'Image', 'dtype': 'Int16',
     'desc': 'SRTM 90 m con vacíos rellenados. CGIAR-CSI v4.'},
    {'label': 'HydroSHEDS — 90 m void-filled (WWF)',
     'collection': 'WWF/HydroSHEDS/03VFDEM', 'band': 'b1',
     'scale': 90, 'tipo': 'Image', 'dtype': 'Int16',
     'desc': 'DEM hidrológicamente acondicionado. Excelente para SWAT.'},
    {'label': 'ASTER GDEM v3 — 30 m global (NASA/METI)',
     'collection': 'NASA/ASTER_GED/AG100_003', 'band': 'elevation',
     'scale': 30, 'tipo': 'Image', 'dtype': 'Float32',
     'desc': 'ASTER GDEM v3. Cobertura 83N-83S.'},
    {'label': '3DEP 1 m (solo EE.UU.) — USGS',
     'collection': 'USGS/3DEP/1m', 'band': 'elevation',
     'scale': 1, 'tipo': 'ImageCollection', 'dtype': 'Float32',
     'desc': '3D Elevation Program 1 metro. Solo EE.UU.'},
]
DEM_LABELS = [d['label'] for d in GEE_DEMS]
LIMITE_MP  = 10_000_000
GDRIVE_FOLDER = 'GEE_geeSWAT'
DTYPE_BYTES   = {'Int16': 2, 'Int32': 4, 'Float32': 4, 'Float64': 8, 'Byte': 1}


# ── Estilos ───────────────────────────────────────────────────────────────────
def _btn_primario(color=AZUL_M, hover=AZUL):
    return (f'QPushButton {{background:{color};color:white;border:none;'
            f'border-radius:6px;padding:9px 18px;font-weight:bold;font-size:12px;}}'
            f'QPushButton:hover {{background:{hover};}}'
            f'QPushButton:disabled {{background:#90A4AE;color:#CFD8DC;}}')

def _btn_secundario():
    return (f'QPushButton {{background:white;color:{GRIS};border:1.5px solid #B0BEC5;'
            f'border-radius:6px;padding:7px 15px;font-size:11px;}}'
            f'QPushButton:hover {{background:{GRIS_C};}}'
            f'QPushButton:disabled {{color:#B0BEC5;}}')

def _btn_exito():
    return _btn_primario(VERDE_M, VERDE)

def _btn_peligro():
    return _btn_primario(NARANJA, '#BF360C')

def _grupo(titulo, color=AZUL):
    g = QGroupBox(titulo)
    g.setStyleSheet(
        f'QGroupBox {{font-weight:bold;color:{color};border:1.5px solid #CFD8DC;'
        f'border-radius:8px;margin-top:10px;padding:12px;}}'
        f'QGroupBox::title {{subcontrol-origin:margin;left:12px;padding:0 5px;}}')
    return g


# ═════════════════════════════════════════════════════════════════════════════
# WORKER THREAD — Descarga MDE
# ═════════════════════════════════════════════════════════════════════════════
class MDEWorker(QThread):
    log     = pyqtSignal(str)          # mensaje de progreso
    progreso= pyqtSignal(int)          # 0-100
    ok      = pyqtSignal(str, bool)    # (ruta_archivo, via_drive)
    error   = pyqtSignal(str)

    def __init__(self, dem_info, lon_min, lat_min, lon_max, lat_max,
                 scale_eff, output_path, project_id, gmail):
        super().__init__()
        self.dem_info    = dem_info
        self.lon_min     = lon_min
        self.lat_min     = lat_min
        self.lon_max     = lon_max
        self.lat_max     = lat_max
        self.scale_eff   = scale_eff
        self.output_path = output_path
        self.project_id  = project_id
        self.gmail       = gmail
        self._cancelar   = False

    def cancelar(self):
        self._cancelar = True

    def run(self):
        try:
            import ee
            # ── Conectar GEE ──────────────────────────────────────────────
            kwargs = {}
            if self.project_id.strip():
                kwargs['project'] = self.project_id.strip()
            self.log.emit(f"Conectando GEE — proyecto: {self.project_id or '(credenciales locales)'}")
            ee.Initialize(opt_url='https://earthengine.googleapis.com', **kwargs)
            self.log.emit("✔ Conexión GEE exitosa.")

            # ── Construir imagen ──────────────────────────────────────────
            dem_info = self.dem_info
            region   = ee.Geometry.Rectangle([
                self.lon_min, self.lat_min, self.lon_max, self.lat_max])

            cid  = dem_info['collection']
            band = dem_info['band']
            if dem_info['tipo'] == 'Image':
                imagen = ee.Image(cid).select(band).clip(region)
            else:
                imagen = (ee.ImageCollection(cid)
                            .filterBounds(region).mosaic()
                            .select(band).clip(region))

            # ── Estimar tamaño ─────────────────────────────────────────────
            lat_med  = (self.lat_min + self.lat_max) / 2.0
            cos_lat  = math.cos(math.radians(lat_med))
            ancho_m  = (self.lon_max - self.lon_min) * 111320.0 * cos_lat
            alto_m   = (self.lat_max - self.lat_min) * 111320.0
            px_x     = max(1, int(ancho_m / self.scale_eff))
            px_y     = max(1, int(alto_m  / self.scale_eff))
            total_px = px_x * px_y
            bpp      = DTYPE_BYTES.get(dem_info['dtype'], 4)
            peso_mb  = total_px * bpp / 1_048_576

            self.log.emit(f"DEM            : {dem_info['label']}")
            self.log.emit(f"Escala efectiva: {self.scale_eff} m")
            self.log.emit(f"Dimensión      : {px_y} × {px_x} px  ({total_px/1e6:.2f} MP | ~{peso_mb:.1f} MB)")

            usar_drive = total_px > LIMITE_MP

            if usar_drive:
                self.log.emit(f"⚠ Área grande ({total_px/1e6:.1f} MP) → exportando a Google Drive / {GDRIVE_FOLDER}")
                self._exportar_drive(ee, imagen, region)
            else:
                self.log.emit(f"✔ Tamaño dentro del límite ({peso_mb:.1f} MB) → descarga directa")
                self._descarga_directa(ee, imagen, region)

        except Exception as ex:
            self.error.emit(str(ex))

    def _descarga_directa(self, ee, imagen, region):
        import zipfile, shutil, requests
        from urllib.parse import urlparse

        self.log.emit("Generando URL de descarga en GEE...")
        try:
            url = imagen.getDownloadURL({
                'scale' : self.scale_eff,
                'region': region,
                'format': 'GEO_TIFF',
                'crs'   : 'EPSG:4326',
            })
        except Exception as ex:
            raise RuntimeError(f"Error al generar URL GEE: {ex}")

        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise RuntimeError(f"URL inválida: esquema '{parsed.scheme}'")

        self.log.emit("Descargando GeoTIFF...")
        tmp = self.output_path + '_tmp.bin'
        try:
            with requests.get(url, stream=True, timeout=180) as r:
                r.raise_for_status()
                total = int(r.headers.get('content-length', 0))
                desc  = 0
                with open(tmp, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=16384):
                        if self._cancelar:
                            raise RuntimeError("Cancelado por el usuario.")
                        if chunk:
                            f.write(chunk)
                            desc += len(chunk)
                            if total > 0:
                                self.progreso.emit(min(int(desc * 100 / total), 99))
        except Exception as ex:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise RuntimeError(f"Error en descarga HTTP: {ex}")

        # Descomprimir si viene en ZIP
        if zipfile.is_zipfile(tmp):
            self.log.emit("Descomprimiendo archivo ZIP...")
            with zipfile.ZipFile(tmp, 'r') as zf:
                tifs = [n for n in zf.namelist() if n.lower().endswith('.tif')]
                if not tifs:
                    raise RuntimeError("El ZIP de GEE no contiene archivos .tif")
                extracted = zf.extract(tifs[0], os.path.dirname(self.output_path) or '.')
            shutil.move(extracted, self.output_path)
            os.remove(tmp)
        else:
            shutil.move(tmp, self.output_path)

        self.progreso.emit(100)
        self.log.emit(f"✔ MDE guardado en:\n  {self.output_path}")
        self.ok.emit(self.output_path, False)

    def _exportar_drive(self, ee, imagen, region):
        ts        = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        dem_slug  = self.dem_info['collection'].replace('/', '_')
        task_name = f"MDE_{dem_slug}_{ts}"

        task = ee.batch.Export.image.toDrive(
            image          = imagen,
            description    = task_name,
            folder         = GDRIVE_FOLDER,
            fileNamePrefix = task_name,
            scale          = self.scale_eff,
            region         = region,
            crs            = 'EPSG:4326',
            fileFormat     = 'GeoTIFF',
            maxPixels      = 1e13,
        )
        task.start()
        self.log.emit(f"Task GEE iniciado: {task.id}")
        self.log.emit("Monitoreando en: https://code.earthengine.google.com/tasks")

        ESTADOS_FIN = {'COMPLETED', 'FAILED', 'CANCELLED', 'CANCEL_REQUESTED'}
        ultimo_estado = ''
        espera_total  = 0
        spinner       = ['|', '/', '-', '\\']
        spin_idx      = 0

        while True:
            time.sleep(12)
            espera_total += 12
            if self._cancelar:
                task.cancel()
                raise RuntimeError("Cancelado por el usuario.")
            try:
                status   = task.status()
                estado   = status.get('state', 'UNKNOWN')
                progreso = status.get('progress', 0.0)
            except Exception as ex:
                self.log.emit(f"No se pudo consultar el estado: {ex}")
                continue
            if estado != ultimo_estado:
                self.log.emit(f"Estado GEE: {estado}")
                ultimo_estado = estado
            mins = espera_total // 60
            segs = espera_total % 60
            spin = spinner[spin_idx % len(spinner)]
            spin_idx += 1
            if progreso and progreso > 0:
                self.progreso.emit(int(progreso * 100))
            self.log.emit(
                f"{spin} {'%.1f%%' % (progreso*100) if progreso else 'procesando...'}"
                f"  |  {mins}m {segs}s")
            if estado in ESTADOS_FIN:
                break

        if estado == 'COMPLETED':
            self.log.emit(f"✔ Exportación completada → Drive/{GDRIVE_FOLDER}/{task_name}.tif")
            self.progreso.emit(100)
            self.ok.emit(task_name, True)
        else:
            err = task.status().get('error_message', 'Error desconocido')
            raise RuntimeError(f"GEE Drive falló [{estado}]: {err}")


# ═════════════════════════════════════════════════════════════════════════════
# WORKERS GEE — inicialización / autenticación en background
# ═════════════════════════════════════════════════════════════════════════════
class _GeeInitWorker(QThread):
    """
    Ejecuta ee.Initialize() + una llamada simple de validación en background.
    Emite ok(proyecto) o error(msg).  Nunca bloquea el hilo principal de Qt.
    """
    ok    = pyqtSignal(str)   # proyecto
    error = pyqtSignal(str)   # mensaje de error

    def __init__(self, proyecto):
        super().__init__()
        self.proyecto = proyecto

    def run(self):
        try:
            import ee
            kwargs = {}
            if self.proyecto.strip():
                kwargs['project'] = self.proyecto.strip()
            ee.Initialize(opt_url='https://earthengine.googleapis.com', **kwargs)
            # Llamada mínima de validación (no descarga datos, solo confirma auth)
            ee.Image(1).getInfo()
            self.ok.emit(self.proyecto.strip())
        except Exception as ex:
            self.error.emit(str(ex))


class _GeeAuthWorker(QThread):
    """
    Ejecuta ee.Authenticate() en background.
    ee.Authenticate() abre el navegador y espera la aprobación del usuario.
    """
    ok    = pyqtSignal()
    error = pyqtSignal(str)

    def run(self):
        try:
            import ee
            ee.Authenticate()
            self.ok.emit()
        except Exception as ex:
            self.error.emit(str(ex))


# ═════════════════════════════════════════════════════════════════════════════
# DIÁLOGO PRINCIPAL
# ═════════════════════════════════════════════════════════════════════════════
class GeeSWATDialog(QDialog):

    SETTINGS_KEY = 'geeSWAT'

    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface   = iface
        self.canvas  = iface.mapCanvas()
        self.setWindowTitle('geeSWAT v1.1.0 — SWAT con Google Earth Engine')
        self.setMinimumSize(900, 660)
        self.resize(980, 720)
        self.setStyleSheet('QDialog {background:#F5F7FA;}'
                           'QTabWidget::pane {border:1.5px solid #CFD8DC;border-radius:4px;}')

        # Estado interno
        self._aoi_geom     = None   # WKT en CRS nativo
        self._aoi_crs_epsg = None
        self._rubber       = None
        self._puntos_poly  = []
        self._tool_dibujo  = None
        self._click_count  = 0
        self._datos_ficha  = {}
        self._worker       = None
        self._gee_worker   = None   # worker for Init/Verify
        self._soil_worker  = None   # worker for SOIL download
        self._landuse_worker = None  # worker for LANDUSE download

        self._settings = QSettings(self.SETTINGS_KEY, self.SETTINGS_KEY)
        self._construir_ui()
        self._cargar_config()
        self._refrescar_capas()
        # Auto-connect after dialog is fully shown (non-blocking, 1 s delay)
        QTimer.singleShot(1000, self._auto_conectar_gee)

    # ══════════════════════════════════════════════════════════════════════════
    # UI PRINCIPAL
    # ══════════════════════════════════════════════════════════════════════════
    def _construir_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # Barra de estado GEE
        self._barra_estado = QLabel('  ⬤  Sin conexión a GEE — Configure en la pestaña Config GEE')
        self._barra_estado.setStyleSheet(
            f'background:{ROJO};color:white;padding:7px 14px;font-size:11px;font-weight:bold;')
        self._barra_estado.setFixedHeight(34)
        main.addWidget(self._barra_estado)

        # Pestañas
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            'QTabBar::tab {padding:9px 22px;font-size:11px;min-width:140px;}'
            f'QTabBar::tab:selected {{background:{AZUL_C};color:{AZUL};'
            f'font-weight:bold;border-bottom:3px solid {AZUL_M};}}')
        main.addWidget(self._tabs)

        self._tabs.addTab(self._tab_config(),   '⚙  Config GEE')
        self._tabs.addTab(self._tab_aoi(),      '🗺  Seleccionar AOI')
        self._tabs.addTab(self._tab_mde(),      '🏔  MDE')
        self._tabs.addTab(self._tab_soil(),     '🌍  SOIL')
        self._tabs.addTab(self._tab_landuse(),  '🌳  LANDUSE')
        self._tabs.addTab(self._tab_acerca(),   'ℹ  Acerca de')

    # ══════════════════════════════════════════════════════════════════════════
    # PESTAÑA 1 — CONFIG GEE
    # ══════════════════════════════════════════════════════════════════════════
    def _tab_config(self):
        w = QWidget()
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        vl = QVBoxLayout(inner)
        vl.setContentsMargins(24, 24, 24, 24); vl.setSpacing(16)

        # ── Conexión GEE ──────────────────────────────────────────────────────
        g1 = _grupo('🔑  Conexión a Google Earth Engine', AZUL)
        gl1 = QGridLayout(g1); gl1.setSpacing(10)

        gl1.addWidget(QLabel('Correo Gmail:'), 0, 0)
        self._inp_gmail = QLineEdit()
        self._inp_gmail.setPlaceholderText('tu.correo@gmail.com')
        self._inp_gmail.setMinimumHeight(32)
        gl1.addWidget(self._inp_gmail, 0, 1)

        gl1.addWidget(QLabel('ID del proyecto GEE:'), 1, 0)
        self._inp_project = QLineEdit()
        self._inp_project.setPlaceholderText('mi-proyecto-gee-123456')
        self._inp_project.setMinimumHeight(32)
        gl1.addWidget(self._inp_project, 1, 1)

        hl = QHBoxLayout()
        self._btn_auth = QPushButton('🔑  Autenticar con Google')
        self._btn_auth.setStyleSheet(_btn_primario())
        self._btn_auth.setMinimumHeight(38)
        self._btn_auth.setToolTip('Abre el navegador para autenticar con tu cuenta Google\ny guardar las credenciales para Earth Engine.')
        self._btn_auth.clicked.connect(self._autenticar_gee)

        self._btn_verificar = QPushButton('🔗  Verificar conexión')
        self._btn_verificar.setStyleSheet(_btn_secundario())
        self._btn_verificar.setMinimumHeight(38)
        self._btn_verificar.clicked.connect(self._verificar_gee)

        hl.addWidget(self._btn_auth)
        hl.addWidget(self._btn_verificar)
        hl.addStretch()
        gl1.addLayout(hl, 2, 0, 1, 2)

        self._lbl_gee_msg = QLabel('')
        self._lbl_gee_msg.setStyleSheet(f'color:{GRIS};font-size:10px;')
        gl1.addWidget(self._lbl_gee_msg, 3, 0, 1, 2)
        vl.addWidget(g1)

        # Info
        info = QLabel(
            '<b>Primera vez:</b> Necesitas una cuenta Gmail registrada en '
            '<a href="https://earthengine.google.com">earthengine.google.com</a> '
            'y un Google Cloud Project con la <b>Earth Engine API</b> habilitada.<br>'
            'Haz clic en <b>Autenticar con Google</b> → se abre el navegador → '
            'luego <b>Verificar conexión</b>.')
        info.setStyleSheet(f'background:{AZUL_C};color:{GRIS_OS};padding:12px;'
                           f'border-radius:6px;font-size:11px;border:1px solid #BBDEFB;')
        info.setOpenExternalLinks(True); info.setWordWrap(True)
        vl.addWidget(info)

        # ── Archivos de salida ────────────────────────────────────────────────
        g2 = _grupo('📁  Archivos de salida', VERDE)
        gl2 = QGridLayout(g2); gl2.setSpacing(10)

        gl2.addWidget(QLabel('Nombre del proyecto:'), 0, 0)
        self._inp_nombre_proy = QLineEdit()
        self._inp_nombre_proy.setPlaceholderText('Ej: Cuenca_Rimac_2026')
        self._inp_nombre_proy.setMinimumHeight(32)
        gl2.addWidget(self._inp_nombre_proy, 0, 1)

        gl2.addWidget(QLabel('Carpeta de salida:'), 1, 0)
        hl_c = QHBoxLayout()
        self._inp_carpeta = QLineEdit()
        self._inp_carpeta.setPlaceholderText('Selecciona la carpeta principal de salida...')
        self._inp_carpeta.setMinimumHeight(32)
        self._btn_carpeta = QPushButton('📁')
        self._btn_carpeta.setFixedSize(38, 34)
        self._btn_carpeta.setStyleSheet(_btn_secundario())
        self._btn_carpeta.clicked.connect(self._seleccionar_carpeta)
        hl_c.addWidget(self._inp_carpeta); hl_c.addWidget(self._btn_carpeta)
        gl2.addLayout(hl_c, 1, 1)

        nota = QLabel('ℹ️  Cada herramienta crea su propia subcarpeta (ej: <b>DEM/</b>, <b>SOIL/</b>) dentro de esta ruta.')
        nota.setStyleSheet(f'color:{GRIS};font-size:10px;')
        nota.setWordWrap(True)
        gl2.addWidget(nota, 2, 0, 1, 2)

        # ── Proyección del proyecto ──────────────────────────────────────────────
        g3 = _grupo('📏  Proyección del proyecto (CRS)', CYAN)
        gl3 = QGridLayout(g3); gl3.setSpacing(10)

        gl3.addWidget(QLabel('Código EPSG:'), 0, 0)
        self._inp_epsg = QLineEdit()
        self._inp_epsg.setPlaceholderText('Ej: 32718  (WGS84 / UTM zona 18S)')
        self._inp_epsg.setMinimumHeight(32)
        self._inp_epsg.setToolTip(
            'Código EPSG de la proyección de salida.\n'
            'Ejemplos:\n'
            '  32718 = WGS84 / UTM zona 18S (Perú sur)\n'
            '  32717 = WGS84 / UTM zona 17S (Perú centro)\n'
            '  32619 = WGS84 / UTM zona 19N (Colombia)\n'
            '  4326  = WGS84 geográfico (lat/lon)')
        gl3.addWidget(self._inp_epsg, 0, 1)

        nota_epsg = QLabel(
            'El DEM y el Suelo se descargarán en esta proyección.\n'
            'Deja en blanco para usar EPSG:4326 (WGS84 geográfico).')
        nota_epsg.setStyleSheet(f'color:{GRIS};font-size:10px;')
        nota_epsg.setWordWrap(True)
        gl3.addWidget(nota_epsg, 1, 0, 1, 2)
        vl.addWidget(g3)

        vl.addWidget(g2)

        self._btn_guardar = QPushButton('💾  Guardar configuración')
        self._btn_guardar.setStyleSheet(_btn_exito())
        self._btn_guardar.setMinimumHeight(40)
        self._btn_guardar.clicked.connect(self._guardar_config)
        vl.addWidget(self._btn_guardar)

        vl.addStretch()
        scroll.setWidget(inner)
        lv = QVBoxLayout(w); lv.setContentsMargins(0,0,0,0); lv.addWidget(scroll)
        return w

    # ══════════════════════════════════════════════════════════════════════════
    # PESTAÑA 2 — SELECCIONAR AOI
    # ══════════════════════════════════════════════════════════════════════════
    def _tab_aoi(self):
        w   = QWidget()
        spl = QSplitter(Qt.Horizontal)
        spl.setHandleWidth(6)
        spl.setStyleSheet('QSplitter::handle {background:#CFD8DC;}')

        # ── Panel izquierdo (controles) ───────────────────────────────────────
        panel_izq = QWidget()
        panel_izq.setMinimumWidth(300)
        panel_izq.setMaximumWidth(400)
        vl = QVBoxLayout(panel_izq)
        vl.setContentsMargins(14, 14, 8, 14); vl.setSpacing(12)

        # -- Desde capa vectorial --
        g_capa = _grupo('📂  Desde capa vectorial', AZUL)
        vl_capa = QVBoxLayout(g_capa); vl_capa.setSpacing(8)

        hl_capa = QHBoxLayout()
        self._cmb_capas = QComboBox()
        self._cmb_capas.setMinimumHeight(30)
        btn_refrescar = QPushButton('↻')
        btn_refrescar.setFixedSize(30, 30)
        btn_refrescar.setStyleSheet(_btn_secundario())
        btn_refrescar.setToolTip('Refrescar lista de capas')
        btn_refrescar.clicked.connect(self._refrescar_capas)
        hl_capa.addWidget(self._cmb_capas, 1)
        hl_capa.addWidget(btn_refrescar)
        vl_capa.addLayout(hl_capa)

        self._btn_usar_capa = QPushButton('✔  Usar capa seleccionada')
        self._btn_usar_capa.setStyleSheet(_btn_primario())
        self._btn_usar_capa.setMinimumHeight(34)
        self._btn_usar_capa.clicked.connect(self._usar_capa)
        vl_capa.addWidget(self._btn_usar_capa)
        vl.addWidget(g_capa)

        # -- Dibujo interactivo --
        g_dibujo = _grupo('✏  Dibujo interactivo en el mapa', CYAN)
        vl_dib = QVBoxLayout(g_dibujo); vl_dib.setSpacing(8)

        lbl_inst = QLabel(
            '① Haz clic en el mapa para agregar vértices\n'
            '② Doble clic o clic derecho para cerrar el polígono')
        lbl_inst.setStyleSheet(f'color:{GRIS};font-size:10px;background:{CYAN_C};'
                               f'border-radius:5px;padding:6px;')
        vl_dib.addWidget(lbl_inst)

        self._btn_dibujar = QPushButton('✏  Activar dibujo de polígono')
        self._btn_dibujar.setStyleSheet(_btn_primario(CYAN, VERDE))
        self._btn_dibujar.setMinimumHeight(34)
        self._btn_dibujar.clicked.connect(self._activar_dibujo)
        vl_dib.addWidget(self._btn_dibujar)
        vl.addWidget(g_dibujo)

        # -- Acciones AOI --
        g_acc = _grupo('🔧  Acciones', GRIS)
        vl_acc = QVBoxLayout(g_acc); vl_acc.setSpacing(6)

        self._btn_zoom_aoi = QPushButton('🔍  Zoom al AOI')
        self._btn_zoom_aoi.setStyleSheet(_btn_secundario())
        self._btn_zoom_aoi.setMinimumHeight(32)
        self._btn_zoom_aoi.setEnabled(False)
        self._btn_zoom_aoi.clicked.connect(self._zoom_aoi)
        vl_acc.addWidget(self._btn_zoom_aoi)

        self._btn_limpiar_aoi = QPushButton('🗑  Limpiar AOI')
        self._btn_limpiar_aoi.setStyleSheet(_btn_peligro())
        self._btn_limpiar_aoi.setMinimumHeight(32)
        self._btn_limpiar_aoi.setEnabled(False)
        self._btn_limpiar_aoi.clicked.connect(self._limpiar_aoi)
        vl_acc.addWidget(self._btn_limpiar_aoi)
        vl.addWidget(g_acc)

        vl.addStretch()

        # Indicador de estado AOI (abajo del panel)
        self._lbl_aoi_estado = QLabel('Sin AOI definida')
        self._lbl_aoi_estado.setAlignment(Qt.AlignCenter)
        self._lbl_aoi_estado.setWordWrap(True)
        self._lbl_aoi_estado.setStyleSheet(
            f'background:#ECEFF1;color:{GRIS};border-radius:6px;'
            f'padding:6px;font-size:10px;')
        vl.addWidget(self._lbl_aoi_estado)

        spl.addWidget(panel_izq)

        # ── Panel derecho (ficha AOI) ──────────────────────────────────────────
        panel_der = QWidget()
        panel_der.setMinimumWidth(340)
        vl_der = QVBoxLayout(panel_der)
        vl_der.setContentsMargins(8, 14, 14, 14); vl_der.setSpacing(8)

        lbl_ficha_h = QLabel('📍  Ficha del Área de Interés')
        lbl_ficha_h.setStyleSheet(
            f'background:{AZUL_M};color:white;padding:9px 14px;'
            f'font-weight:bold;font-size:12px;border-radius:6px 6px 0 0;')
        vl_der.addWidget(lbl_ficha_h)

        self._ficha_widget = QWidget()
        self._ficha_widget.setStyleSheet(
            'background:white;border:1.5px solid #CFD8DC;'
            'border-top:none;border-radius:0 0 6px 6px;')
        self._ficha_layout = QVBoxLayout(self._ficha_widget)
        self._ficha_layout.setContentsMargins(14, 12, 14, 12)
        self._ficha_layout.setSpacing(0)

        self._lbl_sin_aoi = QLabel('Define un área de interés\npara ver su ficha geométrica.')
        self._lbl_sin_aoi.setAlignment(Qt.AlignCenter)
        self._lbl_sin_aoi.setStyleSheet(f'color:#9E9E9E;font-size:11px;padding:40px;')
        self._ficha_layout.addWidget(self._lbl_sin_aoi)
        self._ficha_layout.addStretch()
        vl_der.addWidget(self._ficha_widget, 1)

        # Alerta de tamaño
        self._lbl_alerta_area = QLabel('')
        self._lbl_alerta_area.setWordWrap(True)
        self._lbl_alerta_area.setStyleSheet('font-size:10px;padding:4px;')
        self._lbl_alerta_area.setVisible(False)
        vl_der.addWidget(self._lbl_alerta_area)

        # Botón ir a MDE
        self._btn_ir_mde = QPushButton('🏔  Ir a descargar MDE →')
        self._btn_ir_mde.setStyleSheet(_btn_exito())
        self._btn_ir_mde.setMinimumHeight(38)
        self._btn_ir_mde.setEnabled(False)
        self._btn_ir_mde.clicked.connect(lambda: self._tabs.setCurrentIndex(2))
        vl_der.addWidget(self._btn_ir_mde)

        spl.addWidget(panel_der)
        spl.setSizes([340, 540])

        hl_main = QHBoxLayout(w)
        hl_main.setContentsMargins(0, 0, 0, 0)
        hl_main.addWidget(spl)
        return w

    # ══════════════════════════════════════════════════════════════════════════
    # PESTAÑA 3 — MDE
    # ══════════════════════════════════════════════════════════════════════════
    def _tab_mde(self):
        w   = QWidget()
        spl = QSplitter(Qt.Horizontal)
        spl.setHandleWidth(6)
        spl.setStyleSheet('QSplitter::handle {background:#CFD8DC;}')

        # ── Panel izquierdo (parámetros) ──────────────────────────────────────
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget(); inner.setMinimumWidth(300)
        vl = QVBoxLayout(inner)
        vl.setContentsMargins(14, 14, 8, 14); vl.setSpacing(14)

        # ── AOI actual ────────────────────────────────────────────────────────
        g_aoi = _grupo('🗺  Área de Interés', AZUL)
        vl_aoi = QVBoxLayout(g_aoi); vl_aoi.setSpacing(6)

        self._lbl_mde_aoi = QLabel('Sin AOI definida — ve a la pestaña "Seleccionar AOI"')
        self._lbl_mde_aoi.setWordWrap(True)
        self._lbl_mde_aoi.setStyleSheet(
            f'background:{ROJO_C};color:{ROJO};padding:8px;'
            f'border-radius:5px;font-size:10px;')
        vl_aoi.addWidget(self._lbl_mde_aoi)

        btn_ir_aoi = QPushButton('← Definir AOI')
        btn_ir_aoi.setStyleSheet(_btn_secundario())
        btn_ir_aoi.setMinimumHeight(30)
        btn_ir_aoi.clicked.connect(lambda: self._tabs.setCurrentIndex(1))
        vl_aoi.addWidget(btn_ir_aoi)
        vl.addWidget(g_aoi)

        # ── Fuente DEM ────────────────────────────────────────────────────────
        g_dem = _grupo('🛰  Fuente del DEM', AZUL_M)
        vl_dem = QVBoxLayout(g_dem); vl_dem.setSpacing(10)

        self._cmb_dem = QComboBox()
        self._cmb_dem.setMinimumHeight(32)
        for d in GEE_DEMS:
            self._cmb_dem.addItem(d['label'])
        self._cmb_dem.currentIndexChanged.connect(self._actualizar_info_dem)
        vl_dem.addWidget(self._cmb_dem)

        self._lbl_dem_desc = QLabel('')
        self._lbl_dem_desc.setWordWrap(True)
        self._lbl_dem_desc.setStyleSheet(
            f'background:{AZUL_C};color:{GRIS_OS};padding:8px;'
            f'border-radius:5px;font-size:10px;')
        vl_dem.addWidget(self._lbl_dem_desc)

        # Escala
        gl_esc = QGridLayout(); gl_esc.setSpacing(8)
        gl_esc.addWidget(QLabel('Escala de salida (m):'), 0, 0)
        self._spn_escala = QSpinBox()
        self._spn_escala.setRange(0, 10000)
        self._spn_escala.setValue(0)
        self._spn_escala.setMinimumHeight(30)
        self._spn_escala.setSpecialValueText('0  (resolución nativa del DEM)')
        self._spn_escala.setToolTip(
            '0 = resolución nativa del DEM seleccionado.\n'
            'Ejemplo: SRTM → 30 m, MERIT/HydroSHEDS → 90 m.')
        self._spn_escala.valueChanged.connect(self._actualizar_info_dem)
        gl_esc.addWidget(self._spn_escala, 0, 1)

        self._lbl_escala_info = QLabel('')
        self._lbl_escala_info.setStyleSheet(f'color:{GRIS};font-size:10px;')
        gl_esc.addWidget(self._lbl_escala_info, 1, 0, 1, 2)
        vl_dem.addLayout(gl_esc)
        vl.addWidget(g_dem)
        # NOTE: _actualizar_info_dem() is called AFTER _lbl_ruta_salida is created below

        # ── Salida ────────────────────────────────────────────────────────────
        g_sal = _grupo('💾  Archivo de salida', VERDE)
        vl_sal = QVBoxLayout(g_sal); vl_sal.setSpacing(8)

        nota_sal = QLabel(
            'El archivo se guarda automáticamente en:\n'
            '<carpeta_salida> / <b>DEM</b> / <nombre_dem>.tif')
        nota_sal.setTextFormat(Qt.RichText)
        nota_sal.setWordWrap(True)
        nota_sal.setStyleSheet(
            f'background:{VERDE_C};color:{GRIS_OS};padding:8px;'
            f'border-radius:5px;font-size:10px;')
        vl_sal.addWidget(nota_sal)

        self._lbl_ruta_salida = QLabel('Ruta: (configura la carpeta de salida en Config GEE)')
        self._lbl_ruta_salida.setWordWrap(True)
        self._lbl_ruta_salida.setStyleSheet(
            f'color:{GRIS};font-size:10px;font-style:italic;')
        vl_sal.addWidget(self._lbl_ruta_salida)
        vl.addWidget(g_sal)
        # Now all MDE widgets exist — safe to initialise DEM info
        self._actualizar_info_dem()

        # ── Botones de ejecución ──────────────────────────────────────────────
        self._btn_descargar = QPushButton('▶  Descargar MDE')
        self._btn_descargar.setStyleSheet(_btn_exito())
        self._btn_descargar.setMinimumHeight(42)
        self._btn_descargar.setFont(QFont('Arial', 12, QFont.Bold))
        self._btn_descargar.clicked.connect(self._ejecutar_descarga)
        vl.addWidget(self._btn_descargar)

        self._btn_cancelar_mde = QPushButton('⏹  Cancelar')
        self._btn_cancelar_mde.setStyleSheet(_btn_secundario())
        self._btn_cancelar_mde.setMinimumHeight(36)
        self._btn_cancelar_mde.setEnabled(False)
        self._btn_cancelar_mde.clicked.connect(self._cancelar_descarga)
        vl.addWidget(self._btn_cancelar_mde)

        self._progreso_mde = QProgressBar()
        self._progreso_mde.setStyleSheet(
            f'QProgressBar {{height:18px;border-radius:5px;background:#E0E0E0;}}'
            f'QProgressBar::chunk {{background:{VERDE_M};border-radius:5px;}}')
        self._progreso_mde.setValue(0)
        vl.addWidget(self._progreso_mde)

        vl.addStretch()
        scroll.setWidget(inner)
        spl.addWidget(scroll)

        # ── Panel derecho (log) ───────────────────────────────────────────────
        panel_log = QWidget()
        panel_log.setMinimumWidth(320)
        vl_log = QVBoxLayout(panel_log)
        vl_log.setContentsMargins(8, 14, 14, 14); vl_log.setSpacing(8)

        lbl_log_h = QLabel('📋  Registro de descarga')
        lbl_log_h.setStyleSheet(
            f'background:{GRIS_OS};color:white;padding:9px 14px;'
            f'font-weight:bold;font-size:12px;border-radius:6px 6px 0 0;')
        vl_log.addWidget(lbl_log_h)

        self._txt_log = QTextEdit()
        self._txt_log.setReadOnly(True)
        self._txt_log.setStyleSheet(
            'QTextEdit {background:#1E272E;color:#ECF0F1;font-family:Consolas,monospace;'
            'font-size:10px;border:1.5px solid #CFD8DC;border-top:none;'
            'border-radius:0 0 6px 6px;padding:8px;}')
        self._txt_log.setPlaceholderText('Los mensajes de progreso aparecerán aquí...')
        vl_log.addWidget(self._txt_log, 1)

        btn_limpiar_log = QPushButton('🗑  Limpiar registro')
        btn_limpiar_log.setStyleSheet(_btn_secundario())
        btn_limpiar_log.setMinimumHeight(30)
        btn_limpiar_log.clicked.connect(self._txt_log.clear)
        vl_log.addWidget(btn_limpiar_log)

        spl.addWidget(panel_log)
        spl.setSizes([380, 500])

        hl = QHBoxLayout(w); hl.setContentsMargins(0,0,0,0); hl.addWidget(spl)

        # Actualizar ruta al cambiar la pestaña
        self._tabs_ref = None
        return w

    # ══════════════════════════════════════════════════════════════════════════
    # PESTAÑA 4 — SOIL
    # ══════════════════════════════════════════════════════════════════════════
    def _tab_soil(self):
        from .Script.soil_descargar_suelo import SOIL_SOURCES
        self._SOIL_SOURCES = SOIL_SOURCES

        w   = QWidget()
        spl = QSplitter(Qt.Horizontal)
        spl.setHandleWidth(6)
        spl.setStyleSheet('QSplitter::handle {background:#CFD8DC;}')

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget(); inner.setMinimumWidth(310)
        vl = QVBoxLayout(inner)
        vl.setContentsMargins(14, 14, 8, 14); vl.setSpacing(14)

        # AOI
        g_aoi = _grupo('Mapa  Area de Interes', AZUL)
        vl_aoi = QVBoxLayout(g_aoi); vl_aoi.setSpacing(6)
        self._lbl_soil_aoi = QLabel(
            'Sin AOI definida - ve a la pestana "Seleccionar AOI"')
        self._lbl_soil_aoi.setWordWrap(True)
        self._lbl_soil_aoi.setStyleSheet(
            f'background:{ROJO_C};color:{ROJO};padding:8px;'
            f'border-radius:5px;font-size:10px;')
        vl_aoi.addWidget(self._lbl_soil_aoi)
        btn_ir_aoi2 = QPushButton('Ir a Definir AOI')
        btn_ir_aoi2.setStyleSheet(_btn_secundario())
        btn_ir_aoi2.setMinimumHeight(30)
        btn_ir_aoi2.clicked.connect(lambda: self._tabs.setCurrentIndex(1))
        vl_aoi.addWidget(btn_ir_aoi2)
        vl.addWidget(g_aoi)

        # Fuente de suelo
        g_src = _grupo('Tipo de Suelo - Fuente GEE', AZUL_M)
        vl_src = QVBoxLayout(g_src); vl_src.setSpacing(10)

        self._cmb_soil = QComboBox()
        self._cmb_soil.setMinimumHeight(32)
        for s in SOIL_SOURCES:
            self._cmb_soil.addItem(s['label'])
        self._cmb_soil.currentIndexChanged.connect(self._actualizar_info_soil)
        vl_src.addWidget(self._cmb_soil)

        self._lbl_soil_desc = QLabel('')
        self._lbl_soil_desc.setWordWrap(True)
        self._lbl_soil_desc.setStyleSheet(
            f'background:{AZUL_C};color:{GRIS_OS};padding:8px;'
            f'border-radius:5px;font-size:10px;')
        vl_src.addWidget(self._lbl_soil_desc)

        gl_s = QGridLayout(); gl_s.setSpacing(8)
        gl_s.addWidget(QLabel('Escala de salida (m):'), 0, 0)
        self._spn_soil_escala = QSpinBox()
        self._spn_soil_escala.setRange(0, 10000)
        self._spn_soil_escala.setValue(0)
        self._spn_soil_escala.setMinimumHeight(30)
        self._spn_soil_escala.setSpecialValueText('0  (resolucion nativa del mapa de suelos)')
        self._spn_soil_escala.valueChanged.connect(self._actualizar_info_soil)
        gl_s.addWidget(self._spn_soil_escala, 0, 1)
        self._lbl_soil_esc_info = QLabel('')
        self._lbl_soil_esc_info.setStyleSheet(f'color:{GRIS};font-size:10px;')
        gl_s.addWidget(self._lbl_soil_esc_info, 1, 0, 1, 2)
        vl_src.addLayout(gl_s)
        vl.addWidget(g_src)
        self._actualizar_info_soil()

        # Salida
        g_sal = _grupo('Archivo de salida', VERDE)
        vl_sal = QVBoxLayout(g_sal); vl_sal.setSpacing(8)
        nota2 = QLabel(
            'Los archivos se guardan en:\n'
            'carpeta_salida/SOIL/nombre.tif\n'
            'carpeta_salida/SOIL/nombre_Soil_lookup.csv')
        nota2.setWordWrap(True)
        nota2.setStyleSheet(
            f'background:{VERDE_C};color:{GRIS_OS};padding:8px;'
            f'border-radius:5px;font-size:10px;')
        vl_sal.addWidget(nota2)
        self._lbl_soil_ruta = QLabel(
            'Ruta: (configura la carpeta de salida en Config GEE)')
        self._lbl_soil_ruta.setWordWrap(True)
        self._lbl_soil_ruta.setStyleSheet(
            f'color:{GRIS};font-size:10px;font-style:italic;')
        vl_sal.addWidget(self._lbl_soil_ruta)
        vl.addWidget(g_sal)

        # CRS info
        self._lbl_soil_crs = QLabel('CRS: (configura el EPSG en Config GEE)')
        self._lbl_soil_crs.setStyleSheet(
            f'background:#FFF8E1;color:#F57F17;padding:6px;'
            f'border-radius:5px;font-size:10px;border:1px solid #F57F17;')
        self._lbl_soil_crs.setWordWrap(True)
        vl.addWidget(self._lbl_soil_crs)

        self._tabs.currentChanged.connect(self._on_tab_soil_visible)

        self._btn_soil_desc = QPushButton('Descargar Suelo + Soil_lookup.csv')
        self._btn_soil_desc.setStyleSheet(_btn_exito())
        self._btn_soil_desc.setMinimumHeight(42)
        self._btn_soil_desc.setFont(QFont('Arial', 11, QFont.Bold))
        self._btn_soil_desc.clicked.connect(self._ejecutar_soil)
        vl.addWidget(self._btn_soil_desc)

        self._btn_soil_cancel = QPushButton('Cancelar')
        self._btn_soil_cancel.setStyleSheet(_btn_secundario())
        self._btn_soil_cancel.setMinimumHeight(34)
        self._btn_soil_cancel.setEnabled(False)
        self._btn_soil_cancel.clicked.connect(self._cancelar_soil)
        vl.addWidget(self._btn_soil_cancel)

        self._prog_soil = QProgressBar()
        self._prog_soil.setStyleSheet(
            f'QProgressBar {{height:18px;border-radius:5px;background:#E0E0E0;}}'
            f'QProgressBar::chunk {{background:{VERDE_M};border-radius:5px;}}')
        self._prog_soil.setValue(0)
        vl.addWidget(self._prog_soil)
        vl.addStretch()
        scroll.setWidget(inner)
        spl.addWidget(scroll)

        panel_log = QWidget(); panel_log.setMinimumWidth(320)
        vl_log = QVBoxLayout(panel_log)
        vl_log.setContentsMargins(8, 14, 14, 14); vl_log.setSpacing(8)
        lbl_h = QLabel('Registro de descarga de suelo')
        lbl_h.setStyleSheet(
            f'background:{GRIS_OS};color:white;padding:9px 14px;'
            f'font-weight:bold;font-size:12px;border-radius:6px 6px 0 0;')
        vl_log.addWidget(lbl_h)
        self._txt_soil_log = QTextEdit()
        self._txt_soil_log.setReadOnly(True)
        self._txt_soil_log.setStyleSheet(
            'QTextEdit {background:#1E272E;color:#ECF0F1;'
            'font-family:Consolas,monospace;font-size:10px;'
            'border:1.5px solid #CFD8DC;border-top:none;'
            'border-radius:0 0 6px 6px;padding:8px;}')
        self._txt_soil_log.setPlaceholderText('Los mensajes apareceran aqui...')
        vl_log.addWidget(self._txt_soil_log, 1)
        btn_clear = QPushButton('Limpiar registro')
        btn_clear.setStyleSheet(_btn_secundario())
        btn_clear.setMinimumHeight(30)
        btn_clear.clicked.connect(self._txt_soil_log.clear)
        vl_log.addWidget(btn_clear)

        spl.addWidget(panel_log)
        spl.setSizes([380, 500])
        hl = QHBoxLayout(w); hl.setContentsMargins(0,0,0,0); hl.addWidget(spl)
        return w

    def _on_tab_soil_visible(self, idx):
        if idx != 3:
            return
        if not hasattr(self, '_lbl_soil_ruta'):
            return
        carpeta = self._inp_carpeta.text().strip()
        epsg    = self._get_epsg()
        if carpeta:
            soil_dir = os.path.join(carpeta, 'SOIL')
            self._lbl_soil_ruta.setText(f'Ruta de salida: {soil_dir}')
        else:
            self._lbl_soil_ruta.setText('Ruta: (configura la carpeta de salida en Config GEE)')
        if epsg:
            self._lbl_soil_crs.setText(f'CRS de salida: EPSG:{epsg}')
            self._lbl_soil_crs.setStyleSheet(
                f'background:{VERDE_C};color:{VERDE};padding:6px;'
                f'border-radius:5px;font-size:10px;border:1px solid {VERDE};')
        else:
            self._lbl_soil_crs.setText(
                'CRS: EPSG:4326 sin configurar - '
                'configura el EPSG en Config GEE para reproyectar.')
            self._lbl_soil_crs.setStyleSheet(
                f'background:#FFF8E1;color:#F57F17;padding:6px;'
                f'border-radius:5px;font-size:10px;border:1px solid #F57F17;')
        if self._aoi_geom and self._datos_ficha:
            area = self._datos_ficha.get('Area', '?')
            self._lbl_soil_aoi.setText(
                f'AOI definida - Area: {area} | '
                f'Bbox: [{self._datos_ficha.get("Bbox Oeste","?")} , '
                f'{self._datos_ficha.get("Bbox Sur","?")} , '
                f'{self._datos_ficha.get("Bbox Este","?")} , '
                f'{self._datos_ficha.get("Bbox Norte","?")}]')
            self._lbl_soil_aoi.setStyleSheet(
                f'background:{VERDE_C};color:{VERDE};padding:8px;'
                f'border-radius:5px;font-size:10px;')
        else:
            self._lbl_soil_aoi.setText(
                'Sin AOI definida - ve a la pestana "Seleccionar AOI"')
            self._lbl_soil_aoi.setStyleSheet(
                f'background:{ROJO_C};color:{ROJO};padding:8px;'
                f'border-radius:5px;font-size:10px;')

    def _actualizar_info_soil(self):
        if not hasattr(self, '_cmb_soil'):
            return
        idx = self._cmb_soil.currentIndex()
        if idx < 0 or idx >= len(self._SOIL_SOURCES):
            return
        s      = self._SOIL_SOURCES[idx]
        esc    = self._spn_soil_escala.value()
        esc_ef = esc if esc > 0 else s['scale']
        self._lbl_soil_desc.setText(
            f'<b>Asset GEE:</b> {s["asset"]}<br>'
            f'<b>Tipo:</b> {s["tipo"].capitalize()}  |  '
            f'<b>Res. nativa:</b> {s["scale"]} m  |  '
            f'<b>Campo ID:</b> {s["campo"]}<br>'
            f'<b>Info:</b> {s["desc"]}<br>'
            f'<b>Escala efectiva:</b> {esc_ef} m' +
            (' <i>(nativa)</i>' if esc == 0 else ''))
        self._lbl_soil_esc_info.setText(
            f'0 = resolucion nativa ({s["scale"]} m). Efectiva: {esc_ef} m.')

    def _ejecutar_soil(self):
        from .Script.soil_descargar_suelo import SoilWorker
        if not self._aoi_geom:
            QMessageBox.warning(self, 'geeSWAT',
                'Define primero el area de interes en "Seleccionar AOI".')
            self._tabs.setCurrentIndex(1)
            return
        carpeta = self._inp_carpeta.text().strip()
        if not carpeta:
            QMessageBox.warning(self, 'geeSWAT',
                'Configura la carpeta de salida en "Config GEE".')
            self._tabs.setCurrentIndex(0)
            return
        proyecto = self._inp_project.text().strip()
        idx_src  = self._cmb_soil.currentIndex()
        src      = self._SOIL_SOURCES[idx_src]
        esc      = self._spn_soil_escala.value()
        esc_ef   = esc if esc > 0 else src['scale']
        epsg     = self._get_epsg() or 4326
        bbox = self._datos_ficha.get('_bbox_wgs84')
        if not bbox:
            from qgis.core import (QgsGeometry, QgsCoordinateReferenceSystem,
                                   QgsCoordinateTransform)
            geom  = QgsGeometry.fromWkt(self._aoi_geom)
            crs   = QgsCoordinateReferenceSystem(f'EPSG:{self._aoi_crs_epsg}')
            crs84 = QgsCoordinateReferenceSystem('EPSG:4326')
            if crs != crs84:
                geom.transform(QgsCoordinateTransform(crs, crs84, QgsProject.instance()))
            bb   = geom.boundingBox()
            bbox = (bb.xMinimum(), bb.yMinimum(), bb.xMaximum(), bb.yMaximum())
        lon_min, lat_min, lon_max, lat_max = bbox
        soil_dir = os.path.join(carpeta, 'SOIL')
        os.makedirs(soil_dir, exist_ok=True)
        nombre_proy = self._inp_nombre_proy.text().strip()
        ts      = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        fname   = f'{nombre_proy}_{src["id"]}_{ts}' if nombre_proy else f'{src["id"]}_{ts}'
        out_tif = os.path.join(soil_dir, fname + '.tif')
        out_csv = os.path.join(soil_dir, fname + '_Soil_lookup.csv')
        self._btn_soil_desc.setEnabled(False)
        self._btn_soil_cancel.setEnabled(True)
        self._prog_soil.setValue(0)
        self._txt_soil_log.clear()
        self._soil_log(f'Fuente          : {src["label"]}')
        self._soil_log(f'Escala efectiva : {esc_ef} m')
        self._soil_log(f'Proyeccion      : EPSG:{epsg}')
        self._soil_log(f'Bbox WGS84      : [{lon_min:.5f}, {lat_min:.5f}, {lon_max:.5f}, {lat_max:.5f}]')
        self._soil_log(f'Raster salida   : {out_tif}')
        self._soil_log(f'CSV salida      : {out_csv}')
        self._soil_log('─' * 50)
        self._soil_worker = SoilWorker(
            src, lon_min, lat_min, lon_max, lat_max,
            esc_ef, epsg, out_tif, out_csv, proyecto)
        self._soil_worker.log.connect(self._soil_log)
        self._soil_worker.progreso.connect(self._prog_soil.setValue)
        self._soil_worker.ok.connect(self._soil_completado)
        self._soil_worker.error.connect(self._soil_error)
        self._soil_worker.finished.connect(self._soil_worker_terminado)
        self._soil_worker.start()

    def _cancelar_soil(self):
        if self._soil_worker and self._soil_worker.isRunning():
            self._soil_worker.cancelar()
            self._soil_log('Cancelando...')

    def _soil_log(self, msg):
        ts = datetime.datetime.now().strftime('%H:%M:%S')
        self._txt_soil_log.append(
            f'<span style="color:#95A5A6">[{ts}]</span> {msg}')
        sb = self._txt_soil_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _soil_completado(self, ruta_tif, ruta_csv, via_drive):
        if via_drive:
            self._soil_log('Exportacion a Google Drive completada.')
            QMessageBox.information(self, 'geeSWAT - SOIL Completado',
                'El suelo se exporto a Google Drive.\n'
                'Descargalo desde drive.google.com')
        else:
            self._soil_log(f'Raster guardado: {ruta_tif}')
            if ruta_csv:
                self._soil_log(f'CSV guardado   : {ruta_csv}')
            try:
                src    = self._SOIL_SOURCES[self._cmb_soil.currentIndex()]
                rlayer = QgsRasterLayer(ruta_tif, f'SOIL - {src["id"]}')
                if rlayer.isValid():
                    QgsProject.instance().addMapLayer(rlayer)
                    self._soil_log('Raster cargado en QGIS.')
            except Exception as ex:
                self._soil_log(f'No se pudo cargar en QGIS: {ex}')
            QMessageBox.information(self, 'geeSWAT - SOIL Completado',
                f'Raster de suelo:\n  {ruta_tif}\n\n'
                f'Tabla Soil_lookup.csv:\n  {ruta_csv or "(no generada)"}')

    def _soil_error(self, msg):
        self._soil_log(f'ERROR: {msg}')
        QMessageBox.critical(self, 'geeSWAT - Error SOIL', msg)

    def _soil_worker_terminado(self):
        self._btn_soil_desc.setEnabled(True)
        self._btn_soil_cancel.setEnabled(False)

    # ══════════════════════════════════════════════════════════════════════════
    # PESTAÑA 5 - LANDUSE
    # ══════════════════════════════════════════════════════════════════════════
    def _tab_landuse(self):
        from .Script.landuse_descargar_landuse import LANDUSE_SOURCES
        self._LANDUSE_SOURCES = LANDUSE_SOURCES

        w   = QWidget()
        spl = QSplitter(Qt.Horizontal)
        spl.setHandleWidth(6)
        spl.setStyleSheet('QSplitter::handle {background:#CFD8DC;}')

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget(); inner.setMinimumWidth(310)
        vl = QVBoxLayout(inner)
        vl.setContentsMargins(14, 14, 8, 14); vl.setSpacing(14)

        # AOI
        g_aoi = _grupo('Area de Interes (AOI)', AZUL)
        vl_aoi = QVBoxLayout(g_aoi); vl_aoi.setSpacing(6)
        self._lbl_lu_aoi = QLabel(
            'Sin AOI definida - ve a la pestana "Seleccionar AOI"')
        self._lbl_lu_aoi.setWordWrap(True)
        self._lbl_lu_aoi.setStyleSheet(
            f'background:{ROJO_C};color:{ROJO};padding:8px;'
            f'border-radius:5px;font-size:10px;')
        vl_aoi.addWidget(self._lbl_lu_aoi)
        btn_ir = QPushButton('Ir a Definir AOI')
        btn_ir.setStyleSheet(_btn_secundario())
        btn_ir.setMinimumHeight(30)
        btn_ir.clicked.connect(lambda: self._tabs.setCurrentIndex(1))
        vl_aoi.addWidget(btn_ir)
        vl.addWidget(g_aoi)

        # Fuente de uso del suelo
        g_src = _grupo('Fuente de Uso del Suelo (LANDUSE)', AZUL_M)
        vl_src = QVBoxLayout(g_src); vl_src.setSpacing(10)

        self._cmb_lu = QComboBox()
        self._cmb_lu.setMinimumHeight(32)
        for s in LANDUSE_SOURCES:
            self._cmb_lu.addItem(s['label'])
        self._cmb_lu.currentIndexChanged.connect(self._actualizar_info_landuse)
        vl_src.addWidget(self._cmb_lu)

        self._lbl_lu_desc = QLabel('')
        self._lbl_lu_desc.setWordWrap(True)
        self._lbl_lu_desc.setStyleSheet(
            f'background:{AZUL_C};color:{GRIS_OS};padding:8px;'
            f'border-radius:5px;font-size:10px;')
        vl_src.addWidget(self._lbl_lu_desc)

        # Escala
        gl_s = QGridLayout(); gl_s.setSpacing(8)
        gl_s.addWidget(QLabel('Escala de salida (m):'), 0, 0)
        self._spn_lu_escala = QSpinBox()
        self._spn_lu_escala.setRange(0, 10000)
        self._spn_lu_escala.setValue(0)
        self._spn_lu_escala.setMinimumHeight(30)
        self._spn_lu_escala.setSpecialValueText('0  (resolucion nativa del mapa)')
        self._spn_lu_escala.setToolTip(
            '0 = resolucion nativa.\n'
            'Copernicus 2019: 100 m  |  ESA GlobCover 2009: 300 m')
        self._spn_lu_escala.valueChanged.connect(self._actualizar_info_landuse)
        gl_s.addWidget(self._spn_lu_escala, 0, 1)
        self._lbl_lu_esc_info = QLabel('')
        self._lbl_lu_esc_info.setStyleSheet(f'color:{GRIS};font-size:10px;')
        gl_s.addWidget(self._lbl_lu_esc_info, 1, 0, 1, 2)
        vl_src.addLayout(gl_s)
        vl.addWidget(g_src)
        self._actualizar_info_landuse()

        # Salida
        g_sal = _grupo('Archivo de salida', VERDE)
        vl_sal = QVBoxLayout(g_sal); vl_sal.setSpacing(8)
        nota2 = QLabel(
            'Los archivos se guardan en:\n'
            'carpeta_salida/LANDUSE/nombre.tif\n'
            'carpeta_salida/LANDUSE/nombre_Landuse_lookup.csv')
        nota2.setWordWrap(True)
        nota2.setStyleSheet(
            f'background:{VERDE_C};color:{GRIS_OS};padding:8px;'
            f'border-radius:5px;font-size:10px;')
        vl_sal.addWidget(nota2)
        self._lbl_lu_ruta = QLabel(
            'Ruta: (configura la carpeta de salida en Config GEE)')
        self._lbl_lu_ruta.setWordWrap(True)
        self._lbl_lu_ruta.setStyleSheet(
            f'color:{GRIS};font-size:10px;font-style:italic;')
        vl_sal.addWidget(self._lbl_lu_ruta)
        vl.addWidget(g_sal)

        # CRS info
        self._lbl_lu_crs = QLabel('CRS: (configura el EPSG en Config GEE)')
        self._lbl_lu_crs.setStyleSheet(
            f'background:#FFF8E1;color:#F57F17;padding:6px;'
            f'border-radius:5px;font-size:10px;border:1px solid #F57F17;')
        self._lbl_lu_crs.setWordWrap(True)
        vl.addWidget(self._lbl_lu_crs)

        # Actualizar al cambiar de pestana (idx=4)
        self._tabs.currentChanged.connect(self._on_tab_landuse_visible)

        self._btn_lu_desc = QPushButton('Descargar LANDUSE + Landuse_lookup.csv')
        self._btn_lu_desc.setStyleSheet(_btn_exito())
        self._btn_lu_desc.setMinimumHeight(42)
        self._btn_lu_desc.setFont(QFont('Arial', 11, QFont.Bold))
        self._btn_lu_desc.clicked.connect(self._ejecutar_landuse)
        vl.addWidget(self._btn_lu_desc)

        self._btn_lu_cancel = QPushButton('Cancelar')
        self._btn_lu_cancel.setStyleSheet(_btn_secundario())
        self._btn_lu_cancel.setMinimumHeight(34)
        self._btn_lu_cancel.setEnabled(False)
        self._btn_lu_cancel.clicked.connect(self._cancelar_landuse)
        vl.addWidget(self._btn_lu_cancel)

        self._prog_lu = QProgressBar()
        self._prog_lu.setStyleSheet(
            f'QProgressBar {{height:18px;border-radius:5px;background:#E0E0E0;}}'
            f'QProgressBar::chunk {{background:{VERDE_M};border-radius:5px;}}')
        self._prog_lu.setValue(0)
        vl.addWidget(self._prog_lu)
        vl.addStretch()
        scroll.setWidget(inner)
        spl.addWidget(scroll)

        # Panel derecho: log
        panel_log = QWidget(); panel_log.setMinimumWidth(320)
        vl_log = QVBoxLayout(panel_log)
        vl_log.setContentsMargins(8, 14, 14, 14); vl_log.setSpacing(8)
        lbl_h = QLabel('Registro de descarga LANDUSE')
        lbl_h.setStyleSheet(
            f'background:{GRIS_OS};color:white;padding:9px 14px;'
            f'font-weight:bold;font-size:12px;border-radius:6px 6px 0 0;')
        vl_log.addWidget(lbl_h)
        self._txt_lu_log = QTextEdit()
        self._txt_lu_log.setReadOnly(True)
        self._txt_lu_log.setStyleSheet(
            'QTextEdit {background:#1E272E;color:#ECF0F1;'
            'font-family:Consolas,monospace;font-size:10px;'
            'border:1.5px solid #CFD8DC;border-top:none;'
            'border-radius:0 0 6px 6px;padding:8px;}')
        self._txt_lu_log.setPlaceholderText('Los mensajes apareceran aqui...')
        vl_log.addWidget(self._txt_lu_log, 1)
        btn_clear = QPushButton('Limpiar registro')
        btn_clear.setStyleSheet(_btn_secundario())
        btn_clear.setMinimumHeight(30)
        btn_clear.clicked.connect(self._txt_lu_log.clear)
        vl_log.addWidget(btn_clear)

        spl.addWidget(panel_log)
        spl.setSizes([380, 500])
        hl = QHBoxLayout(w); hl.setContentsMargins(0, 0, 0, 0); hl.addWidget(spl)
        return w

    def _on_tab_landuse_visible(self, idx):
        if idx != 4:
            return
        if not hasattr(self, '_lbl_lu_ruta'):
            return
        carpeta = self._inp_carpeta.text().strip()
        epsg    = self._get_epsg()
        if carpeta:
            lu_dir = os.path.join(carpeta, 'LANDUSE')
            self._lbl_lu_ruta.setText(f'Ruta de salida: {lu_dir}')
        else:
            self._lbl_lu_ruta.setText('Ruta: (configura la carpeta de salida en Config GEE)')
        if epsg:
            self._lbl_lu_crs.setText(f'CRS de salida: EPSG:{epsg}')
            self._lbl_lu_crs.setStyleSheet(
                f'background:{VERDE_C};color:{VERDE};padding:6px;'
                f'border-radius:5px;font-size:10px;border:1px solid {VERDE};')
        else:
            self._lbl_lu_crs.setText(
                'CRS: EPSG:4326 sin configurar - '
                'configura el EPSG en Config GEE para reproyectar.')
            self._lbl_lu_crs.setStyleSheet(
                f'background:#FFF8E1;color:#F57F17;padding:6px;'
                f'border-radius:5px;font-size:10px;border:1px solid #F57F17;')
        if self._aoi_geom and self._datos_ficha:
            area = self._datos_ficha.get('Area', '?')
            self._lbl_lu_aoi.setText(
                f'AOI definida - Area: {area} | '
                f'Bbox: [{self._datos_ficha.get("Bbox Oeste","?")} , '
                f'{self._datos_ficha.get("Bbox Sur","?")} , '
                f'{self._datos_ficha.get("Bbox Este","?")} , '
                f'{self._datos_ficha.get("Bbox Norte","?")}]')
            self._lbl_lu_aoi.setStyleSheet(
                f'background:{VERDE_C};color:{VERDE};padding:8px;'
                f'border-radius:5px;font-size:10px;')
        else:
            self._lbl_lu_aoi.setText(
                'Sin AOI definida - ve a la pestana "Seleccionar AOI"')
            self._lbl_lu_aoi.setStyleSheet(
                f'background:{ROJO_C};color:{ROJO};padding:8px;'
                f'border-radius:5px;font-size:10px;')

    def _actualizar_info_landuse(self):
        if not hasattr(self, '_cmb_lu'):
            return
        idx = self._cmb_lu.currentIndex()
        if idx < 0 or idx >= len(self._LANDUSE_SOURCES):
            return
        s      = self._LANDUSE_SOURCES[idx]
        esc    = self._spn_lu_escala.value()
        esc_ef = esc if esc > 0 else s['scale']
        n_clases = len(s['tabla_swat'])
        self._lbl_lu_desc.setText(
            f'<b>Asset GEE:</b> {s["collection"]}<br>'
            f'<b>Banda:</b> {s["banda"]}  |  '
            f'<b>Res. nativa:</b> {s["scale"]} m  |  '
            f'<b>Clases SWAT:</b> {n_clases}<br>'
            f'<b>Info:</b> {s["desc"]}<br>'
            f'<b>Escala efectiva:</b> {esc_ef} m' +
            (' <i>(nativa)</i>' if esc == 0 else ''))
        self._lbl_lu_esc_info.setText(
            f'0 = resolucion nativa ({s["scale"]} m). Efectiva: {esc_ef} m.')

    def _ejecutar_landuse(self):
        from .Script.landuse_descargar_landuse import LanduseWorker
        if not self._aoi_geom:
            QMessageBox.warning(self, 'geeSWAT',
                'Define primero el area de interes en "Seleccionar AOI".')
            self._tabs.setCurrentIndex(1)
            return
        carpeta = self._inp_carpeta.text().strip()
        if not carpeta:
            QMessageBox.warning(self, 'geeSWAT',
                'Configura la carpeta de salida en "Config GEE".')
            self._tabs.setCurrentIndex(0)
            return
        proyecto = self._inp_project.text().strip()
        idx_src  = self._cmb_lu.currentIndex()
        src      = self._LANDUSE_SOURCES[idx_src]
        esc      = self._spn_lu_escala.value()
        esc_ef   = esc if esc > 0 else src['scale']
        epsg     = self._get_epsg() or 4326
        # Bbox WGS84
        bbox = self._datos_ficha.get('_bbox_wgs84')
        if not bbox:
            from qgis.core import (QgsGeometry, QgsCoordinateReferenceSystem,
                                   QgsCoordinateTransform)
            geom  = QgsGeometry.fromWkt(self._aoi_geom)
            crs   = QgsCoordinateReferenceSystem(f'EPSG:{self._aoi_crs_epsg}')
            crs84 = QgsCoordinateReferenceSystem('EPSG:4326')
            if crs != crs84:
                geom.transform(QgsCoordinateTransform(crs, crs84, QgsProject.instance()))
            bb   = geom.boundingBox()
            bbox = (bb.xMinimum(), bb.yMinimum(), bb.xMaximum(), bb.yMaximum())
        lon_min, lat_min, lon_max, lat_max = bbox
        lu_dir = os.path.join(carpeta, 'LANDUSE')
        os.makedirs(lu_dir, exist_ok=True)
        nombre_proy = self._inp_nombre_proy.text().strip()
        ts      = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        fname   = f'{nombre_proy}_{src["id"]}_{ts}' if nombre_proy else f'{src["id"]}_{ts}'
        out_tif = os.path.join(lu_dir, fname + '.tif')
        out_csv = os.path.join(lu_dir, fname + '_Landuse_lookup.csv')
        self._btn_lu_desc.setEnabled(False)
        self._btn_lu_cancel.setEnabled(True)
        self._prog_lu.setValue(0)
        self._txt_lu_log.clear()
        self._lu_log(f'Fuente          : {src["label"]}')
        self._lu_log(f'Asset GEE       : {src["collection"]}')
        self._lu_log(f'Banda           : {src["banda"]}')
        self._lu_log(f'Escala efectiva : {esc_ef} m')
        self._lu_log(f'Proyeccion      : EPSG:{epsg}')
        self._lu_log(f'Bbox WGS84      : [{lon_min:.5f}, {lat_min:.5f}, {lon_max:.5f}, {lat_max:.5f}]')
        self._lu_log(f'Raster salida   : {out_tif}')
        self._lu_log(f'CSV salida      : {out_csv}')
        self._lu_log('-' * 50)
        self._landuse_worker = LanduseWorker(
            src, lon_min, lat_min, lon_max, lat_max,
            esc_ef, epsg, out_tif, out_csv, proyecto)
        self._landuse_worker.log.connect(self._lu_log)
        self._landuse_worker.progreso.connect(self._prog_lu.setValue)
        self._landuse_worker.ok.connect(self._lu_completado)
        self._landuse_worker.error.connect(self._lu_error)
        self._landuse_worker.finished.connect(self._lu_worker_terminado)
        self._landuse_worker.start()

    def _cancelar_landuse(self):
        if self._landuse_worker and self._landuse_worker.isRunning():
            self._landuse_worker.cancelar()
            self._lu_log('Cancelando...')

    def _lu_log(self, msg):
        ts = datetime.datetime.now().strftime('%H:%M:%S')
        self._txt_lu_log.append(
            f'<span style="color:#95A5A6">[{ts}]</span> {msg}')
        sb = self._txt_lu_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _lu_completado(self, ruta_tif, ruta_csv, via_drive):
        if via_drive:
            self._lu_log('Exportacion a Google Drive completada.')
            QMessageBox.information(self, 'geeSWAT - LANDUSE Completado',
                'El uso del suelo se exporto a Google Drive.\n'
                'Descargalo desde drive.google.com')
        else:
            self._lu_log(f'Raster guardado: {ruta_tif}')
            if ruta_csv:
                self._lu_log(f'CSV guardado   : {ruta_csv}')
            try:
                src    = self._LANDUSE_SOURCES[self._cmb_lu.currentIndex()]
                rlayer = QgsRasterLayer(ruta_tif, f'LANDUSE - {src["id"]}')
                if rlayer.isValid():
                    QgsProject.instance().addMapLayer(rlayer)
                    self._lu_log('Raster cargado en QGIS.')
            except Exception as ex:
                self._lu_log(f'No se pudo cargar en QGIS: {ex}')
            QMessageBox.information(self, 'geeSWAT - LANDUSE Completado',
                f'Raster de uso del suelo:\n  {ruta_tif}\n\n'
                f'Tabla Landuse_lookup.csv:\n  {ruta_csv or "(no generada)"}')

    def _lu_error(self, msg):
        self._lu_log(f'ERROR: {msg}')
        QMessageBox.critical(self, 'geeSWAT - Error LANDUSE', msg)

    def _lu_worker_terminado(self):
        self._btn_lu_desc.setEnabled(True)
        self._btn_lu_cancel.setEnabled(False)

    # ══════════════════════════════════════════════════════════════════════════
    # PESTAÑA 6 - ACERCA DE
    # ══════════════════════════════════════════════════════════════════════════
    def _tab_acerca(self):

        w = QWidget()
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget(); inner.setStyleSheet('background:#F5F7FA;')
        vl = QVBoxLayout(inner); vl.setContentsMargins(0,0,0,0); vl.setSpacing(0)

        # Hero
        hero = QWidget(); hero.setFixedHeight(170)
        hero.setStyleSheet(
            'background:qlineargradient(x1:0,y1:0,x2:1,y2:1,'
            'stop:0 #0A2F6E, stop:0.5 #1565C0, stop:1 #0D47A1);border:none;')
        hero_hl = QHBoxLayout(hero)
        hero_hl.setContentsMargins(36, 24, 36, 24); hero_hl.setSpacing(24)

        lbl_ic = QLabel(); lbl_ic.setFixedSize(90, 90)
        lbl_ic.setPixmap(self._generar_icono_cuenca(90))
        lbl_ic.setAlignment(Qt.AlignCenter)
        hero_hl.addWidget(lbl_ic)

        hvl = QVBoxLayout(); hvl.setSpacing(5)
        lbl_t = QLabel('geeSWAT')
        lbl_t.setStyleSheet('font-size:30px;font-weight:bold;color:white;letter-spacing:2px;background:transparent;border:none;')
        hvl.addWidget(lbl_t)
        lbl_s = QLabel('SWAT Hidrológico con Google Earth Engine para QGIS 3.x / 4.x')
        lbl_s.setStyleSheet('font-size:11px;color:#BBDEFB;background:transparent;border:none;')
        hvl.addWidget(lbl_s)
        lbl_v = QLabel('  v 1.1.0  —  QGIS 3.16+  —  GPL-2.0  ')
        lbl_v.setStyleSheet('font-size:10px;font-weight:bold;color:#0D47A1;background:#BBDEFB;border-radius:10px;padding:3px 10px;border:none;')
        lbl_v.setFixedHeight(22); hvl.addWidget(lbl_v)
        hero_hl.addLayout(hvl); hero_hl.addStretch()
        vl.addWidget(hero)

        inner2 = QWidget(); inner2.setStyleSheet('background:#F5F7FA;border:none;')
        vl2 = QVBoxLayout(inner2); vl2.setContentsMargins(28,22,28,28); vl2.setSpacing(16)

        # Descripción
        desc = QWidget()
        desc.setStyleSheet('background:white;border:1px solid #E0E0E0;border-radius:10px;')
        dl = QVBoxLayout(desc); dl.setContentsMargins(20,16,20,16)
        lbl_d = QLabel(
            '<b>geeSWAT</b> conecta QGIS con <b>Google Earth Engine</b> para automatizar '
            'la descarga y preprocesamiento de datos espaciales para modelado SWAT.<br><br>'
            '✔ Selecciona el área de estudio desde una capa vectorial o dibujando en el mapa.<br>'
            '✔ Descarga DEMs de 9 fuentes globales (SRTM, Copernicus, MERIT, HydroSHEDS, ALOS...).<br>'
            '✔ Los archivos se organizan automáticamente en subcarpetas por tipo (<b>DEM/</b>).<br>'
            '✔ Para áreas grandes usa Google Drive con monitoreo en tiempo real.')
        lbl_d.setWordWrap(True); lbl_d.setTextFormat(Qt.RichText)
        lbl_d.setStyleSheet('font-size:11px;color:#37474F;background:transparent;border:none;')
        dl.addWidget(lbl_d)
        vl2.addWidget(desc)

        # Botones rápidos
        hl_b = QHBoxLayout(); hl_b.setSpacing(12)
        b1 = QPushButton('Abrir www.geomatica.pe'); b1.setStyleSheet(_btn_primario())
        b1.setMinimumHeight(36)
        b1.clicked.connect(lambda: QDesktopServices.openUrl(QUrl('https://www.geomatica.pe')))
        b2 = QPushButton('Registrarse en GEE'); b2.setStyleSheet(_btn_secundario())
        b2.setMinimumHeight(36)
        b2.clicked.connect(lambda: QDesktopServices.openUrl(QUrl('https://earthengine.google.com')))
        hl_b.addWidget(b1); hl_b.addWidget(b2); hl_b.addStretch()
        vl2.addLayout(hl_b)

        # ── Tarjeta de contacto ───────────────────────────────────────────────
        contacto = QWidget()
        contacto.setStyleSheet(
            'background:white;border:1px solid #E0E0E0;border-radius:10px;')
        cl = QVBoxLayout(contacto); cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(0)

        # Cabecera de la tarjeta
        hdr = QWidget()
        hdr.setStyleSheet(
            'background:qlineargradient(x1:0,y1:0,x2:1,y2:0,'
            'stop:0 #0D47A1,stop:1 #1565C0);'
            'border-radius:9px 9px 0 0;')
        hdr.setFixedHeight(46)
        hdr_hl = QHBoxLayout(hdr); hdr_hl.setContentsMargins(18, 0, 18, 0)
        lbl_hdr = QLabel('Contacto del desarrollador')
        lbl_hdr.setStyleSheet(
            'color:white;font-size:12px;font-weight:bold;'
            'background:transparent;border:none;')
        hdr_hl.addWidget(lbl_hdr); hdr_hl.addStretch()
        cl.addWidget(hdr)

        # Cuerpo de la tarjeta
        body = QWidget()
        body.setStyleSheet('background:transparent;border:none;')
        bl = QGridLayout(body); bl.setContentsMargins(18, 14, 18, 16); bl.setSpacing(10)
        bl.setColumnMinimumWidth(0, 26)

        def _fila(row, icono, texto, url=None):
            lbl_ico = QLabel(icono)
            lbl_ico.setStyleSheet(
                f'color:{AZUL_M};font-size:14px;background:transparent;border:none;')
            lbl_ico.setFixedWidth(26)
            bl.addWidget(lbl_ico, row, 0)
            lbl_txt = QLabel(texto)
            lbl_txt.setTextFormat(Qt.RichText)
            lbl_txt.setOpenExternalLinks(True)
            lbl_txt.setStyleSheet(
                'color:#263238;font-size:11px;background:transparent;border:none;')
            lbl_txt.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
            bl.addWidget(lbl_txt, row, 1)

        _fila(0, 'N', '<b>Nino Bravo Morales</b>')
        _fila(1, 'E', 'Especialista en Geomatica')
        _fila(2, 'T', '+51 995 664 488')
        _fila(3, '@',
              '<a href="mailto:nino@geomatica.pe" style="color:#1565C0;">'
              'nino@geomatica.pe</a>')
        _fila(4, 'W',
              '<a href="https://www.geomatica.pe" style="color:#1565C0;">'
              'www.geomatica.pe</a>')

        # Botón WhatsApp
        btn_wa = QPushButton('Contactar por WhatsApp  +51 995 664 488')
        btn_wa.setStyleSheet(
            'QPushButton {background:#25D366;color:white;border-radius:6px;'
            'font-size:11px;font-weight:bold;padding:7px 14px;border:none;}'
            'QPushButton:hover {background:#1EBE57;}')
        btn_wa.setMinimumHeight(36)
        btn_wa.setCursor(Qt.PointingHandCursor)
        btn_wa.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl('https://wa.me/51995664488?text=Hola%20Nino%2C%20consulta%20sobre%20geeSWAT')))

        btn_mail = QPushButton('Enviar correo')
        btn_mail.setStyleSheet(
            'QPushButton {background:#1565C0;color:white;border-radius:6px;'
            'font-size:11px;font-weight:bold;padding:7px 14px;border:none;}'
            'QPushButton:hover {background:#0D47A1;}')
        btn_mail.setMinimumHeight(36)
        btn_mail.setCursor(Qt.PointingHandCursor)
        btn_mail.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl('mailto:nino@geomatica.pe?subject=Consulta%20geeSWAT')))

        btn_row = QHBoxLayout(); btn_row.setSpacing(10)
        btn_row.addWidget(btn_wa); btn_row.addWidget(btn_mail); btn_row.addStretch()
        bl.addLayout(btn_row, 5, 0, 1, 2)

        cl.addWidget(body)
        vl2.addWidget(contacto)

        # Pie de página
        pie = QLabel(
            '<center><span style="color:#BDBDBD;font-size:9px;">'
            'geeSWAT v1.2.0 &mdash; GPL-2.0 &mdash; 2026 Geomatica Ambiental'
            '</span></center>')
        pie.setTextFormat(Qt.RichText); pie.setAlignment(Qt.AlignCenter)
        pie.setStyleSheet('background:transparent;border:none;margin-top:6px;')
        vl2.addWidget(pie); vl2.addStretch()


        vl.addWidget(inner2)
        scroll.setWidget(inner)
        lv = QVBoxLayout(w); lv.setContentsMargins(0,0,0,0); lv.addWidget(scroll)
        return w

    # ══════════════════════════════════════════════════════════════════════════
    # LÓGICA GEE  (todos los calls de red corren en QThread — nunca en el hilo UI)
    # ══════════════════════════════════════════════════════════════════════════
    def _auto_conectar_gee(self):
        """Intento silencioso de reconexión al abrir el diálogo."""
        if not EE_DISPONIBLE:
            return
        proyecto = self._inp_project.text().strip()
        if not proyecto:
            return
        # Lanzar en background — sin bloquear QGIS
        self._lanzar_init_worker(proyecto, silencioso=True)

    def _lanzar_init_worker(self, proyecto, silencioso=False):
        """Crea y arranca un GeeInitWorker para ee.Initialize en background."""
        if self._gee_worker and self._gee_worker.isRunning():
            return
        self._gee_worker = _GeeInitWorker(proyecto)
        self._gee_worker.ok.connect(
            lambda p: self._on_init_ok(p, silencioso))
        if not silencioso:
            self._gee_worker.error.connect(self._on_init_error)
        self._gee_worker.start()

    # ── Callbacks del worker Init ─────────────────────────────────────────────
    def _on_init_ok(self, proyecto, silencioso):
        self._set_barra(True, proyecto)
        self._lbl_gee_msg.setText('✔ Conexión automática exitosa.' if silencioso
                                  else '✔ Conexión GEE verificada correctamente.')
        self._lbl_gee_msg.setStyleSheet(f'color:{VERDE};font-size:10px;')
        if not silencioso:
            QMessageBox.information(
                self, 'geeSWAT',
                f'✔ Conexión a Google Earth Engine exitosa.\nProyecto: {proyecto or "(credenciales locales)"}')

    def _on_init_error(self, msg):
        self._set_barra(False)
        self._lbl_gee_msg.setText(f'✖ Error: {msg[:90]}')
        self._lbl_gee_msg.setStyleSheet(f'color:{ROJO};font-size:10px;')
        # Restaurar botón verificar
        self._btn_verificar.setEnabled(True)
        self._btn_verificar.setText('🔗  Verificar conexión')
        if any(k in msg.lower() for k in ('credentials', 'oauth', 'token', 'authorize')):
            QMessageBox.warning(self, 'Sin credenciales',
                'No se encontraron credenciales GEE.\n'
                'Haz clic en "Autenticar con Google" primero.')
        else:
            QMessageBox.critical(self, 'Error de conexión', f'No se pudo conectar:\n\n{msg}')

    def _autenticar_gee(self):
        if not EE_DISPONIBLE:
            QMessageBox.warning(self, 'geeSWAT',
                'El módulo earthengine-api no está instalado.\n'
                'Usa la opción "Instalar dependencias" del menú geeSWAT.')
            return
        self._btn_auth.setEnabled(False)
        self._btn_auth.setText('⏳  Autenticando...')
        self._lbl_gee_msg.setText('Abriendo navegador para autenticación...')
        self._lbl_gee_msg.setStyleSheet(f'color:{GRIS};font-size:10px;')
        # ee.Authenticate() abre el navegador y espera — corre en background
        worker = _GeeAuthWorker()
        worker.ok.connect(self._on_auth_ok)
        worker.error.connect(self._on_auth_error)
        worker.finished.connect(lambda: (
            self._btn_auth.setEnabled(True),
            self._btn_auth.setText('🔑  Autenticar con Google')))
        # Guardar referencia para evitar GC
        self._auth_worker = worker
        worker.start()

    def _on_auth_ok(self):
        self._lbl_gee_msg.setText('✔ Autenticación completada. Haz clic en "Verificar conexión".')
        self._lbl_gee_msg.setStyleSheet(f'color:{VERDE};font-size:10px;')
        QMessageBox.information(self, 'Autenticación',
            '✔ Autenticación completada.\nHaz clic en "Verificar conexión".')

    def _on_auth_error(self, msg):
        self._lbl_gee_msg.setText(f'✖ Error: {msg[:90]}')
        self._lbl_gee_msg.setStyleSheet(f'color:{ROJO};font-size:10px;')
        QMessageBox.critical(self, 'Error de autenticación', msg)

    def _verificar_gee(self):
        if not EE_DISPONIBLE:
            QMessageBox.warning(self, 'geeSWAT', 'El módulo earthengine-api no está instalado.')
            return
        if self._gee_worker and self._gee_worker.isRunning():
            QMessageBox.information(self, 'geeSWAT', 'Ya hay una verificación en curso...')
            return
        self._btn_verificar.setEnabled(False)
        self._btn_verificar.setText('⏳  Verificando...')
        self._lbl_gee_msg.setText('Conectando con GEE...')
        self._lbl_gee_msg.setStyleSheet(f'color:{GRIS};font-size:10px;')
        proyecto = self._inp_project.text().strip()
        self._lanzar_init_worker(proyecto, silencioso=False)

    def _set_barra(self, ok, proyecto=''):
        if ok:
            txt = f'  ✔  GEE conectado  ·  proyecto: {proyecto}' if proyecto else '  ✔  GEE conectado'
            self._barra_estado.setText(txt)
            self._barra_estado.setStyleSheet(
                f'background:{VERDE_M};color:white;padding:7px 14px;font-size:11px;font-weight:bold;')
        else:
            self._barra_estado.setText('  ⬤  Sin conexión a GEE — Configure en la pestaña Config GEE')
            self._barra_estado.setStyleSheet(
                f'background:{ROJO};color:white;padding:7px 14px;font-size:11px;font-weight:bold;')

    # ══════════════════════════════════════════════════════════════════════════
    # CONFIGURACIÓN
    # ══════════════════════════════════════════════════════════════════════════
    def _seleccionar_carpeta(self):
        d = QFileDialog.getExistingDirectory(
            self, 'Seleccionar carpeta de salida',
            self._inp_carpeta.text() or os.path.expanduser('~'))
        if d:
            self._inp_carpeta.setText(d)
            self._actualizar_ruta_salida()

    def _guardar_config(self):
        self._settings.setValue('gmail',   self._inp_gmail.text().strip())
        self._settings.setValue('project', self._inp_project.text().strip())
        self._settings.setValue('nombre',  self._inp_nombre_proy.text().strip())
        self._settings.setValue('carpeta', self._inp_carpeta.text().strip())
        self._settings.setValue('epsg',    self._inp_epsg.text().strip())
        QMessageBox.information(self, 'geeSWAT', '✔ Configuración guardada.')
        self._actualizar_ruta_salida()

    def _cargar_config(self):
        self._inp_gmail.setText(       self._settings.value('gmail',   ''))
        self._inp_project.setText(     self._settings.value('project', ''))
        self._inp_nombre_proy.setText( self._settings.value('nombre',  ''))
        self._inp_carpeta.setText(     self._settings.value('carpeta', ''))
        self._inp_epsg.setText(        self._settings.value('epsg',    ''))
        self._actualizar_ruta_salida()

    def _get_epsg(self):
        """Devuelve el codigo EPSG como entero, o None si no esta configurado."""
        v = self._inp_epsg.text().strip()
        if not v:
            return None
        try:
            return int(v.upper().replace('EPSG:', '').strip())
        except ValueError:
            return None

    def _actualizar_ruta_salida(self):
        # Guard: widget may not exist yet during dialog construction
        if not hasattr(self, '_lbl_ruta_salida'):
            return
        carpeta = self._inp_carpeta.text().strip()
        epsg    = self._inp_epsg.text().strip() if hasattr(self, '_inp_epsg') else ''
        if carpeta:
            dem_dir  = os.path.join(carpeta, 'DEM')
            soil_dir = os.path.join(carpeta, 'SOIL')
            crs_txt  = f'  |  CRS: EPSG:{epsg}' if epsg else '  |  CRS: EPSG:4326 (sin configurar)'
            self._lbl_ruta_salida.setText(
                f'DEM  -> {dem_dir}\n'
                f'SOIL -> {soil_dir}{crs_txt}')
        else:
            self._lbl_ruta_salida.setText('Ruta: (configura la carpeta de salida en Config GEE)')

    # ══════════════════════════════════════════════════════════════════════════
    # AOI
    # ══════════════════════════════════════════════════════════════════════════
    def _refrescar_capas(self):
        self._cmb_capas.blockSignals(True)
        self._cmb_capas.clear()
        self._cmb_capas.addItem('— Seleccionar capa vectorial —', None)
        for lid, capa in QgsProject.instance().mapLayers().items():
            if isinstance(capa, QgsVectorLayer):
                self._cmb_capas.addItem(f'{capa.name()}  [{capa.geometryType()}]', lid)
        self._cmb_capas.blockSignals(False)

    def _usar_capa(self):
        idx = self._cmb_capas.currentIndex()
        if idx <= 0:
            QMessageBox.warning(self, 'Sin capa', 'Selecciona una capa vectorial primero.')
            return
        lid   = self._cmb_capas.currentData()
        capa  = QgsProject.instance().mapLayer(lid)
        if not capa:
            return
        geoms = [f.geometry() for f in capa.getFeatures()
                 if f.geometry() and not f.geometry().isEmpty()]
        if not geoms:
            QMessageBox.warning(self, 'Sin geometría', 'La capa no tiene geometrías válidas.')
            return
        geom = geoms[0]
        for g in geoms[1:]:
            geom = geom.combine(g)
        self._aoi_geom     = geom.asWkt()
        self._aoi_crs_epsg = capa.crs().postgisSrid()
        self._dibujar_rubber(geom, capa.crs())
        self._calcular_ficha_aoi(geom, capa.crs())
        self._actualizar_estado_aoi()

    def _activar_dibujo(self):
        self._puntos_poly = []
        if self._rubber:
            self._rubber.reset()
        self._rubber = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self._rubber.setColor(QColor(21, 101, 192, 160))
        self._rubber.setWidth(2)
        self._tool_dibujo = QgsMapToolEmitPoint(self.canvas)
        self._tool_dibujo.canvasClicked.connect(self._click_mapa)
        self.canvas.setMapTool(self._tool_dibujo)
        self._btn_dibujar.setText('✏  Dibujando... (doble clic o clic derecho para cerrar)')
        self._btn_dibujar.setStyleSheet(_btn_peligro())
        self._click_count = 0
        self.showMinimized()

    def _click_mapa(self, point, button):
        self._click_count = getattr(self, '_click_count', 0) + 1
        if button == Qt.RightButton or self._click_count > 1:
            if len(self._puntos_poly) >= 3:
                self._cerrar_poligono()
            return
        self._puntos_poly.append(QgsPointXY(point.x(), point.y()))
        self._rubber.addPoint(point)
        self._click_count = 0

    def _cerrar_poligono(self):
        if len(self._puntos_poly) < 3:
            return
        ring = [(p.x(), p.y()) for p in self._puntos_poly]
        ring.append(ring[0])
        wkt  = 'POLYGON((' + ','.join(f'{x} {y}' for x, y in ring) + '))'
        geom = QgsGeometry.fromWkt(wkt)
        self._aoi_geom     = wkt
        crs = self.canvas.mapSettings().destinationCrs()
        self._aoi_crs_epsg = crs.postgisSrid()
        self._dibujar_rubber(geom, crs)
        self._calcular_ficha_aoi(geom, crs)
        self.canvas.unsetMapTool(self._tool_dibujo)
        self._btn_dibujar.setText('✏  Activar dibujo de polígono')
        self._btn_dibujar.setStyleSheet(_btn_primario(CYAN, VERDE))
        self.showNormal(); self.raise_(); self.activateWindow()
        self._actualizar_estado_aoi()

    def _dibujar_rubber(self, geom, crs):
        if self._rubber:
            self._rubber.reset()
        self._rubber = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self._rubber.setColor(QColor(13, 71, 161, 70))
        self._rubber.setStrokeColor(QColor(21, 101, 192, 220))
        self._rubber.setWidth(2)
        dst = self.canvas.mapSettings().destinationCrs()
        if crs != dst:
            geom_t = QgsGeometry(geom)
            geom_t.transform(QgsCoordinateTransform(crs, dst, QgsProject.instance()))
            self._rubber.setToGeometry(geom_t, dst)
        else:
            self._rubber.setToGeometry(geom, crs)

    def _limpiar_aoi(self):
        self._aoi_geom = None; self._aoi_crs_epsg = None
        if self._rubber: self._rubber.reset()
        self._datos_ficha = {}
        self._limpiar_ficha()
        self._actualizar_estado_aoi()
        # Actualizar panel MDE
        self._lbl_mde_aoi.setText('Sin AOI definida — ve a la pestaña "Seleccionar AOI"')
        self._lbl_mde_aoi.setStyleSheet(
            f'background:{ROJO_C};color:{ROJO};padding:8px;border-radius:5px;font-size:10px;')

    def _zoom_aoi(self):
        if not self._aoi_geom or not self._aoi_crs_epsg:
            return
        try:
            geom = QgsGeometry.fromWkt(self._aoi_geom)
            crs  = QgsCoordinateReferenceSystem(f'EPSG:{self._aoi_crs_epsg}')
            dst  = self.canvas.mapSettings().destinationCrs()
            if crs != dst:
                geom.transform(QgsCoordinateTransform(crs, dst, QgsProject.instance()))
            ext = geom.boundingBox()
            ext.grow(ext.width() * 0.1)
            self.canvas.setExtent(ext)
            self.canvas.refresh()
        except Exception as ex:
            QMessageBox.warning(self, 'geeSWAT', f'Error al hacer zoom: {ex}')

    def _actualizar_estado_aoi(self):
        tiene = bool(self._aoi_geom)
        self._btn_zoom_aoi.setEnabled(tiene)
        self._btn_limpiar_aoi.setEnabled(tiene)
        self._btn_ir_mde.setEnabled(tiene)
        if tiene and self._datos_ficha:
            area = self._datos_ficha.get('Area', '?')
            self._lbl_aoi_estado.setText(f'✔ AOI definida\nÁrea: {area}')
            self._lbl_aoi_estado.setStyleSheet(
                f'background:{VERDE_C};color:{VERDE};border-radius:6px;padding:6px;font-size:10px;')
            # Actualizar label en pestaña MDE
            self._lbl_mde_aoi.setText(
                f'✔ AOI definida — Área: {area}\n'
                f'Bbox: [{self._datos_ficha.get("Bbox Oeste","?")} , '
                f'{self._datos_ficha.get("Bbox Sur","?")} , '
                f'{self._datos_ficha.get("Bbox Este","?")} , '
                f'{self._datos_ficha.get("Bbox Norte","?")}]')
            self._lbl_mde_aoi.setStyleSheet(
                f'background:{VERDE_C};color:{VERDE};padding:8px;border-radius:5px;font-size:10px;')
        else:
            self._lbl_aoi_estado.setText('Sin AOI definida')
            self._lbl_aoi_estado.setStyleSheet(
                f'background:#ECEFF1;color:{GRIS};border-radius:6px;padding:6px;font-size:10px;')

    def _calcular_ficha_aoi(self, geom, crs):
        try:
            d = QgsDistanceArea()
            d.setSourceCrs(crs, QgsProject.instance().transformContext())
            d.setEllipsoid('WGS84')
            area_m2  = d.measureArea(geom)
            area_ha  = area_m2 / 10000.0
            area_km2 = area_m2 / 1e6
            perim_m  = d.measurePerimeter(geom)
            perim_km = perim_m / 1000.0

            geom_ll = QgsGeometry(geom)
            crs84   = QgsCoordinateReferenceSystem('EPSG:4326')
            if crs != crs84:
                geom_ll.transform(QgsCoordinateTransform(crs, crs84, QgsProject.instance()))
            centro  = geom_ll.centroid().asPoint()
            lat, lon= centro.y(), centro.x()

            zona_num = int((lon + 180) / 6) + 1
            hemis    = 'N' if lat >= 0 else 'S'
            zona_utm = f'{zona_num}{hemis}'
            epsg_utm = (32600 + zona_num) if lat >= 0 else (32700 + zona_num)

            bb = geom_ll.boundingBox()
            n_verts = 0
            try:
                wt = QgsWkbTypes.geometryType(geom.wkbType())
                if wt == QgsWkbTypes.PolygonGeometry:
                    if QgsWkbTypes.isMultiType(geom.wkbType()):
                        mp = geom.asMultiPolygon()
                        n_verts = len(mp[0][0]) if mp else 0
                    else:
                        p = geom.asPolygon()
                        n_verts = len(p[0]) if p else 0
            except Exception:  # nosec
                pass

            # Alerta área
            if area_ha < 1:
                alerta = '⚠ Área muy pequeña (mínimo recomendado: 1 ha)'
                c_alerta = NARANJA
            elif area_ha > 50000:
                alerta = '⛔ Área grande — se usará Google Drive para la descarga'
                c_alerta = ROJO
            elif area_ha > 5000:
                alerta = '🟡 Área grande — resolución reducida automáticamente'
                c_alerta = '#F57F17'
            else:
                alerta = '✅ Área dentro del rango óptimo para descarga directa'
                c_alerta = VERDE_M

            self._lbl_alerta_area.setText(alerta)
            self._lbl_alerta_area.setStyleSheet(
                f'background:{c_alerta}22;color:{c_alerta};'
                f'border-radius:5px;padding:6px;font-size:10px;'
                f'border:1px solid {c_alerta};')
            self._lbl_alerta_area.setVisible(True)

            self._datos_ficha = {
                'Area'         : f'{area_ha:.2f} ha  /  {area_km2:.4f} km²',
                'Perímetro'    : f'{perim_km:.3f} km',
                'Centroide Lat': f'{lat:.6f}°',
                'Centroide Lon': f'{lon:.6f}°',
                'Zona UTM'     : zona_utm,
                'Bbox Norte'   : f'{bb.yMaximum():.6f}°',
                'Bbox Sur'     : f'{bb.yMinimum():.6f}°',
                'Bbox Este'    : f'{bb.xMaximum():.6f}°',
                'Bbox Oeste'   : f'{bb.xMinimum():.6f}°',
                'Nº vértices'  : str(n_verts),
                '_bbox_wgs84'  : (bb.xMinimum(), bb.yMinimum(), bb.xMaximum(), bb.yMaximum()),
            }
            self._renderizar_ficha()
        except Exception as ex:
            QMessageBox.warning(self, 'geeSWAT', f'Error al calcular ficha AOI:\n{ex}')

    def _renderizar_ficha(self):
        # Limpiar layout ficha
        while self._ficha_layout.count():
            item = self._ficha_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._datos_ficha:
            self._ficha_layout.addWidget(self._lbl_sin_aoi)
            self._ficha_layout.addStretch()
            return

        for k, v in self._datos_ficha.items():
            if k.startswith('_'):
                continue
            fila = QHBoxLayout()
            lk = QLabel(k + ':')
            lk.setStyleSheet(f'font-weight:bold;color:{AZUL};font-size:10px;min-width:110px;')
            lk.setFixedWidth(120)
            lv = QLabel(str(v))
            lv.setStyleSheet(f'color:{GRIS_OS};font-size:10px;')
            lv.setTextInteractionFlags(Qt.TextSelectableByMouse)
            lv.setCursor(Qt.IBeamCursor)
            lv.setWordWrap(True)
            fila.addWidget(lk); fila.addWidget(lv, 1)
            self._ficha_layout.addLayout(fila)

            sep = QFrame(); sep.setFrameShape(QFrame.HLine)
            sep.setStyleSheet('color:#F5F5F5;background:#F5F5F5;border:none;max-height:1px;')
            self._ficha_layout.addWidget(sep)

        self._ficha_layout.addStretch()

    def _limpiar_ficha(self):
        while self._ficha_layout.count():
            item = self._ficha_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._ficha_layout.addWidget(self._lbl_sin_aoi)
        self._ficha_layout.addStretch()
        self._lbl_alerta_area.setVisible(False)

    # ══════════════════════════════════════════════════════════════════════════
    # DEM — parámetros
    # ══════════════════════════════════════════════════════════════════════════
    def _actualizar_info_dem(self):
        idx = self._cmb_dem.currentIndex()
        if idx < 0 or idx >= len(GEE_DEMS):
            return
        d    = GEE_DEMS[idx]
        esc  = self._spn_escala.value()
        esc_ef = esc if esc > 0 else d['scale']
        self._lbl_dem_desc.setText(
            f'<b>Colección GEE:</b> {d["collection"]}<br>'
            f'<b>Banda:</b> {d["band"]}  |  <b>Tipo:</b> {d["dtype"]}  |  <b>Res. nativa:</b> {d["scale"]} m<br>'
            f'<b>Info:</b> {d["desc"]}<br>'
            f'<b>Escala efectiva:</b> {esc_ef} m' +
            (' <i>(nativa)</i>' if esc == 0 else ''))
        self._lbl_escala_info.setText(
            f'0 = resolución nativa ({d["scale"]} m). '
            f'Escala efectiva: {esc_ef} m.')
        self._actualizar_ruta_salida()

    # ══════════════════════════════════════════════════════════════════════════
    # DESCARGA MDE
    # ══════════════════════════════════════════════════════════════════════════
    def _ejecutar_descarga(self):
        # Validaciones
        if not self._aoi_geom:
            QMessageBox.warning(self, 'geeSWAT',
                'Define primero el área de interés en la pestaña "Seleccionar AOI".')
            self._tabs.setCurrentIndex(1)
            return

        carpeta = self._inp_carpeta.text().strip()
        if not carpeta:
            QMessageBox.warning(self, 'geeSWAT',
                'Configura la carpeta de salida en la pestaña "Config GEE".')
            self._tabs.setCurrentIndex(0)
            return

        proyecto = self._inp_project.text().strip()
        gmail    = self._inp_gmail.text().strip()
        idx_dem  = self._cmb_dem.currentIndex()
        dem_info = GEE_DEMS[idx_dem]
        escala   = self._spn_escala.value()
        scale_eff= escala if escala > 0 else dem_info['scale']

        # Obtener bbox WGS84
        bbox = self._datos_ficha.get('_bbox_wgs84')
        if not bbox:
            # Calcular desde WKT
            geom = QgsGeometry.fromWkt(self._aoi_geom)
            crs  = QgsCoordinateReferenceSystem(f'EPSG:{self._aoi_crs_epsg}')
            crs84= QgsCoordinateReferenceSystem('EPSG:4326')
            if crs != crs84:
                geom.transform(QgsCoordinateTransform(crs, crs84, QgsProject.instance()))
            bb  = geom.boundingBox()
            bbox= (bb.xMinimum(), bb.yMinimum(), bb.xMaximum(), bb.yMaximum())

        lon_min, lat_min, lon_max, lat_max = bbox

        # Crear carpeta DEM
        dem_dir = os.path.join(carpeta, 'DEM')
        os.makedirs(dem_dir, exist_ok=True)

        # Nombre del archivo de salida
        nombre_proy = self._inp_nombre_proy.text().strip()
        ts    = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        slug  = dem_info['collection'].replace('/', '_').replace(' ', '_')
        fname = f'{nombre_proy}_{slug}_{ts}.tif' if nombre_proy else f'{slug}_{ts}.tif'
        output_path = os.path.join(dem_dir, fname)

        # Iniciar worker
        self._btn_descargar.setEnabled(False)
        self._btn_cancelar_mde.setEnabled(True)
        self._progreso_mde.setValue(0)
        self._txt_log.clear()
        self._log(f'Iniciando descarga: {dem_info["label"]}')
        self._log(f'Escala efectiva   : {scale_eff} m')
        self._log(f'Bbox WGS84        : [{lon_min:.5f}, {lat_min:.5f}, {lon_max:.5f}, {lat_max:.5f}]')
        self._log(f'Carpeta de salida : {dem_dir}')
        self._log(f'Archivo           : {fname}')
        self._log('─' * 50)

        self._worker = MDEWorker(
            dem_info, lon_min, lat_min, lon_max, lat_max,
            scale_eff, output_path, proyecto, gmail)
        self._worker.log.connect(self._log)
        self._worker.progreso.connect(self._progreso_mde.setValue)
        self._worker.ok.connect(self._descarga_completada)
        self._worker.error.connect(self._descarga_error)
        self._worker.finished.connect(self._worker_terminado)
        self._worker.start()

    def _cancelar_descarga(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancelar()
            self._log('⚠ Cancelando...')

    def _log(self, msg):
        ts = datetime.datetime.now().strftime('%H:%M:%S')
        self._txt_log.append(f'<span style="color:#95A5A6">[{ts}]</span> {msg}')
        sb = self._txt_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _descarga_completada(self, ruta, via_drive):
        if via_drive:
            self._log(f'✔ Exportación a Google Drive completada: {ruta}')
            QMessageBox.information(
                self, 'geeSWAT — Completado',
                f'✔ El MDE se exportó a Google Drive:\n'
                f'  Carpeta: {GDRIVE_FOLDER}\n'
                f'  Archivo: {ruta}.tif\n\n'
                '1. Abre https://drive.google.com\n'
                f'2. Ve a la carpeta "{GDRIVE_FOLDER}"\n'
                '3. Descarga el archivo .tif\n'
                '4. Arrástralo al proyecto QGIS')
        else:
            self._log(f'✔ MDE guardado localmente: {ruta}')
            # Cargar en QGIS
            try:
                dem_info = GEE_DEMS[self._cmb_dem.currentIndex()]
                nombre   = dem_info['label'].split('—')[0].strip()
                rlayer   = QgsRasterLayer(ruta, f'MDE — {nombre}')
                if rlayer.isValid():
                    QgsProject.instance().addMapLayer(rlayer)
                    self._log('✔ Raster cargado en QGIS.')
                else:
                    self._log(f'⚠ Raster guardado pero no pudo cargarse automáticamente:\n  {ruta}')
            except Exception as ex:
                self._log(f'⚠ Error al cargar en QGIS: {ex}')

    def _descarga_error(self, msg):
        self._log(f'✖ ERROR: {msg}')
        QMessageBox.critical(self, 'geeSWAT — Error de descarga', f'{msg}')

    def _worker_terminado(self):
        self._btn_descargar.setEnabled(True)
        self._btn_cancelar_mde.setEnabled(False)

    # ══════════════════════════════════════════════════════════════════════════
    # HELPER VISUAL
    # ══════════════════════════════════════════════════════════════════════════
    def _generar_icono_cuenca(self, size):
        pm = QPixmap(size, size); pm.fill(Qt.transparent)
        p  = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QBrush(QColor('#1565C0'))); p.setPen(Qt.NoPen)
        p.drawEllipse(4, 4, size - 8, size - 8)
        cx = size // 2; cy = size // 2; r = size // 5
        p.setBrush(QBrush(QColor('white')))
        path = QPainterPath()
        path.moveTo(cx, cy - r * 2)
        path.quadTo(cx + r * 2, cy, cx + r, cy + r)
        path.quadTo(cx, cy + r * 3, cx - r, cy + r)
        path.quadTo(cx - r * 2, cy, cx, cy - r * 2)
        p.drawPath(path)
        p.end(); return pm

    def closeEvent(self, event):
        if self._rubber:
            self._rubber.reset()
        if self._worker and self._worker.isRunning():
            self._worker.cancelar()
            self._worker.wait(3000)
        super().closeEvent(event)
