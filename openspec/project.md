# Contexto del Proyecto: SmartHerd — Sistema de Cercos Virtuales y Monitoreo Ganadero

## 1. Propósito y Contexto Institucional (UNCA)

**SmartHerd (Proyecto Cerco Virtual)** es una plataforma web geoespacial desarrollada en el marco de un proyecto interdisciplinario vinculado a la **Universidad Nacional de Catamarca (UNCA)**
El ecosistema completo se compone de tres eslabones:
1. **Hardware IoT y Red (Ingeniería Electrónica)**: Collares con GPS colocados en los animales (inicialmente ganado vacuno/bovino, extensible a otras especies) que transmiten coordenadas geográficas hacia un Gateway local y un nodo de red.
2. **Base de Datos Espacial Centralizada (PostgreSQL + PostGIS / Supabase)**: Repositorio compartido en la nube donde convergen los datos de los collares, los animales registrados y las geometrías de los lotes.
3. **Módulo de Cercos Virtuales y Monitoreo Espacial (Este Repositorio)**: Aplicación Django + GeoDjango que permite:
   - Delimitar, editar y eliminar **Cercos Virtuales (potreros/lotes)** sobre mapas satelitales.
   - Registrar y administrar **Animales/Collares** y su asignación a cada cerco (`Asignar`, `Reasignar`, `Desvincular`).
   - Recibir o simular **Telemetría GPS** en tiempo real y evaluar mediante consultas espaciales en **PostGIS (`ST_Contains`)** si el animal se encuentra dentro o fuera del perímetro asignado.
   - Emitir **Alertas en tiempo real** (con ventana anti-spam de 5 minutos) y gestionar el **Centro de Monitoreo de Fugas (Animales Prófugos)**.

---

## 2. Stack Tecnológico

- **Lenguaje**: Python 3.10+ (desarrollado y probado en Python 3.13).
- **Framework Backend**: Django 6.1.1 + **GeoDjango (`django.contrib.gis`)**.
- **Motor de Base de Datos**: **PostgreSQL 15–18** con extensión espacial **PostGIS 3.x** (compatible tanto en entorno local como en la nube mediante **Supabase Free Tier**).
- **Librerías Geoespaciales Nativas**: GEOS (`libgeos_c`), GDAL (`libgdal`) y PROJ.
- **Frontend**:
  - Plantillas Django (`templates/cercos/`) estructuradas con herencia (`base.html`) y componentes modulares.
  - **Tailwind CSS** para diseño responsivo e interfaz de panel dividido (*Split-Screen Táctico*).
  - **Leaflet.js 1.9.4** con capa satelital *Esri World Imagery* para renderizado de polígonos, marcadores de ganado y edición interactiva.

---

## 3. Convenciones y Reglas Críticas de Ingeniería

### 3.1. Sistema de Referencia Espacial y Orden de Coordenadas
- Todas las geometrías del sistema (`PolygonField` para cercos y `PointField` para posiciones de ganado) utilizan **`SRID 4326` (WGS 84 — Latitud/Longitud GPS estándar)**.
- **Regla de Oro de Inversión de Coordenadas**:
  - **Estándar GeoJSON / PostGIS / GEOS**: Usa orden cartesiano **`[Longitud, Latitud]`** ($X, Y$). Ejemplo Catamarca: `[-65.7852, -28.4696]`.
  - **Leaflet.js (Navegador)**: Usa orden geográfico **`[Latitud, Longitud]`**. Ejemplo Catamarca: `[-28.4696, -65.7852]`.
  - Toda comunicación por la API JSON entre frontend y backend se realiza en formato **GeoJSON (`[lng, lat]`)** o especificando explícitamente `latitud` y `longitud` numéricas.

### 3.2. Integridad Topológica de Polígonos
- Un cerco virtual debe tener un mínimo de **3 vértices únicos** (4 puntos en el anillo cerrado GeoJSON donde el último repite al primero).
- **Prohibición de Auto-intersección (`Self-Intersection`)**: Ningún cerco puede guardarse si sus aristas se cruzan entre sí (figura en "8" o reloj de arena). Tanto el frontend como el backend (`geometria.valid` en GEOS) deben rechazar polígonos inválidos antes de tocar la base de datos.

### 3.3. Integridad Referencial con el Ganado (`ON DELETE SET NULL`)
- Cuando se elimina un `CercoVirtual`, **nunca se deben eliminar los animales asignados a él**. La relación `Animal.cerco` utiliza `on_delete=models.SET_NULL, null=True`, devolviendo automáticamente a los animales al estado *"Sin cerco asignado"* y desactivando su estado de fuga.

### 3.4. Monitoreo Pasivo (`RNF_3`)
- El sistema es estrictamente de **monitoreo y alerta al operador**. No envía comandos de descarga eléctrica ni estímulos físicos hacia el collar del animal.

