# Guía Paso a Paso: Conexión de Node-RED (PC de la Universidad) con Supabase (`tabla lectura`)

**Documento interno del equipo (Ingeniería / IoT Node-RED $\rightarrow$ Supabase $\rightarrow$ GeoDjango)**  
*(Separado de [`GUIA_SUPABASE_E_INTEGRACION.md`](GUIA_SUPABASE_E_INTEGRACION.md), la cual queda dedicada exclusivamente a los docentes y al otro grupo).*

---

## 1. Diagnóstico del Flujo Actual en la Rama `Development-bel`

En la rama `Development-bel` se encuentra el archivo `JSON-node-red/prototipo_1.0_websocket.json`, que tiene actualmente estos 3 nodos:

1. **`Disparar dato` (`inject`)**
2. **`Simular Telemetría` (`function`)** con este código:
   ```javascript
   msg.payload = {
       device_id: "IOT-DEV-001",
       timestamp: new Date().toISOString(),
       status: "active",
       data: {
           battery: 95.5,
           lat: -28.4696,
           lng: -65.7852
       }
   };
   return msg;
   ```
   *(Y en la última versión mostrada en captura por tu compañero, ya sanitizado con `id_hardware`, `latitud`, `longitud`, `fecha-hora`).*
3. **`Enviar a Django` (`websocket out`)** apuntando a `ws://127.0.0.1:8000/ws/iot/`.

### ¿Por qué hay que cambiar ese último nodo (`ws://127.0.0.1:8000/ws/iot/`) en la PC de la Universidad?
- Porque `127.0.0.1` es `localhost` (la misma máquina). Si Node-RED corre en la PC de la universidad y apunta a `127.0.0.1:8000`, **nadie más puede recibir los datos** (ni tu notebook, ni la de tu compañero, ni otra PC en la defensa) y si el servidor de Django se reinicia, los paquetes del collar se pierden.
- En cambio, al reemplazar el nodo final por el envío a la tabla **`public.lectura`** en **Supabase**, la PC de la universidad sube las lecturas del collar a la nube y **cualquier computadora que abra el mapa ve el collar moverse y recibe las alertas de fuga**.

---

## 2. Paso a Paso en la PC de la Universidad (Node-RED $\rightarrow$ Tabla `lectura`)

En el proyecto ya está creada en Supabase la tabla **`public.lectura`** con estas columnas exactas:
- `id_hardware` (`varchar`)
- `latitud` (`double precision`)
- `longitud` (`double precision`)
- `fecha_hora` (`timestamptz`, por defecto `NOW()`)
- `procesada` (`boolean`, por defecto `FALSE` — la maneja Django automáticamente)

A continuación tenés los pasos exactos para dejar funcionando el flujo en el Node-RED de la facultad:

---

### Paso 1: Instalar el nodo PostgreSQL en Node-RED (si aún no está instalado)
1. Abrir Node-RED en el navegador de la PC de la universidad (usualmente `http://127.0.0.1:1880`).
2. Hacer clic en el menú de arriba a la derecha (**`☰`**) $\rightarrow$ **`Manage palette`** (Gestionar paleta).
3. Ir a la pestaña **`Install`**, buscar **`@digitaloak/node-red-contrib-postgresql`** (o **`node-red-contrib-postgresql`**) y hacer clic en **Install**.

---

### Paso 2: Ajustar el nodo `Simular Telemetría` (o el nodo que sanitiza los datos del collar)

Hacer doble clic en el nodo **`Simular Telemetría`** (`function`) y dejar este código exacto:

```javascript
// 1. Datos sanitizados del collar (o simulados para prueba)
const id_hardware = msg.payload?.id_hardware || "IOT-DEV-001";
const latitud = Number(msg.payload?.latitud ?? -28.4696);
const longitud = Number(msg.payload?.longitud ?? -65.7852);
const fecha_hora = msg.payload?.fecha_hora || msg.payload?.["fecha-hora"] || new Date().toISOString();

// 2. Payload limpio con los 4 campos acordados
msg.payload = {
    "id_hardware": id_hardware,
    "latitud": latitud,
    "longitud": longitud,
    "fecha_hora": fecha_hora
};

// 3. Parámetros ordenados ($1, $2, $3, $4) para el INSERT en Supabase
msg.queryParameters = [
    id_hardware,
    latitud,
    longitud,
    fecha_hora
];

return msg;
```

