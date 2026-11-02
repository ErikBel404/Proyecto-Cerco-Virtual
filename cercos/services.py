"""
==============================================================================
CAPA DE SERVICIOS Y LÓGICA ESPACIAL DE NEGOCIO: cercos/services.py
==============================================================================
¿QUÉ HACE ESTE ARCHIVO?
Concentra todas las reglas de negocio geoespaciales del sistema:
1. Validación topológica de polígonos mediante la librería nativa GEOS (`validar_geometria_poligono`).
2. Evaluación de contención espacial en PostGIS (`ST_Contains`) y emisión de alertas
con ventana Anti-Spam de 5 minutos (`evaluar_y_registrar_fuga`).
3. Re-evaluación automática de animales cuando un cerco cambia de tamaño (`reevaluar_animales_de_cerco`).
4. Borrado seguro de cercos con desvinculación `SET NULL` (`eliminar_cerco_seguro`).
5. Operaciones de pertenencia de ganado (`asignar_animal_a_cerco`, `desvincular_animal_de_cerco`).

¿POR QUÉ SEPARAR ESTO DE `views.py`?
Mantener la lógica espacial en `services.py` permite reutilizar las mismas funciones
desde las vistas HTTP, desde comandos de consola, desde tareas programadas o desde
los tests unitarios sin duplicar código.
==============================================================================
"""

import json
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.contrib.gis.geos import GEOSGeometry, Point, Polygon
from django.db import transaction
from django.utils import timezone
from .models import CercoVirtual, Animal, TelemetriaGPS, AlertaFuga

# Ventana de enfriamiento Anti-Spam en minutos (RF_5 / CU_06 - Camino Alternativo 2)
VENTANA_ANTISPAM_MINUTOS = 5

# Identificadores reservados exclusivamente para el escenario de prueba / simulación
IDS_ANIMALES_DEMO = ['COLLAR-101', 'COLLAR-102', 'COLLAR-103', 'COLLAR-104']
NOMBRES_CERCOS_DEMO = ['Lote Norte - Pastura INTA', 'Lote Sur - Sector Aguada']


def validar_geometria_poligono(datos_geometria):
    """
    ¿QUÉ HACE ESTA FUNCIÓN?
    Recibe un diccionario o string GeoJSON y lo convierte en un objeto `GEOSGeometry`
    con `SRID 4326`, aplicando todas las reglas topológicas de `RF_1` y `RF_2`.

    ¿POR QUÉ ES CRÍTICA ESTA VALIDACIÓN?
    En el prototipo original solo se comprobaba `geom_type == 'Polygon'`, lo que
    permitía guardar polígonos cuyas líneas se cruzaban entre sí (forma de "8" o
    reloj de arena). Un polígono auto-intersectante corrompe las consultas espaciales
    `ST_Contains` en PostGIS. Al verificar `geometria.valid`, el motor C++ GEOS
    bloquea cualquier polígono con cruces antes de llegar a la base de datos.
    """
    if not datos_geometria:
        raise ValidationError(
            'No se recibieron coordenadas para el perímetro.')

    try:
        cadena_geojson = json.dumps(datos_geometria) if isinstance(
            datos_geometria, dict) else str(datos_geometria)
        geometria = GEOSGeometry(cadena_geojson, srid=4326)
    except Exception as exc:
        raise ValidationError(
            'El formato geométrico recibido no es un GeoJSON válido.') from exc

    # 1. Control de Cierre de Figura: debe ser exactamente un Polígono
    if geometria.geom_type != 'Polygon':
        raise ValidationError('La figura debe ser un polígono cerrado.')

    # 2. Control de Geometría Mínima: en GeoJSON el último punto repite al primero,
    # por lo tanto un triángulo (3 vértices únicos) tiene 4 pares de coordenadas.
    anillo_exterior = geometria.coords[0] if geometria.coords else ()
    vertices_unicos = set(
        anillo_exterior[:-1]) if len(anillo_exterior) > 1 else set()
    if len(anillo_exterior) < 4 or len(vertices_unicos) < 3:
        raise ValidationError(
            'Debe marcar al menos 3 vértices distintos para conformar un cerco virtual.')

    # 3. Control de Topología / No Auto-intersección (Camino Alternativo 1 de CU_01 y CU_02)
    if not geometria.valid:
        raise ValidationError(
            'El perímetro no puede tener cruces de líneas (auto-intersección). '
            'Por favor, redibuje o ajuste los vértices sin cruzar los lados.'
        )

    # 4. Verificación de área positiva (evita polígonos colineales aplastados en una línea)
    if geometria.area <= 0:
        raise ValidationError(
            'El polígono trazado no encierra un área válida.')

    return geometria


