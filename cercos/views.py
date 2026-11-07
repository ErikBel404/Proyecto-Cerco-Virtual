"""
==============================================================================
CAPA DE VISTAS Y ENDPOINTS HTTP / GEOJSON: cercos/views.py
==============================================================================
Controlador HTTP liviano entre el navegador/IoT y `services.py`.
Cada vista solo decodifica el JSON, valida con `forms.py` y delega en `services.py`.
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
from .models import Lectura, CercoVirtual, Animal, AlertaFuga
from .services import (
    validar_geometria_poligono,
    reevaluar_animales_de_cerco,
    eliminar_cerco_seguro,
    asignar_animal_a_cerco,
    desvincular_animal_de_cerco,
    evaluar_y_registrar_fuga,
    serializar_cerco_geojson,
    serializar_animal,
    serializar_alerta,
    cargar_escenario_demo_catamarca,
    limpiar_escenario_demo_catamarca,
    sincronizar_lecturas_externas_nodered,
    IDS_ANIMALES_DEMO,
    NOMBRES_CERCOS_DEMO,
)


# ==============================================================================
# UTILIDADES INTERNAS CORTAS
# ==============================================================================

def _decodificar_json(request):
    """Decodifica el cuerpo JSON de una petición POST."""
    try:
        return json.loads(request.body or b'{}'), None
    except json.JSONDecodeError:
        return None, JsonResponse({'estado': 'error', 'mensaje': 'JSON inválido.'}, status=400)


def _extraer_error_form(form):
    """Devuelve el primer mensaje de error de un formulario."""
    for errores in form.errors.values():
        if errores:
            return errores[0]
    return 'Datos de entrada inválidos.'


def _extraer_error_validacion(error_val):
    """Extrae el texto principal de un `ValidationError`."""
    if hasattr(error_val, 'messages') and error_val.messages:
        return error_val.messages[0]
    return str(error_val)


def _ubicar_animal_recien_creado(animal, form, cerco_obj):
    """Ubica al animal recién creado en las coordenadas indicadas o en el centro de su lote."""
    lat = form.cleaned_data.get('latitud')
    lng = form.cleaned_data.get('longitud')
    if lat is not None and lng is not None:
        res = evaluar_y_registrar_fuga(animal, Point(lng, lat, srid=4326))
        return res.get('alerta') if res.get('alerta_emitida') else None

    if cerco_obj:
        centro = cerco_obj.perimetro.centroid
        evaluar_y_registrar_fuga(animal, Point(centro.x, centro.y, srid=4326))
    return None


def _buscar_animal_por_id_o_collar(animal_id, id_hw):
    """Busca un animal por su ID numérico o por su `id_hardware`."""
    if animal_id:
        return Animal.objects.select_related('cerco').get(pk=animal_id)
    return Animal.objects.select_related('cerco').get(id_hardware__iexact=id_hw)


@ensure_csrf_cookie
def gestion_cercos(request):
    """Renderiza la interfaz principal (`cercos/mapa.html`)."""
    return render(request, 'cercos/mapa.html')


# ==============================================================================
# 1. ENDPOINTS DE CERCOS VIRTUALES (RF_1, RF_2, RF_8)
# ==============================================================================

@require_http_methods(["GET"])
def obtener_cercos(request):
    """Devuelve los cercos en formato GeoJSON (`FeatureCollection`)."""
    modo = request.GET.get('modo', 'real')
    cercos = CercoVirtual.objects.prefetch_related('animales').all()
    if modo == 'real':
        cercos = cercos.exclude(nombre__in=NOMBRES_CERCOS_DEMO)

    return JsonResponse({
        'type': 'FeatureCollection',
        'features': [serializar_cerco_geojson(c) for c in cercos],
    })


@require_http_methods(["POST"])
def crear_cerco(request):
    """Crea un nuevo cerco virtual (`RF_1`)."""
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
                usuario=request.user if request.user.is_authenticated else None,
            )
        return JsonResponse({
            'estado': 'exito',
            'id': nuevo_cerco.id,
            'area_hectareas': nuevo_cerco.area_hectareas,
            'mensaje': 'Cerco virtual guardado correctamente.',
        })
    except ValidationError as error_val:
        return JsonResponse({'estado': 'error', 'mensaje': _extraer_error_validacion(error_val)}, status=400)
    except Exception:
        return JsonResponse({'estado': 'error', 'mensaje': 'Error interno al guardar el cerco.'}, status=500)


@require_http_methods(["POST"])
def editar_cerco(request, id_cerco):
    """Modifica un cerco virtual y re-evalúa sus animales (`RF_2`)."""
    try:
        cerco = CercoVirtual.objects.get(pk=id_cerco)
    except CercoVirtual.DoesNotExist:
        return JsonResponse({'estado': 'error', 'codigo': 'no_encontrado', 'mensaje': 'El cerco ya no existe.'}, status=404)

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
        with transaction.atomic():
            cerco.nombre = form.cleaned_data['nombre']
            cerco.color = form.cleaned_data['color']
            cerco.alerta_continua = form.cleaned_data['alerta_continua']
            if datos.get('geometria'):
                cerco.perimetro = validar_geometria_poligono(datos['geometria'])
            cerco.save()
            alertas_nuevas = reevaluar_animales_de_cerco(cerco)

        return JsonResponse({
            'estado': 'exito',
            'alertas_generadas': alertas_nuevas,
            'mensaje': 'Cerco virtual modificado correctamente.',
        })
    except ValidationError as error_val:
        return JsonResponse({'estado': 'error', 'mensaje': _extraer_error_validacion(error_val)}, status=400)
    except Exception:
        return JsonResponse({'estado': 'error', 'mensaje': 'Error interno al actualizar el cerco.'}, status=500)


@require_http_methods(["POST"])
def eliminar_cerco(request, id_cerco):
    """Elimina un cerco virtual dejando sus animales sin cerco asignado (`RF_8`)."""
    try:
        cerco = CercoVirtual.objects.get(pk=id_cerco)
        eliminar_cerco_seguro(cerco)
        return JsonResponse({
            'estado': 'exito',
            'mensaje': 'Cerco eliminado correctamente. Los animales quedaron sin cerco asignado.',
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
    """Consume las lecturas nuevas de `Lectura` y retorna los animales actualizados."""
    modo = request.GET.get('modo', 'real')
    if modo == 'real':
        limpiar_escenario_demo_catamarca()

    alertas_detectadas = sincronizar_lecturas_externas_nodered()

    animales = Animal.objects.select_related('cerco').all()
    if modo == 'real':
        animales = animales.exclude(id_hardware__in=IDS_ANIMALES_DEMO)

    return JsonResponse({
        'estado': 'exito',
        'alertas_nuevas': alertas_detectadas,
        'animales': [serializar_animal(a) for a in animales],
    })


@require_http_methods(["POST"])
def crear_animal(request):
    """Registra un animal con su collar `id_hardware`."""
    datos, error_resp = _decodificar_json(request)
    if error_resp:
        return error_resp

    form = AnimalForm(data=datos)
    if not form.is_valid():
        return JsonResponse({'estado': 'error', 'mensaje': _extraer_error_form(form)}, status=400)

    cerco_obj = None
    if datos.get('cerco_id'):
        cerco_obj = CercoVirtual.objects.filter(pk=datos['cerco_id']).first()
        if not cerco_obj:
            return JsonResponse({'estado': 'error', 'mensaje': 'El cerco seleccionado no existe.'}, status=404)

    try:
        with transaction.atomic():
            animal = Animal.objects.create(
                id_hardware=form.cleaned_data['id_hardware'],
                nombre=form.cleaned_data['nombre'],
                especie=form.cleaned_data.get('especie') or 'Bovino',
                cerco=cerco_obj,
            )
            alerta = _ubicar_animal_recien_creado(animal, form, cerco_obj)

        return JsonResponse({
            'estado': 'exito',
            'animal': serializar_animal(animal),
            'alerta': alerta,
            'mensaje': f'Animal {animal.id_hardware} registrado correctamente.',
        })
    except Exception:
        return JsonResponse({'estado': 'error', 'mensaje': 'Error al registrar el animal.'}, status=500)


@require_http_methods(["POST"])
def asignar_cerco_animal(request, id_animal):
    """Asigna o cambia el cerco de un animal (`RF-08`, `RF-09`)."""
    animal = Animal.objects.select_related('cerco').filter(pk=id_animal).first()
    if not animal:
        return JsonResponse({'estado': 'error', 'mensaje': 'El animal seleccionado no existe.'}, status=404)

    datos, error_resp = _decodificar_json(request)
    if error_resp:
        return error_resp

    nuevo_cerco = CercoVirtual.objects.filter(pk=datos.get('cerco_id')).first()
    if not nuevo_cerco:
        return JsonResponse({'estado': 'error', 'codigo': 'cerco_no_disponible', 'mensaje': 'Cerco no disponible.'}, status=404)

    try:
        tenia_cerco = animal.cerco_id is not None
        res = asignar_animal_a_cerco(animal, nuevo_cerco, validar_cambio=tenia_cerco)
        accion = 'reasignado' if tenia_cerco else 'asignado'
        return JsonResponse({
            'estado': 'exito',
            'animal': serializar_animal(animal),
            'alerta': res.get('alerta') if res and res.get('alerta_emitida') else None,
            'mensaje': f'Animal {animal.id_hardware} {accion} al cerco «{nuevo_cerco.nombre}».',
        })
    except ValidationError as error_val:
        return JsonResponse({'estado': 'error', 'mensaje': _extraer_error_validacion(error_val)}, status=400)


@require_http_methods(["POST"])
def desvincular_cerco_animal(request, id_animal):
    """Quita la pertenencia de cerco de un animal (`RF-10`)."""
    animal = Animal.objects.select_related('cerco').filter(pk=id_animal).first()
    if not animal:
        return JsonResponse({'estado': 'error', 'mensaje': 'El animal seleccionado no existe.'}, status=404)

    try:
        nombre_anterior = animal.cerco.nombre if animal.cerco else ''
        desvincular_animal_de_cerco(animal)
        return JsonResponse({
            'estado': 'exito',
            'animal': serializar_animal(animal),
            'mensaje': f'Animal {animal.id_hardware} desvinculado del cerco «{nombre_anterior}».',
        })
    except ValidationError as error_val:
        return JsonResponse({'estado': 'error', 'mensaje': _extraer_error_validacion(error_val)}, status=400)


@require_http_methods(["POST"])
def eliminar_animal(request, id_animal):
    """Elimina un animal registrado."""
    animal = Animal.objects.filter(pk=id_animal).first()
    if not animal:
        return JsonResponse({'estado': 'error', 'mensaje': 'El animal no existe.'}, status=404)

    identificador = animal.id_hardware
    animal.delete()
    return JsonResponse({'estado': 'exito', 'mensaje': f'Animal {identificador} eliminado del sistema.'})


# ==============================================================================
# 3. ENDPOINTS DE TELEMETRÍA GPS, ALERTAS Y DEMO (RF_3 A RF_7)
# ==============================================================================

@require_http_methods(["POST"])
def procesar_telemetria(request):
    """Registra la coordenada en `Lectura` y la evalúa con `TelemetriaGPS` (`RF_3`, `RF_4`, `RF_5`)."""
    datos, error_resp = _decodificar_json(request)
    if error_resp:
        return error_resp

    form = TelemetriaGPSForm(data=datos)
    if not form.is_valid():
        return JsonResponse({'estado': 'error', 'mensaje': _extraer_error_form(form)}, status=400)

    try:
        animal = _buscar_animal_por_id_o_collar(
            form.cleaned_data.get('animal_id'),
            form.cleaned_data.get('id_hardware'),
        )
    except Animal.DoesNotExist:
        return JsonResponse({'estado': 'error', 'codigo': 'collar_no_registrado', 'mensaje': 'Collar no registrado.'}, status=404)

    lat = form.cleaned_data['latitud']
    lng = form.cleaned_data['longitud']
    lectura = Lectura.objects.create(id_hardware=animal.id_hardware, latitud=lat, longitud=lng, procesada=True)
    res = evaluar_y_registrar_fuga(animal, Point(lng, lat, srid=4326), momento=lectura.fecha_hora, lectura_origen=lectura)

    return JsonResponse({
        'estado': 'exito',
        'animal': serializar_animal(animal),
        'dentro_del_cerco': res['dentro_del_cerco'],
        'sin_cerco_asignado': res.get('sin_cerco_asignado', False),
        'alerta_emitida': res['alerta_emitida'],
        'suprimida_por_antispam': res.get('suprimida_por_antispam', False),
        'alerta': res.get('alerta'),
        'mensaje': res['alerta']['mensaje'] if res.get('alerta_emitida') and res.get('alerta') else f'Posición de {animal.id_hardware} actualizada.',
    })


@require_http_methods(["GET"])
def obtener_alertas(request):
    """Lista los animales prófugos y alertas activas (`RF_6`, `RF_7`)."""
    modo = request.GET.get('modo', 'real')
    profugos = Animal.objects.select_related('cerco').filter(estado_fuga=True)
    alertas = AlertaFuga.objects.select_related('animal', 'cerco').filter(resuelta=False)

    if modo == 'real':
        profugos = profugos.exclude(id_hardware__in=IDS_ANIMALES_DEMO)
        alertas = alertas.exclude(animal__id_hardware__in=IDS_ANIMALES_DEMO)

    lista_profugos = [serializar_animal(a) for a in profugos]
    return JsonResponse({
        'estado': 'exito',
        'total_profugos': len(lista_profugos),
        'animales_profugos': lista_profugos,
        'alertas_activas': [serializar_alerta(al) for al in alertas[:30]],
    })


@require_http_methods(["POST"])
def resolver_alerta(request, id_alerta):
    """Marca una alerta como revisada/resuelta."""
    alerta = AlertaFuga.objects.filter(pk=id_alerta).first()
    if not alerta:
        return JsonResponse({'estado': 'error', 'mensaje': 'La alerta indicada no existe.'}, status=404)

    alerta.resuelta = True
    alerta.fecha_resolucion = timezone.now()
    alerta.save(update_fields=['resuelta', 'fecha_resolucion'])
    return JsonResponse({'estado': 'exito', 'mensaje': 'Incidente marcado como revisado.'})


@require_http_methods(["POST"])
def cargar_demo(request):
    """Carga el escenario de demostración en Modo Simulación."""
    datos, _ = _decodificar_json(request)
    datos = datos or {}
    usuario = request.user if request.user.is_authenticated else None
    resumen = cargar_escenario_demo_catamarca(usuario=usuario, lat_base=datos.get('latitud'), lng_base=datos.get('longitud'))
    return JsonResponse({'estado': 'exito', 'resumen': resumen, 'mensaje': 'Escenario de demostración cargado.'})


@require_http_methods(["POST"])
def limpiar_demo(request):
    """Elimina los datos de prueba de la demostración."""
    resumen = limpiar_escenario_demo_catamarca()
    return JsonResponse({'estado': 'exito', 'resumen': resumen, 'mensaje': 'Datos de demostración eliminados.'})
