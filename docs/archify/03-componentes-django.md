# Nivel 3 (C4 Componentes): Estructura Interna de la Aplicación `cercos`

Para superar las limitaciones del prototipo inicial (donde toda la lógica estaba concentrada en las vistas sin formularios ni capa de servicios), la aplicación `cercos` se organiza en capas bien definidas:

```mermaid
flowchart TD
    subgraph Presentacion["Capa de Presentación (Templates & Static JS Modular)"]
        BaseHTML["templates/cercos/base.html\nLayout general, Navbar, Toast container"]
        MapaHTML["templates/cercos/mapa.html + partials/\nPaneles de Cercos, Ganado, Telemetría y Prófugos"]
        MapaJS["static/cercos/js/\nestado_y_utilidades.js, cercos_abm.js, ganado_pertenencia.js,\ntelemetria_y_alertas.js, navegacion_y_modos.js"]
        BaseHTML --> MapaHTML
        MapaHTML --> MapaJS
    end

    subgraph Controladores["Capa de Entrada HTTP (cercos/urls.py & views.py)"]
        V_Cercos["Vistas de Cercos\nobtener_cercos, crear_cerco, editar_cerco, eliminar_cerco"]
        V_Ganado["Vistas de Ganado y Pertenencia\nobtener_animales, crear_animal, asignar_cerco,\ndesvincular_cerco, eliminar_animal"]
        V_Telemetria["Vistas de Telemetría y Alertas\nprocesar_telemetria, obtener_alertas, resolver_alerta"]
    end

    subgraph Negocio["Capa de Validación y Dominio (forms.py & services.py)"]
        Forms["cercos/forms.py\nCercoVirtualForm, AnimalForm, TelemetriaForm\nValidación de campos, colores hex y rangos GPS"]
        SvcCerco["cercos/services.py :: Servicios de Cerco\nValidación topológica GEOS (sin auto-intersección)\ny re-evaluación automática de animales"]
        SvcTelemetria["cercos/services.py :: Motor de Detección\nConsulta PostGIS perimetro__contains,\ncálculo de fuga y Rate-Limiting de 5 min"]
    end

    subgraph Datos["Capa de Persistencia (cercos/models.py)"]
        M_Cerco["Modelo CercoVirtual\nPolygonField(srid=4326)"]
        M_Animal["Modelo Animal\nPointField(srid=4326) + FK Cerco (SET_NULL)"]
        M_Telemetria["Modelo TelemetriaGPS\nPointField(srid=4326)"]
        M_Alerta["Modelo AlertaFuga\nPointField(srid=4326) + control temporal"]
    end

    MapaJS --> V_Cercos
    MapaJS --> V_Ganado
    MapaJS --> V_Telemetria

    V_Cercos --> Forms
    V_Ganado --> Forms
    V_Telemetria --> Forms

    V_Cercos --> SvcCerco
    V_Ganado --> SvcCerco
    V_Telemetria --> SvcTelemetria

    SvcCerco --> M_Cerco
    SvcCerco --> M_Animal
    SvcTelemetria --> M_Animal
    SvcTelemetria --> M_Telemetria
    SvcTelemetria --> M_Alerta
```

## Descripción de Archivos Clave

- [`cercos/models.py`](../../cercos/models.py): Define las 4 tablas espaciales (`CercoVirtual`, `Animal`, `TelemetriaGPS`, `AlertaFuga`).
- [`cercos/forms.py`](../../cercos/forms.py): Formularios de Django que validan tipos de datos, longitudes de texto, formato hexadecimal de colores y rangos geográficos ($[-90, 90]$ para latitud y $[-180, 180]$ para longitud).
- [`cercos/services.py`](../../cercos/services.py): Contiene las reglas de negocio puras documentadas en OpenSpec y la ERS:
  - Conversión de GeoJSON a `GEOSGeometry(..., srid=4326)` y verificación de `geometria.valid` (rechazando polígonos con líneas cruzadas).
  - Evaluación espacial `CercoVirtual.objects.filter(pk=cerco.id, perimetro__contains=punto).exists()`.
  - Ventana anti-spam de 5 minutos (`timedelta(minutes=5)`) antes de emitir una nueva `AlertaFuga`.
- [`cercos/views.py`](../../cercos/views.py): Controladores HTTP livianos que delegan la validación a `forms.py` y la lógica espacial a `services.py`.

