"""
==============================================================================
CAPA DE SERVICIOS Y LÓGICA ESPACIAL DE NEGOCIO: cercos/services.py
==============================================================================
Organizado en 5 bloques de funciones cortas:
1. Validación topológica de polígonos (`validar_geometria_poligono`).
2. Evaluación espacial PostGIS y registro en `TelemetriaGPS` (`evaluar_y_registrar_fuga`).
3. Consumo de `Lectura` desde Node-RED (`procesar_lecturas_pendientes_nodered`).
4. Gestión de cercos y pertenencia de animales.
5. Serializadores JSON y escenario de demostración.
==============================================================================
"""

import json
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.contrib.gis.geos import GEOSGeometry, Point, Polygon
from django.db import transaction
from django.utils import timezone

from .models import Lectura, CercoVirtual, Animal, TelemetriaGPS, AlertaFuga

VENTANA_ANTISPAM_MINUTOS = 5
IDS_ANIMALES_DEMO = ['COLLAR-101', 'COLLAR-102', 'COLLAR-103', 'COLLAR-104']
NOMBRES_CERCOS_DEMO = [
    'Lote Norte - Pastura UNCA',
    'Lote Sur - Sector Aguada',
    'Lote Norte - Pastura INTA',
]


# ==============================================================================
# 1. VALIDACIÓN TOPOLÓGICA DE POLÍGONOS (RF_1, RF_2)
# ==============================================================================

def _convertir_geojson_a_geometria(datos_geometria):
    """Convierte un dict o texto GeoJSON en `GEOSGeometry(srid=4326)`."""
    if not datos_geometria:
        raise ValidationError('No se recibieron coordenadas para el perímetro.')
    try:
        texto = json.dumps(datos_geometria) if isinstance(datos_geometria, dict) else str(datos_geometria)
        return GEOSGeometry(texto, srid=4326)
    except Exception as exc:
        raise ValidationError('El formato geométrico recibido no es un GeoJSON válido.') from exc


def validar_geometria_poligono(datos_geometria):
    """Valida polígono cerrado, mínimo 3 vértices y sin auto-intersección (`RF_1`, `RF_2`)."""
    geometria = _convertir_geojson_a_geometria(datos_geometria)

    if geometria.geom_type != 'Polygon':
        raise ValidationError('La figura debe ser un polígono cerrado.')

    anillo = geometria.coords[0] if geometria.coords else ()
    vertices_unicos = set(anillo[:-1]) if len(anillo) > 1 else set()
    if len(anillo) < 4 or len(vertices_unicos) < 3:
        raise ValidationError('Debe marcar al menos 3 vértices distintos para conformar un cerco virtual.')

    if not geometria.valid:
        raise ValidationError('El perímetro no puede tener cruces de líneas (auto-intersección).')

    if geometria.area <= 0:
        raise ValidationError('El polígono trazado no encierra un área válida.')

    return geometria


# ==============================================================================
# 2. FLUJO DE TELEMETRÍA: `Lectura` -> `TelemetriaGPS` -> `AlertaFuga`
# ==============================================================================

def _verificar_punto_dentro_de_cerco(cerco_id, punto_gps):
    """Pregunta a PostGIS si el punto cae dentro del cerco (`ST_Contains`)."""
    return CercoVirtual.objects.filter(pk=cerco_id, perimetro__contains=punto_gps).exists()


def _registrar_telemetria_gps(animal, punto_gps, dentro_del_cerco, momento, lectura_origen=None):
    """Guarda la posición validada en `TelemetriaGPS` referenciando la `Lectura` de origen."""
    return TelemetriaGPS.objects.create(
        animal=animal,
        lectura_origen=lectura_origen,
        posicion=punto_gps,
        dentro_del_cerco=dentro_del_cerco,
        fecha_recepcion=momento,
    )


