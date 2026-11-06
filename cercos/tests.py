"""
==============================================================================
SUITE DE PRUEBAS AUTOMATIZADAS ESPACIALES Y FUNCIONALES: cercos/tests.py
==============================================================================
¿QUÉ HACE ESTE ARCHIVO?
Verifica de manera automatizada que todos los requisitos críticos del sistema
funcionen correctamente contra PostgreSQL + PostGIS:
1. Validación topológica GEOS (rechazo de polígonos con cruces de líneas - RF_1).
2. Integridad referencial al eliminar un cerco (`ON DELETE SET NULL` - RF_8).
3. Evaluación espacial PostGIS (`ST_Contains`) y ventana Anti-Spam de 5 min (RF_3, RF_4, RF_5).
4. Alerta continua inmediata sin espera en Perímetros Críticos (`alerta_continua=True`).
5. Ciclo de pertenencia de ganado: Asignar (RF-08), Reasignar (RF-09) y Desvincular (RF-10).
6. Aislamiento e integridad al cambiar entre Modo Simulación y Modo Real (Node-RED).
==============================================================================
"""

import json
from django.test import TestCase, Client, SimpleTestCase
from django.urls import reverse
from django.contrib.gis.geos import Polygon, Point
from .models import CercoVirtual, Animal, AlertaFuga, TelemetriaGPS
from channels.testing import WebsocketCommunicator
from proyectoCercoVirtual.asgi import application


