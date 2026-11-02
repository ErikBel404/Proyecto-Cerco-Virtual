# Documento de Diseño del Sistema (SDD / Diseño Técnico)
**Proyecto:** SmartHerd — Módulo de Cercos Virtuales y Monitoreo Geoespacial Ganadero  

---

## 1. Modelo Entidad-Relación Espacial (DER)

El diseño de base de datos extiende el diagrama original incorporando los atributos espaciales de **PostGIS (`Geometry: Polygon` y `Geometry: Point` en `SRID 4326`)** y las tablas de trazabilidad de telemetría e incidentes de fuga.

```mermaid
erDiagram
    AUTH_USER ||--o{ CERCO_VIRTUAL : "es propietario (1:N)"
    CERCO_VIRTUAL ||--o{ ANIMAL : "contiene / monitorea (1:N, ON DELETE SET NULL)"
    ANIMAL ||--o{ TELEMETRIA_GPS : "reporta posiciones (1:N)"
    ANIMAL ||--o{ ALERTA_FUGA : "genera incidentes (1:N)"
    CERCO_VIRTUAL ||--o{ ALERTA_FUGA : "registra vulneracion (1:N)"

    CERCO_VIRTUAL {
        bigint id PK
        int usuario_id FK "Nullable"
        varchar(100) nombre "Nombre del Lote"
        varchar(7) color "Hexadecimal (#2ecc71)"
        boolean alerta_continua "True = Perimetro critico (sin espera de 5 min)"
        geometry_Polygon_4326 perimetro "Poligono PostGIS SRID 4326"
        datetime fecha_creacion
        datetime fecha_modificacion
    }

    ANIMAL {
        bigint id PK
        varchar(50) id_hardware UK "ID Collar / Caravana (ej. COLLAR-001)"
        varchar(100) nombre "Alias o identificacion (ej. Vaca #104)"
        varchar(50) especie "Default: Bovino"
        bigint cerco_id FK "Nullable (ON DELETE SET NULL)"
        geometry_Point_4326 ultima_posicion "Punto PostGIS [lng, lat] SRID 4326"
        datetime fecha_ultima_posicion "Nullable"
        boolean estado_fuga "True si esta fuera del cerco"
        datetime fecha_hora_fuga "Hora exacta en que salio del perimetro"
        datetime fecha_registro
    }

    TELEMETRIA_GPS {
        bigint id PK
        bigint animal_id FK
        geometry_Point_4326 posicion "Punto PostGIS [lng, lat] SRID 4326"
        boolean dentro_del_cerco "Resultado de ST_Contains al momento"
        datetime fecha_recepcion
    }

    ALERTA_FUGA {
        bigint id PK
        bigint animal_id FK
        bigint cerco_id FK "Nullable"
        geometry_Point_4326 posicion_fuga "Coordenada donde se detecto la brecha"
        varchar(255) mensaje "Detalle formateado del incidente"
        datetime fecha_hora_salida "Marca temporal exacta"
        boolean resuelta "False mientras siga activa"
        datetime fecha_resolucion "Nullable"
    }
```

---

## 2. Diagramas de Secuencia de los Flujos Críticos

### 2.1. Creación y Validación Topológica de un Cerco Virtual (`CU_01` / `RF_1`)

```mermaid
sequenceDiagram
    actor Operador
    participant MapaJS as Frontend (Leaflet / static/cercos/js/)
    participant View as Django View (crear_cerco)
    participant Service as Servicio Espacial (services.py)
    participant PostGIS as PostgreSQL + PostGIS (Supabase/Local)

    Operador->>MapaJS: Marca vértices en el mapa y presiona "Guardar Cerco"
    MapaJS->>MapaJS: Verifica >= 3 vértices y que no haya cruce de segmentos
    alt Polígono inválido en cliente
        MapaJS-->>Operador: Muestra alerta "El perímetro no puede tener cruces"
    else Polígono válido en cliente
        MapaJS->>MapaJS: Invierte [lat, lng] a GeoJSON [lng, lat] y cierra el anillo
        MapaJS->>View: POST /api/cercos/crear/ (GeoJSON)
        View->>Service: validar_y_crear_cerco(nombre, color, geojson)
        Service->>Service: GEOSGeometry(geojson) -> verifica geom.valid
        alt Auto-intersección detectada por GEOS
            Service-->>View: ValidationError ("El perímetro no puede tener cruces")
            View-->>MapaJS: HTTP 400 JSON {estado: "error", mensaje: "..."}
            MapaJS-->>Operador: Notifica error topológico y solicita corregir
        else Geometría válida
            Service->>PostGIS: INSERT INTO cercos_cercovirtual (ST_GeomFromEWKT)
            PostGIS-->>Service: ID del nuevo cerco
            Service-->>View: Instancia CercoVirtual
            View-->>MapaJS: HTTP 200 JSON {estado: "exito", id: ...}
            MapaJS->>View: GET /api/cercos/
            MapaJS-->>Operador: Renderiza el nuevo polígono en el mapa
        end
    end
```

### 2.2. Procesamiento de Telemetría GPS, Detección Espacial y Emisión de Alerta (`CU_05` + `CU_06`)

