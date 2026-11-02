# Archify — Documentación Arquitectónica Visual (SmartHerd)

Bienvenido al directorio **Archify** del proyecto **SmartHerd (Cerco Virtual — UNCA)**.  
Aquí se documenta de forma visual (mediante el modelo **C4** con diagramas Mermaid) y mediante **Registros de Decisiones de Arquitectura (ADR)** cómo está construido el sistema y cómo se integra con el resto de los equipos.

## Índice de Arquitectura

1. [**Nivel 1 (Contexto): Ecosistema IoT UNCA / INTA y Grupos de Trabajo**](./01-contexto-iot-unca-inta.md)
   - Cómo viaja el dato desde el collar en la vaca $\rightarrow$ Gateway $\rightarrow$ Base de Datos en la Nube (Supabase) $\rightarrow$ Aplicaciones Web.
2. [**Nivel 2 (Contenedores): Django + GeoDjango + Supabase (PostGIS) + Leaflet**](./02-contenedores-y-postgis.md)
   - Interacción entre el navegador, el servidor Django y el motor espacial PostGIS en Supabase/Local.
3. [**Nivel 3 (Componentes): Arquitectura Interna de la App `cercos`**](./03-componentes-django.md)
   - Separación de responsabilidades en `models.py`, `forms.py`, `services.py`, `views.py` y `mapa.js`.
4. **Decisiones de Arquitectura (ADRs)**:
   - [**ADR-001**: Adopción de Supabase (PostgreSQL + PostGIS en la nube) como base de datos compartida](./adr/ADR-001-supabase-postgis.md).
   - [**ADR-002**: Validación topológica GEOS y cálculo de contención espacial en base de datos](./adr/ADR-002-validacion-topologica-geos.md).

