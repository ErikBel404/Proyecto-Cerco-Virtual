# Guía Oficial de Supabase: Acceso para Compañeros, Docentes e Integración IoT (Node-RED)

**Proyecto:** SmartHerd — Sistema de Cercos Virtuales y Monitoreo Ganadero (UNCA)  
**Base de Datos en la Nube:** Supabase PostgreSQL 17 + **PostGIS 3.3.7**  
**ID del Proyecto en Supabase:** `<ID_PROYECTO_SUPABASE>` *(configurado en el archivo `.env` privado del equipo)*

---

## 📌 Resumen Rápido: ¿Quién necesita qué para conectarse?

> [!IMPORTANT]
> **Nadie debe compartir su cuenta personal de Supabase.** Cada integrante o docente opera con su propia cuenta o desde su propio entorno según esta tabla:

| ¿Qué querés hacer? | ¿Necesitás cuenta en `supabase.com`? | ¿Qué necesitás hacer? |
| :--- | :--- | :--- |
| **1. Correr el proyecto Django en tu PC y usar el mapa web** | ❌ **No** | Clonar el repo, crear tu archivo `.env` con los datos de la Sección 1 y ejecutar `python manage.py runserver`. |
| **2. Cargar o editar vacas/cercos desde el navegador (sin SQL)** | ❌ **No** | Entrar a `http://127.0.0.1:8000/admin/` con el superusuario del equipo (Sección 2). |
| **3. Entrar a la web de `supabase.com` para ver las tablas crudas o el SQL Editor** | ✅ **Sí (tu propia cuenta personal)** | Pedirle al administrador del proyecto que invite tu correo en **Team / Members** (Sección 3). |
| **4. Conectar Node-RED (Collares IoT) a la base de datos** | ❌ **No** | Configurar el nodo PostgreSQL en Node-RED con los datos de la Sección 4. |

---

## 1. Cómo Conectarse desde el Proyecto Django (Para Compañeros que Clonan el Repo)

La base de datos de Supabase **ya tiene activada la extensión espacial PostGIS y todas las tablas creadas**. Cuando un compañero clona el repositorio en su computadora, **no necesita instalar una base de datos local ni volver a correr migraciones**: se conecta directo a la nube.

