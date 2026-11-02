# ADR-001: Adopción de Supabase (PostgreSQL + PostGIS) como Base de Datos en la Nube

- **Estado:** Aceptado
- **Fecha:** Noviembre 2026
- **Contexto:** Proyecto Cerco Virtual (UNCA)

## Contexto y Problema
El proyecto involucra múltiples actores trabajando en paralelo (integrantes del módulo de Cercos Virtuales, otro grupo desarrollando la plataforma web general y los datos provenientes de los collares IoT de Ingeniería Electrónica). Cuando cada desarrollador utiliza únicamente una base de datos PostgreSQL local en su propia PC:
1. No existe una fuente de datos compartida para pruebas de integración.
2. Si la PC de un integrante no está encendida o accesible en red, el resto del equipo no puede consultar ni demostrar los datos cargados.
3. Como equipo estudiantil universitario, se requiere una solución en la nube **gratuita (Free Tier)** que soporte de manera nativa **PostgreSQL con la extensión espacial PostGIS** y que permita migrar en el futuro a un servidor propio de la UNCA sin reescribir código.

## Decisión
Utilizar **Supabase (Free Tier)** como motor PostgreSQL + PostGIS en la nube, configurando `proyectoCercoVirtual/settings.py` mediante variables de entorno (`.env`) para conectarse indistintamente a **Supabase** o a **PostgreSQL local**, incluyendo soporte para `DB_SSLMODE=require`.

## Consecuencias Positivas
1. **Compatibilidad 100% con GeoDjango**: Supabase provee una instancia real de PostgreSQL donde la extensión `postgis` se habilita con `CREATE EXTENSION IF NOT EXISTS postgis;`.
2. **Cero Vendor Lock-in**: Al usar el conector estándar `django.contrib.gis.db.backends.postgis` (`psycopg2`), pasar de local a Supabase o de Supabase a un servidor propio de la facultad requiere únicamente cambiar las credenciales en el archivo `.env`.
3. **Integración inmediata entre equipos**: Tanto la app de Cercos Virtuales como la web del otro grupo y el gateway de telemetría pueden apuntar a la misma base de datos en la nube.

