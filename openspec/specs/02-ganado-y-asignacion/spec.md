# Especificación 02: Gestión de Ganado y Asignación a Cercos (`RF-08`, `RF-09`, `RF-10`)

## Alcance
Define el modelo de datos de la entidad `Animal` (ganado monitoreado con collar GPS), su alta/baja para autonomía del sistema y las tres operaciones de pertenencia espacial a un `CercoVirtual`.

---

## Modelo de Dominio (`Animal`)
Cada animal registrado cuenta con:
- `id_hardware` (`CharField`, único): Identificador físico del collar o caravana electrónica (ej. `COLLAR-001`).
- `nombre` (`CharField`): Nombre o alias identificatorio del animal (ej. `"Vaca #104 - Holando"`).
- `especie` (`CharField`): Por defecto `"Bovino"` (pensado inicialmente para vacas, extensible a ovinos, equinos, caprinos).
- `cerco` (`ForeignKey` a `CercoVirtual`, `null=True, blank=True, on_delete=models.SET_NULL`): Cerco virtual al que está asignado actualmente.
- `ultima_posicion` (`PointField(srid=4326)`, `null=True, blank=True`): Última coordenada GPS reportada por el collar.
- `fecha_ultima_posicion` (`DateTimeField`, `null=True, blank=True`): Fecha y hora de la última lectura GPS.
- `estado_fuga` (`BooleanField`, `default=False`): Indica si el animal se encuentra actualmente fuera de los límites de su cerco asignado.
- `fecha_hora_fuga` (`DateTimeField`, `null=True, blank=True`): Marca de tiempo exacta en que se detectó la salida del perímetro.

---

## Requisitos Cubiertos

### `RF-08` — Asignar Animal a Cerco Virtual
El sistema DEBE permitir vincular un animal sin cerco (`cerco IS NULL`) a un cerco virtual existente.

#### Escenario 1.1: Asignación desde la lista "Animales sin cerco"
- **Dado** un animal registrado que no posee cerco asignado (`cerco = None`),
- **Cuando** el operador selecciona un cerco destino válido y confirma la asignación,
- **Entonces** el sistema actualiza `animal.cerco`, evalúa inmediatamente si su `ultima_posicion` (si existe) está dentro o fuera del nuevo cerco, y actualiza la interfaz.

#### Escenario 1.2: Cerco destino inexistente (Camino Alternativo 1)
- **Dado** que el cerco elegido fue eliminado antes de confirmar la asignación,
- **Entonces** el sistema aborta la operación con código 404, informa al operador y refresca la lista de cercos disponibles.

---

### `RF-09` — Modificar Pertenencia a Cerco (Reasignar)
El sistema DEBE permitir trasladar un animal desde su cerco virtual actual hacia un nuevo cerco virtual diferente.

#### Escenario 2.1: Reasignación exitosa a un nuevo lote
- **Dado** un animal actualmente asignado al `"Lote Norte"`,
- **Cuando** el operador elige reasignarlo al `"Lote Sur"` y confirma,
- **Entonces** el sistema actualiza `animal.cerco` al `"Lote Sur"`, limpia o recalcula su estado de fuga respecto al nuevo polígono y muestra confirmación visual.

#### Escenario 2.2: Prevención de reasignación redundante (Camino Alternativo 1)
- **Dado** un animal asignado al `"Lote Norte"`,
- **Cuando** el operador intenta reasignarlo al mismo `"Lote Norte"`,
- **Entonces** el sistema advierte que el animal ya pertenece a ese cerco y evita una escritura innecesaria en la base de datos.

---

### `RF-10` — Desvincular / Eliminar Pertenencia a Cerco
El sistema DEBE permitir quitar la asignación de cerco a un animal (`cerco = NULL`), dejándolo sin monitoreo espacial activo.

#### Escenario 3.1: Desvinculación con limpieza de estado de fuga
- **Dado** un animal asignado a un cerco (esté o no en estado de fuga),
- **Cuando** el operador presiona "Desvincular" y confirma la acción,
- **Entonces** el sistema establece `animal.cerco = None`, `animal.estado_fuga = False`, `animal.fecha_hora_fuga = None` y cierra las alertas activas pendientes de ese animal.

