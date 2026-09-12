from django.contrib.gis import admin
from .models import CercoVirtual

@admin.register(CercoVirtual)
class CercoVirtualAdmin(admin.GISModelAdmin):
    list_display = ('nombre', 'color', 'usuario', 'fecha_creacion')
    search_fields = ('nombre',)
    
    # Configuración del mapa visual dentro del panel de administración
    gis_widget_kwargs = {
        'attrs': {
            'default_zoom': 14,
        }
    }