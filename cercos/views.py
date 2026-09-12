import json
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.gis.geos import GEOSGeometry
from .models import CercoVirtual

@ensure_csrf_cookie
def gestion_cercos(request):
    """Muestra la interfaz principal de gestión y delimitación de cercos."""
    return render(request, 'cercos/mapa.html')

def obtener_cercos(request):
    """Consulta la base de datos y entrega los cercos en formato GeoJSON para el mapa."""
    cercos_registrados = CercoVirtual.objects.all()
    elementos = []
    
    for cerco in cercos_registrados:
        geometria_geojson = json.loads(cerco.perimetro.geojson)
        elementos.append({
            'type': 'Feature',
            'id': cerco.id,
            'properties': {
                'id': cerco.id,
                'nombre': cerco.nombre,
                'color': cerco.color,
                'fecha_creacion': cerco.fecha_creacion.strftime("%d/%m/%Y")
            },
            'geometry': geometria_geojson
        })
        
    return JsonResponse({
        'type': 'FeatureCollection',
        'features': elementos
    })

@require_http_methods(["POST"])
def crear_cerco(request):
    """Recibe los vértices trazados desde el mapa y los guarda en PostGIS (RF_1)."""
    try:
        datos = json.loads(request.body)
        nombre = datos.get('nombre', '').strip()
        color = datos.get('color', '#2ecc71')
        datos_geometria = datos.get('geometria')

        if not nombre:
            return JsonResponse({'estado': 'error', 'mensaje': 'Debe ingresar un nombre para el lote.'}, status=400)
        if not datos_geometria:
            return JsonResponse({'estado': 'error', 'mensaje': 'No se recibieron coordenadas para el perímetro.'}, status=400)

        # Conversión del GeoJSON a objeto geométrico de GeoDjango (SRID 4326)
        geometria = GEOSGeometry(json.dumps(datos_geometria))
        
        if geometria.geom_type != 'Polygon':
            return JsonResponse({'estado': 'error', 'mensaje': 'La figura debe ser un polígono cerrado.'}, status=400)

        nuevo_cerco = CercoVirtual.objects.create(
            nombre=nombre,
            color=color,
            perimetro=geometria,
            usuario=request.user if request.user.is_authenticated else None
        )
        return JsonResponse({'estado': 'exito', 'id': nuevo_cerco.id, 'mensaje': 'Cerco virtual guardado correctamente.'})
    except Exception as error:
        return JsonResponse({'estado': 'error', 'mensaje': str(error)}, status=500)

@require_http_methods(["POST"])
def editar_cerco(request, id_cerco):
    """Actualiza vértices o nombre de un cerco existente (RF_2)."""
    try:
        cerco = CercoVirtual.objects.get(pk=id_cerco)
        datos = json.loads(request.body)
        
        nombre = datos.get('nombre', '').strip()
        color = datos.get('color')
        datos_geometria = datos.get('geometria')

        if nombre:
            cerco.nombre = nombre
        if color:
            cerco.color = color
        if datos_geometria:
            geometria = GEOSGeometry(json.dumps(datos_geometria))
            if geometria.geom_type == 'Polygon':
                cerco.perimetro = geometria

        cerco.save()
        return JsonResponse({'estado': 'exito', 'mensaje': 'Cerco virtual modificado correctamente.'})
    except CercoVirtual.DoesNotExist:
        return JsonResponse({'estado': 'error', 'mensaje': 'El cerco seleccionado no existe en el sistema.'}, status=404)
    except Exception as error:
        return JsonResponse({'estado': 'error', 'mensaje': str(error)}, status=500)

@require_http_methods(["POST"])
def eliminar_cerco(request, id_cerco):
    """Elimina de forma permanente un cerco virtual (RF_8)."""
    try:
        cerco = CercoVirtual.objects.get(pk=id_cerco)
        cerco.delete()
        return JsonResponse({'estado': 'exito', 'mensaje': 'Cerco virtual eliminado correctamente.'})
    except CercoVirtual.DoesNotExist:
        return JsonResponse({'estado': 'error', 'mensaje': 'El cerco no existe.'}, status=404)
    except Exception as error:
        return JsonResponse({'estado': 'error', 'mensaje': str(error)}, status=500)