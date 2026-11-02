# Tareas de Implementación — Cambio 001

- [x] **1. Estructura OpenSpec (`openspec/`)**:
  - [x] Crear `AGENTS.md` y `project.md`.
  - [x] Crear especificaciones `01` a `04` en `openspec/specs/`.
  - [x] Registrar propuesta, diseño y checklist de avance en `openspec/changes/001-arquitectura-integral-y-supabase/`.
- [x] **2. Documentación Arquitectónica Archify y Universitaria (`docs/`)**:
  - [x] Crear `docs/ERS_Especificacion_Requisitos.md` (con `RU_1`–`RU_7`, `RF_1`–`RF_10`, `RNF_1`–`RNF_3` y Casos de Uso `CU_01`–`CU_09`).
  - [x] Crear `docs/SDD_Diseno_Sistema.md` (DER espacial, diagramas de secuencia y contratos de la API).
  - [x] Crear diagramas C4 y ADRs en `docs/archify/`.
  - [x] Crear `docs/GUIA_SUPABASE_E_INTEGRACION.md` (guía para compañeros, docentes y conexión con Node-RED).
- [x] **3. Refactorización del Backend Django (`cercos/` y `proyectoCercoVirtual/`)**:
  - [x] Actualizar `settings.py`, `.env` y `.env.example` con soporte para Supabase (`DB_SSLMODE=require`, `CONN_MAX_AGE=600`) y autodetección de GDAL/GEOS.
  - [x] Ampliar `cercos/models.py` con `CercoVirtual.alerta_continua`, `Animal` (`ON DELETE SET NULL`), `TelemetriaGPS` y `AlertaFuga`.
  - [x] Crear `cercos/forms.py` y `cercos/services.py` con validación topológica GEOS, consulta `perimetro__contains`, ventana Anti-Spam de 5 min vs. Perímetro Crítico y sincronización en memoria para Node-RED.
  - [x] Actualizar `cercos/views.py`, `cercos/urls.py` y `cercos/admin.py`.
- [x] **4. Refactorización de Templates y Modularización del Frontend JS**:
  - [x] Estructurar `templates/cercos/base.html`, `mapa.html` y `partials/`.
  - [x] Incorporar selector y buscador de **📍 Ubicación Base del Campo** (San Fernando del Valle, Belén, Tinogasta, Andalgalá, Santa María, Recreo o buscador libre).
  - [x] Separar **`📡 Modo Real (Node-RED)`** y **`🧪 Modo Simulación (Pruebas)`** con limpieza automática de datos de prueba al volver a Modo Real.
  - [x] Implementar bloqueo anti-doble-clic (`ejecutarConBloqueo`) y dividir el código cliente en 5 módulos legibles dentro de `cercos/static/cercos/js/`.
- [x] **5. Vinculación con Supabase Cloud y Pruebas Automatizadas**:
  - [x] Activar extensión `postgis` y aplicar todas las migraciones en Supabase Cloud.
  - [x] Crear superusuario en Supabase para el panel `/admin/`.
  - [x] Ejecutar y aprobar los 6 tests unitarios y espaciales en `cercos/tests.py`.

