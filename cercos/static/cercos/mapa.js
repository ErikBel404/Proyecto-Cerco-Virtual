// =======================================================
// 1. INICIALIZACIÓN DEL MAPA BASE
// =======================================================
const COORDENADAS_CATAMARCA = [-28.4696, -65.7852];
const ZOOM_INICIAL = 14;

const mapa = L.map('visor-mapa', { zoomControl: true }).setView(COORDENADAS_CATAMARCA, ZOOM_INICIAL);

L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
   maxZoom: 18,
   attribution: 'Tiles © Esri'
}).addTo(mapa);

// Función para centrar la cámara en los cercos o en Catamarca
function enfocarCercos() {
   if (capaCercosExistentes && capaCercosExistentes.getLayers().length > 0) {
      mapa.flyToBounds(capaCercosExistentes.getBounds(), {
         padding: [50, 50],
         duration: 2 // animación suave de vuelo
      });
   } else {
      mapa.flyTo(COORDENADAS_CATAMARCA, ZOOM_INICIAL, { duration: 2 });
   }
}

// Botón flotante personalizado en Leaflet
const controlEnfoque = L.control({ position: 'topright' });
controlEnfoque.onAdd = function () {
   const contenedor = L.DomUtil.create('div', 'leaflet-bar');
   const boton = L.DomUtil.create('a', '', contenedor);
   boton.innerHTML = '🎯';
   boton.href = '#';
   boton.title = 'Enfocar cercos virtuales';
   boton.style.display = 'flex';
   boton.style.alignItems = 'center';
   boton.style.justifyContent = 'center';
   boton.style.fontSize = '16px';
   boton.style.width = '34px';
   boton.style.height = '34px';
   boton.style.backgroundColor = '#ffffff';
   boton.style.cursor = 'pointer';

   L.DomEvent.disableClickPropagation(boton);
   L.DomEvent.on(boton, 'click', function (e) {
      L.DomEvent.preventDefault(e);
      enfocarCercos();
   });

   return contenedor;
};
controlEnfoque.addTo(mapa);




// Capas y estado global
let capaCercosExistentes = L.featureGroup().addTo(mapa);
let listaCercosDatos = [];
let modoActual = 'general';
let colorElegido = '#2ecc71';

// Variables para Creación (RF_1)
let puntosDibujo = [];
let marcadoresVertices = [];
let lineaGuiaDinamica = null;
let poligonoCerrado = null;
let trazadoFinalizado = false;

// Variables para Modificación (RF_2)
let cercoEnEdicion = null;
let puntosEdicion = [];
let marcadoresEdicion = [];
let poligonoEdicionDinamico = null;

// Variables para Eliminación (RF_8)
let cercoParaEliminar = null;
let poligonoResaltadoEliminar = null;

// =======================================================
// 2. SEGURIDAD (CSRF) Y CARGA DE DATOS
// =======================================================
function obtenerTokenCsrf() {
   let valorCookie = null;
   if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
         const cookie = cookies[i].trim();
         if (cookie.startsWith('csrftoken=')) {
            valorCookie = decodeURIComponent(cookie.substring(10));
            break;
         }
      }
   }
   return valorCookie;
}
const tokenCsrf = obtenerTokenCsrf();

function cargarCercos() {
   fetch('/api/cercos/')
      .then(respuesta => respuesta.json())
      .then(datosGeoJson => {
         listaCercosDatos = datosGeoJson.features;
         dibujarCercosEnMapa();
         poblarListaModificacion();
      })
      .catch(error => console.error('Error al cargar cercos:', error));
}

function dibujarCercosEnMapa() {
   capaCercosExistentes.clearLayers();

   listaCercosDatos.forEach(elemento => {
      // Ignorar en la capa general el cerco que está en proceso de eliminación
      if (cercoParaEliminar && elemento.properties.id === cercoParaEliminar.properties.id) {
         return;
      }

      // Ignorar en la capa general el cerco que se está editando activamente
      if (cercoEnEdicion && elemento.properties.id === cercoEnEdicion.properties.id) {
         return;
      }


      const coordenadas = elemento.geometry.coordinates[0].map(coord => [coord[1], coord[0]]);
      const color = elemento.properties.color || '#2ecc71';

      const poligono = L.polygon(coordenadas, {
         color: color,
         fillColor: color,
         fillOpacity: 0.35,
         weight: 2
      }).addTo(capaCercosExistentes);

      poligono.bindTooltip(`<strong>${elemento.properties.nombre}</strong>`, {
         permanent: true,
         direction: 'center',
         className: 'text-xs font-semibold px-2 py-1 rounded shadow-sm border border-slate-300'
      });

      poligono.idCerco = elemento.properties.id;
   });

   if (listaCercosDatos.length > 0 && modoActual === 'general') {
      mapa.fitBounds(capaCercosExistentes.getBounds(), { padding: [40, 40] });
   }
}

