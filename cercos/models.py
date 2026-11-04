"""
==============================================================================
MODELOS DE DATOS GEOESPACIALES: cercos/models.py
==============================================================================
¿QUÉ HACE ESTE ARCHIVO?
Define la estructura de tablas en PostgreSQL + PostGIS mediante el ORM de GeoDjango:
1. `CercoVirtual`: Almacena los polígonos perimetrales de los lotes (RF_1, RF_2, RF_8).
2. `Animal`: Almacena el ganado monitoreado, su collar físico (`id_hardware`),
el cerco al que está asignado y su última coordenada GPS (RF-08, RF-09, RF-10).
3. `TelemetriaGPS`: Bitácora histórica de posiciones enviadas por los collares (RF_3, RF_4).
4. `AlertaFuga`: Registro de incidentes cuando un animal sale de su cerco (RF_5, RF_6, RF_7).

¿POR QUÉ USAMOS SRID 4326 EN TODOS LOS CAMPOS ESPACIALES?
SRID 4326 corresponde al sistema geodésico mundial WGS 84 (Latitud y Longitud
en grados decimales), que es el estándar nativo que entregan los módulos GPS
de los collares desarrollados por Ingeniería Electrónica y el formato GeoJSON.
==============================================================================
"""

from django.contrib.gis.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class CercoVirtual(models.Model):
    """
    Representa un potrero, lote o parcela rural delimitada por un polígono cerrado.

    ¿POR QUÉ ESTÁ DISEÑADO ASÍ?
    - `perimetro = models.PolygonField(srid=4326)` crea una columna espacial nativa
    `geometry(Polygon, 4326)` en PostGIS con un índice espacial GiST automático.
    Eso permite que la base de datos resuelva en milisegundos si un punto GPS cae
    dentro o fuera del lote mediante la función espacial `ST_Contains`.
    """
    # Relación opcional con el usuario operador que creó el cerco (según DER)
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='cercos',
        null=True,
        blank=True
    )

    # Nombre identificatorio del potrero o lote (ej: "Lote Norte - Alfalfa")
    nombre = models.CharField(max_length=100, verbose_name="Nombre del Lote")

    # Color hexadecimal (#RRGGBB) para distinguir visualmente cada lote en Leaflet
    color = models.CharField(
        max_length=7, default="#2ecc71", verbose_name="Color de Identificación")

    # Polígono espacial en coordenadas WGS84 [Longitud, Latitud]
    perimetro = models.PolygonField(
        srid=4326, verbose_name="Perímetro del Cerco")

    # Configuración de criticidad de alertas por lote:
    # - False (por defecto): Potrero interno (aplica ventana Anti-Spam de 5 min entre alertas).
    # - True: Perímetro crítico / lindero con vecino, ruta o canal (emite alerta continua en cada lectura fuera).
    alerta_continua = models.BooleanField(
        default=False,
        verbose_name="Perímetro Crítico (Alerta Continua sin Anti-Spam)"
    )

    # Auditoría temporal automática
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
        """
        ¿QUÉ HACE ESTA PROPIEDAD?
        Calcula la superficie aproximada del lote en hectáreas (1 ha = 10.000 m²).

        ¿POR QUÉ TRANSFORMA A SRID 3857?
        Porque en SRID 4326 las unidades son grados esféricos (no metros). Al clonar
        la geometría en memoria y proyectarla a Web Mercator (SRID 3857) aplicando el
        factor de corrección de latitud de Catamarca (~cos(-28.47°)² = 0.772),
        obtenemos los metros cuadrados sin alterar el registro original en la base.
        """
        try:
            geom_metrica = self.perimetro.transform(3857, clone=True)
            factor_latitud = 0.772
            area_m2 = geom_metrica.area * factor_latitud
            return round(area_m2 / 10000.0, 2)
        except Exception:
            return 0.0


