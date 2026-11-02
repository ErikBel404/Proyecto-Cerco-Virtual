# Especificación 04: Emisión de Alertas y Centro de Monitoreo de Fugas (`RF_5`, `RF_6`, `RF_7`, `RNF_3`)

## Alcance
Define el subsistema de notificaciones ante incidentes de fuga, el control de frecuencia (*Rate Limiting* de 5 minutos) y el panel de visualización de animales prófugos.

---

## Requisitos Cubiertos

### `RF_5` — Emisión de Alertas con Control Anti-Spam (5 minutos)
Cuando `Procesar Ubicación` detecta que un animal está fuera de su cerco asignado, el sistema DEBE registrar el incidente en `AlertaFuga` y notificar visualmente al operador mediante un componente transversal (*Toast / Pop-up*), respetando una ventana de enfriamiento de **5 minutos** por animal.

#### Escenario 1.1: Disparo de nueva alerta de fuga
- **Dado** que un animal cruza el límite de su cerco y no tiene alertas emitidas en los últimos 5 minutos,
- **Cuando** se procesa su ubicación fuera del perímetro,
- **Entonces** se crea un registro en `AlertaFuga` con `id_hardware`, nombre del animal, nombre del cerco, coordenada exacta y `fecha_hora_salida`, y la interfaz despliega una notificación emergente (*Toast*) con alerta visual.

#### Escenario 1.2: Supresión silenciosa por alerta duplicada / Rate Limiting (Camino Alternativo 2)
- **Dado** que un animal sigue caminando fuera del cerco y el collar envía nuevas coordenadas cada pocos segundos,
- **Cuando** ha transcurrido menos de 5 minutos desde la última alerta emitida para ese mismo animal,
- **Entonces** el sistema actualiza la posición del animal en el mapa pero **suprime la creación de una nueva alerta repetida** para no saturar al operador.

#### Escenario 1.3: Persistencia para operador desconectado (Camino Alternativo 1)
- **Dado** que ocurre una fuga cuando ningún operador tiene el navegador abierto,
- **Cuando** el operador ingresa posteriormente a la aplicación,
- **Entonces** las alertas pendientes (`resuelta = False`) se cargan desde la base de datos y se muestran en el indicador superior de alertas y en el Centro de Monitoreo de Fugas.

---

### `RF_6` y `RF_7` — Listado de Animales Fuera de Límite y Detalle de Incidentes
El sistema DEBE proporcionar una vista dedicada (**"Alertas / Prófugos"**) que liste todos los animales cuyo estado actual sea `estado_fuga = True`, mostrando su identificador, el cerco vulnerado y la hora exacta de salida.

#### Escenario 2.1: Visualización y enfoque táctico de un animal prófugo
- **Dado** que existen animales con `estado_fuga = True`,
- **Cuando** el operador abre el panel de "Alertas / Prófugos" y hace clic sobre la tarjeta de un animal fugado,
- **Entonces** el mapa ejecuta una animación (`flyTo` / `fitBounds`) centrando la cámara entre el animal prófugo (marcador rojo pulsante) y el polígono del cerco del cual escapó.

#### Escenario 2.2: Estado vacío (Sin prófugos — Camino Alternativo 1)
- **Dado** que todos los animales monitoreados se encuentran dentro de sus respectivos cercos,
- **Cuando** el operador consulta la vista de "Alertas / Prófugos",
- **Entonces** el panel muestra el estado *"No hay animales fuera del cerco actualmente"*.

