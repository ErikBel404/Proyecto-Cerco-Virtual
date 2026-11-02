"""
==============================================================================
CAPA DE VISTAS Y ENDPOINTS HTTP / GEOJSON: cercos/views.py
==============================================================================
¿QUÉ HACE ESTE ARCHIVO?
Actúa como controlador HTTP entre el cliente (navegador con Leaflet o Gateway IoT)
y nuestras capas internas de validación (`forms.py`) y negocio espacial (`services.py`).

Cada vista sigue tres pasos simples:
1. Decodificar la entrada HTTP (`_decodificar_json`) y validarla con `forms.py`.
2. Invocar la función transaccional de `services.py`.
3. Retornar un `JsonResponse` con códigos HTTP semánticos (200, 400, 404, 500).
==============================================================================
"""

import json
from django.core.exceptions import ValidationError
from django.contrib.gis.geos import Point
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from .forms import CercoVirtualForm, AnimalForm, TelemetriaGPSForm
from .models import CercoVirtual, Animal, AlertaFuga
from .services import (
    validar_geometria_poligono,
    reevaluar_animales_de_cerco,
    eliminar_cerco_seguro,
    asignar_animal_a_cerco,
    desvincular_animal_de_cerco,
    evaluar_y_registrar_fuga,
    serializar_animal,
    serializar_alerta,
    cargar_escenario_demo_catamarca,
    limpiar_escenario_demo_catamarca,
    sincronizar_lecturas_externas_nodered,
    IDS_ANIMALES_DEMO,
    NOMBRES_CERCOS_DEMO,
)


# ==============================================================================
# UTILIDADES INTERNAS PARA EVITAR CÓDIGO REPETIDO EN LAS VISTAS
# ==============================================================================

def _decodificar_json(request):
    """
    Decodifica el cuerpo JSON de una petición POST.
    Retorna `(datos_dict, None)` si es válido, o `(None, JsonResponse_400)` si falla.
    """
    try:
        return json.loads(request.body or b'{}'), None
    except json.JSONDecodeError:
        respuesta_error = JsonResponse(
            {'estado': 'error', 'mensaje': 'El cuerpo de la solicitud no es un JSON válido.'},
            status=400
        )
        return None, respuesta_error


def _extraer_error_form(form):
    """Devuelve el primer mensaje de validación legible de un formulario de Django."""
    for errores in form.errors.values():
        if errores:
            return errores[0]
    return 'Datos de entrada inválidos.'


def _extraer_error_validacion(error_val):
    """Extrae el texto principal de una excepción `ValidationError`."""
    if hasattr(error_val, 'messages') and error_val.messages:
        return error_val.messages[0]
    return str(error_val)


@ensure_csrf_cookie
def gestion_cercos(request):
    """Renderiza la interfaz principal de pantalla dividida (`cercos/mapa.html`)."""
    return render(request, 'cercos/mapa.html')


# ==============================================================================
# 1. ENDPOINTS DE CERCOS VIRTUALES (RF_1, RF_2, RF_8)
# ==============================================================================

@require_http_methods(["GET"])
def obtener_cercos(request):
    """
    Consulta los cercos en PostGIS y los serializa en estándar GeoJSON (`FeatureCollection`).
    En Modo Real (`?modo=real`) excluye los lotes de demostración.
    """
    modo = request.GET.get('modo', 'real')
    queryset_cercos = CercoVirtual.objects.prefetch_related('animales').all()

    if modo == 'real':
        queryset_cercos = queryset_cercos.exclude(nombre__in=NOMBRES_CERCOS_DEMO)

    elementos = []
    for cerco in queryset_cercos:
        animales_lote = list(cerco.animales.all())
        elementos.append({
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
                'fecha_creacion': timezone.localtime(cerco.fecha_creacion).strftime("%d/%m/%Y")
            },
            'geometry': json.loads(cerco.perimetro.geojson)
        })

    return JsonResponse({'type': 'FeatureCollection', 'features': elementos})


@require_http_methods(["POST"])
def crear_cerco(request):
    """Implementa `CU_01 (Crear Cerco Virtual - RF_1)`."""
    datos, error_resp = _decodificar_json(request)
    if error_resp:
        return error_resp

    form = CercoVirtualForm(data={
        'nombre': datos.get('nombre', ''),
        'color': datos.get('color', '#2ecc71'),
        'alerta_continua': bool(datos.get('alerta_continua', False)),
    })
    if not form.is_valid():
        return JsonResponse({'estado': 'error', 'mensaje': _extraer_error_form(form)}, status=400)

    try:
        geometria = validar_geometria_poligono(datos.get('geometria'))
        with transaction.atomic():
            nuevo_cerco = CercoVirtual.objects.create(
                nombre=form.cleaned_data['nombre'],
                color=form.cleaned_data['color'],
                alerta_continua=form.cleaned_data['alerta_continua'],
                perimetro=geometria,
                usuario=request.user if request.user.is_authenticated else None
            )
        return JsonResponse({
            'estado': 'exito',
            'id': nuevo_cerco.id,
            'area_hectareas': nuevo_cerco.area_hectareas,
            'mensaje': 'Cerco virtual guardado correctamente.'
        })
    except ValidationError as error_val:
        return JsonResponse({'estado': 'error', 'mensaje': _extraer_error_validacion(error_val)}, status=400)
    except Exception:
        return JsonResponse({'estado': 'error', 'mensaje': 'Error interno al guardar el cerco.'}, status=500)