// =======================================================
// 3. NAVEGACIÓN Y CONTROL DE PANELES
// =======================================================
function cambiarModo(nuevoModo) {
   modoActual = nuevoModo;

   document.querySelectorAll('.vista-panel').forEach(panel => {
      panel.classList.add('hidden');
      panel.classList.remove('flex');
   });

   const panelActivo = document.getElementById(`panel-${nuevoModo}`);
   if (panelActivo) {
      panelActivo.classList.remove('hidden');
      panelActivo.classList.add('flex');
   }

   // Limpieza de estados anteriores
   limpiarTrazadoCreacion();
   limpiarEdicion();
   limpiarEliminacion();

   if (nuevoModo === 'crear') {
      document.getElementById('campo-nuevo-nombre').value = '';
      trazadoFinalizado = false;
      mapa.getContainer().style.cursor = 'crosshair';
   } else if (nuevoModo === 'modificar') {
      mapa.getContainer().style.cursor = '';
      const buscador = document.getElementById('campo-buscar-modificar');
      if (buscador) buscador.value = '';
      poblarListaModificacion();
      dibujarCercosEnMapa();
   } else if (nuevoModo === 'eliminar') {
      mapa.getContainer().style.cursor = '';
      // AQUÍ: Se genera el listado de tarjetas de cercos para eliminar
      poblarListaEliminar();
      dibujarCercosEnMapa();
   } else {
      mapa.getContainer().style.cursor = '';
      dibujarCercosEnMapa();
   }
}

function cancelarOperacion() {
   cambiarModo('general');
   cargarCercos();
}

function elegirColor(elemento) {
   document.querySelectorAll('.circulo-color').forEach(circulo => {
      circulo.classList.remove('scale-125', 'ring-2', 'ring-slate-800');
   });
   elemento.classList.add('scale-125', 'ring-2', 'ring-slate-800');
   colorElegido = elemento.getAttribute('data-color');

   if (poligonoCerrado) {
      poligonoCerrado.setStyle({ color: colorElegido, fillColor: colorElegido });
   }
}

// =======================================================
// 4. CREACIÓN DE CERCO (RF_1)
// =======================================================
mapa.on('click', function (evento) {
   if (modoActual !== 'crear' || trazadoFinalizado) return;

   const puntoNuevo = [evento.latlng.lat, evento.latlng.lng];
   puntosDibujo.push(puntoNuevo);

   const marcador = L.circleMarker(puntoNuevo, {
      radius: 6,
      color: '#1e293b',
      fillColor: '#ffffff',
      fillOpacity: 1,
      weight: 2
   }).addTo(mapa);

   marcadoresVertices.push(marcador);
});

mapa.on('mousemove', function (evento) {
   if (modoActual !== 'crear' || trazadoFinalizado || puntosDibujo.length === 0) return;

   const posicionCursor = [evento.latlng.lat, evento.latlng.lng];

   if (lineaGuiaDinamica) {
      mapa.removeLayer(lineaGuiaDinamica);
   }

   const trayecto = [...puntosDibujo, posicionCursor, puntosDibujo[0]];

   lineaGuiaDinamica = L.polyline(trayecto, {
      color: colorElegido,
      weight: 2,
      dashArray: '5, 5',
      opacity: 0.85
   }).addTo(mapa);
});

mapa.on('contextmenu', function (evento) {
   if (modoActual !== 'crear') return;
   L.DomEvent.preventDefault(evento);

   if (trazadoFinalizado) return;

   if (puntosDibujo.length <= 2) {
      alert('Debe marcar al menos 3 vértices antes de cerrar el cerco.');
      return;
   }

   trazadoFinalizado = true;

   if (lineaGuiaDinamica) {
      mapa.removeLayer(lineaGuiaDinamica);
      lineaGuiaDinamica = null;
   }

   poligonoCerrado = L.polygon(puntosDibujo, {
      color: colorElegido,
      fillColor: colorElegido,
      fillOpacity: 0.35,
      weight: 2
   }).addTo(mapa);

   mapa.getContainer().style.cursor = 'default';
});