@transaction.atomic
def evaluar_y_registrar_fuga(animal, punto_gps, momento=None):
    """
    ¿QUÉ HACE ESTA FUNCIÓN?
    Implementa el corazón de los Casos de Uso `CU_05 (Procesar Ubicación)` y
    `CU_06 (Emitir Alerta)` (`RF_3`, `RF_4`, `RF_5`, `RNF_1`):
    1. Si el animal no tiene cerco asignado, solo guarda su nueva posición GPS.
    2. Si tiene cerco asignado, le pregunta directamente a PostGIS si el punto cae
    dentro del polígono usando `perimetro__contains=punto_gps` (`ST_Contains`).
    3. Si está dentro: mantiene `estado_fuga = False` y resuelve alertas previas.
    4. Si está fuera (fuga detectada): marca `estado_fuga = True`, registra la hora
    exacta de salida y verifica si ya se emitió una alerta en los últimos 5 minutos
    antes de disparar una nueva `AlertaFuga`.
    """
    ahora = momento or timezone.now()

    # Caso A: Animal sin cerco asignado (Camino Alternativo 3 de Procesar Ubicación)
    if not animal.cerco_id:
        animal.ultima_posicion = punto_gps
        animal.fecha_ultima_posicion = ahora
        animal.estado_fuga = False
        animal.fecha_hora_fuga = None
        animal.save(update_fields=[
                    'ultima_posicion', 'fecha_ultima_posicion', 'estado_fuga', 'fecha_hora_fuga'])
        TelemetriaGPS.objects.create(
            animal=animal,
            posicion=punto_gps,
            dentro_del_cerco=True,
            fecha_recepcion=ahora
        )
        return {
            'dentro_del_cerco': True,
            'sin_cerco_asignado': True,
            'alerta_emitida': False,
            'alerta': None,
        }

    # Caso B: Animal con cerco asignado -> Consulta espacial directa en PostGIS (RNF_1)
    # `perimetro__contains=punto_gps` ejecuta en SQL: ST_Contains(perimetro, punto_gps)
    esta_dentro = CercoVirtual.objects.filter(
        pk=animal.cerco_id,
        perimetro__contains=punto_gps
    ).exists()

    animal.ultima_posicion = punto_gps
    animal.fecha_ultima_posicion = ahora

    # Guardar lectura en la bitácora histórica de telemetría
    TelemetriaGPS.objects.create(
        animal=animal,
        posicion=punto_gps,
        dentro_del_cerco=esta_dentro,
        fecha_recepcion=ahora
    )

    # Subcaso B1: El animal se encuentra DENTRO del perímetro (Estado Seguro)
    if esta_dentro:
        estaba_en_fuga = animal.estado_fuga
        animal.estado_fuga = False
        animal.fecha_hora_fuga = None
        animal.save(update_fields=[
                    'ultima_posicion', 'fecha_ultima_posicion', 'estado_fuga', 'fecha_hora_fuga'])

        # Si antes estaba fugado y volvió a entrar al lote, cerramos sus alertas pendientes
        if estaba_en_fuga:
            AlertaFuga.objects.filter(animal=animal, resuelta=False).update(
                resuelta=True,
                fecha_resolucion=ahora
            )

        return {
            'dentro_del_cerco': True,
            'sin_cerco_asignado': False,
            'alerta_emitida': False,
            'alerta': None,
        }

    # Subcaso B2: El animal está FUERA del perímetro (Camino Alternativo 1: Fuga Detectada)
    # Conservamos la hora original en que salió si ya estaba fugado
    if not animal.estado_fuga or not animal.fecha_hora_fuga:
        animal.fecha_hora_fuga = ahora
    animal.estado_fuga = True
    animal.save(update_fields=[
                'ultima_posicion', 'fecha_ultima_posicion', 'estado_fuga', 'fecha_hora_fuga'])

    # Control de Frecuencia / Rate Limiting Anti-Spam (5 minutos) de CU_06:
    # Si el cerco es un potrero interno (`alerta_continua = False`), verificamos si ya se emitió
    # una alerta hace menos de 5 minutos. En cambio, si el cerco está marcado como
    # "Perímetro Crítico" (`alerta_continua = True`, ej. lindero con vecino, ruta, canal o riesgo
    # de robo), NO se silencia ninguna alerta y se notifica en cada lectura fuera del cerco.
    usar_antispam = not (animal.cerco and animal.cerco.alerta_continua)
    if usar_antispam:
        limite_antispam = ahora - timedelta(minutes=VENTANA_ANTISPAM_MINUTOS)
        alerta_reciente = AlertaFuga.objects.filter(
            animal=animal,
            fecha_hora_salida__gte=limite_antispam
        ).order_by('-fecha_hora_salida').first()

        if alerta_reciente:
            return {
                'dentro_del_cerco': False,
                'sin_cerco_asignado': False,
                'alerta_emitida': False,
                'suprimida_por_antispam': True,
                'alerta': serializar_alerta(alerta_reciente),
            }

    # Construcción y persistencia del incidente de fuga (RF_5 y RF_7)
    hora_local = timezone.localtime(ahora).strftime('%H:%M:%S')
    nombre_cerco = animal.cerco.nombre if animal.cerco else 'Cerco'
    prefijo = "🚨 [PERÍMETRO CRÍTICO]" if (
        animal.cerco and animal.cerco.alerta_continua) else "¡Fuga detectada!"
    mensaje_alerta = (
        f"{prefijo} {animal.nombre} ({animal.id_hardware}) "
        f"fuera del cerco «{nombre_cerco}» a las {hora_local}."
    )

    nueva_alerta = AlertaFuga.objects.create(
        animal=animal,
        cerco=animal.cerco,
        posicion_fuga=punto_gps,
        mensaje=mensaje_alerta,
        fecha_hora_salida=ahora,
        resuelta=False
    )

    return {
        'dentro_del_cerco': False,
        'sin_cerco_asignado': False,
        'alerta_emitida': True,
        'suprimida_por_antispam': False,
        'alerta': serializar_alerta(nueva_alerta),
    }


