# Guía de OpenSpec para Agentes e Integrantes (SmartHerd - Cerco Virtual)

Este directorio implementa **OpenSpec** en español: un sistema de **Desarrollo Guiado por Especificaciones (Spec-Driven Development)** pensado para que desarrolladores, docentes, otros grupos de trabajo e inteligencias artificiales comprendan y evolucionen el proyecto sin ambigüedades.

## Estructura del Directorio `openspec/`

```text
openspec/
├── AGENTS.md                        # Instrucciones de uso de OpenSpec (este archivo)
├── project.md                       # Contexto general del proyecto, stack y reglas de dominio
├── specs/                           # Especificaciones vivas (fuente de verdad actual)
│   ├── 01-cercos-virtuales/
│   │   └── spec.md                  # RF_1, RF_2, RF_8: Gestión espacial de cercos
│   ├── 02-ganado-y-asignacion/
│   │   └── spec.md                  # ABM de Ganado + RF-08, RF-09, RF-10: Pertenencia a cercos
│   ├── 03-telemetria-y-deteccion/
│   │   └── spec.md                  # RF_3, RF_4: Ingesta GPS y validación PostGIS (ST_Contains)
│   └── 04-alertas-y-profugos/
│       └── spec.md                  # RF_5, RF_6, RF_7: Alertas en tiempo real y panel de fugas
└── changes/                         # Historial de propuestas y cambios arquitectónicos
    └── 001-arquitectura-integral-y-supabase/
        ├── proposal.md              # Qué se cambia y por qué
        ├── design.md                # Decisiones técnicas y de modelo de datos
        └── tasks.md                 # Lista de tareas de implementación y verificación
```

## Flujo de Trabajo para Nuevos Cambios

1. **Consultar `project.md` y `specs/`**: Antes de modificar modelos, vistas o lógica de mapa, leer la especificación del módulo correspondiente en `openspec/specs/`.
2. **Registrar propuesta en `changes/`**: Todo cambio estructural (nuevas tablas, nuevos endpoints o cambios de reglas de negocio) debe documentarse en una subcarpeta numerada dentro de `openspec/changes/` con:
   - `proposal.md`: Motivación y alcance.
   - `design.md`: Impacto en modelos GeoDjango, endpoints y UI.
   - `tasks.md`: Checklist de pasos.
3. **Implementar y Validar**: Ejecutar `python manage.py test` y verificar que se cumplan todos los escenarios (`Escenario: ...`) definidos en las especificaciones.
4. **Actualizar `specs/`**: Una vez completado el cambio, reflejar el comportamiento vigente en `openspec/specs/`.

