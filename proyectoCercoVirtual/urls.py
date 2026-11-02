"""
==============================================================================
ENRUTADOR RAÍZ DEL PROYECTO: proyectoCercoVirtual/urls.py
==============================================================================
¿QUÉ HACE ESTE ARCHIVO?
Es el punto de entrada de todas las URLs del servidor Django.
1. '/admin/' expone el panel administrativo de GeoDjango (con mapas OpenLayers).
2. '' delega todas las rutas de interfaz y API REST/GeoJSON a `cercos/urls.py`.
==============================================================================
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('cercos.urls')),
]
