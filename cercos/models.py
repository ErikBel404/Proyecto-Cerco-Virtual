"""
==============================================================================
MODELOS DE DATOS GEOESPACIALES: cercos/models.py
==============================================================================
Estructura de tablas en PostgreSQL + PostGIS (SRID 4326 - WGS84):
1. `Lectura`: Bandeja de entrada cruda donde Node-RED deposita los datos del collar
   (`id_hardware`, `latitud`, `longitud`, `fecha_hora`) sin depender de otros modelos.
2. `CercoVirtual`: Polígonos perimetrales de los lotes (RF_1, RF_2, RF_8).
3. `Animal`: Vinculación del collar (`id_hardware`) con su cerco y estado actual (RF-08 a RF-10).
4. `TelemetriaGPS`: Historial geoespacial validado que consume los datos de `Lectura` (RF_3, RF_4).
5. `AlertaFuga`: Incidentes emitidos cuando una posición sale del cerco (RF_5, RF_6, RF_7).
==============================================================================
"""

from django.contrib.gis.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Lectura(models.Model):
    """
    Tabla de entrada (`public.lectura`) donde Node-RED deposita las lecturas crudas
    que llegan desde los collares GPS.

    ¿Por qué está separada de `TelemetriaGPS` y `Animal`?
    - Desacopla totalmente a Node-RED del resto del sistema: Node-RED solo inserta
      `id_hardware`, `latitud`, `longitud` y `fecha_hora` en esta tabla sin necesitar
      claves foráneas ni geometrías PostGIS.
    - Luego, `TelemetriaGPS` consume las filas pendientes (`procesada=False`), construye
      el punto geográfico y evalúa si está dentro o fuera del cerco.
    """
    id_hardware = models.CharField(
        max_length=50,
        db_index=True,
        verbose_name="ID de Hardware / Collar"
    )
    latitud = models.FloatField(
        verbose_name="Latitud"
    )
    longitud = models.FloatField(
        verbose_name="Longitud"
    )
    fecha_hora = models.DateTimeField(
        default=timezone.now,
        verbose_name="Fecha y Hora de Lectura"
    )
    procesada = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Procesada por Telemetría GPS"
    )

    class Meta:
        db_table = 'lectura'
        verbose_name = "Lectura Cruda (Node-RED)"
        verbose_name_plural = "Lecturas Crudas (Node-RED)"
        ordering = ['-fecha_hora']

    def __str__(self):
        estado = "Procesada" if self.procesada else "Pendiente"
        return f"{self.id_hardware} ({self.latitud}, {self.longitud}) [{estado}]"


class CercoVirtual(models.Model):
    """
    Representa un potrero o lote delimitado por un polígono cerrado (`PolygonField` SRID 4326).
    PostGIS indexa este campo para resolver en milisegundos si un punto cae dentro (`ST_Contains`).
    """
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='cercos',
        null=True,
        blank=True
    )
    nombre = models.CharField(max_length=100, verbose_name="Nombre del Lote")
    color = models.CharField(
        max_length=7, default="#2ecc71", verbose_name="Color de Identificación"
    )
    perimetro = models.PolygonField(
        srid=4326, verbose_name="Perímetro del Cerco"
    )
    alerta_continua = models.BooleanField(
        default=False,
        verbose_name="Perímetro Crítico (Alerta Continua sin Anti-Spam)"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cerco Virtual"
        verbose_name_plural = "Cercos Virtuales"
        ordering = ['-fecha_creacion']

    def __str__(self):
        return self.nombre

    @property
    def area_hectareas(self):
        """Calcula la superficie aproximada en hectáreas proyectando en memoria a SRID 3857."""
        try:
            geom_metrica = self.perimetro.transform(3857, clone=True)
            area_m2 = geom_metrica.area * 0.772
            return round(area_m2 / 10000.0, 2)
        except Exception:
            return 0.0


class Animal(models.Model):
    """
    Vincula un collar (`id_hardware`) con su cerco asignado y conserva su última ubicación
    conocida para dibujarlo rápido en el mapa sin recorrer todo el historial.
    """
    ESPECIE_CHOICES = [
        ('Bovino', 'Bovino (Vaca / Toro)'),
        ('Ovino', 'Ovino'),
        ('Caprino', 'Caprino'),
        ('Equino', 'Equino'),
        ('Otro', 'Otro'),
    ]

    id_hardware = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="ID de Collar / Hardware"
    )
    nombre = models.CharField(
        max_length=100,
        verbose_name="Nombre / Identificación del Animal"
    )
    especie = models.CharField(
        max_length=30,
        choices=ESPECIE_CHOICES,
        default='Bovino',
        verbose_name="Especie"
    )
    # on_delete=SET_NULL: Si se elimina el cerco (RF_8), el animal queda "Sin cerco asignado"
    cerco = models.ForeignKey(
        CercoVirtual,
        on_delete=models.SET_NULL,
        related_name='animales',
        null=True,
        blank=True,
        verbose_name="Cerco Virtual Asignado"
    )
    ultima_posicion = models.PointField(
        srid=4326,
        null=True,
        blank=True,
        verbose_name="Última Ubicación GPS"
    )
    fecha_ultima_posicion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de Última Lectura GPS"
    )
    estado_fuga = models.BooleanField(
        default=False,
        verbose_name="Fuera del Cerco (En Fuga)"
    )
    fecha_hora_fuga = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Marca de Tiempo de Salida (Fuga)"
    )
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Animal Monitoreado"
        verbose_name_plural = "Animales Monitoreados"
        ordering = ['id_hardware']

    def __str__(self):
        return f"{self.id_hardware} - {self.nombre}"