```mermaid
sequenceDiagram
    actor CollarGPS as Nodo IoT GPS / Simulador
    participant API as Endpoint (/api/telemetria/procesar/)
    participant Service as Servicio Telemetría (services.py)
    participant PostGIS as PostgreSQL + PostGIS
    participant UI as Interfaz Operador (Toast / Mapa)

    CollarGPS->>API: POST {id_hardware: "COLLAR-001", latitud: -28.471, longitud: -65.789}
    API->>Service: procesar_ubicacion_gps(id_hardware, latitud, longitud)
    Service->>PostGIS: SELECT Animal WHERE id_hardware = "COLLAR-001"
    Service->>Service: Crea Point(longitud, latitud, srid=4326)
    Service->>PostGIS: Evalúa ST_Contains(cerco.perimetro, punto_gps)
    alt Animal DENTRO del cerco (ST_Contains = True)
        Service->>PostGIS: UPDATE Animal SET estado_fuga=False, ultima_posicion=punto
        Service-->>API: Resultado {dentro_del_cerco: true, alerta_emitida: false}
    else Animal FUERA del cerco (ST_Contains = False -> Fuga detectada)
        Service->>PostGIS: UPDATE Animal SET estado_fuga=True, fecha_hora_fuga=NOW()
        Service->>PostGIS: Consulta AlertaFuga de este animal en últimos 5 minutos
        alt Ya se emitió alerta hace < 5 minutos (Rate Limiting Anti-Spam)
            Service-->>API: {dentro_del_cerco: false, alerta_emitida: false, suprimida_por_spam: true}
        else No hay alerta reciente (>= 5 min o primera fuga)
            Service->>PostGIS: INSERT INTO AlertaFuga (animal, cerco, posicion_fuga, fecha_hora_salida)
            Service-->>API: {dentro_del_cerco: false, alerta_emitida: true, alerta: {...}}
            API-->>UI: Dispara Toast de Alerta + Actualiza Contador de Prófugos
        end
    end
```

---

## 3. Especificación de Contratos de la API (Para Integración con Otros Equipos)

Todos los endpoints devuelven y reciben `application/json`.

### 3.1. Endpoints de Cercos Virtuales
| Método | Ruta | Descripción |
| :--- | :--- | :--- |
| `GET` | `/api/cercos/` | Retorna un `FeatureCollection` GeoJSON con todos los cercos y la cantidad de animales asignados y prófugos en cada uno. |
| `POST` | `/api/cercos/crear/` | Crea un cerco. Body: `{"nombre": "Lote 1", "color": "#2ecc71", "geometria": {"type": "Polygon", "coordinates": [...]}}`. |
| `POST` | `/api/cercos/<id>/editar/` | Actualiza nombre, color y/o geometría de un cerco y re-evalúa la contención de sus animales asignados. |
| `POST` | `/api/cercos/<id>/eliminar/` | Elimina el cerco y desvincula (`cerco = NULL`) sus animales. |

### 3.2. Endpoints de Ganado y Pertenencia (`RF-08`, `RF-09`, `RF-10`)
| Método | Ruta | Descripción |
| :--- | :--- | :--- |
| `GET` | `/api/animales/` | Retorna la lista completa de animales con su `id_hardware`, `nombre`, `cerco_id`, `cerco_nombre`, `estado_fuga`, `fecha_hora_fuga` y coordenadas `[latitud, longitud]`. |
| `POST` | `/api/animales/crear/` | Registra un nuevo animal/collar. Body: `{"id_hardware": "COLLAR-001", "nombre": "Vaca #104", "especie": "Bovino", "cerco_id": 1, "latitud": -28.469, "longitud": -65.785}`. |
| `POST` | `/api/animales/<id>/asignar-cerco/` | Implementa **`RF-08` (Asignar)** y **`RF-09` (Modificar pertenencia)**. Body: `{"cerco_id": 2}`. |
| `POST` | `/api/animales/<id>/desvincular-cerco/` | Implementa **`RF-10` (Desvincular)**. Pasa `cerco = NULL`, limpia `estado_fuga` y resuelve alertas abiertas del animal. |
| `POST` | `/api/animales/<id>/eliminar/` | Da de baja un registro de animal. |

### 3.3. Endpoints de Telemetría GPS, Alertas y Modos de Operación (`RF_3`–`RF_7`)
| Método | Ruta | Descripción |
| :--- | :--- | :--- |
| `POST` | `/api/telemetria/procesar/` | **Endpoint para el Gateway IoT o el Simulador**. Body: `{"id_hardware": "COLLAR-001", "latitud": -28.472, "longitud": -65.781}` (también acepta `animal_id`). Evalúa `ST_Contains` en PostGIS y retorna si está dentro o fuera y si disparó alerta. |
| `GET` | `/api/alertas/?modo=real\|simulacion` | Retorna la lista de animales actualmente prófugos (`RF_6`, `RF_7`) y las alertas activas pendientes de revisión. |
| `POST` | `/api/alertas/<id>/resolver/` | Permite marcar una alerta/incidente como revisado o resuelto desde el Centro de Monitoreo de Fugas. |
| `POST` | `/api/demo/cargar/` | Crea/actualiza el escenario de demostración en Catamarca (2 lotes y 4 animales `COLLAR-101`..`104`) para pruebas en `🧪 Modo Simulación`. |
| `POST` | `/api/demo/limpiar/` | Elimina exclusivamente los registros de demostración sin afectar cercos ni animales reales del productor. |

