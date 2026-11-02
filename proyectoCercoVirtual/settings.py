"""
==============================================================================
ARCHIVO DE CONFIGURACIÓN PRINCIPAL: proyectoCercoVirtual/settings.py
==============================================================================
¿QUÉ HACE ESTE ARCHIVO?
Configura el núcleo del proyecto Django 6.1 y el motor geoespacial GeoDjango
(`django.contrib.gis`), conectándolo a una base de datos PostgreSQL + PostGIS
tanto en entorno local como en la nube (Supabase).

¿POR QUÉ ESTÁ DISEÑADO ASÍ?
1. En Windows, GeoDjango requiere cargar librerías dinámicas en C/C++ (GDAL,
   GEOS y PROJ) que procesan la matemática de polígonos y coordenadas GPS. En el
   prototipo original, la ruta estaba clavada a una versión fija; aquí se
   autodecta dinámicamente entre PostgreSQL 18, 17 o 16 (o la variable POSTGRES_DIR
   del archivo .env), evitando que el proyecto falle en distintas PCs del equipo.
2. En Linux/Servidores/Docker, el bloque `if os.name == 'nt'` se ignora
   automáticamente para usar las librerías nativas del sistema operativo.
3. Soporta conexión transparente a Supabase Cloud activando SSL (`sslmode=require`)
   cuando detecta un host de Supabase o cuando se define `DB_SSLMODE` en `.env`.
==============================================================================
"""

import glob
import os
from pathlib import Path
from dotenv import load_dotenv

# BASE_DIR apunta a la raíz del repositorio (donde está manage.py)
BASE_DIR = Path(__file__).resolve().parent.parent

# Carga las variables de entorno definidas en el archivo .env de la raíz
load_dotenv(BASE_DIR / '.env')


# ==============================================================================
# 1. DETECCIÓN Y CARGA DE LIBRERÍAS NATIVAS POSTGIS / GDAL / GEOS EN WINDOWS
# ==============================================================================
# ¿PARA QUÉ SIRVE ESTE BLOQUE?
# Python por sí solo no realiza cálculos geométricos sobre la curvatura de la
# Tierra. GeoDjango delega la validación de polígonos (GEOS) y las proyecciones
# cartográficas (GDAL/PROJ) a los binarios que instala el paquete PostGIS Bundle.
if os.name == 'nt':
    candidatos_pg = [
        os.getenv('POSTGRES_DIR', ''),
        r'C:\Program Files\PostgreSQL\18',
        r'C:\Program Files\PostgreSQL\17',
        r'C:\Program Files\PostgreSQL\16',
    ]
    # Selecciona la primera carpeta de PostgreSQL existente en la máquina local
    POSTGRES_DIR = next((ruta for ruta in candidatos_pg if ruta and os.path.exists(ruta)), None)

    if POSTGRES_DIR:
        BIN_DIR = os.path.join(POSTGRES_DIR, 'bin')
        if os.path.exists(BIN_DIR):
            # Agrega la carpeta bin al PATH del proceso actual
            os.environ['PATH'] = BIN_DIR + ';' + os.environ.get('PATH', '')
            # En Python 3.8+ sobre Windows es obligatorio registrar el directorio de DLLs
            if hasattr(os, 'add_dll_directory'):
                os.add_dll_directory(BIN_DIR)

        # Catálogo de datos de GDAL (elipsoides y datums geodésicos)
        gdal_data = os.path.join(POSTGRES_DIR, 'gdal-data')
        if os.path.exists(gdal_data):
            os.environ['GDAL_DATA'] = gdal_data

        # Base de datos de proyecciones PROJ (necesaria para transformar SRID 4326 <-> 3857)
        proj_matches = glob.glob(os.path.join(POSTGRES_DIR, 'share', 'contrib', 'postgis-*', 'proj'))
        if proj_matches:
            os.environ['PROJ_LIB'] = proj_matches[0]
            os.environ['PROJ_DATA'] = proj_matches[0]

        # Localiza dinámicamente el binario de GDAL (ej. libgdal-35.dll)
        gdal_dlls = glob.glob(os.path.join(BIN_DIR, 'libgdal*.dll'))
        if gdal_dlls:
            GDAL_LIBRARY_PATH = gdal_dlls[0]

        # Localiza el binario de GEOS (motor que valida auto-intersecciones y contención)
        geos_dll = os.path.join(BIN_DIR, 'libgeos_c.dll')
        if os.path.exists(geos_dll):
            GEOS_LIBRARY_PATH = geos_dll


