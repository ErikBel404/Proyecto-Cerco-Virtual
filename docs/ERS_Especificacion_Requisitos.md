# Especificación de Requisitos de Software (ERS / SRS)
**Proyecto:** SmartHerd — Módulo de Cercos Virtuales y Monitoreo Geoespacial Ganadero  
**Contexto Académico / Institucional:** Universidad Nacional de Catamarca (UNCA)  
**Estándar de Referencia:** IEEE Std 830 / ISO/IEC/IEEE 29148 
    
---

## 1. Introducción

### 1.1. Propósito del Documento
Este documento especifica de forma completa y verificable los **Requerimientos de Usuario (RU)**, **Requisitos Funcionales (RF)**, **Requisitos No Funcionales (RNF)**, la **Matriz de Trazabilidad** y los **Casos de Uso (CU)** del subsistema de **Cercos Virtuales y Detección de Fugas**. Está diseñado para servir como referencia común entre:
1. El equipo de **Desarrollo del Módulo Geoespacial (Cerco Virtual)**.
2. El equipo de la **Plataforma Web General de Gestión Agropecuaria**.
3. El equipo de **Ingeniería Electrónica / IoT (Collares GPS y Gateway de Red)**.
4. El cuerpo docente y evaluadores externos.

### 1.2. Alcance del Producto
El sistema permite delimitar potreros o lotes rurales mediante polígonos georreferenciados sobre imágenes satelitales, asociar animales equipados con collares GPS a dichos perímetros, procesar las coordenadas recibidas desde el campo utilizando el motor espacial **PostGIS** y alertar en tiempo real cuando un animal vulnera los límites de su cerco asignado.

---

## 2. Requerimientos del Usuario (RU)

| Código | Descripción del Requerimiento de Usuario | Prioridad |
| :--- | :--- | :--- |
| **`RU_1`** | El sistema debe permitir demarcar en un mapa interactivo el perímetro del cerco virtual que desee el usuario. | Alta |
| **`RU_2`** | El sistema debe monitorear al ganado y, en caso de que el mismo se salga de los límites establecidos, emitir una alerta en la aplicación. | Alta |
| **`RU_3`** | El sistema debe proporcionar un listado de los animales que están actualmente fuera del perímetro cercado (prófugos). | Alta |
| **`RU_4`** | El sistema debe mostrar información detallada (hora exacta en que salió del cerco, ID del animal, lote asignado) de los animales que están fuera del cerco. | Media |
| **`RU_5`** | El sistema debe permitir modificar las dimensiones o eliminar el perímetro de un cerco cuando se desee. | Alta |
| **`RU_6`** | El sistema solo deberá emitir alertas informativas cuando un animal cruce los límites establecidos; **no involucra ninguna acción física sobre el animal**. | Alta |
| **`RU_7`** | Los datos que se utilizarán para evaluar si el ganado está dentro o fuera del perímetro deben consultarse y validarse directamente contra la base de datos espacial. | Alta |

---

## 3. Requisitos Funcionales (RF)

| Código | Nombre | Descripción Detallada | Origen (RU) |
| :--- | :--- | :--- | :--- |
| **`RF_1`** | **Definición de cerco virtual** | El sistema debe permitir al usuario trazar y guardar en PostGIS (`SRID 4326`) las coordenadas del perímetro de un cerco virtual interactuando con un mapa satelital, validando que tenga al menos 3 vértices y no posea cruces de líneas (auto-intersecciones). | `RU_1` |
| **`RF_2`** | **Modificación de cerco virtual** | El sistema debe permitir al usuario actualizar el nombre, color y las dimensiones (arrastrando sus vértices) de un cerco virtual previamente registrado, preservando la validez topológica del polígono. | `RU_5` |
| **`RF_3`** | **Monitoreo de ubicación** | El sistema debe recibir y procesar las posiciones actuales del ganado (`id_hardware`, `latitud`, `longitud`) provenientes de los collares GPS o del simulador de telemetría. | `RU_2` |
| **`RF_4`** | **Detección de brechas** | El sistema debe evaluar cada posición recibida del ganado mediante consultas espaciales en PostGIS (`ST_Contains`) para determinar si sus coordenadas caen dentro o fuera del polígono que define su cerco virtual asignado. | `RU_2`, `RU_7` |
| **`RF_5`** | **Emisión de alertas** | El sistema debe generar y disparar una notificación en la aplicación en el instante en que se detecte que un animal ha cruzado el límite establecido, con control de frecuencia (*Rate Limiting*) de 5 minutos por animal en lotes internos y opción de **Alerta Continua Inmediata (`alerta_continua = True`)** en perímetros críticos (linderos, rutas, canales o riesgo de robo). | `RU_2`, `RU_6` |
| **`RF_6`** | **Listado de animales fuera de límite** | El sistema debe generar una vista o lista que agrupe en tiempo real a todos los animales cuyo estado actual sea `"fuera del cerco"` (`estado_fuga = True`). | `RU_3` |
| **`RF_7`** | **Detalle de incidentes** | El sistema debe proveer información específica de cada animal fugado, mostrando su ID identificador (`id_hardware`), nombre/alias, cerco vulnerado, coordenadas y la marca de tiempo exacta en la que salió del perímetro, permitiendo enfocar su ubicación en el mapa. | `RU_4` |
| **`RF_8`** | **Eliminación de cerco virtual** | El sistema debe permitir al usuario eliminar un cerco virtual previamente registrado previa confirmación, desvinculando automáticamente (`SET NULL`) a los animales que tuviera asignados sin eliminarlos. | `RU_1`, `RU_5` |
| **`RF-08`** | **Asignar animal a cerco** | El sistema debe permitir al usuario asignar un animal registrado sin cerco a un cerco virtual existente en la base de datos. | `RU_2` |
| **`RF-09`** | **Modificar pertenencia a cerco** | El sistema debe permitir al usuario reasignar un animal desde su cerco virtual actual hacia uno nuevo diferente. | `RU_2` |
| **`RF-10`** | **Desvincular pertenencia a cerco** | El sistema debe permitir al usuario quitar la asignación de un cerco virtual a un animal (`cerco = NULL`), dejándolo sin monitoreo espacial activo y cerrando alertas abiertas de dicho animal. | `RU_2` |

