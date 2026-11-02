"""
==============================================================================
PANEL DE ADMINISTRACIÓN GEODJANGO: cercos/admin.py
==============================================================================
¿QUÉ HACE ESTE ARCHIVO?
Registra los 4 modelos espaciales (`CercoVirtual`, `Animal`, `TelemetriaGPS`,
`AlertaFuga`) en el panel `/admin/` de Django heredando de `GISModelAdmin`.

¿PARA QUÉ SIRVE `GISModelAdmin`?
Permite que en el panel de administración de Django los campos `PolygonField` y
`PointField` se muestren como un mapa interactivo centrado en Catamarca en lugar
de un campo de texto plano.
==============================================================================
"""
from django.contrib.gis import admin
from .models import CercoVirtual, Animal, TelemetriaGPS, AlertaFuga


@admin.register(CercoVirtual)
class CercoVirtualAdmin(admin.GISModelAdmin):
    list_display = ('nombre', 'color', 'usuario', 'fecha_creacion')
    search_fields = ('nombre',)
    gis_widget_kwargs = {
        'attrs': {
            'default_zoom': 14,
            'default_lon': -65.7852,
            'default_lat': -28.4696,
        }
    }


@admin.register(Animal)
class AnimalAdmin(admin.GISModelAdmin):
    list_display = ('id_hardware', 'nombre', 'especie', 'cerco', 'estado_fuga', 'fecha_ultima_posicion')
    list_filter = ('especie', 'estado_fuga', 'cerco')
    search_fields = ('id_hardware', 'nombre')
    gis_widget_kwargs = {
        'attrs': {
            'default_zoom': 14,
            'default_lon': -65.7852,
            'default_lat': -28.4696,
        }
    }


@admin.register(TelemetriaGPS)
class TelemetriaGPSAdmin(admin.GISModelAdmin):
    list_display = ('animal', 'dentro_del_cerco', 'fecha_recepcion')
    list_filter = ('dentro_del_cerco', 'fecha_recepcion')
    search_fields = ('animal__id_hardware', 'animal__nombre')


@admin.register(AlertaFuga)
class AlertaFugaAdmin(admin.GISModelAdmin):
    list_display = ('animal', 'cerco', 'fecha_hora_salida', 'resuelta')
    list_filter = ('resuelta', 'cerco')
    search_fields = ('animal__id_hardware', 'animal__nombre', 'mensaje')