@transaction.atomic
def reevaluar_animales_de_cerco(cerco):
    """
    ¿QUÉ HACE ESTA FUNCIÓN Y POR QUÉ EXISTE?
    Cuando el operador achica o mueve los vértices de un cerco existente (`RF_2`),
    una vaca que antes estaba adentro puede haber quedado afuera del nuevo perímetro
    (o viceversa). Esta función recorre todos los animales de ese lote y re-evalúa
    su posición contra la nueva geometría en PostGIS.
    """
    alertas_generadas = []
    for animal in cerco.animales.all():
        if animal.ultima_posicion:
            resultado = evaluar_y_registrar_fuga(
                animal, animal.ultima_posicion)
            if resultado.get('alerta_emitida') and resultado.get('alerta'):
                alertas_generadas.append(resultado['alerta'])
    return alertas_generadas


@transaction.atomic
def eliminar_cerco_seguro(cerco):
    """
    ¿QUÉ HACE ESTA FUNCIÓN?
    Ejecuta el borrado de un `CercoVirtual` (`RF_8` / `CU_03`) dentro de una
    transacción atómica, cerrando alertas pendientes de ese lote y pasando todos
    sus animales al estado "Sin cerco asignado" (`cerco=None, estado_fuga=False`).
    """
    ahora = timezone.now()
    AlertaFuga.objects.filter(cerco=cerco, resuelta=False).update(
        resuelta=True,
        fecha_resolucion=ahora
    )
    cerco.animales.all().update(
        cerco=None,
        estado_fuga=False,
        fecha_hora_fuga=None
    )
    cerco.delete()


@transaction.atomic
def asignar_animal_a_cerco(animal, nuevo_cerco, validar_cambio=False):
    """
    ¿QUÉ HACE ESTA FUNCIÓN?
    Implementa `CU_07 (Asignar Animal a Cerco Virtual - RF-08)` y
    `CU_08 (Modificar Pertenencia a Cerco - RF-09)`.
    - Si `validar_cambio=True` (cuando el animal ya tenía un cerco), verifica el
    Control de Redundancia: bloquea la operación si el usuario eligió el mismo
    cerco en el que ya estaba el animal.
    - Si el animal no tenía ninguna posición GPS previa, lo ubica inicialmente en el
    centro geométrico (`centroid`) del nuevo lote para que sea visible en el mapa.
    """
    if validar_cambio and animal.cerco_id == nuevo_cerco.id:
        raise ValidationError(
            f'El animal {animal.id_hardware} ya se encuentra asignado al cerco «{nuevo_cerco.nombre}».')

    animal.cerco = nuevo_cerco
    animal.save(update_fields=['cerco'])

    if animal.ultima_posicion:
        resultado_espacial = evaluar_y_registrar_fuga(
            animal, animal.ultima_posicion)
    else:
        centro = nuevo_cerco.perimetro.centroid
        resultado_espacial = evaluar_y_registrar_fuga(
            animal, Point(centro.x, centro.y, srid=4326))

    return resultado_espacial


