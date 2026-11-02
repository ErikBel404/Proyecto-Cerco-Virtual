# Especificación 01: Gestión de Cercos Virtuales (`RF_1`, `RF_2`, `RF_8`)

## Alcance
Define las reglas de negocio, validaciones topológicas y flujos de interfaz para crear, listar, modificar y eliminar perímetros geográficos (`CercoVirtual`) sobre el mapa satelital.

---

## Requisitos Cubiertos

### `RF_1` — Definición de Cerco Virtual (Crear)
El sistema DEBE permitir al usuario trazar sobre el mapa satelital los vértices de un polígono, asignarle un nombre identificatorio y un color hexadecimal, y persistirlo en PostGIS con `SRID 4326`.

#### Escenario 1.1: Creación exitosa de un cerco válido
- **Dado** que el operador activa el modo "Crear Cerco",
- **Cuando** ingresa un nombre válido (ej. `"Lote Norte"`), selecciona un color y marca al menos 3 vértices en el mapa cuyas líneas no se cruzan entre sí, y presiona "Guardar Cerco",
- **Entonces** el backend valida `geometria.geom_type == 'Polygon'` y `geometria.valid == True`, guarda el registro dentro de una transacción atómica (`transaction.atomic()`) y retorna HTTP 200 con el ID del nuevo cerco.

#### Escenario 1.2: Bloqueo por puntos insuficientes (Camino Alternativo 2)
- **Dado** que el operador intenta cerrar o guardar un cerco con menos de 3 vértices,
- **Entonces** el sistema bloquea la operación e informa que debe marcar al menos 3 vértices para conformar un área válida.

#### Escenario 1.3: Bloqueo por auto-intersección / cruce de líneas (Camino Alternativo 1)
- **Dado** que el operador traza un polígono cuyos segmentos se cruzan entre sí (auto-intersección),
- **Cuando** intenta guardar el cerco,
- **Entonces** el sistema detecta que la geometría no es válida (`not geometria.valid` en GEOS y validación de cruce de segmentos en JS) y rechaza el guardado con el mensaje: *"El perímetro no puede tener cruces de líneas (auto-intersección). Por favor, corrija el trazado."*

---

### `RF_2` — Modificación de Cerco Virtual (Editar)
El sistema DEBE permitir seleccionar un cerco existente, editar su nombre, su color y arrastrar sus vértices en el mapa (`Drag & Drop`), guardando las nuevas dimensiones en PostGIS.

#### Escenario 2.1: Edición exitosa de vértices, nombre o color
- **Dado** un cerco existente seleccionado en el panel de modificación,
- **Cuando** el operador arrastra sus vértices manteniendo una figura sin cruces, modifica el nombre o color y presiona "Guardar Cambios",
- **Entonces** el sistema actualiza el `PolygonField` en PostGIS y re-evalúa automáticamente la situación espacial de los animales asignados a dicho cerco.

#### Escenario 2.2: Reversión ante auto-intersección en edición (Camino Alternativo 1)
- **Dado** que el operador arrastra un vértice generando un cruce de líneas en el polígono,
- **Cuando** intenta guardar o soltar el vértice en posición inválida,
- **Entonces** el sistema advierte el error topológico, impide guardar la geometría corrupta y permite revertir a la última posición válida.

#### Escenario 2.3: Manejo de conflicto de concurrencia (Camino Alternativo 2)
- **Dado** que el operador está editando un cerco que fue eliminado simultáneamente en otra sesión,
- **Cuando** presiona "Guardar Cambios" y el servidor responde HTTP 404,
- **Entonces** el frontend informa el conflicto de sincronización, limpia el polígono en edición y recarga el listado actualizado desde la base de datos.

---

### `RF_8` — Eliminación de Cerco Virtual (Borrar)
El sistema DEBE permitir eliminar permanentemente un cerco virtual previa confirmación explícita, garantizando la integridad referencial del ganado vinculado.

#### Escenario 3.1: Eliminación con desvinculación segura de animales
- **Dado** un cerco virtual que tiene animales asignados,
- **Cuando** el operador selecciona el cerco, visualiza la advertencia de acción permanente y confirma la eliminación,
- **Entonces** el cerco se elimina de la base de datos y todos los animales que apuntaban a él pasan automáticamente a `cerco = NULL` (`Sin cerco asignado`) y `estado_fuga = False`, sin perder ningún registro de animal.

