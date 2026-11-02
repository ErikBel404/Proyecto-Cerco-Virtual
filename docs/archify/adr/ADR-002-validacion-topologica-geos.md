# ADR-002: Validación Topológica en Dos Capas y Evaluación Espacial en Base de Datos

- **Estado:** Aceptado
- **Fecha:** Noviembre 2026

## Contexto y Problema
En el prototipo inicial:
1. Si un usuario trazaba o editaba un cerco virtual cruzando sus aristas (formando un "8" o polígono auto-intersectante), el sistema lo guardaba en PostGIS sin validar su topología. Un polígono con auto-intersección es inválido según el estándar OGC (Open Geospatial Consortium) y provoca errores o resultados falsos al ejecutar funciones espaciales como `ST_Contains`.
2. El requerimiento no funcional `RNF_1` exige que la validación de si un animal está dentro o fuera del cerco se resuelva consultando directamente la base de datos espacial.

## Decisión
1. **Doble Validación de No Auto-Intersección (`Self-Intersection`)**:
   - **Frontend (`mapa.js`)**: Antes de enviar el polígono al servidor (tanto al crear como al modificar arrastrando vértices), se ejecuta una comprobación geométrica de intersección de segmentos no adyacentes. Si hay cruce, se alerta inmediatamente al usuario y en modo edición se permite revertir el vértice.
   - **Backend (`cercos/services.py`)**: Antes de hacer `.save()`, se instancia `GEOSGeometry` y se comprueba `if not geometria.valid:`. Si es inválido, se rechaza con HTTP 400.
2. **Evaluación Espacial Delegada a PostGIS (`perimetro__contains`)**:
   - Cada vez que llega una coordenada GPS (`Point(longitud, latitud, srid=4326)`) o se modifica el perímetro de un cerco con animales adentro, se ejecuta la consulta ORM `CercoVirtual.objects.filter(pk=cerco_id, perimetro__contains=punto).exists()`, que traduce directamente a `ST_Contains` en PostGIS.

## Consecuencias Positivas
- Se garantiza que el 100% de los polígonos almacenados en PostGIS sean geométricamente válidos.
- Se cumple estrictamente con `RF_1`, `RF_2`, `RF_4` y `RNF_1` de la especificación.