class Animal(models.Model):
    """
    Representa un animal del rodeo vinculado a un collar IoT GPS.

    ¿POR QUÉ `cerco` TIENE `on_delete=models.SET_NULL`?
    Cumple estrictamente el Control de Integridad Referencial del Caso de Uso
    "Eliminar Cerco Virtual" (RF_8): si el productor borra un cerco del mapa,
    las vacas asignadas a ese cerco NO deben borrarse de la base de datos;
    deben pasar automáticamente al estado "Sin cerco asignado" (`cerco = NULL`).
    """
    ESPECIE_CHOICES = [
        ('Bovino', 'Bovino (Vaca / Toro)'),
        ('Ovino', 'Ovino'),
        ('Caprino', 'Caprino'),
        ('Equino', 'Equino'),
        ('Otro', 'Otro'),
    ]

    # Identificador único del collar electrónico (clave de cruce con el Gateway IoT)
    id_hardware = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="ID de Collar / Hardware"
    )
    # Nombre o caravana visible para el productor (ej. "Vaca #104 - Aberdeen Angus")
    nombre = models.CharField(
        max_length=100,
        verbose_name="Nombre / Identificación del Animal"
    )
    # Pensado inicialmente para vacas (Bovino), pero preparado para otras especies
    especie = models.CharField(
        max_length=30,
        choices=ESPECIE_CHOICES,
        default='Bovino',
        verbose_name="Especie"
    )
    # Cerco virtual al que pertenece actualmente (Null = Sin cerco asignado)
    cerco = models.ForeignKey(
        CercoVirtual,
        on_delete=models.SET_NULL,
        related_name='animales',
        null=True,
        blank=True,
        verbose_name="Cerco Virtual Asignado"
    )
    # Última coordenada conocida del animal como punto geométrico PostGIS [lng, lat]
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
    # Bandera rápida para filtrar animales prófugos (RF_6: Listado fuera de límite)
    estado_fuga = models.BooleanField(
        default=False,
        verbose_name="Fuera del Cerco (En Fuga)"
    )
    # Marca de tiempo exacta en que se detectó que cruzó el perímetro (RF_7)
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
    Almacena el historial de coordenadas recibidas desde el collar GPS (RF_3).

    ¿PARA QUÉ SIRVE ESTA TABLA ADEMÁS DE `Animal.ultima_posicion`?
    Mientras `Animal.ultima_posicion` permite saber dónde está el animal ahora mismo
    sin recorrer millones de filas, `TelemetriaGPS` conserva la traza histórica de
    movimientos para auditoría, mapas de calor de pastoreo o análisis.
    """
    animal = models.ForeignKey(
        Animal,
        on_delete=models.CASCADE,
        related_name='telemetrias',
        verbose_name="Animal"
    )
    posicion = models.PointField(
        srid=4326,
        verbose_name="Coordenada GPS"
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
        verbose_name = "Lectura de Telemetría GPS"
        verbose_name_plural = "Lecturas de Telemetría GPS"
        ordering = ['-fecha_recepcion']

    def __str__(self):
        estado = "Dentro" if self.dentro_del_cerco else "Fuera"
        return f"{self.animal.id_hardware} ({estado}) @ {self.fecha_recepcion:%d/%m/%Y %H:%M:%S}"


class AlertaFuga(models.Model):
    """
    Representa un incidente formal de escape cuando un animal cruza el límite de su cerco (RF_5, RF_7).

    ¿PARA QUÉ SIRVE ESTA TABLA?
    1. Permite encolar y persistir alertas si el operador estaba desconectado cuando
    ocurrió la fuga (Camino Alternativo 1 de Emitir Alerta).
    2. Permite aplicar la ventana Anti-Spam de 5 minutos (Camino Alternativo 2):
    consultando cuándo se emitió la última `AlertaFuga` para ese animal evitamos
    bombardear al usuario con cientos de alertas mientras la vaca camina fuera.
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