def _buscar_alerta_en_ventana_antispam(animal, momento):
    """Devuelve la alerta previa si aún no pasaron los 5 minutos de enfriamiento."""
    if animal.cerco and animal.cerco.alerta_continua:
        return None
    limite = momento - timedelta(minutes=VENTANA_ANTISPAM_MINUTOS)
    return AlertaFuga.objects.filter(
        animal=animal,
        fecha_hora_salida__gte=limite
    ).order_by('-fecha_hora_salida').first()


def _emitir_alerta_si_corresponde(animal, punto_gps, momento):
    """Crea un incidente en `AlertaFuga` respetando la regla Anti-Spam de 5 minutos."""
    alerta_reciente = _buscar_alerta_en_ventana_antispam(animal, momento)
    if alerta_reciente:
        return {
            'alerta_emitida': False,
            'suprimida_por_antispam': True,
            'alerta': serializar_alerta(alerta_reciente),
        }

    hora_local = timezone.localtime(momento).strftime('%H:%M:%S')
    nombre_cerco = animal.cerco.nombre if animal.cerco else 'Cerco'
    es_critico = bool(animal.cerco and animal.cerco.alerta_continua)
    prefijo = "🚨 [PERÍMETRO CRÍTICO]" if es_critico else "¡Fuga detectada!"

    nueva_alerta = AlertaFuga.objects.create(
        animal=animal,
        cerco=animal.cerco,
        posicion_fuga=punto_gps,
        mensaje=f"{prefijo} {animal.nombre} ({animal.id_hardware}) fuera del cerco «{nombre_cerco}» a las {hora_local}.",
        fecha_hora_salida=momento,
        resuelta=False,
    )
    return {
        'alerta_emitida': True,
        'suprimida_por_antispam': False,
        'alerta': serializar_alerta(nueva_alerta),
    }


def _procesar_animal_sin_cerco(animal, punto_gps, ahora, lectura_origen):
    """Actualiza un animal que aún no tiene cerco asignado."""
    animal.estado_fuga = False
    animal.fecha_hora_fuga = None
    animal.save(update_fields=['ultima_posicion', 'fecha_ultima_posicion', 'estado_fuga', 'fecha_hora_fuga'])
    _registrar_telemetria_gps(animal, punto_gps, True, ahora, lectura_origen)
    return {'dentro_del_cerco': True, 'sin_cerco_asignado': True, 'alerta_emitida': False, 'alerta': None}


def _procesar_animal_dentro_del_cerco(animal, ahora):
    """Actualiza el animal como seguro dentro del lote y cierra alertas previas si regresó."""
    estaba_en_fuga = animal.estado_fuga
    animal.estado_fuga = False
    animal.fecha_hora_fuga = None
    animal.save(update_fields=['ultima_posicion', 'fecha_ultima_posicion', 'estado_fuga', 'fecha_hora_fuga'])

    if estaba_en_fuga:
        AlertaFuga.objects.filter(animal=animal, resuelta=False).update(resuelta=True, fecha_resolucion=ahora)

    return {'dentro_del_cerco': True, 'sin_cerco_asignado': False, 'alerta_emitida': False, 'alerta': None}


def _procesar_animal_en_fuga(animal, punto_gps, ahora):
    """Marca al animal en estado de fuga y dispara la alerta correspondiente."""
    if not animal.estado_fuga or not animal.fecha_hora_fuga:
        animal.fecha_hora_fuga = ahora
    animal.estado_fuga = True
    animal.save(update_fields=['ultima_posicion', 'fecha_ultima_posicion', 'estado_fuga', 'fecha_hora_fuga'])

    resultado_alerta = _emitir_alerta_si_corresponde(animal, punto_gps, ahora)
    return {'dentro_del_cerco': False, 'sin_cerco_asignado': False, **resultado_alerta}


@transaction.atomic
def evaluar_y_registrar_fuga(animal, punto_gps, momento=None, lectura_origen=None):
    """Función coordinadora: evalúa la ubicación en PostGIS y registra en `TelemetriaGPS`."""
    ahora = momento or timezone.now()
    animal.ultima_posicion = punto_gps
    animal.fecha_ultima_posicion = ahora

    if not animal.cerco_id:
        return _procesar_animal_sin_cerco(animal, punto_gps, ahora, lectura_origen)

    esta_dentro = _verificar_punto_dentro_de_cerco(animal.cerco_id, punto_gps)
    _registrar_telemetria_gps(animal, punto_gps, esta_dentro, ahora, lectura_origen)

    if esta_dentro:
        return _procesar_animal_dentro_del_cerco(animal, ahora)
    return _procesar_animal_en_fuga(animal, punto_gps, ahora)