function guardarNuevoCerco() {
   const nombreLote = document.getElementById('campo-nuevo-nombre').value.trim();

   if (!nombreLote) {
      alert('Debe indicar un nombre para el lote.');
      return;
   }
   if (puntosDibujo.length <= 2) {
      alert('Debe trazar al menos 3 vértices en el mapa.');
      return;
   }

   const coordenadasGeoJson = puntosDibujo.map(punto => [punto[1], punto[0]]);
   coordenadasGeoJson.push(coordenadasGeoJson[0]);

   const cargaUtil = {
      nombre: nombreLote,
      color: colorElegido,
      geometria: {
         type: 'Polygon',
         coordinates: [coordenadasGeoJson]
      }
   };

   fetch('/api/cercos/crear/', {
      method: 'POST',
      headers: {
         'Content-Type': 'application/json',
         'X-CSRFToken': tokenCsrf
      },
      body: JSON.stringify(cargaUtil)
   })
      .then(respuesta => respuesta.json())
      .then(resultado => {
         if (resultado.estado === 'exito') {
            alert(resultado.mensaje);
            cambiarModo('general');
            cargarCercos();
         } else {
            alert('Error: ' + resultado.mensaje);
         }
      })
      .catch(error => {
         console.error('Error al registrar el cerco:', error);
         alert('Error al conectar con el servidor.');
      });
}

function limpiarTrazadoCreacion() {
   puntosDibujo = [];
   trazadoFinalizado = false;

   marcadoresVertices.forEach(marcador => mapa.removeLayer(marcador));
   marcadoresVertices = [];

   if (lineaGuiaDinamica) {
      mapa.removeLayer(lineaGuiaDinamica);
      lineaGuiaDinamica = null;
   }
   if (poligonoCerrado) {
      mapa.removeLayer(poligonoCerrado);
      poligonoCerrado = null;
   }
}

// =======================================================
// 5. MODIFICACIÓN DE CERCO (RF_2)
// =======================================================

// A. Llenar el listado de tarjetas en el panel lateral
// A. Llenar el listado de tarjetas con soporte de filtro de búsqueda
function poblarListaModificacion(filtroTexto = '') {
   const contenedor = document.getElementById('contenedor-lista-modificar');
   if (!contenedor) return;

   contenedor.innerHTML = '';

   if (listaCercosDatos.length === 0) {
      contenedor.innerHTML = '<p class="text-xs text-slate-400 py-2">No hay cercos registrados aún.</p>';
      return;
   }

   // Filtrar ignorando mayúsculas, minúsculas y espacios sobrantes
   const cercosFiltrados = listaCercosDatos.filter(cerco => {
      const nombre = cerco.properties.nombre.toLowerCase();
      return nombre.includes(filtroTexto.toLowerCase().trim());
   });

   if (cercosFiltrados.length === 0) {
      contenedor.innerHTML = '<p class="text-xs text-slate-400 py-3 text-center">No se encontraron lotes con ese nombre.</p>';
      return;
   }

   cercosFiltrados.forEach(cerco => {
      const tarjeta = document.createElement('div');
      const estaSeleccionado = cercoEnEdicion && cercoEnEdicion.properties.id === cerco.properties.id;

      tarjeta.className = `tarjeta-elemento flex items-center justify-between p-3 border rounded-lg cursor-pointer transition-all text-sm ${estaSeleccionado
         ? 'border-campo-500 bg-campo-50 ring-1 ring-campo-500'
         : 'border-slate-200 hover:bg-campo-50/60 hover:border-campo-400'
         }`;

      tarjeta.innerHTML = `
            <div class="flex items-center gap-3">
                <span class="w-3.5 h-3.5 rounded-full" style="background:${cerco.properties.color}"></span>
                <span class="font-semibold text-slate-800">${cerco.properties.nombre}</span>
            </div>
            <span class="text-xs text-slate-400">✏️</span>
        `;
      tarjeta.onclick = () => iniciarModificacionCerco(cerco, tarjeta);
      contenedor.appendChild(tarjeta);
   });
}

// B. Evento en vivo del input de búsqueda
function filtrarListaModificacion() {
   const buscador = document.getElementById('campo-buscar-modificar');
   const valor = buscador ? buscador.value : '';
   poblarListaModificacion(valor);
}

