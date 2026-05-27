# -*- coding: utf-8 -*-
"""
soil_descargar_suelo.py — geeSWAT
Descarga tipo de suelo desde GEE para SWAT.

Fuentes disponibles:
  1. FAO DSMW  — FeatureCollection vectorial, campo SNUM, rasterizado a escala deseada.
                 Assets GEE publicos usados:
                   - FAO/HWSD/soil_data (o asset propio DSMW_GEO)
  2. DSoilMap  — Raster Digital Soil Open Land Map (250 m).
                 'projects/gee-unas/assets/DSOLMap'

Salidas por ejecucion:
  <carpeta_salida>/SOIL/
      <proyecto>_<fuente>_<timestamp>.tif    — raster de tipo de suelo (Int16)
      <proyecto>_<fuente>_<timestamp>_Soil_lookup.csv — tabla SNUM,SNAM para SWAT

Proyeccion: usa el EPSG del proyecto configurado en geeSWAT.

geeSWAT v1.2.0 — Geomatica Ambiental
"""
import os
import math
import time
import datetime
import csv

from qgis.PyQt.QtCore import QThread, pyqtSignal

# ── Fuentes de suelo disponibles ─────────────────────────────────────────────
SOIL_SOURCES = [
    {
        'id'   : 'FAO',
        'label': 'Suelo FAO (DSMW - FAO/UNESCO World Soil Map)',
        'tipo' : 'vector',
        'asset': 'projects/gee-unas/assets/DSMW_GEO',  # pragma: allowlist secret
        'campo': 'SNUM',
        'campo_nombre': 'SNAM',
        'scale': 250,
        'dtype': 'Int16',
        'desc' : (
            'Mapa Mundial de Suelos FAO/UNESCO (DSMW). '
            'Fuente vectorial rasterizada al AOI. Escala 1:5,000,000. '
            'Campos SWAT: SNUM (ID numerico), SNAM (nombre del suelo).'
        ),
        'tabla_asset': 'projects/gee-unas/assets/SWAT/Equivalencia_Suelo_FAO',  # pragma: allowlist secret
        'nodata': -9999,
    },
    {
        'id'   : 'DSoilMap',
        'label': 'DSoilMap - Digital Soil Open Land Map (250 m)',
        'tipo' : 'raster',
        'asset': 'projects/gee-unas/assets/DSOLMap',  # pragma: allowlist secret
        'campo': 'SNUM',
        'campo_nombre': 'SNAM',
        'scale': 250,
        'dtype': 'Int16',
        'desc' : (
            'Digital Soil Open Land Map — raster global 250 m. '
            'IDs numericos directamente compatibles con SWAT. '
            'Mayor detalle espacial que FAO en regiones tropicales.'
        ),
        'tabla_asset': 'projects/gee-unas/assets/SWAT/Equivalencia_DSOLMap',  # pragma: allowlist secret
        'campo_id_tabla': 'OBJECTID',
        'nodata': -9999,
    },
]
SOIL_LABELS = [s['label'] for s in SOIL_SOURCES]

GDRIVE_FOLDER  = 'GEE_geeSWAT'
LIMITE_MP      = 10_000_000
POLL_INTERVAL  = 12