class TelemetriaGPS(models.Model):
    """
    Bitácora geoespacial procesada por Django (RF_3, RF_4).
    Toma los datos crudos de `Lectura`, los convierte en geometría PostGIS (`PointField`)
    y guarda el resultado de evaluar si la coordenada cayó dentro o fuera del cerco.
    """
    animal = models.ForeignKey(
        Animal,
        on_delete=models.CASCADE,
        related_name='telemetrias',
        verbose_name="Animal"
    )
    lectura_origen = models.ForeignKey(
        Lectura,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='telemetrias_procesadas',
        verbose_name="Lectura Cruda de Origen"
    )
    posicion = models.PointField(
        srid=4326,
        verbose_name="Coordenada GPS (PostGIS)"
    )
    dentro_del_cerco = models.BooleanField(
        default=True,
        verbose_name="Dentro del Perímetro"
    )
    fecha_recepcion = models.DateTimeField(
        default=timezone.now,
        verbose_name="Fecha y Hora de Recepción"
    )

    class Meta:
        verbose_name = "Telemetría GPS Procesada"
        verbose_name_plural = "Telemetrías GPS Procesadas"
        ordering = ['-fecha_recepcion']

    def __str__(self):
        estado = "Dentro" if self.dentro_del_cerco else "Fuera"
        return f"{self.animal.id_hardware} ({estado}) @ {self.fecha_recepcion:%d/%m/%Y %H:%M:%S}"


class AlertaFuga(models.Model):
    """
    Incidente formal de escape cuando `TelemetriaGPS` detecta que el animal salió de su cerco (RF_5, RF_7).
    Permite auditar fugas históricas y aplicar la ventana Anti-Spam de 5 minutos.
    """
    animal = models.ForeignKey(
        Animal,
        on_delete=models.CASCADE,
        related_name='alertas',
        verbose_name="Animal Fugado"
    )
    cerco = models.ForeignKey(
        CercoVirtual,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alertas',
        verbose_name="Cerco Vulnerado"
    )
    posicion_fuga = models.PointField(
        srid=4326,
        verbose_name="Coordenada de Salida"
    )
    mensaje = models.CharField(
        max_length=255,
        verbose_name="Detalle del Incidente"
    )
    fecha_hora_salida = models.DateTimeField(
        default=timezone.now,
        verbose_name="Hora Exacta de Salida"
    )
    resuelta = models.BooleanField(
        default=False,
        verbose_name="Incidente Resuelto"
    )
    fecha_resolucion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de Resolución"
    )

    class Meta:
        verbose_name = "Alerta de Fuga"
        verbose_name_plural = "Alertas de Fuga"
        ordering = ['-fecha_hora_salida']

    def __str__(self):
        return f"Alerta {self.animal.id_hardware} - {self.fecha_hora_salida:%d/%m/%Y %H:%M:%S}"