// B. Activar la edición del cerco seleccionado
// A. Iniciar modificación (limpiar primero, asignar el cerco después)
function iniciarModificacionCerco(cerco, elementoTarjeta) {
   // 1. Limpiar cualquier edición previa antes de asignar el nuevo cerco
   limpiarEdicion();

   // 2. Asignar el cerco seleccionado
   cercoEnEdicion = cerco;

   // 3. Resaltar tarjeta en el panel lateral
   document.querySelectorAll('#contenedor-lista-modificar .tarjeta-elemento').forEach(t => {
      t.classList.remove('border-campo-500', 'bg-campo-50', 'ring-1', 'ring-campo-500');
   });
   elementoTarjeta.classList.add('border-campo-500', 'bg-campo-50', 'ring-1', 'ring-campo-500');

   // 4. Mostrar campos de edición
   const grupoNombre = document.getElementById('grupo-editar-nombre');
   const campoNombre = document.getElementById('campo-editar-nombre');
   const avisoModificar = document.getElementById('aviso-modificar');
   const btnGuardar = document.getElementById('boton-guardar-cambios');
   const btnDescartar = document.getElementById('boton-descartar-cambios'); // Referencia al botón

   grupoNombre.classList.remove('hidden');
   grupoNombre.classList.add('flex');
   campoNombre.value = cerco.properties.nombre;

   avisoModificar.classList.remove('hidden');
   btnGuardar.classList.remove('hidden');
   if (btnDescartar) btnDescartar.classList.remove('hidden'); // Mostrar Descartar Cambios

   // 5. Cargar coordenadas: GeoJSON viene [longitud, latitud], Leaflet usa [latitud, longitud]
   const anilloCoordenadas = cerco.geometry.coordinates[0].slice(0, -1);
   puntosEdicion = anilloCoordenadas.map(coord => [coord[1], coord[0]]);

   // 6. Polígono interactivo en edición
   poligonoEdicionDinamico = L.polygon(puntosEdicion, {
      color: cerco.properties.color || '#2ecc71',
      fillColor: cerco.properties.color || '#2ecc71',
      fillOpacity: 0.4,
      weight: 2,
      dashArray: '4, 4'
   }).addTo(mapa);

   // Ocultar el cerco estático original para no duplicarlo visualmente
   dibujarCercosEnMapa();

   // 7. Colocar vértices arrastrables
   puntosEdicion.forEach((punto, indice) => {
      const marcador = L.marker(punto, {
         draggable: true,
         icon: L.divIcon({
            className: 'vertice-marcador',
            html: '<div class="w-3.5 h-3.5 bg-white border-2 border-slate-800 rounded-full shadow-md cursor-grab active:cursor-grabbing"></div>',
            iconSize: [14, 14],
            iconAnchor: [7, 7]
         })
      }).addTo(mapa);

      marcador.on('drag', function (evento) {
         const nuevaPos = evento.target.getLatLng();
         puntosEdicion[indice] = [nuevaPos.lat, nuevaPos.lng];
         poligonoEdicionDinamico.setLatLngs(puntosEdicion);
      });

      marcadoresEdicion.push(marcador);
   });

   mapa.fitBounds(poligonoEdicionDinamico.getBounds(), { padding: [60, 60] });
}

// B. Guardar modificación en la base de datos (PostGIS)
function guardarModificacion() {
   if (!cercoEnEdicion) {
      alert('Seleccione un cerco antes de guardar cambios.');
      return;
   }

   const nombreModificado = document.getElementById('campo-editar-nombre').value.trim();

   if (!nombreModificado) {
      alert('El nombre del lote no puede quedar vacío.');
      return;
   }

   if (puntosEdicion.length <= 2) {
      alert('El polígono debe conservar al menos 3 vértices.');
      return;
   }

   // Convertir a formato GeoJSON [longitud, latitud] cerrando el anillo
   const coordenadasGeoJson = puntosEdicion.map(punto => [punto[1], punto[0]]);
   coordenadasGeoJson.push(coordenadasGeoJson[0]);

   const cargaUtil = {
      nombre: nombreModificado,
      color: cercoEnEdicion.properties.color,
      geometria: {
         type: 'Polygon',
         coordinates: [coordenadasGeoJson]
      }
   };

   fetch(`/api/cercos/${cercoEnEdicion.properties.id}/editar/`, {
      method: 'POST',
      headers: {
         'Content-Type': 'application/json',
         'X-CSRFToken': tokenCsrf
      },
      body: JSON.stringify(cargaUtil)
   })
      .then(async respuesta => {
         const datos = await respuesta.json();
         if (!respuesta.ok || datos.estado !== 'exito') {
            throw new Error(datos.mensaje || 'Error en el servidor');
         }
         return datos;
      })
      .then(resultado => {
         alert(resultado.mensaje);

         // 1. Limpia los marcadores de arrastre y oculta los campos de edición
         descartarModificacion();

         // 2. Consulta a la API para traer la nueva geometría desde PostGIS y redibujar el mapa en vivo
         cargarCercos();
      })
      .catch(error => {
         console.error('Error al guardar modificación:', error);
         alert('No se pudo guardar la modificación: ' + error.message);
      });
}

