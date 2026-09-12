from django.urls import path
from . import views

urlpatterns = [
    # Vista principal de gestión de cercos (interfaz web con mapa)
    path('', views.gestion_cercos, name='gestion_cercos'),
    
    # Endpoints de comunicación (API liviana para Leaflet)
    path('api/cercos/', views.obtener_cercos, name='obtener_cercos'),
    path('api/cercos/crear/', views.crear_cerco, name='crear_cerco'),
    path('api/cercos/<int:cerco_id>/editar/', views.editar_cerco, name='editar_cerco'),
    path('api/cercos/<int:cerco_id>/eliminar/', views.eliminar_cerco, name='eliminar_cerco'),
]