"""
Configuración principal de Django 6.1 + GeoDjango (PostgreSQL / Supabase + PostGIS).
"""

import glob
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


# 1. Detección automática de librerías C/C++ de PostGIS (GDAL, GEOS y PROJ) en Windows
if os.name == 'nt':
    candidatos_pg = [
        os.getenv('POSTGRES_DIR', ''),
        r'C:\Program Files\PostgreSQL\18',
        r'C:\Program Files\PostgreSQL\17',
        r'C:\Program Files\PostgreSQL\16',
    ]
    POSTGRES_DIR = next((ruta for ruta in candidatos_pg if ruta and os.path.exists(ruta)), None)

    if POSTGRES_DIR:
        BIN_DIR = os.path.join(POSTGRES_DIR, 'bin')
        if os.path.exists(BIN_DIR):
            os.environ['PATH'] = BIN_DIR + ';' + os.environ.get('PATH', '')
            if hasattr(os, 'add_dll_directory'):
                os.add_dll_directory(BIN_DIR)

        gdal_data = os.path.join(POSTGRES_DIR, 'gdal-data')
        if os.path.exists(gdal_data):
            os.environ['GDAL_DATA'] = gdal_data

        proj_matches = glob.glob(os.path.join(POSTGRES_DIR, 'share', 'contrib', 'postgis-*', 'proj'))
        if proj_matches:
            os.environ['PROJ_LIB'] = proj_matches[0]
            os.environ['PROJ_DATA'] = proj_matches[0]

        gdal_dlls = glob.glob(os.path.join(BIN_DIR, 'libgdal*.dll'))
        if gdal_dlls:
            GDAL_LIBRARY_PATH = gdal_dlls[0]

        geos_dll = os.path.join(BIN_DIR, 'libgeos_c.dll')
        if os.path.exists(geos_dll):
            GEOS_LIBRARY_PATH = geos_dll


# 2. Seguridad y Entorno
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-default-dev-key-cambiar-en-produccion')
DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 'yes')
ALLOWED_HOSTS = [h.strip() for h in os.getenv('ALLOWED_HOSTS', '*').split(',') if h.strip()]


# 3. Aplicaciones y Middleware
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis',
    'cercos',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'proyectoCercoVirtual.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
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


# 4. Base de Datos Espacial (PostgreSQL local o Supabase Cloud con PostGIS)
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_SSLMODE = os.getenv('DB_SSLMODE', '')
if not DB_SSLMODE and ('supabase.co' in DB_HOST or 'supabase.com' in DB_HOST):
    DB_SSLMODE = 'require'

DATABASES = {
    'default': {
        'ENGINE': os.getenv('DB_ENGINE', 'django.contrib.gis.db.backends.postgis'),
        'NAME': os.getenv('DB_NAME', 'cerco_virtual_db'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': DB_HOST,
        'PORT': os.getenv('DB_PORT', '5432'),
        'CONN_MAX_AGE': int(os.getenv('DB_CONN_MAX_AGE', '600')),
        'CONN_HEALTH_CHECKS': True,
        'OPTIONS': {'sslmode': DB_SSLMODE} if DB_SSLMODE else {},
    }
}


# 5. Internacionalización y Archivos Estáticos
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

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