### Paso 1.1: Clonar la rama `Development` e instalar dependencias
```powershell
git clone <URL_DEL_REPOSITORIO>
cd Proyecto-Cerco-Virtual
git checkout Development

python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```
*(Nota en Windows: GeoDjango utiliza las librerías `libgdal` y `libgeos_c` que vienen con el bundle PostGIS de PostgreSQL; [`proyectoCercoVirtual/settings.py`](../proyectoCercoVirtual/settings.py) las detecta automáticamente en `C:\Program Files\PostgreSQL\`).*

### Paso 1.2: Crear el archivo `.env` en la raíz del proyecto
Copia el archivo `.env.example` con el nombre `.env` en la raíz del proyecto (`Proyecto-Cerco-Virtual/.env`) y coloca las variables de conexión:

```env
SECRET_KEY=reemplazar_por_clave_secreta_del_equipo
DEBUG=True

DB_ENGINE=django.contrib.gis.db.backends.postgis
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=<CONTRASEÑA_DE_LA_BASE_SUPABASE_DEL_EQUIPO>
DB_HOST=db.<ID_PROYECTO_SUPABASE>.supabase.co
DB_PORT=5432
DB_SSLMODE=require
```
*(Por seguridad, `DB_HOST`, `DB_PASSWORD` y `SECRET_KEY` reales viven únicamente en el archivo `.env` local —ignorado por `.gitignore`— y se comparten por el canal privado del grupo para no exponerlos en GitHub público).*

> [!TIP]
> **¿Qué pasa si en la casa de un compañero o en el Wi-Fi de la facultad tira error `could not translate host name`?**  
> En el plan gratuito de Supabase:
> - El host directo (`db.<ID_PROYECTO_SUPABASE>.supabase.co`) usa **IPv6**.
> - Si el proveedor de internet de un compañero solo tiene **IPv4**, Supabase ofrece **gratis** el **Session Pooler (IPv4)**. Solo debe cambiar estas dos líneas en su `.env`:
>   ```env
>   DB_USER=postgres.<ID_PROYECTO_SUPABASE>
>   DB_HOST=aws-0-us-east-1.pooler.supabase.com
>   ```
>   *(El host exacto del Session Pooler se ve dentro de Supabase tocando el botón verde **Connect** arriba $\rightarrow$ tarjeta **Direct** $\rightarrow$ bajando hasta **Session pooler**).*

### Paso 1.3: Iniciar el servidor
```powershell
.\venv\Scripts\python.exe manage.py runserver
```
Abre en el navegador: **`http://127.0.0.1:8000/`**.

---

## 2. Cómo Ver y Cargar Datos desde el Navegador de la Aplicación (Docentes y Compañeros)

Sin necesidad de entrar a `supabase.com`, cualquier docente o compañero puede ver y administrar todo lo que hay en Supabase desde dos pantallas del navegador:

### A. Panel de Administración Maestro (`http://127.0.0.1:8000/admin/`)
Permite ver las 4 tablas de Supabase, dar de alta o baja vacas reales y editar cercos en un formulario visual:
- **URL:** `http://127.0.0.1:8000/admin/`
- **Usuario:** `admin`
- **Contraseña:** *(Solicitar al equipo o crear un usuario propio con `python manage.py createsuperuser`)*

Desde ahí puedes entrar a:
1. **Animales Monitoreados (`cercos_animal`):** Cargar vacas reales con su ID de collar (ej. `COLLAR-REAL-01`), elegir su lote y ver su estado.
2. **Cercos Virtuales (`cercos_cercovirtual`):** Ver los polígonos guardados, su color y si son **Perímetro Crítico (`alerta_continua`)**.
3. **Lecturas de Telemetría GPS (`cercos_telemetriagps`)** y **Alertas de Fuga (`cercos_alertafuga`)**.

### B. Visor Cartográfico Principal (`http://127.0.0.1:8000/`)
- **`📡 Modo Real (Node-RED)` (Activo por defecto):** Muestra únicamente las vacas y cercos reales guardados en Supabase. Las vacas no se mueven con el mouse por accidente; se actualizan solas cada 5 segundos cuando llegan datos desde Node-RED/Supabase.
- **`🧪 Modo Simulación (Pruebas)`:** Al activarlo con el botón superior derecho, habilita **`⚡ Cargar Demo`** (que crea 2 lotes y 4 vacas de prueba en la localidad elegida: Capital, Belén, Tinogasta, etc.), **`+ Nuevo (Sim)`** y el arrastre de vacas con el mouse. Al volver a **`📡 Modo Real`**, los datos de prueba se borran solos de Supabase para dejar limpia la base.

---

## 3. Cómo Dar Acceso al Panel Web de `supabase.com` (Sin Compartir tu Cuenta)

Si un compañero de grupo o la docente quiere entrar desde su navegador a **`https://supabase.com`** para ver el **Table Editor** o tirar consultas en el **SQL Editor**:

### Paso 3.1: Cómo los invita el dueño del proyecto (se hace una sola vez)
1. El compañero o docente se crea su propia cuenta gratuita en [https://supabase.com/](https://supabase.com/) (puede entrar con su propio GitHub).
2. Vos (el dueño del proyecto en Supabase) entrás a tu panel de Supabase y hacés clic arriba de todo en el nombre de tu organización: **`Proyecto-Cerco-Virtual`**.
3. En el menú lateral izquierdo de la organización, entrás a **Team** (o **Organization Settings $\rightarrow$ Members**).
4. Hacés clic en el botón **"Invite member"**:
   - **Email address:** Escribís el correo con el que tu compañero o docente se registró en Supabase.
   - **Role:** Elegís **Developer** (le permite ver las tablas, insertar filas y usar el SQL Editor, pero no borrar el proyecto ni cambiar facturación).
5. Tu compañero/docente recibe un mail de Supabase, toca **"Accept Invitation"** y ya ve el proyecto **`Cerco-Virtual`** dentro de su propia cuenta.

### Paso 3.2: Cómo ver los datos dentro de `supabase.com`
Una vez dentro del proyecto **`Cerco-Virtual`** en `supabase.com`:
1. **En el menú izquierdo $\rightarrow$ `Table Editor` (ícono `⊞`):**
   - Seleccionar arriba `schema: public`.
   - Hacer clic en las 4 tablas del sistema para ver sus filas en vivo:
     - `cercos_cercovirtual` (Lotes/cercos)
     - `cercos_animal` (Vacas y última posición GPS)
     - `cercos_telemetriagps` (Historial de coordenadas recibidas)
     - `cercos_alertafuga` (Incidentes de fuga)
2. **En el menú izquierdo $\rightarrow$ `SQL Editor` (ícono `>_`):**
   Como PostGIS guarda las geometrías en binario (`EWKB`), para ver la latitud y longitud en números legibles pegá esta consulta y dale a **Run**:
   ```sql
   SELECT 
       id,
       id_hardware,
       nombre,
       estado_fuga,
       ST_Y(ultima_posicion) AS latitud,
       ST_X(ultima_posicion) AS longitud,
       fecha_ultima_posicion
   FROM public.cercos_animal
   ORDER BY id;
   ```

---

## 4. Cómo Conectar Node-RED (Collares IoT) a Supabase

El compañero encargado de recibir los datos de los collares en **Node-RED** tiene dos formas directas de enviar las coordenadas al sistema:

### Opción A: Node-RED escribe directo en Supabase (Nodo PostgreSQL)
En Node-RED (con el paquete `node-red-contrib-postgresql`), configura el servidor con los mismos datos del `.env`:
- **Host:** `db.<ID_PROYECTO_SUPABASE>.supabase.co` *(el mismo `DB_HOST` del `.env`)*
- **Port:** `5432`
- **Database:** `postgres`
- **User:** `postgres`
- **Password:** *(La contraseña `DB_PASSWORD` del `.env`)*
- **SSL:** `true` (Requerido por Supabase)

Cuando llega un paquete del collar (`id_hardware`, `latitud`, `longitud`), el nodo ejecuta este SQL:

```sql
UPDATE public.cercos_animal
SET ultima_posicion = ST_SetSRID(ST_MakePoint($1, $2), 4326),
    fecha_ultima_posicion = NOW()
WHERE id_hardware = $3;
```
- **`$1`**: Longitud (ej. `-65.7875`) — *En PostGIS `ST_MakePoint(X, Y)` va primero Longitud y segundo Latitud*.
- **`$2`**: Latitud (ej. `-28.4670`).
- **`$3`**: ID del collar (ej. `'COLLAR-REAL-01'`).

> 💡 **Cómo demostrar esto en vivo en la defensa sin tener el collar prendido:**  
> Abrí el mapa en `http://127.0.0.1:8000/` en **`📡 Modo Real`**, y en otra pestaña abrí el **SQL Editor** de Supabase y ejecutá:
> ```sql
> UPDATE public.cercos_animal
> SET ultima_posicion = ST_SetSRID(ST_MakePoint(-65.7850, -28.4500), 4326),
>     fecha_ultima_posicion = NOW()
> WHERE id_hardware = 'COLLAR-REAL-01';
> ```
> A los pocos segundos vas a ver cómo la vaca se mueve sola en el mapa y, si esa coordenada cayó fuera de su cerco, **PostGIS detecta la brecha y lanza la alerta en pantalla automáticamente**.

### Opción B: Node-RED envía un HTTP POST al Backend de Django
Usando un nodo estándar `http request` en Node-RED apuntando a `POST http://<IP_SERVIDOR>:8000/api/telemetria/procesar/`:
```json
{
  "id_hardware": "COLLAR-REAL-01",
  "latitud": -28.4670,
  "longitud": -65.7875
}
```

---

## 5. Comandos de Limpieza y Mantenimiento de la Base

- **Borrar únicamente los lotes y vacas de la Demo:** Pasar el botón superior de la página a **`📡 Modo Real (Node-RED)`** o tocar **`🧹 Limpiar Demo`**.
- **Vaciar todos los datos de todas las tablas dejando las tablas vacías:**
  ```powershell
  .\venv\Scripts\python.exe manage.py flush
  ```
- **Destruir y recrear desde cero las tablas de `cercos` si el equipo cambia los modelos:**
  ```powershell
  .\venv\Scripts\python.exe manage.py migrate cercos zero
  .\venv\Scripts\python.exe manage.py makemigrations cercos
  .\venv\Scripts\python.exe manage.py migrate
  ```