@require_http_methods(["POST"])
def editar_cerco(request, id_cerco):
    """Implementa `CU_02 (Modificar Cerco Virtual - RF_2)`."""
    try:
        cerco = CercoVirtual.objects.get(pk=id_cerco)
    except CercoVirtual.DoesNotExist:
        return JsonResponse({
            'estado': 'error',
            'codigo': 'no_encontrado',
            'mensaje': 'El cerco seleccionado ya no existe en el sistema.'
        }, status=404)

    datos, error_resp = _decodificar_json(request)
    if error_resp:
        return error_resp

    form = CercoVirtualForm(data={
        'nombre': datos.get('nombre', cerco.nombre),
        'color': datos.get('color') or cerco.color,
        'alerta_continua': datos.get('alerta_continua', cerco.alerta_continua),
    }, instance=cerco)
    if not form.is_valid():
        return JsonResponse({'estado': 'error', 'mensaje': _extraer_error_form(form)}, status=400)

    try:
        datos_geometria = datos.get('geometria')
        with transaction.atomic():
            cerco.nombre = form.cleaned_data['nombre']
            cerco.color = form.cleaned_data['color']
            cerco.alerta_continua = form.cleaned_data['alerta_continua']
            if datos_geometria:
                cerco.perimetro = validar_geometria_poligono(datos_geometria)
            cerco.save()
            alertas_nuevas = reevaluar_animales_de_cerco(cerco)

        return JsonResponse({
            'estado': 'exito',
            'alertas_generadas': alertas_nuevas,
            'mensaje': 'Cerco virtual modificado correctamente.'
        })
    except ValidationError as error_val:
        return JsonResponse({'estado': 'error', 'mensaje': _extraer_error_validacion(error_val)}, status=400)
    except Exception:
        return JsonResponse({'estado': 'error', 'mensaje': 'Error interno al actualizar el cerco.'}, status=500)


@require_http_methods(["POST"])
def eliminar_cerco(request, id_cerco):
    """Implementa `CU_03 (Eliminar Cerco Virtual - RF_8)`."""
    try:
        cerco = CercoVirtual.objects.get(pk=id_cerco)
        eliminar_cerco_seguro(cerco)
        return JsonResponse({
            'estado': 'exito',
            'mensaje': 'Cerco virtual eliminado correctamente. Los animales vinculados quedaron sin cerco asignado.'
        })
    except CercoVirtual.DoesNotExist:
        return JsonResponse({'estado': 'error', 'mensaje': 'El cerco seleccionado ya no existe.'}, status=404)
    except Exception:
        return JsonResponse({'estado': 'error', 'mensaje': 'Error interno al eliminar el cerco.'}, status=500)


# ==============================================================================
# 2. ENDPOINTS DE GANADO Y PERTENENCIA A CERCOS (RF-08, RF-09, RF-10)
# ==============================================================================

@require_http_methods(["GET"])
def obtener_animales(request):
    """
    Retorna el padrón de animales monitoreados con su estado y coordenadas.
    Si el cliente opera en Modo Real (`?modo=real`), limpia cualquier dato
    remanente de la Demo y sincroniza en memoria las lecturas de Node-RED.
    """
    modo = request.GET.get('modo', 'real')
    queryset_animales = Animal.objects.select_related('cerco').all()

    if modo == 'real':
        limpiar_escenario_demo_catamarca()
        queryset_animales = queryset_animales.exclude(id_hardware__in=IDS_ANIMALES_DEMO)

    lista_animales = list(queryset_animales)
    alertas_detectadas = sincronizar_lecturas_externas_nodered(lista_animales)

    return JsonResponse({
        'estado': 'exito',
        'alertas_nuevas': alertas_detectadas,
        'animales': [serializar_animal(a) for a in lista_animales]
    })


