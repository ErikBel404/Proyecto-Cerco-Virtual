# 🌱 SmartHerd — Sistema de Cercos Virtuales y Monitoreo Ganadero (UNCA)

Aplicación web geoespacial desarrollada con **Django 6.1 + GeoDjango + PostGIS + Leaflet.js** para la delimitación de potreros/cercos virtuales, asignación de ganado con collares GPS IoT, evaluación espacial en tiempo real (`ST_Contains`) y emisión de alertas de fuga.

---

## 📚 Documentación Integral del Proyecto (OpenSpec & Archify)

Toda la arquitectura, especificaciones funcionales y guías de integración se encuentran documentadas en español dentro del repositorio:

1. **Especificaciones Vivas ([`openspec/`](./openspec/AGENTS.md))**:
   - [`openspec/project.md`](./openspec/project.md): Contexto del proyecto (UNCA), stack y convenciones geoespaciales (`SRID 4326`).
   - [`01-cercos-virtuales`](./openspec/specs/01-cercos-virtuales/spec.md): Creación, modificación, validación topológica GEOS (sin cruces de líneas) y eliminación de cercos (`RF_1`, `RF_2`, `RF_8`).
   - [`02-ganado-y-asignacion`](./openspec/specs/02-ganado-y-asignacion/spec.md): Registro de animales/collares y pertenencia a cercos (`RF-08`, `RF-09`, `RF-10`).
   - [`03-telemetria-y-deteccion`](./openspec/specs/03-telemetria-y-deteccion/spec.md): Ingesta de posiciones GPS y consulta espacial PostGIS `ST_Contains` (`RF_3`, `RF_4`, `RNF_1`).
   - [`04-alertas-y-profugos`](./openspec/specs/04-alertas-y-profugos/spec.md): Alertas emergentes con ventana Anti-Spam de 5 minutos y panel de animales prófugos (`RF_5`, `RF_6`, `RF_7`).

2. **Documentación Formal Universitaria y Arquitectura Visual ([`docs/`](./docs/archify/README.md))**:
   - 📄 [**ERS — Especificación de Requisitos de Software**](./docs/ERS_Especificacion_Requisitos.md) (Requerimientos de Usuario, Requisitos Funcionales, No Funcionales y Matriz de Trazabilidad).
   - 📐 [**SDD — Documento de Diseño del Sistema**](./docs/SDD_Diseno_Sistema.md) (Diagrama Entidad-Relación Espacial, Diagramas de Secuencia y Contratos de API JSON/GeoJSON).
   - 🏛️ [**Archify — Arquitectura C4 y ADRs**](./docs/archify/README.md):
     - [Nivel 1: Contexto Ecosistema IoT UNCA](./docs/archify/01-contexto-iot-unca.md)
     - [Nivel 2: Contenedores (Leaflet, GeoDjango, Supabase/PostGIS)](./docs/archify/02-contenedores-y-postgis.md)
     - [Nivel 3: Componentes Internos de la App `cercos`](./docs/archify/03-componentes-django.md)
   - ☁️ [**Guía Paso a Paso de Supabase (PostgreSQL + PostGIS en la Nube)**](./docs/GUIA_SUPABASE_E_INTEGRACION.md).

---

## 🚀 Requisitos Previos e Instalación Rápida

- **Python 3.10+**
- **PostgreSQL 15–18 con extensión PostGIS** (en local o mediante cuenta gratuita en **Supabase**).

### 1. Crear y activar el entorno virtual
```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configurar variables de entorno (`.env`)
Copia `.env.example` a `.env` y completa tus credenciales (locales o de Supabase según la [Guía de Supabase](./docs/GUIA_SUPABASE_E_INTEGRACION.md)):
```powershell
copy .env.example .env
```

### 3. Aplicar migraciones y levantar el servidor
```powershell
python manage.py migrate
python manage.py runserver
```
Abre `http://127.0.0.1:8000/` en tu navegador. Puedes presionar el botón superior **`⚡ Cargar Demo`** para poblar instantáneamente 2 lotes y 4 animales monitoreados en el Valle Central de Catamarca.

### 4. Ejecutar pruebas automatizadas
```powershell
python manage.py test
```
