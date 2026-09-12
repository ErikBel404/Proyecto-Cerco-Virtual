from django.contrib.gis.db import models
from django.contrib.auth.models import User

class CercoVirtual(models.Model):
    # Relación con el usuario dueño del cerco (según DER)
    usuario = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='cercos',
        null=True, 
        blank=True
    )
    
    # Nombre identificatorio (ej: Lote Norte)
    nombre = models.CharField(max_length=100, verbose_name="Nombre del Lote")
    
    # Color en formato hexadecimal para pintar el polígono en Leaflet
    color = models.CharField(max_length=7, default="#2ecc71", verbose_name="Color de Identificación")
    
    # Geometría del perímetro en PostGIS (coordenadas GPS lat/lon estándar 4326)
    perimetro = models.PolygonField(srid=4326, verbose_name="Perímetro del Cerco")
    
    # Registro temporal
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cerco Virtual"
        verbose_name_plural = "Cercos Virtuales"
        ordering = ['-fecha_creacion']

    def __str__(self):
        return self.nombre