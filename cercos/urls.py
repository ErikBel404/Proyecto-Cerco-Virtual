"""
==============================================================================
MAPA DE RUTAS DE LA APLICACIÓN: cercos/urls.py
==============================================================================
¿QUÉ HACE ESTE ARCHIVO?
Conecta cada URL de la interfaz y de la API REST/GeoJSON con su vista en `views.py`.
Está organizado en 4 bloques correspondientes a los módulos de la especificación:
1. Interfaz Principal (`GET /`).
2. Gestión de Cercos Virtuales (`RF_1`, `RF_2`, `RF_8`).
3. Gestión de Ganado y Pertenencia (`RF-08`, `RF-09`, `RF-10`).
4. Telemetría GPS, Detección Espacial y Alertas de Fuga (`RF_3` a `RF_7`).
==============================================================================
"""
from django.urls import path
from . import views

urlpatterns = [
    # 1. Vista principal interactiva (Split-Screen: Cercos, Ganado, Telemetría y Alertas)
    path('', views.gestion_cercos, name='gestion_cercos'),

    # 2. Endpoints de Cercos Virtuales (RF_1, RF_2, RF_8)
    path('api/cercos/', views.obtener_cercos, name='obtener_cercos'),
    path('api/cercos/crear/', views.crear_cerco, name='crear_cerco'),
    path('api/cercos/<int:id_cerco>/editar/',
         views.editar_cerco, name='editar_cerco'),
    path('api/cercos/<int:id_cerco>/eliminar/',
         views.eliminar_cerco, name='eliminar_cerco'),

    # 3. Endpoints de Ganado y Asignación a Cercos (RF-08, RF-09, RF-10)
    path('api/animales/', views.obtener_animales, name='obtener_animales'),
    path('api/animales/crear/', views.crear_animal, name='crear_animal'),
    path('api/animales/<int:id_animal>/asignar-cerco/',
         views.asignar_cerco_animal, name='asignar_cerco_animal'),
    path('api/animales/<int:id_animal>/desvincular-cerco/',
         views.desvincular_cerco_animal, name='desvincular_cerco_animal'),
    path('api/animales/<int:id_animal>/eliminar/',
         views.eliminar_animal, name='eliminar_animal'),

    # 4. Endpoints de Telemetría GPS y Detección Espacial en PostGIS (RF_3, RF_4)
    path('api/telemetria/procesar/', views.procesar_telemetria,
         name='procesar_telemetria'),

    # 5. Endpoints de Alertas y Animales Prófugos (RF_5, RF_6, RF_7)
    path('api/alertas/', views.obtener_alertas, name='obtener_alertas'),
    path('api/alertas/<int:id_alerta>/resolver/',
         views.resolver_alerta, name='resolver_alerta'),

    # 6. Utilidades de carga y limpieza de escenario de demostración (UNCA)
    path('api/demo/cargar/', views.cargar_demo, name='cargar_demo'),
    path('api/demo/limpiar/', views.limpiar_demo, name='limpiar_demo'),
]
