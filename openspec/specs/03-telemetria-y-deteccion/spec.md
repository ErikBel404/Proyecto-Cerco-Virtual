# Especificación 03: Monitoreo de Ubicación y Detección de Brechas (`RF_3`, `RF_4`, `RNF_1`, `RNF_2`)

## Alcance
Define el flujo de recepción de coordenadas GPS desde los collares IoT (o desde el simulador táctico de demostración) y la evaluación espacial en tiempo real contra los polígonos almacenados en PostGIS.

---

## Requisitos Cubiertos

### `RF_3` — Monitoreo de Ubicación (Ingesta de Telemetría GPS)
El sistema DEBE proveer un endpoint HTTP (`POST /api/telemetria/procesar/`) que reciba el identificador del collar/animal (`id_hardware` o `animal_id`) y sus coordenadas geográficas (`latitud`, `longitud`).

#### Escenario 1.1: Recepción de trama GPS válida
- **Dado** un paquete JSON con `{"id_hardware": "COLLAR-001", "latitud": -28.469, "longitud": -65.785}`,
- **Cuando** el endpoint procesa la solicitud,
- **Entonces** valida que `latitud` $\in [-90, 90]$ y `longitud` $\in [-180, 180]$, construye un `Point(longitud, latitud, srid=4326)`, registra la lectura en `TelemetriaGPS` y actualiza `animal.ultima_posicion`.

#### Escenario 1.2: Trama malformada o incompleta (Camino Alternativo 2)
- **Dado** un paquete sin coordenadas numéricas válidas o sin identificador,
- **Entonces** el sistema descarta la lectura sin modificar la base de datos y retorna HTTP 400 detallando el error de formato.

#### Escenario 1.3: Collar no registrado o animal sin cerco asignado (Camino Alternativo 3)
- **Dado** un `id_hardware` que no existe en la base de datos, o un animal que tiene `cerco = None`,
- **Entonces** si el collar no existe retorna HTTP 404 sin colapsar; si el animal existe pero no tiene cerco asignado, actualiza su `ultima_posicion` en el mapa pero omite la evaluación de fuga.

---

### `RF_4` y `RNF_1` — Detección Espacial de Brechas en Base de Datos (PostGIS)
El sistema DEBE evaluar si la coordenada actual del animal se encuentra dentro del polígono de su cerco asignado consultando directamente las funciones espaciales de la base de datos (`CercoVirtual.objects.filter(pk=animal.cerco_id, perimetro__contains=punto)`).

#### Escenario 2.1: Animal dentro del perímetro (Estado Seguro)
- **Dado** un animal asignado a un cerco cuya nueva coordenada cae dentro del polígono (`perimetro__contains=punto` es `True`),
- **Entonces** el sistema asegura `animal.estado_fuga = False`, `animal.fecha_hora_fuga = None` y marca como resueltas las alertas abiertas previas si el animal reingresó por su cuenta al lote.

#### Escenario 2.2: Fuga detectada (Animal fuera del perímetro — Camino Alternativo 1)
- **Dado** un animal asignado a un cerco cuya nueva coordenada cae fuera del polígono (`perimetro__contains=punto` es `False`),
- **Entonces** el sistema:
  1. Cambia `animal.estado_fuga = True`.
  2. Si recién acaba de salir, registra la marca de tiempo exacta en `animal.fecha_hora_fuga`.
  3. Dispara el punto de extensión **`Emitir Alerta` (`RF_5`)**.