> [!NOTE]
> Fijate que la línea `msg.payload?.fecha_hora || msg.payload?.["fecha-hora"]` acepta tanto `fecha_hora` (con guion bajo) como `fecha-hora` (con guion medio, como estaba en la captura de tu compañero), así no falla nunca.

---

### Paso 3: Reemplazar el nodo `Enviar a Django (WebSocket)` por el nodo `postgresql`

1. Borrar el nodo **`Enviar a Django`** (`websocket out`) del flujo.
2. Arrastrar un nodo **`postgresql`** desde la paleta izquierda y conectarlo a la salida de **`Simular Telemetría`**.
3. Hacer doble clic en el nodo **`postgresql`** y configurar la conexión al servidor (**Server** $\rightarrow$ ícono del lápiz `✏️`):
   - **Host:** `db.<ID_PROYECTO_SUPABASE>.supabase.co` *(copiar el `DB_HOST` del archivo `.env`)*
   - **Port:** `5432`
   - **Database:** `postgres`
   - **User:** `postgres`
   - **Password:** *(copiar el `DB_PASSWORD` del archivo `.env`)*
   - **SSL:** Activar / Tildar la casilla **Use SSL** (`rejectUnauthorized: false` si la red de la facultad usa certificados intermedios).
   - *(Tip: Si el internet de la universidad no tiene IPv6, usar en **Host** y **User** los datos del **Session Pooler IPv4** de Supabase que figuran en el botón `Connect` de Supabase).*
4. En la pestaña **Query** del mismo nodo **`postgresql`**, pegar esta única consulta SQL:

```sql
INSERT INTO public.lectura (id_hardware, latitud, longitud, fecha_hora)
VALUES ($1, $2, $3, $4);
```

5. Hacer clic en **Done** y luego arriba a la derecha en el botón rojo **`Deploy`**.

---

## 3. Cómo Verificar que Todo Funciona de Punta a Punta

1. **En Node-RED (PC de la Universidad):**
   - Tocar el botón cuadrado a la izquierda del nodo **`Disparar dato`** (`inject`).
   - En el panel `Debug` de la derecha vas a ver que se disparó el JSON con `"id_hardware": "IOT-DEV-001"`.
2. **En Supabase (`Table Editor` $\rightarrow$ tabla `lectura`):**
   - Vas a ver que apareció la fila nueva con `id_hardware = IOT-DEV-001`, `latitud = -28.4696`, `longitud = -65.7852`.
3. **En el Mapa de Django (`http://127.0.0.1:8000/` en `📡 Modo Real`):**
   - En menos de 5 segundos, [`procesar_lecturas_pendientes_nodered()`](../cercos/services.py) lee la fila pendiente de `lectura`:
     - Si el collar `IOT-DEV-001` no existía, lo da de alta solo y lo dibuja en el mapa.
     - Crea el registro espacial en [`TelemetriaGPS`](../cercos/models.py) vinculado a esa `lectura`.
     - Marca la fila de `lectura` con `procesada = true`.
     - Si el collar tenía un cerco asignado y la coordenada cayó afuera, dispara en pantalla la **`AlertaFuga`**.

---

## 4. Plan B Rápido (Si en la PC de la Universidad NO deja instalar el paquete PostgreSQL en Node-RED)

Si la PC del laboratorio tiene bloqueada la instalación de paquetes en Node-RED, **no hace falta instalar nada**: pueden usar el nodo **`http request`** que ya viene de fábrica en Node-RED conectándolo a la salida de **`Simular Telemetría`**:

- **Method:** `POST`
- **URL:** `https://<ID_PROYECTO_SUPABASE>.supabase.co/rest/v1/lectura`
- **Headers (agregar 3 cabeceras en el nodo `http request`):**
  - `apikey`: `<ANON_O_SERVICE_ROLE_KEY_DE_SUPABASE>` *(se copia de Project Settings $\rightarrow$ API en Supabase)*
  - `Authorization`: `Bearer <ANON_O_SERVICE_ROLE_KEY_DE_SUPABASE>`
  - `Content-Type`: `application/json`
- **Return:** `a UTF-8 string`

Al hacer clic en **`Disparar dato`**, el nodo `http request` inserta directamente el `msg.payload` (`id_hardware`, `latitud`, `longitud`, `fecha_hora`) en la tabla `public.lectura` de Supabase por HTTPS (puerto 443, que nunca está bloqueado por el firewall de la universidad y funciona tanto en IPv4 como en IPv6).

