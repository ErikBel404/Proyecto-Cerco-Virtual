# Nivel 2 (C4 Contenedores): Interacción Frontend, Backend GeoDjango y PostGIS

```mermaid
flowchart TB
    subgraph Browser["🌐 Navegador Web del Operador"]
        UI_Tailwind["Interfaz Split-Screen (Tailwind CSS)\nPaneles: Cercos | Ganado | Telemetría | Alertas"]
        Leaflet["Motor Cartográfico (Leaflet.js 1.9.4)\nCapas: Esri Satelital + Polígonos + Marcadores GPS"]
        Toast["Sistema Transversal de Alertas (Toast Pop-up)\nNotificaciones en tiempo real de fugas"]
        UI_Tailwind <--> Leaflet
        Leaflet --> Toast
    end

    subgraph DjangoServer["🐍 Servidor de Aplicación (Django 6.1 + GeoDjango)"]
        Views["Capa de Vistas y API JSON/GeoJSON\n(cercos/views.py)"]
        Forms["Capa de Validación y Sanitización\n(cercos/forms.py)"]
        Services["Capa de Servicios Geoespaciales\n(cercos/services.py + GEOS / GDAL)"]
        ORM["GeoDjango ORM\n(cercos/models.py)"]

        Views --> Forms
        Views --> Services
        Services --> ORM
    end

    subgraph CloudServices["☁️ Servicios Externos y Base de Datos"]
        Esri["🛰️ Esri World Imagery\nServidor de Teselas Satelitales"]
        Supabase[("🐘 Supabase PostgreSQL 15+ / Local PG 18\nExtensión Espacial PostGIS 3.x\nÍndices Espaciales GiST (SRID 4326)")]
    end

    Leaflet -->|"Carga imágenes satelitales\nGET /{z}/{y}/{x}"| Esri
    UI_Tailwind <-->|"Fetch JSON / GeoJSON\n+ Token CSRF"| Views
    ORM <-->|"Conexión psycopg2 (Puerto 5432 / 6543)\nFunciones: ST_Contains, ST_AsGeoJSON, ST_GeomFromEWKT"| Supabase
```

## Responsabilidades por Contenedor

| Contenedor | Tecnología | Responsabilidad Principal |
| :--- | :--- | :--- |
| **Visor Cartográfico** | Leaflet.js + Esri | Renderizar el mapa satelital de Catamarca, capturar clics de dibujo, permitir arrastrar vértices y mostrar la posición de cada vaca con código de colores (verde = dentro del cerco, rojo = prófuga, gris = sin cerco). |
| **Servidor GeoDjango** | Python + Django + GEOS | Validar que los polígonos sean topológicamente correctos (`GEOSGeometry.valid`), gestionar transacciones atómicas y exponer la API REST/GeoJSON. |
| **Motor Espacial PostGIS** | PostgreSQL + PostGIS (Supabase) | Almacenar tipos nativos `geometry(Polygon, 4326)` y `geometry(Point, 4326)` y resolver mediante índices espaciales si la coordenada de un collar está contenida en su lote (`ST_Contains`). |