# ==============================================================================
# 2. SEGURIDAD Y CONFIGURACIÓN DE ENTORNO
# ==============================================================================
# Clave criptográfica para firmar sesiones y tokens CSRF (se lee desde .env)
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-default-dev-key-cambiar-en-produccion')

# En desarrollo DEBUG=True muestra trazas detalladas; en producción debe ser False
DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 'yes')

# Lista de dominios/IPs autorizados a servir la aplicación
allowed_hosts_env = os.getenv('ALLOWED_HOSTS', '*')
ALLOWED_HOSTS = [h.strip() for h in allowed_hosts_env.split(',') if h.strip()]


# ==============================================================================
# 3. APLICACIONES INSTALADAS Y MIDDLEWARE
# ==============================================================================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Motor SIG de Django: habilita PolygonField, PointField y consultas espaciales
    'django.contrib.gis',
    # Aplicación principal de nuestro dominio: Cercos Virtuales, Ganado, Telemetría y Alertas
    'cercos',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    # CsrfViewMiddleware protege los endpoints POST contra ataques Cross-Site Request Forgery
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'proyectoCercoVirtual.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # Permite buscar templates tanto en una carpeta global /templates como dentro de cada app
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'proyectoCercoVirtual.wsgi.application'


# ==============================================================================
# 4. BASE DE DATOS ESPACIAL (POSTGRESQL LOCAL O SUPABASE EN LA NUBE CON POSTGIS)
# ==============================================================================
# ¿POR QUÉ USAMOS EL ENGINE 'django.contrib.gis.db.backends.postgis'?
# Porque el backend estándar de PostgreSQL no traduce tipos geométricos ni
# consultas espaciales como `perimetro__contains=punto` (ST_Contains en SQL).
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_SSLMODE = os.getenv('DB_SSLMODE', '')

# Si el host pertenece a Supabase Cloud, forzamos conexión segura SSL por defecto
if not DB_SSLMODE and ('supabase.co' in DB_HOST or 'supabase.com' in DB_HOST):
    DB_SSLMODE = 'require'

db_options = {}
if DB_SSLMODE:
    db_options['sslmode'] = DB_SSLMODE

DATABASES = {
    'default': {
        'ENGINE': os.getenv('DB_ENGINE', 'django.contrib.gis.db.backends.postgis'),
        'NAME': os.getenv('DB_NAME', 'cerco_virtual_db'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': DB_HOST,
        'PORT': os.getenv('DB_PORT', '5432'),
        # Mantiene viva la conexión SSL con Supabase durante 600s (10 min) y verifica su salud
        # para evitar el costo de abrir un nuevo túnel TCP+SSL en cada petición HTTP (RNF_2)
        'CONN_MAX_AGE': int(os.getenv('DB_CONN_MAX_AGE', '600')),
        'CONN_HEALTH_CHECKS': True,
        'OPTIONS': db_options,
    }
}


# ==============================================================================
# 5. VALIDACIÓN DE CONTRASEÑAS E INTERNACIONALIZACIÓN
# ==============================================================================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Configurado para Español (Argentina) y huso horario de Catamarca (UTC-3)
# para que las marcas de tiempo de fugas (RF_7) reflejen la hora local exacta del campo.
LANGUAGE_CODE = 'es-ar'
TIME_ZONE = 'America/Argentina/Catamarca'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

MAILERS = {
    'default': {
        'BACKEND': 'django.core.mail.backends.console.EmailBackend',
    },
}