@transaction.atomic
def desvincular_animal_de_cerco(animal):
    """
    ¿QUÉ HACE ESTA FUNCIÓN?
    Implementa `CU_09 (Eliminar Pertenencia / Desvincular Animal de Cerco - RF-10)`.
    Quita la asignación de cerco (`cerco = None`), apaga la bandera `estado_fuga`
    para que deje de figurar como prófugo y cierra las alertas abiertas de ese animal.
    """
    if not animal.cerco_id:
        raise ValidationError(
            f'El animal {animal.id_hardware} no tiene ningún cerco asignado actualmente.')

    ahora = timezone.now()
    AlertaFuga.objects.filter(animal=animal, resuelta=False).update(
        resuelta=True,
        fecha_resolucion=ahora
    )
    animal.cerco = None
    animal.estado_fuga = False
    animal.fecha_hora_fuga = None
    animal.save(update_fields=['cerco', 'estado_fuga', 'fecha_hora_fuga'])


def serializar_animal(animal):
    """
    Transforma un objeto `Animal` de GeoDjango en un diccionario JSON plano,
    extrayendo `latitud` (`y`) y `longitud` (`x`) de su `PointField`.
    """
    lat = animal.ultima_posicion.y if animal.ultima_posicion else None
    lng = animal.ultima_posicion.x if animal.ultima_posicion else None
    return {
        'id': animal.id,
        'id_hardware': animal.id_hardware,
        'nombre': animal.nombre,
        'especie': animal.especie,
        'cerco_id': animal.cerco_id,
        'cerco_nombre': animal.cerco.nombre if animal.cerco else None,
        'cerco_color': animal.cerco.color if animal.cerco else '#64748b',
        'latitud': lat,
        'longitud': lng,
        'fecha_ultima_posicion': (
            timezone.localtime(animal.fecha_ultima_posicion).strftime(
                '%d/%m/%Y %H:%M:%S')
            if animal.fecha_ultima_posicion else None
        ),
        'estado_fuga': animal.estado_fuga,
        'fecha_hora_fuga': (
            timezone.localtime(animal.fecha_hora_fuga).strftime(
                '%d/%m/%Y %H:%M:%S')
            if animal.fecha_hora_fuga else None
        ),
        'hora_fuga_corta': (
            timezone.localtime(animal.fecha_hora_fuga).strftime('%H:%M:%S')
            if animal.fecha_hora_fuga else None
        ),
    }


def serializar_alerta(alerta):
    """Transforma un objeto `AlertaFuga` en diccionario JSON para notificaciones Toast y listas."""
    return {
        'id': alerta.id,
        'animal_id': alerta.animal_id,
        'id_hardware': alerta.animal.id_hardware,
        'animal_nombre': alerta.animal.nombre,
        'cerco_id': alerta.cerco_id,
        'cerco_nombre': alerta.cerco.nombre if alerta.cerco else 'Cerco eliminado',
        'latitud': alerta.posicion_fuga.y if alerta.posicion_fuga else None,
        'longitud': alerta.posicion_fuga.x if alerta.posicion_fuga else None,
        'mensaje': alerta.mensaje,
        'fecha_hora_salida': timezone.localtime(alerta.fecha_hora_salida).strftime('%d/%m/%Y %H:%M:%S'),
        'hora_salida_corta': timezone.localtime(alerta.fecha_hora_salida).strftime('%H:%M:%S'),
        'resuelta': alerta.resuelta,
    }