# ==============================================================================
# 3. CONSUMO DE LA TABLA `Lectura` (NODE-RED -> TELEMETRÍA GPS)
# ==============================================================================

def _obtener_o_crear_animal_por_collar(id_hardware):
    """Busca el animal por `id_hardware` o lo da de alta automáticamente si es nuevo."""
    animal = Animal.objects.select_related('cerco').filter(id_hardware__iexact=id_hardware).first()
    if not animal:
        animal = Animal.objects.create(id_hardware=id_hardware, nombre=f"Collar {id_hardware}", especie='Bovino')
    return animal


def _procesar_una_lectura(lectura):
    """Convierte una fila de `Lectura` en un punto PostGIS y la pasa a `TelemetriaGPS`."""
    id_hw = (lectura.id_hardware or '').strip()
    if not id_hw:
        lectura.procesada = True
        lectura.save(update_fields=['procesada'])
        return None

    animal = _obtener_o_crear_animal_por_collar(id_hw)
    punto_gps = Point(float(lectura.longitud), float(lectura.latitud), srid=4326)
    resultado = evaluar_y_registrar_fuga(animal, punto_gps, momento=lectura.fecha_hora, lectura_origen=lectura)

    lectura.procesada = True
    lectura.save(update_fields=['procesada'])
    return resultado.get('alerta') if resultado.get('alerta_emitida') else None


def procesar_lecturas_pendientes_nodered():
    """Consume todas las filas pendientes (`procesada=False`) de la tabla `Lectura`."""
    lecturas_nuevas = list(Lectura.objects.filter(procesada=False).order_by('fecha_hora')[:100])
    alertas_emitidas = []
    for lectura in lecturas_nuevas:
        alerta = _procesar_una_lectura(lectura)
        if alerta:
            alertas_emitidas.append(alerta)
    return alertas_emitidas


def sincronizar_lecturas_externas_nodered():
    """Punto de entrada de sincronización con las lecturas depositadas por Node-RED."""
    return procesar_lecturas_pendientes_nodered()


# ==============================================================================
# 4. GESTIÓN DE CERCOS Y PERTENENCIA DE ANIMALES (RF_2, RF_8, RF-08 A RF-10)
# ==============================================================================

@transaction.atomic
def reevaluar_animales_de_cerco(cerco):
    """Re-evalúa todos los animales de un cerco cuando se modifica su polígono (`RF_2`)."""
    alertas_generadas = []
    for animal in cerco.animales.all():
        if animal.ultima_posicion:
            res = evaluar_y_registrar_fuga(animal, animal.ultima_posicion)
            if res.get('alerta_emitida') and res.get('alerta'):
                alertas_generadas.append(res['alerta'])
    return alertas_generadas


@transaction.atomic
def eliminar_cerco_seguro(cerco):
    """Elimina un cerco dejando a sus animales en estado 'Sin cerco asignado' (`RF_8`)."""
    AlertaFuga.objects.filter(cerco=cerco, resuelta=False).update(resuelta=True, fecha_resolucion=timezone.now())
    cerco.animales.all().update(cerco=None, estado_fuga=False, fecha_hora_fuga=None)
    cerco.delete()


@transaction.atomic
def asignar_animal_a_cerco(animal, nuevo_cerco, validar_cambio=False):
    """Asigna o reasigna un animal a un cerco virtual (`RF-08`, `RF-09`)."""
    if validar_cambio and animal.cerco_id == nuevo_cerco.id:
        raise ValidationError(f'El animal {animal.id_hardware} ya pertenece al cerco «{nuevo_cerco.nombre}».')

    animal.cerco = nuevo_cerco
    animal.save(update_fields=['cerco'])

    punto = animal.ultima_posicion or Point(nuevo_cerco.perimetro.centroid.x, nuevo_cerco.perimetro.centroid.y, srid=4326)
    return evaluar_y_registrar_fuga(animal, punto)