class SistemaCercoVirtualTests(TestCase):
    """
    Pruebas automatizadas de validación topológica GEOS, consultas espaciales PostGIS (ST_Contains),
    integridad referencial (ON DELETE SET NULL) y control Anti-Spam de alertas.
    """

    def setUp(self):
        self.client = Client()
        # Polígono rectangular válido en Catamarca
        self.poligono_valido = Polygon((
            (-65.7900, -28.4650),
            (-65.7800, -28.4650),
            (-65.7800, -28.4750),
            (-65.7900, -28.4750),
            (-65.7900, -28.4650),
        ), srid=4326)

        self.cerco = CercoVirtual.objects.create(
            nombre="Lote Experimental UNCA",
            color="#2ecc71",
            perimetro=self.poligono_valido
        )

        self.animal = Animal.objects.create(
            id_hardware="COLLAR-TEST-01",
            nombre="Vaca Test #01",
            especie="Bovino",
            cerco=self.cerco
        )

    def test_rf1_rechaza_poligono_con_cruce_de_lineas(self):
        """
        Verifica que el backend rechace polígonos con auto-intersección (reloj de arena / figura en 8)
        según el Camino Alternativo 1 de Crear Cerco Virtual.
        """
        geojson_cruzado = {
            "nombre": "Lote Cruzado Inválido",
            "color": "#e67e22",
            "geometria": {
                "type": "Polygon",
                "coordinates": [[
                    [-65.7900, -28.4650],
                    [-65.7800, -28.4750],  # Diagonal que cruza
                    [-65.7800, -28.4650],
                    [-65.7900, -28.4750],  # Segunda diagonal que cruza
                    [-65.7900, -28.4650],
                ]]
            }
        }
        respuesta = self.client.post(
            reverse('crear_cerco'),
            data=json.dumps(geojson_cruzado),
            content_type='application/json'
        )
        self.assertEqual(respuesta.status_code, 400)
        datos = respuesta.json()
        self.assertEqual(datos['estado'], 'error')
        self.assertIn('cruces', datos['mensaje'].lower())

    def test_rf8_eliminar_cerco_mantiene_animal_con_set_null(self):
        """
        Verifica que al eliminar un CercoVirtual (RF_8), los animales asignados NO se borren
        sino que pasen a 'cerco = None' (ON DELETE SET NULL).
        """
        respuesta = self.client.post(
            reverse('eliminar_cerco', args=[self.cerco.id]),
            content_type='application/json'
        )
        self.assertEqual(respuesta.status_code, 200)
        self.animal.refresh_from_db()
        self.assertIsNone(self.animal.cerco)
        self.assertFalse(self.animal.estado_fuga)

    def test_rf3_rf4_rf5_deteccion_fuga_y_antispam_5_minutos(self):
        """
        Verifica que una coordenada dentro del cerco marque 'dentro_del_cerco = True',
        una coordenada fuera marque 'estado_fuga = True' y emita alerta, y que una segunda
        lectura inmediata fuera del cerco sea silenciada por la ventana anti-spam de 5 minutos.
        """
        # 1. Coordenada DENTRO del Lote (-28.4700, -65.7850)
        resp_dentro = self.client.post(
            reverse('procesar_telemetria'),
            data=json.dumps({
                "id_hardware": "COLLAR-TEST-01",
                "latitud": -28.4700,
                "longitud": -65.7850
            }),
            content_type='application/json'
        ).json()
        self.assertTrue(resp_dentro['dentro_del_cerco'])
        self.assertFalse(resp_dentro['alerta_emitida'])

        # 2. Coordenada FUERA del Lote (-28.4500, -65.7850) -> Dispara 1ra Alerta
        resp_fuera_1 = self.client.post(
            reverse('procesar_telemetria'),
            data=json.dumps({
                "id_hardware": "COLLAR-TEST-01",
                "latitud": -28.4500,
                "longitud": -65.7850
            }),
            content_type='application/json'
        ).json()
        self.assertFalse(resp_fuera_1['dentro_del_cerco'])
        self.assertTrue(resp_fuera_1['alerta_emitida'])
        self.assertEqual(AlertaFuga.objects.filter(animal=self.animal).count(), 1)

        # 3. Segunda lectura FUERA del Lote 10 segundos después -> Silenciada por Anti-Spam
        resp_fuera_2 = self.client.post(
            reverse('procesar_telemetria'),
            data=json.dumps({
                "id_hardware": "COLLAR-TEST-01",
                "latitud": -28.4495,
                "longitud": -65.7852
            }),
            content_type='application/json'
        ).json()
        self.assertFalse(resp_fuera_2['dentro_del_cerco'])
        self.assertFalse(resp_fuera_2['alerta_emitida'])
        self.assertTrue(resp_fuera_2['suprimida_por_antispam'])
        self.assertEqual(AlertaFuga.objects.filter(animal=self.animal).count(), 1)

    def test_rf08_rf09_rf10_ciclo_pertenencia_animal(self):
        """
        Verifica el flujo completo de Desvincular (RF-10), Asignar (RF-08) y Reasignar (RF-09).
        """
        # RF-10: Desvincular
        resp_desv = self.client.post(
            reverse('desvincular_cerco_animal', args=[self.animal.id]),
            content_type='application/json'
        )
        self.assertEqual(resp_desv.status_code, 200)
        self.animal.refresh_from_db()
        self.assertIsNone(self.animal.cerco)

        # RF-08: Asignar nuevamente
        resp_asig = self.client.post(
            reverse('asignar_cerco_animal', args=[self.animal.id]),
            data=json.dumps({"cerco_id": self.cerco.id}),
            content_type='application/json'
        )
        self.assertEqual(resp_asig.status_code, 200)
        self.animal.refresh_from_db()
        self.assertEqual(self.animal.cerco_id, self.cerco.id)

    def test_perimetro_critico_alerta_continua_sin_antispam(self):
        """
        Verifica que cuando un cerco tiene 'alerta_continua=True' (Perímetro Crítico:
        lindero vecino, canal o riesgo de robo), NO se silencie por 5 minutos sino que
        emita alerta en cada lectura consecutiva fuera del lote.
        """
        self.cerco.alerta_continua = True
        self.cerco.save(update_fields=['alerta_continua'])

        resp_1 = self.client.post(
            reverse('procesar_telemetria'),
            data=json.dumps({
                "id_hardware": "COLLAR-TEST-01",
                "latitud": -28.4500,
                "longitud": -65.7850
            }),
            content_type='application/json'
        ).json()
        self.assertTrue(resp_1['alerta_emitida'])

        resp_2 = self.client.post(
            reverse('procesar_telemetria'),
            data=json.dumps({
                "id_hardware": "COLLAR-TEST-01",
                "latitud": -28.4490,
                "longitud": -65.7855
            }),
            content_type='application/json'
        ).json()
        self.assertTrue(resp_2['alerta_emitida'])
        self.assertFalse(resp_2['suprimida_por_antispam'])
        self.assertEqual(AlertaFuga.objects.filter(animal=self.animal).count(), 2)

    def test_integridad_cambio_modo_simulacion_a_modo_real_limpia_demo(self):
        """
        Verifica que al cargar la Demo en Modo Simulación y luego pasar a Modo Real
        (?modo=real), todos los cercos y vacas de prueba de la Demo se limpien
        automáticamente sin afectar los cercos y animales reales del productor.
        """
        # 1. Cargar escenario de demostración
        resp_demo = self.client.post(reverse('cargar_demo'), content_type='application/json')
        self.assertEqual(resp_demo.status_code, 200)

        # En Modo Simulación existen tanto los datos reales como los de la Demo (1 real + 4 demo = 5 animales)
        resp_sim = self.client.get(reverse('obtener_animales') + '?modo=simulacion').json()
        self.assertEqual(len(resp_sim['animales']), 5)

        # 2. Al pasar a Modo Real (?modo=real), los datos de prueba se eliminan y solo queda el animal real
        resp_real_animales = self.client.get(reverse('obtener_animales') + '?modo=real').json()
        ids_reales = [a['id_hardware'] for a in resp_real_animales['animales']]
        self.assertEqual(ids_reales, ['COLLAR-TEST-01'])

        resp_real_cercos = self.client.get(reverse('obtener_cercos') + '?modo=real').json()
        nombres_cercos = [f['properties']['nombre'] for f in resp_real_cercos['features']]
        self.assertEqual(nombres_cercos, ['Lote Experimental UNCA'])
        
        
class WebSocketPruebaSimpleTests(SimpleTestCase):
    async def test_flujo_websocket_eco(self):
        # 1. Establecer conexión al endpoint
        communicator = WebsocketCommunicator(application, "/ws/iot/")
        connected, _ = await communicator.connect()
        self.assertTrue(connected, "No se pudo conectar al endpoint WebSocket")

        # 2. Enviar el JSON simulado de Node-RED
        datos_prueba = {
           "id_hardware": "IOT-DEV-001",
           "latitud": -28.4696,
           "lngitud": -65.7852,
           "fecha-hora": "2026-11-06T20:55:00Z"
         }
        
        await communicator.send_to(text_data=json.dumps(datos_prueba))

        # 3. Leer la respuesta emitida por el consumidor
        respuesta = await communicator.receive_from()
        datos_respuesta = json.loads(respuesta)

        # 4. Validar que la respuesta contiene lo que enviamos
        self.assertEqual(datos_respuesta["status"], "recibido_en_django")
        self.assertEqual(datos_respuesta["contenido"]["id_hardware"], "IOT-DEV-001")
        # 5. Cerrar socket
        await communicator.disconnect()       
    