# ═════════════════════════════════════════════════════════════════════════════
# WORKER THREAD — Descarga Suelo + Tabla lookup
# ═════════════════════════════════════════════════════════════════════════════
class SoilWorker(QThread):
    log      = pyqtSignal(str)
    progreso = pyqtSignal(int)
    ok       = pyqtSignal(str, str, bool)  # (ruta_raster, ruta_csv, via_drive)
    error    = pyqtSignal(str)

    def __init__(self, source_info, lon_min, lat_min, lon_max, lat_max,
                 scale_eff, crs_epsg, output_raster, output_csv,
                 project_id):
        super().__init__()
        self.source_info   = source_info
        self.lon_min       = lon_min
        self.lat_min       = lat_min
        self.lon_max       = lon_max
        self.lat_max       = lat_max
        self.scale_eff     = scale_eff
        self.crs_epsg      = crs_epsg          # ej. 32718
        self.output_raster = output_raster
        self.output_csv    = output_csv
        self.project_id    = project_id
        self._cancelar     = False

    def cancelar(self):
        self._cancelar = True

    def run(self):
        try:
            import ee
            # ── Conectar ──────────────────────────────────────────────────────
            kwargs = {}
            if self.project_id.strip():
                kwargs['project'] = self.project_id.strip()
            self.log.emit(f"Conectando GEE — proyecto: {self.project_id or '(local)'}")
            ee.Initialize(opt_url='https://earthengine.googleapis.com', **kwargs)
            self.log.emit("GEE conectado.")

            src    = self.source_info
            region = ee.Geometry.Rectangle(
                [self.lon_min, self.lat_min, self.lon_max, self.lat_max])
            crs_str = f'EPSG:{self.crs_epsg}' if self.crs_epsg else 'EPSG:4326'

            # ── Construir imagen de suelo ──────────────────────────────────────
            self.log.emit(f"Fuente        : {src['label']}")
            self.log.emit(f"Asset GEE     : {src['asset']}")
            self.log.emit(f"Escala        : {self.scale_eff} m")
            self.log.emit(f"Proyeccion    : {crs_str}")

            if src['tipo'] == 'vector':
                self.log.emit("Rasterizando FeatureCollection FAO...")
                fc     = ee.FeatureCollection(src['asset'])
                imagen = (fc
                    .reduceToImage(
                        properties=[src['campo']],
                        reducer=ee.Reducer.first()
                    )
                    .rename(src['campo'])
                    .toInt16()
                    .reproject(crs=crs_str, scale=self.scale_eff)
                    .unmask(src['nodata'])
                    .clip(region)
                )
            else:
                self.log.emit("Cargando raster DSoilMap...")
                imagen = (ee.Image(src['asset'])
                    .rename(src['campo'])
                    .toInt16()
                    .reproject(crs=crs_str, scale=self.scale_eff)
                    .unmask(src['nodata'])
                    .clip(region)
                )
            self.progreso.emit(10)

            # ── Decidir: descarga directa o Drive ─────────────────────────────
            lat_med = (self.lat_min + self.lat_max) / 2.0
            cos_lat = math.cos(math.radians(lat_med))
            ancho_m = (self.lon_max - self.lon_min) * 111320.0 * cos_lat
            alto_m  = (self.lat_max - self.lat_min) * 111320.0
            total_px= max(1, int(ancho_m / self.scale_eff)) * \
                      max(1, int(alto_m  / self.scale_eff))
            peso_mb = total_px * 2 / 1_048_576  # Int16 = 2 bytes/px

            self.log.emit(
                f"Dimension aprox: {total_px/1e6:.2f} MP  |  ~{peso_mb:.1f} MB")

            if self._cancelar:
                return

            usar_drive = total_px > LIMITE_MP

            if usar_drive:
                self.log.emit(
                    f"Area grande ({total_px/1e6:.1f} MP) "
                    f"-> exportando a Google Drive / {GDRIVE_FOLDER}")
                raster_ok = self._exportar_drive(ee, imagen, region, crs_str)
                if not raster_ok:
                    return
                # Tabla lookup: intentar descargar aunque sea Drive
                csv_ok = self._generar_csv(ee, imagen, region, src)
                self.ok.emit(self.output_raster, self.output_csv if csv_ok else '', True)
            else:
                self.log.emit(f"Tamano dentro del limite ({peso_mb:.1f} MB) -> descarga directa")
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

        self.log.emit("Descargando GeoTIFF de suelo...")
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
                extracted = zf.extract(tifs[0], os.path.dirname(self.output_raster) or '.')
            shutil.move(extracted, self.output_raster)
            os.remove(tmp)
        else:
            shutil.move(tmp, self.output_raster)

        self.log.emit(f"Raster suelo guardado: {self.output_raster}")

    # ── Exportar a Drive ──────────────────────────────────────────────────────
    def _exportar_drive(self, ee, imagen, region, crs_str):
        ts        = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        src_slug  = self.source_info['id']
        task_name = f"SOIL_{src_slug}_{ts}"

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
        self.log.emit(
            "Monitorea en: https://code.earthengine.google.com/tasks")

        ESTADOS_FIN = {'COMPLETED', 'FAILED', 'CANCELLED', 'CANCEL_REQUESTED'}
        ultimo_estado = ''
        espera = 0
        spinner = ['|', '/', '-', '\\']
        idx = 0

        while True:
            time.sleep(POLL_INTERVAL)
            espera += POLL_INTERVAL
            if self._cancelar:
                task.cancel()
                raise RuntimeError("Cancelado por el usuario.")
            try:
                status   = task.status()
                estado   = status.get('state', 'UNKNOWN')
                progreso = status.get('progress', 0.0)
            except Exception as ex:
                self.log.emit(f"No se pudo consultar estado: {ex}")
                continue
            if estado != ultimo_estado:
                self.log.emit(f"Estado GEE: {estado}")
                ultimo_estado = estado
            if progreso and progreso > 0:
                self.progreso.emit(int(progreso * 100))
            m, s = espera // 60, espera % 60
            self.log.emit(
                f"{spinner[idx % 4]} {'%.1f%%' % (progreso*100) if progreso else 'procesando...'}"
                f"  |  {m}m {s}s")
            idx += 1
            if estado in ESTADOS_FIN:
                break

        if estado == 'COMPLETED':
            self.log.emit(
                f"Exportacion completada -> Drive/{GDRIVE_FOLDER}/{task_name}.tif")
            self.progreso.emit(100)
            return True
        err = task.status().get('error_message', 'Error desconocido')
        raise RuntimeError(f"GEE Drive fallo [{estado}]: {err}")

    # ── Generar CSV Soil_lookup ───────────────────────────────────────────────
    def _generar_csv(self, ee, imagen, region, src):
        """
        Extrae los IDs unicos del raster, cruza con la tabla de equivalencia GEE
        y genera el CSV Soil_lookup.csv compatible con SWAT.

        Columnas: SNUM, SNAM
        """
        try:
            self.log.emit("Generando tabla Soil_lookup.csv...")

            # ── IDs unicos presentes en el raster recortado ───────────────────
            ids_list = (
                imagen
                .reduceRegion(
                    reducer   = ee.Reducer.toList(),
                    geometry  = region,
                    scale     = self.scale_eff,
                    maxPixels = 1e10,
                    tileScale = 16,
                    bestEffort= True,
                )
                .get(imagen.bandNames().get(0))
            )
            ids_uniq = ee.List(ids_list).distinct()
            ids_py   = [int(x) for x in ids_uniq.getInfo()
                        if x != src['nodata'] and x is not None]
            ids_py   = sorted(set(ids_py))
            self.log.emit(f"IDs unicos en AOI: {len(ids_py)}")

            # ── Intentar descargar tabla de equivalencia de GEE ───────────────
            lookup = {}
            try:
                tabla_fc = ee.FeatureCollection(src['tabla_asset'])
                # Campo ID en tabla
                campo_id   = src.get('campo_id_tabla', 'OBJECTID')
                campo_nom  = src.get('campo_nombre', 'SNAM')
                filas = tabla_fc.select([campo_id, campo_nom]).getInfo()
                for feat in filas.get('features', []):
                    props = feat.get('properties', {})
                    # El campo OBJECTID puede venir con BOM en FAO
                    sid  = None
                    snam = str(props.get(campo_nom, ''))
                    for k, v in props.items():
                        k_clean = k.lstrip('\ufeff').strip()
                        if k_clean.upper() in (campo_id.upper(), 'SOIL_ID',
                                               'OBJECTID', 'SNUM', 'ID'):
                            try:
                                sid = int(float(v))
                            except Exception:  # nosec
                                pass
                            break
                    if sid is not None and sid in ids_py:
                        lookup[sid] = snam
                self.log.emit(
                    f"Tabla GEE descargada: {len(lookup)} entradas coincidentes")
            except Exception as ex:
                self.log.emit(
                    f"Tabla GEE no disponible ({ex}). "
                    "CSV generado solo con IDs numericos.")

            # ── Escribir CSV ──────────────────────────────────────────────────
            with open(self.output_csv, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['SNUM', 'SNAM'])
                for sid in ids_py:
                    snam = lookup.get(sid, f'SOIL_{sid:04d}')
                    writer.writerow([sid, snam])

            self.log.emit(f"Soil_lookup.csv guardado: {self.output_csv}")
            return True

        except Exception as ex:
            self.log.emit(f"Error al generar CSV: {ex}")
            return False
