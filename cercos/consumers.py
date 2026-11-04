import json
from channels.generic.websocket import AsyncWebsocketConsumer

class TelemetriaConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_group_name = 'telemetria_group'

        # Unir esta conexión al grupo
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()
        print(">>> [WebSocket] Cliente conectado exitosamente.")

    async def disconnect(self, close_code):
        # Salir del grupo
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        print(f">>> [WebSocket] Cliente desconectado (Código: {close_code}).")

    async def receive(self, text_data=None, bytes_data=None):
        """
        Recibe el dato enviado por Node-RED o cualquier cliente,
        lo imprime en la terminal y lo retransmite en eco.
        """
        if not text_data:
            return

        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            print(">>> [WebSocket] Error: Dato recibido no es un JSON válido.")
            await self.send(text_data=json.dumps({"error": "Formato JSON no válido"}))
            return

        # Imprimimos en la consola de Django lo que llegó desde Node-RED
        print(f">>> [WebSocket] Mensaje recibido desde Node-RED: {payload}")

        # Retransmitir al grupo para comprobar que el canal de salida funciona
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'broadcast_telemetria',
                'data': payload
            }
        )

    async def broadcast_telemetria(self, event):
        # Envía el dato de vuelta por el socket
        await self.send(text_data=json.dumps({
            "status": "recibido_en_django",
            "contenido": event['data']
        }))