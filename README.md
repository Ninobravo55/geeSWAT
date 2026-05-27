# geeSWAT v1.2.0

> **QGIS Plugin for SWAT (Soil and Water Assessment Tool) Modeling Data Preparation via Google Earth Engine (GEE).**

[![QGIS Version](https://img.shields.io/badge/QGIS-3.16%20--%203.38%20%7C%204.x-blue.svg?logo=qgis&logoColor=white)](https://qgis.org)
[![Python Version](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-green.svg?logo=python&logoColor=white)](https://python.org)
[![License: GPL v2](https://img.shields.io/badge/License-GPL%20v2-orange.svg)](LICENSE)
[![Developed by Geomatica Ambiental](https://img.shields.io/badge/Developed%20by-Geomatica%20Ambiental-0D47A1.svg)](https://www.geomatica.pe/)

**geeSWAT** es un complemento profesional para **QGIS** diseñado para optimizar de manera exponencial la descarga y el procesamiento de los datos espaciales necesarios para la modelación hidrológica con **SWAT (Soil & Water Assessment Tool)**. Al conectarse directamente con las APIs de **Google Earth Engine (GEE)**, elimina las barreras de descarga manual, recorte y reproyección de grandes conjuntos de datos geoespaciales globales.

---

## 🚀 Características Clave

*   **⚙️ Conexión y Configuración GEE Genuina**: Autenticación segura mediante navegador, verificación de estado en tiempo real mediante LEDs de estado, y guardado persistente de parámetros del proyecto.
*   **🌐 Reproyección en Tiempo Real**: Todo archivo raster descargado (DEM, Suelos, Coberturas) se proyecta automáticamente a la **proyección exacta de tu proyecto** (por ejemplo, coordenadas UTM en el EPSG especificado como `32718` para Zona 18S).
*   **🗺️ Selector Interactivo de AOI (Área de Interés)**:
    *   Carga automática de geometría desde capas vectoriales en tu proyecto.
    *   Herramienta de dibujo de polígono interactivo directamente en el lienzo del mapa de QGIS.
    *   Ficha técnica completa: Área (ha/km²), perímetro, zona UTM correspondiente y coordenadas del cuadro delimitador (Bounding Box).
*   **🏔️ Descarga de MDE (DEM) Inteligente**:
    *   9 fuentes globales integradas (SRTM 30m, Copernicus GLO-30, NASADEM, ALOS AW3D30, MERIT DEM, HydroSHEDS, etc.).
    *   Estrategia dual de descarga: directo al disco local para áreas pequeñas (< 10 MP) o vía Google Drive para áreas extensas (> 10 MP).
*   **🪨 Descarga de Suelos (SOIL) y Lookup SWAT**:
    *   Fuentes globales de alta precisión: `suelo_FAO` y `OpenLandMap Soil` (250 m).
    *   Exporta automáticamente el raster de suelos y la correspondiente tabla relacional **`Soil_lookup.csv`** formateada según las especificaciones del modelo SWAT.
*   **🌳 Descarga de Coberturas (LANDUSE) y Lookup SWAT**:
    *   Fuentes: **Copernicus Land Cover 2019** (100 m) y **ESA GlobCover 2009** (300 m).
    *   Recorte a la AOI y generación automática de la tabla de equivalencias **`Landuse_lookup.csv`** mapeando las clases originales a las categorías estándar de SWAT (`WATR`, `URMD`, `FRSD`, `AGRL`, etc.).

---

## 📁 Estructura del Proyecto

```
geeSWAT/
├── Icons/                     # Recursos visuales del plugin
│   ├── dem.png
│   └── dep.png
├── Script/                    # Procesadores y Algoritmos GEE (QThreads)
│   ├── __init__.py
│   ├── mde_descargar_mde.py          # Procesamiento y descarga de DEMs
│   ├── soil_descargar_suelo.py        # Procesamiento de Suelos + Tabla Lookup
│   └── landuse_descargar_landuse.py  # Procesamiento de Coberturas + Tabla Lookup
├── LICENSE                    # Licencia Oficial GNU GPL v2
├── README.md                  # Documentación del Repositorio
├── geeswat_dialog.py         # Interfaz de Usuario UI (PyQt5 / PyQt6)
├── geeswat_provider.py       # Integración con Caja de Herramientas Processing
├── icon.png                  # Icono de acceso rápido
├── metadata.txt              # Metadatos del complemento para QGIS
└── plugin.py                 # Orquestador y Registro de Eventos del Ciclo QGIS
```

---

## 🛠️ Requisitos de Instalación

El plugin requiere la biblioteca oficial de Google Earth Engine para Python (`earthengine-api`). 

### Método A: Instalación Automática (Recomendado)
1. Instala el plugin desde el archivo ZIP o el repositorio de QGIS.
2. Abre el menú **Complementos → geeSWAT → Instalar dependencias de Python...**
3. Confirma la acción. Se abrirá una ventana de terminal externa ejecutando la instalación interactiva de dependencias mediante pip.
4. Reinicia QGIS al finalizar.

### Método B: Instalación Manual
Abre tu consola de comandos de QGIS (**OSGeo4W Shell** en Windows) y ejecuta:
```bash
python -m pip install earthengine-api
```

---

## 🖥️ Pestañas de la Interfaz

### 1. ⚙️ Config GEE
Configura tu espacio de trabajo. Ingresa tu dirección de correo electrónico asociada a Earth Engine y el ID de tu proyecto de Google Cloud. Autentica y verifica tu conexión con el indicador visual. Configura la proyección de salida (`EPSG`) y la ruta del proyecto.

### 2. 🗺️ Seleccionar AOI
Permite definir tu zona de estudio. Puedes seleccionar una capa vectorial existente en tu panel de capas de QGIS o pulsar el botón de dibujo para trazar un polígono interactivo. El sistema calculará automáticamente la zona UTM idónea, área total, perímetro y las coordenadas geográficas de los extremos de tu cuenca.

### 3. 🏔️ MDE (Modelo Digital de Elevación)
Elige una de las 9 fuentes disponibles. Determina el pixelado deseado (0 mantiene la resolución nativa de la fuente) y pulsa "Descargar". El proceso correrá en segundo plano (QThread) sin bloquear la interfaz de QGIS, y creará automáticamente una carpeta `DEM/` en tu directorio del proyecto.

### 4. 🪨 SOIL (Suelos)
Selecciona entre el mapa global de la FAO o el modelo detallado OpenLandMap. Descarga el raster recortado, proyectado y crea de manera paralela el archivo **`Soil_lookup.csv`** necesario para alimentar la base de datos de SWAT.

### 5. 🌳 LANDUSE (Uso del Suelo)
Elige entre las coberturas mundiales detalladas del año 2009 o 2019. El algoritmo recortará la capa, aplicará la proyección asignada en la primera pestaña y exportará el raster y el archivo **`Landuse_lookup.csv`** mapeando las clases originales a códigos compatibles con la interfaz QSWAT / ArcSWAT.

### 6. ℹ️ Acerca de
Pestaña de soporte y contacto del especialista a cargo del desarrollo. Cuenta con botones directos para abrir la web oficial, enviar correos de consulta técnica y abrir una conversación directa en **WhatsApp**.

---

## 🤝 Soporte y Consultas Técnicas

Desarrollado y mantenido por **Geomatica Ambiental**:

*   **Desarrollador principal**: Nino Bravo Morales (Especialista en Geomática)
*   **📞 Celular**: [+51 995664488](https://wa.me/51995664488?text=Hola%20Nino,%20tengo%20una%20consulta%20sobre%20el%20plugin%20geeSWAT)
*   **✉️ Correo**: [nino@geomatica.pe](mailto:nino@geomatica.pe?subject=Consulta%20geeSWAT)
*   **🌐 Sitio Web**: [https://www.geomatica.pe/](https://www.geomatica.pe/)

---

## 📄 Licencia

Este software se distribuye bajo la licencia **GNU General Public License v2 (GPL-2.0)**. Consulta el archivo [LICENSE](LICENSE) para obtener más información.
