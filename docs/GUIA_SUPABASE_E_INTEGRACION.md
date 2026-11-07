# Guía de Supabase y Base de Datos (Para Docentes y Equipos en Paralelo)

**Proyecto:** SmartHerd — Sistema de Cercos Virtuales y Monitoreo Ganadero (UNCA)  
**Base de Datos en la Nube:** Supabase PostgreSQL 17 + **PostGIS 3.3.7**  
**ID del Proyecto en Supabase:** `<ID_PROYECTO_SUPABASE>` *(configurado en el archivo `.env` privado del equipo)*

*(Nota: Para la configuración interna de los collares y Node-RED en la PC del laboratorio, consultar el documento específico [`GUIA_CONEXION_NODE_RED.md`](GUIA_CONEXION_NODE_RED.md)).*

---

## 📌 Resumen Rápido: ¿Quién necesita qué para acceder al proyecto?

> [!IMPORTANT]
> **Nadie necesita compartir su cuenta personal de Supabase.** Cada docente o integrante accede según lo que necesite revisar:

| ¿Qué querés hacer? | ¿Necesitás cuenta en `supabase.com`? | ¿Qué necesitás hacer? |
| :--- | :--- | :--- |
| **1. Correr el proyecto Django en tu PC y probar el mapa web** | ❌ **No** | Clonar el repo, crear el archivo `.env` (Sección 1) y ejecutar `python manage.py runserver`. |
| **2. Ver o administrar cercos, animales y lecturas desde el navegador** | ❌ **No** | Entrar a `http://127.0.0.1:8000/admin/` con el usuario administrador (Sección 2). |
| **3. Entrar a la consola web de `supabase.com` (Table Editor / SQL Editor)** | ✅ **Sí (tu propia cuenta)** | Pedir que inviten tu correo en **Team / Members** de la organización (Sección 3). |
| **4. Integrar el modelo de Animales del otro grupo con Cercos Virtuales** | ❌ **No** | Ver el esquema de tablas desacopladas por `id_hardware` (Sección 4). |

---

## 1. Cómo Levantar el Proyecto Localmente

La base de datos de Supabase **ya tiene activada la extensión espacial PostGIS y todas las tablas migradas**. Quien clona el repositorio **no necesita instalar una base de datos local ni correr migraciones**: se conecta directo a la nube.