@require_http_methods(["POST"])
def crear_animal(request):
    """Da de alta un animal con su collar `id_hardware`."""
    datos, error_resp = _decodificar_json(request)
    if error_resp:
        return error_resp

    form = AnimalForm(data=datos)
    if not form.is_valid():
        return JsonResponse({'estado': 'error', 'mensaje': _extraer_error_form(form)}, status=400)

    try:
        with transaction.atomic():
            cerco_id = datos.get('cerco_id')
            cerco_obj = None
            if cerco_id:
                try:
                    cerco_obj = CercoVirtual.objects.get(pk=cerco_id)
                except CercoVirtual.DoesNotExist:
                    return JsonResponse({'estado': 'error', 'mensaje': 'El cerco seleccionado no existe.'}, status=404)

            animal = Animal.objects.create(
                id_hardware=form.cleaned_data['id_hardware'],
                nombre=form.cleaned_data['nombre'],
                especie=form.cleaned_data.get('especie') or 'Bovino',
                cerco=cerco_obj
            )

            lat = form.cleaned_data.get('latitud')
            lng = form.cleaned_data.get('longitud')
            alerta_generada = None

            if lat is not None and lng is not None:
                res = evaluar_y_registrar_fuga(animal, Point(lng, lat, srid=4326))
                if res.get('alerta_emitida'):
                    alerta_generada = res.get('alerta')
            elif cerco_obj:
                centro = cerco_obj.perimetro.centroid
                evaluar_y_registrar_fuga(animal, Point(centro.x, centro.y, srid=4326))

        return JsonResponse({
            'estado': 'exito',
            'animal': serializar_animal(animal),
            'alerta': alerta_generada,
            'mensaje': f'Animal {animal.id_hardware} registrado correctamente.'
        })
    except Exception:
        return JsonResponse({'estado': 'error', 'mensaje': 'Error al registrar el animal.'}, status=500)


@require_http_methods(["POST"])
def asignar_cerco_animal(request, id_animal):
    """Implementa `CU_07 (Asignar Animal - RF-08)` y `CU_08 (Modificar Pertenencia - RF-09)`."""
    try:
        animal = Animal.objects.select_related('cerco').get(pk=id_animal)
    except Animal.DoesNotExist:
        return JsonResponse({'estado': 'error', 'mensaje': 'El animal seleccionado no existe.'}, status=404)

    datos, error_resp = _decodificar_json(request)
    if error_resp:
        return error_resp

    cerco_id = datos.get('cerco_id')
    if not cerco_id:
        return JsonResponse({'estado': 'error', 'mensaje': 'Debe seleccionar un cerco virtual destino.'}, status=400)

    try:
        nuevo_cerco = CercoVirtual.objects.get(pk=cerco_id)
    except CercoVirtual.DoesNotExist:
        return JsonResponse({
            'estado': 'error',
            'codigo': 'cerco_no_disponible',
            'mensaje': 'El cerco seleccionado ya no está disponible.'
        }, status=404)

    try:
        tenia_cerco_previo = animal.cerco_id is not None
        resultado = asignar_animal_a_cerco(animal, nuevo_cerco, validar_cambio=tenia_cerco_previo)
        accion = 'reasignado' if tenia_cerco_previo else 'asignado'
        return JsonResponse({
            'estado': 'exito',
            'animal': serializar_animal(animal),
            'alerta': resultado.get('alerta') if resultado and resultado.get('alerta_emitida') else None,
            'mensaje': f'Animal {animal.id_hardware} {accion} al cerco «{nuevo_cerco.nombre}».'
        })
    except ValidationError as error_val:
        return JsonResponse({'estado': 'error', 'mensaje': _extraer_error_validacion(error_val)}, status=400)


@require_http_methods(["POST"])
def desvincular_cerco_animal(request, id_animal):
    """Implementa `CU_09 (Desvincular de Cerco - RF-10)`."""
    try:
        animal = Animal.objects.select_related('cerco').get(pk=id_animal)
    except Animal.DoesNotExist:
        return JsonResponse({'estado': 'error', 'mensaje': 'El animal seleccionado no existe.'}, status=404)

    try:
        nombre_cerco_anterior = animal.cerco.nombre if animal.cerco else ''
        desvincular_animal_de_cerco(animal)
        return JsonResponse({
            'estado': 'exito',
            'animal': serializar_animal(animal),
            'mensaje': f'Animal {animal.id_hardware} desvinculado del cerco «{nombre_cerco_anterior}».'
        })
    except ValidationError as error_val:
        return JsonResponse({'estado': 'error', 'mensaje': _extraer_error_validacion(error_val)}, status=400)


@require_http_methods(["POST"])
def eliminar_animal(request, id_animal):
    """Permite dar de baja un animal registrado."""
    try:
        animal = Animal.objects.get(pk=id_animal)
        identificador = animal.id_hardware
        animal.delete()
        return JsonResponse({'estado': 'exito', 'mensaje': f'Animal {identificador} eliminado del sistema.'})
    except Animal.DoesNotExist:
        return JsonResponse({'estado': 'error', 'mensaje': 'El animal no existe.'}, status=404)