---

## 4. Requisitos No Funcionales (RNF)

| Código | Categoría | Descripción | Origen (RU) |
| :--- | :--- | :--- | :--- |
| **`RNF_1`** | **Arquitectura de Datos Espaciales** | La validación del estado posicional del ganado (`dentro` vs. `fuera`) debe ejecutarse consultando directamente el motor espacial **PostgreSQL / PostGIS** (`PolygonField` y `PointField` con `SRID 4326`), permitiendo su alojamiento centralizado en **Supabase** o servidor dedicado. | `RU_7` |
| **`RNF_2`** | **Rendimiento y Tiempo Real** | El procesamiento de una trama GPS y la evaluación espacial deben completarse con latencia mínima (< 500 ms en red local/nube), emitiendo la alerta de forma inmediata en la respuesta y en el monitor de alertas. | `RU_2` |
| **`RNF_3`** | **Límite de Control (Monitoreo Pasivo)** | El sistema es estrictamente de monitoreo pasivo para toma de decisiones del productor. No ejecuta ni transmite señales de estímulo físico, sonoro ni eléctrico sobre el animal. | `RU_6` |

---

## 5. Matriz de Trazabilidad (RU $\leftrightarrow$ RF $\leftrightarrow$ Casos de Uso)

| Requerimiento Usuario | Requisitos Funcionales / RNF | Caso de Uso Asociado | Módulo de Código |
| :--- | :--- | :--- | :--- |
| `RU_1` | `RF_1`, `RF_8` | `CU_01` Crear Cerco / `CU_03` Eliminar Cerco | `cercos/services.py`, `cercos/views.py` |
| `RU_5` | `RF_2`, `RF_8` | `CU_02` Modificar Cerco / `CU_03` Eliminar Cerco | `cercos/services.py`, `cercos/views.py` |
| `RU_2` | `RF_3`, `RF_4`, `RF_5`, `RF-08`, `RF-09`, `RF-10`, `RNF_2` | `CU_05` Procesar Ubicación, `CU_06` Emitir Alerta, `CU_07`–`CU_09` Gestión Pertenencia | `cercos/services.py`, `cercos/models.py` |
| `RU_3`, `RU_4` | `RF_6`, `RF_7` | `CU_04` Ver Animales Prófugos | `cercos/views.py`, `cercos/static/cercos/js/` |
| `RU_6` | `RF_5`, `RNF_3` | `CU_06` Emitir Alerta | `cercos/services.py` |
| `RU_7` | `RF_4`, `RNF_1` | `CU_05` Procesar Ubicación | `cercos/services.py` (PostGIS `perimetro__contains`) |

---

## 6. Catálogo de Casos de Uso (`CU_01` a `CU_09`)

1. **`CU_01` — Crear Cerco Virtual (`RF_1`)**: Actor: *Operador*. Traza vértices en el mapa, valida >= 3 vértices y ausencia de auto-intersección (`GEOSGeometry.valid`), guarda polígono en PostGIS.
2. **`CU_02` — Modificar Cerco Virtual (`RF_2`)**: Actor: *Operador*. Selecciona lote, edita nombre/color o arrastra vértices, valida no auto-intersección y existencia del registro (control de concurrencia), actualiza PostGIS y re-evalúa animales asignados.
3. **`CU_03` — Eliminar Cerco Virtual (`RF_8`)**: Actor: *Operador*. Selecciona lote, confirma advertencia permanente, elimina polígono y ejecuta `ON DELETE SET NULL` sobre los animales vinculados.
4. **`CU_04` — Ver Animales Prófugos (`RF_6`, `RF_7`)**: Actor: *Operador*. Consulta la lista filtrada por `estado_fuga = True`, visualiza ID de collar, nombre, lote vulnerado y hora exacta de salida, pudiendo centrar la cámara del mapa en el animal o marcar el incidente como resuelto.
5. **`CU_05` — Procesar Ubicación (`RF_3`, `RF_4`, `RNF_1`)**: Actor: *Nodo GPS / Simulador*. Envía `id_hardware`, `latitud`, `longitud`. El sistema registra el punto GPS, consulta `ST_Contains` contra el cerco asignado y actualiza `estado_fuga`. Si sale del cerco, extiende a `CU_06`.
6. **`CU_06` — Emitir Alerta (`RF_5`, `RNF_3`)**: Actor: *Sistema (Extensión de `CU_05`)*. Verifica ventana anti-spam de 5 minutos para ese animal; si corresponde, persiste `AlertaFuga` y dispara notificación emergente (*Toast*) en la interfaz.
7. **`CU_07` — Asignar Animal a Cerco Virtual (`RF-08`)**: Actor: *Operador*. Vincula un animal de la lista `"Animales sin cerco"` a un `CercoVirtual` activo.
8. **`CU_08` — Modificar Pertenencia a Cerco (`RF-09`)**: Actor: *Operador*. Reasigna un animal monitoreado a un nuevo `CercoVirtual` distinto del actual.
9. **`CU_09` — Eliminar Pertenencia / Desvincular de Cerco (`RF-10`)**: Actor: *Operador*. Quita la asignación de cerco (`cerco = NULL`) previa confirmación, deteniendo el monitoreo espacial sobre ese animal.

