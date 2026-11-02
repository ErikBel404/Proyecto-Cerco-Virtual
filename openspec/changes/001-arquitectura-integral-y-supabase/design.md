# Diseño Técnico — Cambio 001

## 1. Arquitectura en Capas (Django + GeoDjango + PostGIS)
- **`cercos/models.py`**:
  - `CercoVirtual`: `PolygonField(srid=4326)`, `alerta_continua` (Perímetro Crítico) y propiedad calculada `area_hectareas`.
  - `Animal`: `id_hardware` único, `cerco` (`ForeignKey` con `on_delete=models.SET_NULL`), `ultima_posicion` (`PointField(srid=4326)`), `estado_fuga` y `fecha_hora_fuga`.
  - `TelemetriaGPS`: Bitácora histórica de posiciones recibidas y resultado de `ST_Contains`.
  - `AlertaFuga`: Registro de incidentes con marca temporal exacta para el control Anti-Spam y panel de prófugos.
- **`cercos/forms.py`**: Validación y sanitización de nombres únicos de cercos, colores hexadecimales, IDs de collares y rangos de coordenadas GPS.
- **`cercos/services.py`**: Lógica espacial transaccional (`validar_geometria_poligono`, `evaluar_y_registrar_fuga`, `sincronizar_lecturas_externas_nodered`, `cargar_escenario_demo_catamarca`, `limpiar_escenario_demo_catamarca`).
- **`cercos/static/cercos/js/`**:
  1. `estado_y_utilidades.js` (Mapa base, selector/buscador de Ubicación Base del Campo, bloqueo anti-doble-clic `ejecutarConBloqueo`, `peticionPostJson`, Toasts y validación de cruces).
  2. `cercos_abm.js` (Creación, modificación y eliminación de cercos).
  3. `ganado_pertenencia.js` (Padrón de ganado y asignación/cambio/desvinculación de lotes).
  4. `telemetria_y_alertas.js` (Simulador GPS y monitor de animales prófugos).
  5. `navegacion_y_modos.js` (Sincronización con Supabase y alternancia limpia entre `📡 Modo Real` y `🧪 Modo Simulación`).

