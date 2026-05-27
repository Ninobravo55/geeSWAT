# -*- coding: utf-8 -*-
"""
landuse_descargar_landuse.py — geeSWAT
Descarga uso del suelo desde GEE para SWAT.

Fuentes disponibles:
  1. Copernicus 2019 — COPERNICUS/Landcover/100m/Proba-V-C3/Global/2019
                        banda: discrete_classification  | escala nativa: 100 m
  2. ESA GlobCover 2009 — ESA/GLOBCOVER_L4_200901_200912_V2_3
                          banda: landcover               | escala nativa: 300 m

Salidas por ejecucion:
  <carpeta_salida>/LANDUSE/
      <proyecto>_<fuente>_<timestamp>.tif             — raster Int16
      <proyecto>_<fuente>_<timestamp>_Landuse_lookup.csv — LANDUSE_ID, SWAT_CODE

geeSWAT v1.2.0 — Geomatica Ambiental
"""
import os
import math
import time
import datetime
import csv

from qgis.PyQt.QtCore import QThread, pyqtSignal

# ── Tablas SWAT embebidas (del notebook 05_LANDUSE.ipynb) ────────────────────
_TABLA_2019 = [
    {"LANDUSE_ID": 0,   "SWAT_CODE": "RNGB"},
    {"LANDUSE_ID": 20,  "SWAT_CODE": "SHRB"},
    {"LANDUSE_ID": 30,  "SWAT_CODE": "PAST"},
    {"LANDUSE_ID": 40,  "SWAT_CODE": "AGRL"},
    {"LANDUSE_ID": 50,  "SWAT_CODE": "URHD"},
    {"LANDUSE_ID": 60,  "SWAT_CODE": "BSVG"},
    {"LANDUSE_ID": 70,  "SWAT_CODE": "WATR"},
    {"LANDUSE_ID": 80,  "SWAT_CODE": "WATR"},
    {"LANDUSE_ID": 90,  "SWAT_CODE": "WETL"},
    {"LANDUSE_ID": 100, "SWAT_CODE": "RNGE"},
    {"LANDUSE_ID": 111, "SWAT_CODE": "FRSE"},
    {"LANDUSE_ID": 112, "SWAT_CODE": "FRSE"},
    {"LANDUSE_ID": 113, "SWAT_CODE": "FRSD"},
    {"LANDUSE_ID": 114, "SWAT_CODE": "FRSD"},
    {"LANDUSE_ID": 115, "SWAT_CODE": "FRST"},
    {"LANDUSE_ID": 116, "SWAT_CODE": "FRST"},
    {"LANDUSE_ID": 121, "SWAT_CODE": "RNGB"},
    {"LANDUSE_ID": 122, "SWAT_CODE": "RNGB"},
    {"LANDUSE_ID": 123, "SWAT_CODE": "RNGB"},
    {"LANDUSE_ID": 124, "SWAT_CODE": "RNGB"},
    {"LANDUSE_ID": 125, "SWAT_CODE": "FRST"},
    {"LANDUSE_ID": 126, "SWAT_CODE": "FRST"},
    {"LANDUSE_ID": 200, "SWAT_CODE": "WATR"},
]