# ==============================================================================
# 3. ENDPOINTS DE TELEMETRÍA GPS, ALERTAS Y DEMO (RF_3 A RF_7)
# ==============================================================================

@require_http_methods(["POST"])
def procesar_telemetria(request):
    """Implementa `CU_05 (Procesar Ubicación - RF_3, RF_4)` y `CU_06 (Emitir Alerta - RF_5)`."""
    datos, error_resp = _decodificar_json(request)
    if error_resp:
        return error_resp

    form = TelemetriaGPSForm(data=datos)
    if not form.is_valid():
        return JsonResponse({'estado': 'error', 'mensaje': _extraer_error_form(form)}, status=400)

    id_hw = form.cleaned_data.get('id_hardware')
    animal_id = form.cleaned_data.get('animal_id')
    latitud = form.cleaned_data['latitud']
    longitud = form.cleaned_data['longitud']

    try:
        if animal_id:
            animal = Animal.objects.select_related('cerco').get(pk=animal_id)
        else:
            animal = Animal.objects.select_related('cerco').get(id_hardware__iexact=id_hw)
    except Animal.DoesNotExist:
        return JsonResponse({
            'estado': 'error',
            'codigo': 'collar_no_registrado',
            'mensaje': 'El collar o animal indicado no se encuentra registrado en el sistema.'
        }, status=404)

    # En PostGIS/GEOS Point recibe primero X=Longitud y luego Y=Latitud
    resultado = evaluar_y_registrar_fuga(animal, Point(longitud, latitud, srid=4326))

    return JsonResponse({
        'estado': 'exito',
        'animal': serializar_animal(animal),
        'dentro_del_cerco': resultado['dentro_del_cerco'],
        'sin_cerco_asignado': resultado.get('sin_cerco_asignado', False),
        'alerta_emitida': resultado['alerta_emitida'],
        'suprimida_por_antispam': resultado.get('suprimida_por_antispam', False),
        'alerta': resultado.get('alerta'),
        'mensaje': (
            resultado['alerta']['mensaje']
            if resultado.get('alerta_emitida') and resultado.get('alerta')
            else f'Posición de {animal.id_hardware} actualizada correctamente.'
        )
    })


@require_http_methods(["GET"])
def obtener_alertas(request):
    """Implementa `CU_04 (Ver Animales Prófugos - RF_6, RF_7)`."""
    modo = request.GET.get('modo', 'real')
    animales_profugos = Animal.objects.select_related('cerco').filter(estado_fuga=True)
    alertas_activas = AlertaFuga.objects.select_related('animal', 'cerco').filter(resuelta=False)

    if modo == 'real':
        animales_profugos = animales_profugos.exclude(id_hardware__in=IDS_ANIMALES_DEMO)
        alertas_activas = alertas_activas.exclude(animal__id_hardware__in=IDS_ANIMALES_DEMO)

    lista_profugos = [serializar_animal(a) for a in animales_profugos]
    return JsonResponse({
        'estado': 'exito',
        'total_profugos': len(lista_profugos),
        'animales_profugos': lista_profugos,
        'alertas_activas': [serializar_alerta(al) for al in alertas_activas[:30]],
    })


@require_http_methods(["POST"])
def resolver_alerta(request, id_alerta):
    """Permite marcar una alerta de la bitácora como revisada/resuelta."""
    try:
        alerta = AlertaFuga.objects.select_related('animal').get(pk=id_alerta)
        alerta.resuelta = True
        alerta.fecha_resolucion = timezone.now()
        alerta.save(update_fields=['resuelta', 'fecha_resolucion'])
        return JsonResponse({'estado': 'exito', 'mensaje': 'Incidente marcado como revisado.'})
    except AlertaFuga.DoesNotExist:
        return JsonResponse({'estado': 'error', 'mensaje': 'La alerta indicada no existe.'}, status=404)


@require_http_methods(["POST"])
def cargar_demo(request):
    """Puebla el escenario de demostración alrededor de la ubicación base actual."""
    datos, _ = _decodificar_json(request)
    datos = datos or {}

    usuario = request.user if request.user.is_authenticated else None
    resumen = cargar_escenario_demo_catamarca(
        usuario=usuario,
        lat_base=datos.get('latitud'),
        lng_base=datos.get('longitud')
    )
    return JsonResponse({
        'estado': 'exito',
        'resumen': resumen,
        'mensaje': 'Escenario de demostración cargado: 2 lotes y 4 animales monitoreados.'
    })


@require_http_methods(["POST"])
def limpiar_demo(request):
    """Elimina exclusivamente los datos de prueba de la demo sin afectar registros reales."""
    resumen = limpiar_escenario_demo_catamarca()
    return JsonResponse({
        'estado': 'exito',
        'resumen': resumen,
        'mensaje': 'Datos de demostración eliminados correctamente de la base de datos.'
    })