@transaction.atomic
def desvincular_animal_de_cerco(animal):
    """Desvincula un animal de su cerco actual y cierra sus alertas abiertas (`RF-10`)."""
    if not animal.cerco_id:
        raise ValidationError(f'El animal {animal.id_hardware} no tiene ningún cerco asignado.')

    AlertaFuga.objects.filter(animal=animal, resuelta=False).update(resuelta=True, fecha_resolucion=timezone.now())
    animal.cerco = None
    animal.estado_fuga = False
    animal.fecha_hora_fuga = None
    animal.save(update_fields=['cerco', 'estado_fuga', 'fecha_hora_fuga'])


# ==============================================================================
# 5. SERIALIZADORES JSON Y ESCENARIO DE DEMOSTRACIÓN
# ==============================================================================

def _formatear_fecha(fecha):
    return timezone.localtime(fecha).strftime('%d/%m/%Y %H:%M:%S') if fecha else None


def _formatear_hora_corta(fecha):
    return timezone.localtime(fecha).strftime('%H:%M:%S') if fecha else None


def serializar_cerco_geojson(cerco):
    """Convierte un `CercoVirtual` en un Feature GeoJSON para Leaflet."""
    animales_lote = list(cerco.animales.all())
    return {
        'type': 'Feature',
        'id': cerco.id,
        'properties': {
            'id': cerco.id,
            'nombre': cerco.nombre,
            'color': cerco.color,
            'alerta_continua': cerco.alerta_continua,
            'area_hectareas': cerco.area_hectareas,
            'total_animales': len(animales_lote),
            'animales_en_fuga': sum(1 for a in animales_lote if a.estado_fuga),
            'fecha_creacion': timezone.localtime(cerco.fecha_creacion).strftime('%d/%m/%Y'),
        },
        'geometry': json.loads(cerco.perimetro.geojson),
    }


def serializar_animal(animal):
    """Convierte un objeto `Animal` en diccionario JSON plano para el mapa."""
    pos = animal.ultima_posicion
    return {
        'id': animal.id,
        'id_hardware': animal.id_hardware,
        'nombre': animal.nombre,
        'especie': animal.especie,
        'cerco_id': animal.cerco_id,
        'cerco_nombre': animal.cerco.nombre if animal.cerco else None,
        'cerco_color': animal.cerco.color if animal.cerco else '#64748b',
        'latitud': pos.y if pos else None,
        'longitud': pos.x if pos else None,
        'fecha_ultima_posicion': _formatear_fecha(animal.fecha_ultima_posicion),
        'estado_fuga': animal.estado_fuga,
        'fecha_hora_fuga': _formatear_fecha(animal.fecha_hora_fuga),
        'hora_fuga_corta': _formatear_hora_corta(animal.fecha_hora_fuga),
    }


def serializar_alerta(alerta):
    """Convierte un objeto `AlertaFuga` en diccionario JSON para notificaciones."""
    pos = alerta.posicion_fuga
    return {
        'id': alerta.id,
        'animal_id': alerta.animal_id,
        'id_hardware': alerta.animal.id_hardware,
        'animal_nombre': alerta.animal.nombre,
        'cerco_id': alerta.cerco_id,
        'cerco_nombre': alerta.cerco.nombre if alerta.cerco else 'Cerco eliminado',
        'latitud': pos.y if pos else None,
        'longitud': pos.x if pos else None,
        'mensaje': alerta.mensaje,
        'fecha_hora_salida': _formatear_fecha(alerta.fecha_hora_salida),
        'hora_salida_corta': _formatear_hora_corta(alerta.fecha_hora_salida),
        'resuelta': alerta.resuelta,
    }


