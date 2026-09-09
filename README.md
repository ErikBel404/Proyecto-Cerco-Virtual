# Proyecto-Cerco-Virtual

Este proyecto es una aplicación Django diseñada para la gestión de cercos virtuales. A continuación, se detallan los pasos necesarios para configurar el entorno de desarrollo local.

## Requisitos Previos

Asegúrate de tener instalado lo siguiente en tu sistema:
- **Python 3.10+**
- **PostgreSQL** con la extensión **PostGIS**
- **Git**

## Pasos para la Instalación

### 1. Clonar el Repositorio

Primero, clona este repositorio en tu máquina local:

```bash
git clone https://github.com/TU_USUARIO/Proyecto-Cerco-Virtual.git
cd Proyecto-Cerco-Virtual
```

### 2. Crear un Entorno Virtual

Es recomendable utilizar un entorno virtual para aislar las dependencias del proyecto:

```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar Dependencias

Instala todas las librerías necesarias utilizando el archivo `requirements.txt`:

```bash
pip install -r requirements.txt
```

### 4. Configurar la Base de Datos

El proyecto utiliza **PostgreSQL** con **PostGIS**. Debes crear una base de datos y activar la extensión espacial:

1. Accede a tu terminal de PostgreSQL (`psql`) o utiliza una herramienta como pgAdmin.
2. Crea la base de datos:
   ```sql
   CREATE DATABASE nombre_de_tu_db;
   ```
3. Conéctate a la base de datos y activa PostGIS:
   ```sql
   \c nombre_de_tu_db;
   CREATE EXTENSION postgis;
   ```

### 5. Configurar Variables de Entorno

El proyecto utiliza un archivo `.env` para manejar información sensible. 

1. Localiza el archivo `.env.example` en la raíz del proyecto.
2. Crea una copia de este archivo y renómbrala a `.env`:
   ```bash
   cp .env.example .env
   ```
3. Abre el archivo `.env` y completa los campos con tu configuración local:

   - `SECRET_KEY`: Una clave secreta para Django (puedes generar una o poner una temporal).
   - `DEBUG`: Establécelo en `True` para desarrollo.
   - `DB_NAME`: El nombre de la base de datos que creaste.
   - `DB_USER`: Tu usuario de PostgreSQL.
   - `DB_PASSWORD`: Tu contraseña de PostgreSQL.
   - `DB_HOST`: Usualmente `localhost`.
   - `DB_PORT`: Usualmente `5432`.

### 6. Ejecutar Migraciones

Una vez configurada la base de datos y el archivo `.env`, aplica las migraciones de Django:

```bash
python manage.py migrate
```

### 7. Iniciar el Servidor de Desarrollo

Finalmente, arranca el servidor:

```bash
python manage.py runserver
```

Ahora puedes acceder a la aplicación en `http://127.0.0.1:8000/`.

## Notas Adicionales

- Si tienes problemas con la instalación de `psycopg2-binary`, asegúrate de tener instaladas las herramientas de compilación y las librerías de desarrollo de PostgreSQL en tu sistema operativo.
- Al usar PostGIS, asegúrate de que las librerías de GDAL/GEOS estén correctamente configuradas en tu sistema si Django no las detecta automáticamente.