@transaction.atomic
def cargar_escenario_demo_catamarca(usuario=None, lat_base=None, lng_base=None):
    """
    ¿PARA QUÉ SIRVE ESTA FUNCIÓN?
    Permite poblar con un solo clic un escenario completo de prueba (2 lotes agrícolas
    y 4 vacas en distintos estados: dentro del cerco, prófuga fuera del cerco y sin
    cerco asignado) alrededor de la ubicación base seleccionada por el usuario
    (por defecto San Fernando del Valle de Catamarca, o Belén, Tinogasta, Andalgalá, etc.).
    """
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
        nombre='Lote Norte - Pastura INTA',
        defaults={
            'color': '#2ecc71',
            'perimetro': poligono_norte,
            'alerta_continua': True,
            'usuario': usuario,
        }
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
        defaults={
            'color': '#3498db',
            'perimetro': poligono_sur,
            'alerta_continua': False,
            'usuario': usuario,
        }
    )

    datos_animales = [
        ('COLLAR-101', 'Vaca #101 (Aberdeen Angus)',
         'Bovino', cerco_norte, lat_c + 0.0026, lng_c - 0.0023),
        ('COLLAR-102', 'Vaca #102 (Hereford)',
         'Bovino', cerco_sur, lat_c - 0.0019, lng_c + 0.0087),
        ('COLLAR-103', 'Vaca #103 (Holando - Prófuga)',
         'Bovino', cerco_norte, lat_c + 0.0084, lng_c - 0.0018),
        ('COLLAR-104', 'Toro #104 (Braford - Sin Lote)',
         'Bovino', None, lat_c - 0.0039, lng_c - 0.0033),
    ]

    for id_hw, nombre, especie, cerco_obj, lat, lng in datos_animales:
        animal, _ = Animal.objects.update_or_create(
            id_hardware=id_hw,
            defaults={
                'nombre': nombre,
                'especie': especie,
                'cerco': cerco_obj,
            }
        )
        evaluar_y_registrar_fuga(animal, Point(lng, lat, srid=4326))

    return {
        'cercos_creados': 2,
        'animales_creados': 4,
    }


def limpiar_escenario_demo_catamarca():
    """
    Elimina exclusivamente los registros de prueba creados por `cargar_escenario_demo_catamarca`
    (COLLAR-101 a COLLAR-104 y los 2 lotes de demostración).
    OPTIMIZACIÓN SUPABASE: Verifica primero si existen datos de demo antes de abrir
    una transacción de borrado en la nube, ahorrando viajes de red innecesarios.
    """
    hay_demo = (
        Animal.objects.filter(id_hardware__in=IDS_ANIMALES_DEMO).exists()
        or CercoVirtual.objects.filter(nombre__in=NOMBRES_CERCOS_DEMO).exists()
    )
    if not hay_demo:
        return {'animales_eliminados': 0, 'cercos_eliminados': 0}

    with transaction.atomic():
        AlertaFuga.objects.filter(
            animal__id_hardware__in=IDS_ANIMALES_DEMO).delete()
        AlertaFuga.objects.filter(cerco__nombre__in=NOMBRES_CERCOS_DEMO).delete()
        TelemetriaGPS.objects.filter(
            animal__id_hardware__in=IDS_ANIMALES_DEMO).delete()
        animales_borrados, _ = Animal.objects.filter(
            id_hardware__in=IDS_ANIMALES_DEMO).delete()
        cercos_borrados, _ = CercoVirtual.objects.filter(
            nombre__in=NOMBRES_CERCOS_DEMO).delete()

    return {
        'animales_eliminados': animales_borrados,
        'cercos_eliminados': cercos_borrados,
    }


def sincronizar_lecturas_externas_nodered(lista_animales=None):
    """
    ¿QUÉ HACE ESTA FUNCIÓN Y POR QUÉ ES RÁPIDA EN SUPABASE?
    Cuando Node-RED actualiza `cercos_animal.ultima_posicion` directamente en Supabase,
    compara en memoria (con GEOS C-API, en 0.01 ms y sin hacer consultas SQL extra)
    si el punto cae dentro del polígono de su cerco ya precargado con `select_related('cerco')`.
    Solo si detecta que el estado cambió (entró en fuga o regresó al lote), ejecuta la
    escritura transaccional en la base de datos.
    """
    alertas_nuevas = []
    if lista_animales is None:
        lista_animales = list(
            Animal.objects.select_related('cerco').filter(
                cerco__isnull=False,
                ultima_posicion__isnull=False
            )
        )

    for animal in lista_animales:
        if not animal.cerco or not animal.ultima_posicion:
            continue

        esta_dentro = animal.cerco.perimetro.contains(animal.ultima_posicion)

        if esta_dentro and animal.estado_fuga:
            evaluar_y_registrar_fuga(animal, animal.ultima_posicion)
        elif not esta_dentro and not animal.estado_fuga:
            res = evaluar_y_registrar_fuga(animal, animal.ultima_posicion)
            if res.get('alerta_emitida') and res.get('alerta'):
                alertas_nuevas.append(res['alerta'])

    return alertas_nuevas