_TABLA_2009 = [
    {"LANDUSE_ID": 11,  "SWAT_CODE": "WETL"},
    {"LANDUSE_ID": 14,  "SWAT_CODE": "AGRL"},
    {"LANDUSE_ID": 20,  "SWAT_CODE": "AGRL"},
    {"LANDUSE_ID": 30,  "SWAT_CODE": "RNGB"},
    {"LANDUSE_ID": 40,  "SWAT_CODE": "FRSE"},
    {"LANDUSE_ID": 50,  "SWAT_CODE": "FRSD"},
    {"LANDUSE_ID": 60,  "SWAT_CODE": "FRSD"},
    {"LANDUSE_ID": 70,  "SWAT_CODE": "FRSE"},
    {"LANDUSE_ID": 90,  "SWAT_CODE": "FRST"},
    {"LANDUSE_ID": 100, "SWAT_CODE": "FRST"},
    {"LANDUSE_ID": 110, "SWAT_CODE": "RNGE"},
    {"LANDUSE_ID": 120, "SWAT_CODE": "RNGB"},
    {"LANDUSE_ID": 130, "SWAT_CODE": "RNGB"},
    {"LANDUSE_ID": 140, "SWAT_CODE": "RNGE"},
    {"LANDUSE_ID": 150, "SWAT_CODE": "BSVG"},
    {"LANDUSE_ID": 160, "SWAT_CODE": "WETF"},
    {"LANDUSE_ID": 170, "SWAT_CODE": "WETF"},
    {"LANDUSE_ID": 180, "SWAT_CODE": "WETL"},
    {"LANDUSE_ID": 190, "SWAT_CODE": "URHD"},
    {"LANDUSE_ID": 200, "SWAT_CODE": "BARR"},
    {"LANDUSE_ID": 210, "SWAT_CODE": "WATR"},
    {"LANDUSE_ID": 220, "SWAT_CODE": "WATR"},
    {"LANDUSE_ID": 230, "SWAT_CODE": "RNGB"},
]

# ── Fuentes disponibles ───────────────────────────────────────────────────────
LANDUSE_SOURCES = [
    {
        'id'        : 'COPERNICUS_2019',
        'label'     : 'Copernicus Global Land Cover 2019 (100 m)',
        'collection': 'COPERNICUS/Landcover/100m/Proba-V-C3/Global/2019',
        'banda'     : 'discrete_classification',
        'scale'     : 100,
        'tabla_swat': _TABLA_2019,
        'desc'      : (
            'Copernicus Global Land Cover Layers CGLS-LC100 Collection 3. '
            '23 clases. Resolucion nativa 100 m. '
            'Recomendado para estudios actuales (ano 2019).'
        ),
    },
    {
        'id'        : 'GLOBCOVER_2009',
        'label'     : 'ESA GlobCover 2009 (300 m)',
        'collection': 'ESA/GLOBCOVER_L4_200901_200912_V2_3',
        'banda'     : 'landcover',
        'scale'     : 300,
        'tabla_swat': _TABLA_2009,
        'desc'      : (
            'ESA GlobCover L4 2009. 23 clases. Resolucion nativa 300 m. '
            'Util para estudios historicos o comparaciones temporales.'
        ),
    },
]
LANDUSE_LABELS = [s['label'] for s in LANDUSE_SOURCES]

GDRIVE_FOLDER = 'GEE_geeSWAT'
LIMITE_MP     = 10_000_000
POLL_INTERVAL = 12