### Paso 1.1: Clonar el repositorio e instalar dependencias
```powershell
git clone <URL_DEL_REPOSITORIO>
cd Proyecto-Cerco-Virtual
git checkout Development

python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```
*(En Windows, GeoDjango utiliza las librerías `libgdal` y `libgeos_c` del bundle PostGIS de PostgreSQL; [`proyectoCercoVirtual/settings.py`](../proyectoCercoVirtual/settings.py) las detecta automáticamente en `C:\Program Files\PostgreSQL\`).*

### Paso 1.2: Crear el archivo `.env` en la raíz del proyecto
Copia el archivo `.env.example` con el nombre `.env` en la raíz del proyecto y completa las variables entregadas por el equipo:

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

> [!TIP]
> **¿Qué hacer si en una red sin IPv6 aparece `could not translate host name`?**  
> En el plan gratuito de Supabase, el host directo usa IPv6. Si el proveedor de internet solo tiene IPv4, basta con usar el **Session Pooler (IPv4)** gratuito de Supabase cambiando estas dos líneas en el `.env`:
> ```env
> DB_USER=postgres.<ID_PROYECTO_SUPABASE>
> DB_HOST=aws-0-us-east-1.pooler.supabase.com
> ```

### Paso 1.3: Iniciar el servidor
```powershell
.\venv\Scripts\python.exe manage.py runserver
```
Abrir en el navegador: **`http://127.0.0.1:8000/`**.

---

## 2. Cómo Revisar el Sistema desde el Navegador (Docentes)

### A. Visor Cartográfico Principal (`http://127.0.0.1:8000/`)
- **`📡 Modo Real (Node-RED)` (Activo por defecto):** Muestra únicamente los cercos y collares reales almacenados en Supabase.
- **`🧪 Modo Simulación (Pruebas)`:** Al activarlo con el botón superior derecho, habilita **`⚡ Cargar Demo`** (2 lotes y 4 animales de prueba en la localidad elegida: Capital, Belén, Tinogasta, Andalgalá, etc.), **`+ Nuevo (Sim)`** y el arrastre de marcadores con el mouse para verificar las alertas de PostGIS en vivo. Al volver a **`📡 Modo Real`**, los datos de demostración se limpian solos.

### B. Panel de Administración (`http://127.0.0.1:8000/admin/`)
Permite inspeccionar todas las tablas de Supabase desde una interfaz visual:
1. **Lecturas Crudas (`lectura`):** Datos recibidos desde el collar (`id_hardware`, `latitud`, `longitud`, `fecha_hora`, `procesada`).
2. **Telemetrías GPS Procesadas (`cercos_telemetriagps`):** Historial geoespacial validado por PostGIS (`posicion` SRID 4326 y `dentro_del_cerco`).
3. **Cercos Virtuales (`cercos_cercovirtual`):** Polígonos perimetrales de los lotes y configuración de Perímetro Crítico (`alerta_continua`).
4. **Animales Monitoreados (`cercos_animal`)** y **Alertas de Fuga (`cercos_alertafuga`)**.

---

## 3. Cómo Dar Acceso al Panel Web de `supabase.com`

Si un docente o integrante de otro grupo desea entrar desde su navegador a **`https://supabase.com`** para ver el **Table Editor** o el **SQL Editor**:

1. La persona se registra con su propia cuenta gratuita en [https://supabase.com/](https://supabase.com/).
2. El administrador del proyecto entra en Supabase a la organización **`Proyecto-Cerco-Virtual` $\rightarrow$ Team $\rightarrow$ Invite member**, ingresa el correo y selecciona el rol **Developer**.
3. Una vez dentro del proyecto en `supabase.com`, en **`Table Editor`** (`schema: public`) verá las 5 tablas del dominio:
   - `lectura` *(Entrada cruda de los collares)*
   - `cercos_telemetriagps` *(Evaluación espacial PostGIS que consume de `lectura`)*
   - `cercos_cercovirtual` *(Polígonos de los lotes)*
   - `cercos_animal` *(Vinculación collar $\leftrightarrow$ cerco)*
   - `cercos_alertafuga` *(Incidentes de escape)*

---

## 4. Integración y Desacoplamiento con el Otro Grupo (Módulo de Animales)

La arquitectura de base de datos está diseñada para que **el módulo de Cercos Virtuales y Telemetría no se rompa ni requiera reescribirse** cuando se integre con la tabla de animales desarrollada por el otro grupo:

1. **Separación entre `Lectura` y `TelemetriaGPS`:**
   - La tabla **`public.lectura`** recibe los paquetes del collar identificados únicamente por el texto `id_hardware` (sin claves foráneas obligatorias a `Animal`).
   - Luego, [`TelemetriaGPS`](../cercos/models.py) consume las lecturas pendientes (`procesada = False`) y evalúa con PostGIS (`ST_Contains`) si la coordenada está dentro o fuera del [`CercoVirtual`](../cercos/models.py).
2. **Adaptación inmediata si el otro grupo usa otro nombre de tabla o columnas para `Animal`:**
   - En el ORM de Django ([`cercos/models.py`](../cercos/models.py)), el nombre de la tabla física en PostgreSQL se define en `Meta: db_table` y el nombre de cada columna en `db_column`.
   - Si el otro grupo nombra a su tabla `ani` o `ganado` en la base de datos compartida, basta con apuntar `db_table` a esa tabla sin modificar ninguna vista ni ningún cálculo espacial en [`cercos/services.py`](../cercos/services.py).