@transaction.atomic
def cargar_escenario_demo_catamarca(usuario=None, lat_base=None, lng_base=None):
    """Carga 2 lotes y 4 animales de prueba alrededor de la ubicación base elegida."""
    lat_c = float(lat_base) if lat_base is not None else -28.4696
    lng_c = float(lng_base) if lng_base is not None else -65.7852

    poligono_norte = Polygon((
        (lng_c - 0.0068, lat_c + 0.0056),
        (lng_c + 0.0022, lat_c + 0.0056),
        (lng_c + 0.0022, lat_c - 0.0009),
        (lng_c - 0.0068, lat_c - 0.0009),
        (lng_c - 0.0068, lat_c + 0.0056),
    ), srid=4326)

    cerco_norte, _ = CercoVirtual.objects.update_or_create(
        nombre='Lote Norte - Pastura UNCA',
        defaults={'color': '#2ecc71', 'perimetro': poligono_norte, 'alerta_continua': True, 'usuario': usuario}
    )

    poligono_sur = Polygon((
        (lng_c + 0.0042, lat_c + 0.0016),
        (lng_c + 0.0132, lat_c + 0.0016),
        (lng_c + 0.0132, lat_c - 0.0059),
        (lng_c + 0.0042, lat_c - 0.0059),
        (lng_c + 0.0042, lat_c + 0.0016),
    ), srid=4326)

    cerco_sur, _ = CercoVirtual.objects.update_or_create(
        nombre='Lote Sur - Sector Aguada',
        defaults={'color': '#3498db', 'perimetro': poligono_sur, 'alerta_continua': False, 'usuario': usuario}
    )

    datos_animales = [
        ('COLLAR-101', 'Vaca #101 (Aberdeen Angus)', 'Bovino', cerco_norte, lat_c + 0.0026, lng_c - 0.0023),
        ('COLLAR-102', 'Vaca #102 (Hereford)', 'Bovino', cerco_sur, lat_c - 0.0019, lng_c + 0.0087),
        ('COLLAR-103', 'Vaca #103 (Holando - Prófuga)', 'Bovino', cerco_norte, lat_c + 0.0084, lng_c - 0.0018),
        ('COLLAR-104', 'Toro #104 (Braford - Sin Lote)', 'Bovino', None, lat_c - 0.0039, lng_c - 0.0033),
    ]

    for id_hw, nombre, especie, cerco_obj, lat, lng in datos_animales:
        animal, _ = Animal.objects.update_or_create(
            id_hardware=id_hw,
            defaults={'nombre': nombre, 'especie': especie, 'cerco': cerco_obj}
        )
        evaluar_y_registrar_fuga(animal, Point(lng, lat, srid=4326))

    return {'cercos_creados': 2, 'animales_creados': 4}


def limpiar_escenario_demo_catamarca():
    """Elimina exclusivamente los datos de demostración sin tocar registros reales."""
    hay_demo = (
        Animal.objects.filter(id_hardware__in=IDS_ANIMALES_DEMO).exists()
        or CercoVirtual.objects.filter(nombre__in=NOMBRES_CERCOS_DEMO).exists()
        or Lectura.objects.filter(id_hardware__in=IDS_ANIMALES_DEMO).exists()
    )
    if not hay_demo:
        return {'animales_eliminados': 0, 'cercos_eliminados': 0}

    with transaction.atomic():
        AlertaFuga.objects.filter(animal__id_hardware__in=IDS_ANIMALES_DEMO).delete()
        AlertaFuga.objects.filter(cerco__nombre__in=NOMBRES_CERCOS_DEMO).delete()
        TelemetriaGPS.objects.filter(animal__id_hardware__in=IDS_ANIMALES_DEMO).delete()
        Lectura.objects.filter(id_hardware__in=IDS_ANIMALES_DEMO).delete()
        animales_borrados, _ = Animal.objects.filter(id_hardware__in=IDS_ANIMALES_DEMO).delete()
        cercos_borrados, _ = CercoVirtual.objects.filter(nombre__in=NOMBRES_CERCOS_DEMO).delete()

    return {'animales_eliminados': animales_borrados, 'cercos_eliminados': cercos_borrados}