// C. Cancelar o restaurar la vista
// Cancela la edición activa y regresa a la lista de selección de lotes
function descartarModificacion() {
   // 1. Quitar los vértices interactivos y el polígono elástico
   limpiarEdicion();

   // 2. Ocultar los campos de edición (nombre, aviso y botones)
   const grupoNombre = document.getElementById('grupo-editar-nombre');
   const avisoModificar = document.getElementById('aviso-modificar');
   const btnGuardar = document.getElementById('boton-guardar-cambios');
   const btnDescartar = document.getElementById('boton-descartar-cambios'); // Referencia al botón

   if (grupoNombre) {
      grupoNombre.classList.add('hidden');
      grupoNombre.classList.remove('flex');
   }
   if (avisoModificar) avisoModificar.classList.add('hidden');
   if (btnGuardar) btnGuardar.classList.add('hidden');
   if (btnDescartar) btnDescartar.classList.add('hidden'); // Volver a ocultar Descartar

   // 3. Desmarcar cualquier tarjeta seleccionada en la lista
   document.querySelectorAll('#contenedor-lista-modificar .tarjeta-elemento').forEach(tarjeta => {
      tarjeta.classList.remove('border-campo-500', 'bg-campo-50', 'ring-1', 'ring-campo-500');
   });

   // 4. Redibujar el cerco original en el mapa con sus dimensiones intactas
   dibujarCercosEnMapa();
}

// Función exclusiva para el botón superior "← Volver al menú"
function volverAlMenu() {
   descartarModificacion();
   cambiarModo('general');
   cargarCercos();
}

// D. Limpieza de elementos gráficos de edición
function limpiarEdicion() {
   marcadoresEdicion.forEach(m => mapa.removeLayer(m));
   marcadoresEdicion = [];

   if (poligonoEdicionDinamico) {
      mapa.removeLayer(poligonoEdicionDinamico);
      poligonoEdicionDinamico = null;
   }

   cercoEnEdicion = null;
   puntosEdicion = [];
}

// =======================================================
// ELIMINACIÓN DE CERCO (RF_8)
// =======================================================

// A. Llenar la lista de tarjetas en el panel lateral
function poblarListaEliminar() {
   const contenedor = document.getElementById('contenedor-lista-eliminar');
   if (!contenedor) return;

   contenedor.innerHTML = '';

   if (!listaCercosDatos || listaCercosDatos.length === 0) {
      contenedor.innerHTML = '<p class="text-xs text-slate-400 py-3 text-center">No hay cercos registrados aún.</p>';
      return;
   }

   listaCercosDatos.forEach(cerco => {
      const tarjeta = document.createElement('div');
      const estaSeleccionado = cercoParaEliminar && cercoParaEliminar.properties.id === cerco.properties.id;

      tarjeta.className = `tarjeta-elemento flex items-center justify-between p-3 border rounded-lg cursor-pointer transition-all text-sm ${estaSeleccionado
         ? 'border-red-500 bg-red-50 ring-1 ring-red-500'
         : 'border-slate-200 hover:bg-red-50/50 hover:border-red-400'
         }`;

      tarjeta.innerHTML = `
            <div class="flex items-center gap-3">
                <span class="w-3.5 h-3.5 rounded-full" style="background:${cerco.properties.color}"></span>
                <span class="font-semibold text-slate-800">${cerco.properties.nombre}</span>
            </div>
            <span class="text-xs text-red-500">🗑️</span>
        `;

      tarjeta.onclick = () => seleccionarCercoParaEliminar(cerco, tarjeta);
      contenedor.appendChild(tarjeta);
   });
}