# ═════════════════════════════════════════════════════════════════════════════
# WORKER THREAD
# ═════════════════════════════════════════════════════════════════════════════
class LanduseWorker(QThread):
    log      = pyqtSignal(str)
    progreso = pyqtSignal(int)
    ok       = pyqtSignal(str, str, bool)   # (ruta_tif, ruta_csv, via_drive)
    error    = pyqtSignal(str)

    def __init__(self, source_info, lon_min, lat_min, lon_max, lat_max,
                 scale_eff, crs_epsg, output_raster, output_csv, project_id):
        super().__init__()
        self.source_info   = source_info
        self.lon_min       = lon_min
        self.lat_min       = lat_min
        self.lon_max       = lon_max
        self.lat_max       = lat_max
        self.scale_eff     = scale_eff
        self.crs_epsg      = crs_epsg
        self.output_raster = output_raster
        self.output_csv    = output_csv
        self.project_id    = project_id
        self._cancelar     = False

    def cancelar(self):
        self._cancelar = True

    def run(self):
        try:
            import ee
            kwargs = {}
            if self.project_id.strip():
                kwargs['project'] = self.project_id.strip()
            self.log.emit(f"Conectando GEE — proyecto: {self.project_id or '(local)'}")
            ee.Initialize(opt_url='https://earthengine.googleapis.com', **kwargs)
            self.log.emit("GEE conectado.")

            src     = self.source_info
            region  = ee.Geometry.Rectangle(
                [self.lon_min, self.lat_min, self.lon_max, self.lat_max])
            crs_str = f'EPSG:{self.crs_epsg}' if self.crs_epsg else 'EPSG:4326'

            self.log.emit(f"Fuente        : {src['label']}")
            self.log.emit(f"Asset GEE     : {src['collection']}")
            self.log.emit(f"Banda         : {src['banda']}")
            self.log.emit(f"Escala        : {self.scale_eff} m")
            self.log.emit(f"Proyeccion    : {crs_str}")

            # Cargar imagen
            imagen = (ee.Image(src['collection'])
                .select(src['banda'])
                .clip(region)
                .toInt16()
                .reproject(crs=crs_str, scale=self.scale_eff)
                .unmask(-9999)
            )
            self.progreso.emit(10)

            # Estimar tamano
            cos_lat = math.cos(math.radians((self.lat_min + self.lat_max) / 2.0))
            ancho_m = (self.lon_max - self.lon_min) * 111320.0 * cos_lat
            alto_m  = (self.lat_max - self.lat_min) * 111320.0
            total_px = max(1, int(ancho_m / self.scale_eff)) * \
                       max(1, int(alto_m  / self.scale_eff))
            peso_mb  = total_px * 2 / 1_048_576
            self.log.emit(
                f"Dimension aprox: {total_px/1e6:.2f} MP  |  ~{peso_mb:.1f} MB")

            if self._cancelar:
                return

            usar_drive = total_px > LIMITE_MP

            if usar_drive:
                self.log.emit(
                    f"Area grande ({total_px/1e6:.1f} MP) "
                    f"-> exportando a Google Drive / {GDRIVE_FOLDER}")
                self._exportar_drive(ee, imagen, region, crs_str)
                csv_ok = self._generar_csv(ee, imagen, region, src)
                self.ok.emit(self.output_raster, self.output_csv if csv_ok else '', True)
            else:
                self.log.emit(f"Tamano dentro del limite -> descarga directa")
                self._descarga_directa(ee, imagen, region, crs_str)
                self.progreso.emit(80)
                self._generar_csv(ee, imagen, region, src)
                self.progreso.emit(100)
                self.ok.emit(self.output_raster, self.output_csv, False)

        except Exception as ex:
            self.error.emit(str(ex))

    # ── Descarga directa ──────────────────────────────────────────────────────
    def _descarga_directa(self, ee, imagen, region, crs_str):
        import zipfile, shutil, requests
        from urllib.parse import urlparse
        self.log.emit("Generando URL de descarga GEE...")
        try:
            url = imagen.getDownloadURL({
                'scale' : self.scale_eff,
                'region': region,
                'format': 'GEO_TIFF',
                'crs'   : crs_str,
            })
        except Exception as ex:
            raise RuntimeError(f"Error al generar URL: {ex}")
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            raise RuntimeError(f"URL invalida: esquema '{parsed.scheme}'")
        self.log.emit("Descargando GeoTIFF de uso del suelo...")
        tmp = self.output_raster + '_tmp.bin'
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
                                self.progreso.emit(
                                    10 + min(int(desc * 65 / total), 65))
        except Exception as ex:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise RuntimeError(f"Error HTTP: {ex}")
        if zipfile.is_zipfile(tmp):
            self.log.emit("Descomprimiendo ZIP...")
            with zipfile.ZipFile(tmp, 'r') as zf:
                tifs = [n for n in zf.namelist() if n.lower().endswith('.tif')]
                if not tifs:
                    raise RuntimeError("El ZIP no contiene archivos .tif")
                extracted = zf.extract(
                    tifs[0], os.path.dirname(self.output_raster) or '.')
            import shutil as _sh
            _sh.move(extracted, self.output_raster)
            os.remove(tmp)
        else:
            import shutil as _sh
            _sh.move(tmp, self.output_raster)
        self.log.emit(f"Raster guardado: {self.output_raster}")

    # ── Exportar a Drive ──────────────────────────────────────────────────────
    def _exportar_drive(self, ee, imagen, region, crs_str):
        ts        = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        task_name = f"LANDUSE_{self.source_info['id']}_{ts}"
        task = ee.batch.Export.image.toDrive(
            image          = imagen,
            description    = task_name,
            folder         = GDRIVE_FOLDER,
            fileNamePrefix = task_name,
            scale          = self.scale_eff,
            region         = region,
            crs            = crs_str,
            fileFormat     = 'GeoTIFF',
            maxPixels      = 1e13,
        )
        task.start()
        self.log.emit(f"Task GEE iniciado: {task.id}")
        self.log.emit("Monitorea en: https://code.earthengine.google.com/tasks")
        ESTADOS_FIN = {'COMPLETED', 'FAILED', 'CANCELLED', 'CANCEL_REQUESTED'}
        ultimo = ''; espera = 0; spinner = ['|', '/', '-', '\\']; idx = 0
        while True:
            time.sleep(POLL_INTERVAL)
            espera += POLL_INTERVAL
            if self._cancelar:
                task.cancel()
                raise RuntimeError("Cancelado por el usuario.")
            try:
                status = task.status()
                estado = status.get('state', 'UNKNOWN')
                prog   = status.get('progress', 0.0)
            except Exception as ex:
                self.log.emit(f"No se pudo consultar estado: {ex}")
                continue
            if estado != ultimo:
                self.log.emit(f"Estado GEE: {estado}")
                ultimo = estado
            if prog and prog > 0:
                self.progreso.emit(int(prog * 100))
            m, s = espera // 60, espera % 60
            self.log.emit(
                f"{spinner[idx % 4]} "
                f"{'%.1f%%' % (prog*100) if prog else 'procesando...'}  |  {m}m {s}s")
            idx += 1
            if estado in ESTADOS_FIN:
                break
        if estado == 'COMPLETED':
            self.log.emit(
                f"Exportacion completada -> Drive/{GDRIVE_FOLDER}/{task_name}.tif")
            self.progreso.emit(100)
        else:
            err = task.status().get('error_message', 'Error desconocido')
            raise RuntimeError(f"GEE Drive fallo [{estado}]: {err}")

    # ── Generar CSV Landuse_lookup ─────────────────────────────────────────────
    def _generar_csv(self, ee, imagen, region, src):
        """
        Usa reduceRegion con frequencyHistogram para obtener las clases presentes
        en el raster recortado, luego cruza con la tabla SWAT embebida y genera
        el CSV Landuse_lookup.csv con columnas LANDUSE_ID, SWAT_CODE.
        """
        try:
            self.log.emit("Generando Landuse_lookup.csv...")
            banda = src['banda']
            histo = imagen.reduceRegion(
                reducer   = ee.Reducer.frequencyHistogram(),
                geometry  = region,
                scale     = self.scale_eff,
                maxPixels = 1e13,
                bestEffort= True,
            )
            clases_dict = histo.get(banda).getInfo()
            if not clases_dict:
                self.log.emit("Histograma vacio; CSV no generado.")
                return False
            ids_presentes = sorted([int(k) for k in clases_dict.keys()])
            # Filtrar nodata
            ids_presentes = [i for i in ids_presentes if i != -9999]
            self.log.emit(
                f"Clases presentes en AOI: {len(ids_presentes)} — {ids_presentes}")
            # Lookup embebido
            lookup = {r['LANDUSE_ID']: r['SWAT_CODE'] for r in src['tabla_swat']}
            with open(self.output_csv, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['LANDUSE_ID', 'SWAT_CODE'])
                for lid in ids_presentes:
                    code = lookup.get(lid, f'LU{lid:04d}')
                    writer.writerow([lid, code])
            self.log.emit(f"Landuse_lookup.csv guardado: {self.output_csv}")
            return True
        except Exception as ex:
            self.log.emit(f"Error al generar CSV: {ex}")
            return False
