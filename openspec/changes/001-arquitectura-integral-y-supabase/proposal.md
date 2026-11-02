# Propuesta de Cambio 001: Arquitectura Integral, Cierre de Brechas ERS y Migración a Supabase

## 1. Motivación
El prototipo original cumplía la creación, edición y borrado visual de polígonos (`RF_1`, `RF_2`, `RF_8` parcial), pero carecía de:
1. Validación topológica de auto-intersección (`GEOSGeometry.valid`).
2. Modelos y vistas para **Ganado (`Animal`)**, **Telemetría (`TelemetriaGPS`)** y **Alertas (`AlertaFuga`)**, necesarios para cubrir **`RF_3` a `RF_7`** y **`RF-08` a `RF-10`**.
3. Separación clara entre **`📡 Modo Real (Node-RED)`** y **`🧪 Modo Simulación (Pruebas)`**.
4. Conexión en la nube mediante **Supabase (PostgreSQL + PostGIS)**.

## 2. Alcance del Cambio
- Incorporación de especificaciones vivas **OpenSpec** (`openspec/specs/`) y arquitectura **Archify** (`docs/archify/`).
- Refactorización de la app `cercos` en capas (`models.py`, `forms.py`, `services.py`, `views.py`, `urls.py`, `admin.py`, `tests.py`) y modularización del frontend JavaScript en 5 módulos dentro de `cercos/static/cercos/js/`.
- Implementación del motor de evaluación espacial PostGIS (`perimetro__contains`), control Anti-Spam de 5 minutos en potreros internos y **Alerta Continua (`alerta_continua = True`)** en Perímetros Críticos.
- Vinculación activa con **Supabase Cloud (PostgreSQL 17 + PostGIS 3.3.7)** con conexiones persistentes (`CONN_MAX_AGE = 600`).