// B. Seleccionar el cerco a borrar y resaltarlo en rojo
function seleccionarCercoParaEliminar(cerco, elementoTarjeta) {
   limpiarEliminacionGrafica();

   cercoParaEliminar = cerco;

   // Resaltar visualmente la tarjeta en el panel
   document.querySelectorAll('#contenedor-lista-eliminar .tarjeta-elemento').forEach(t => {
      t.classList.remove('border-red-500', 'bg-red-50', 'ring-1', 'ring-red-500');
   });
   elementoTarjeta.classList.add('border-red-500', 'bg-red-50', 'ring-1', 'ring-red-500');

   // Mostrar el aviso de advertencia y ambos botones de acción
   const avisoEliminar = document.getElementById('aviso-eliminar');
   const btnConfirmar = document.getElementById('boton-confirmar-eliminar');
   const btnCancelar = document.getElementById('boton-cancelar-eliminar'); // Referencia al botón

   if (avisoEliminar) avisoEliminar.classList.remove('hidden');
   if (btnConfirmar) btnConfirmar.classList.remove('hidden');
   if (btnCancelar) btnCancelar.classList.remove('hidden'); // Mostrar Cancelar

   // Ocultar el polígono verde original y dibujar el rojo punteado
   dibujarCercosEnMapa();

   const coordenadas = cerco.geometry.coordinates[0].map(coord => [coord[1], coord[0]]);
   poligonoResaltadoEliminar = L.polygon(coordenadas, {
      color: '#dc2626',
      fillColor: '#ef4444',
      fillOpacity: 0.45,
      weight: 3,
      dashArray: '5, 5'
   }).addTo(mapa);

   mapa.fitBounds(poligonoResaltadoEliminar.getBounds(), { padding: [60, 60] });
}

// C. Enviar la petición POST a Django
function ejecutarEliminacion() {
   if (!cercoParaEliminar) {
      alert('Debe seleccionar un lote para eliminar.');
      return;
   }

   const idCerco = cercoParaEliminar.properties.id;

   fetch(`/api/cercos/${idCerco}/eliminar/`, {
      method: 'POST',
      headers: {
         'Content-Type': 'application/json',
         'X-CSRFToken': tokenCsrf
      }
   })
      .then(async respuesta => {
         const datos = await respuesta.json();
         if (!respuesta.ok || datos.estado !== 'exito') {
            throw new Error(datos.mensaje || 'Error al eliminar');
         }
         return datos;
      })
      .then(resultado => {
         alert(resultado.mensaje);

         // 1. Limpiar la selección y el polígono resaltado
         limpiarEliminacion();

         // 2. Volver a consultar la base de datos sin salir de la pantalla de eliminar
         fetch('/api/cercos/')
            .then(respuesta => respuesta.json())
            .then(datosGeoJson => {
               listaCercosDatos = datosGeoJson.features;
               dibujarCercosEnMapa();
               poblarListaEliminar(); // Actualiza la lista sin el cerco borrado
            })
            .catch(err => console.error('Error al actualizar datos:', err));
      })
      .catch(error => {
         console.error('Error al eliminar cerco:', error);
         alert('No se pudo eliminar el cerco: ' + error.message);
      });
}

// Cancela la selección actual y permanece en la lista de eliminación
function cancelarEliminacion() {
   limpiarEliminacion();
   dibujarCercosEnMapa();
}

// D. Funciones de limpieza
function limpiarEliminacionGrafica() {
   if (poligonoResaltadoEliminar) {
      mapa.removeLayer(poligonoResaltadoEliminar);
      poligonoResaltadoEliminar = null;
   }
}

function limpiarEliminacion() {
   limpiarEliminacionGrafica();
   cercoParaEliminar = null;

   const avisoEliminar = document.getElementById('aviso-eliminar');
   const btnConfirmar = document.getElementById('boton-confirmar-eliminar');
   const btnCancelar = document.getElementById('boton-cancelar-eliminar'); // Referencia al botón

   if (avisoEliminar) avisoEliminar.classList.add('hidden');
   if (btnConfirmar) btnConfirmar.classList.add('hidden');
   if (btnCancelar) btnCancelar.classList.add('hidden'); // Ocultar Cancelar

   document.querySelectorAll('#contenedor-lista-eliminar .tarjeta-elemento').forEach(t => {
      t.classList.remove('border-red-500', 'bg-red-50', 'ring-1', 'ring-red-500');
   });
}

// =======================================================
// 7. INICIALIZACIÓN
// =======================================================
cargarCercos();