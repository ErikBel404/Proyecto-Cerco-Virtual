/**
 * ============================================================================
 * MÓDULO 2: GESTIÓN DE CERCOS VIRTUALES (CREAR, MODIFICAR Y ELIMINAR)
 * Archivo: cercos/static/cercos/js/cercos_abm.js
 * ============================================================================
 * ¿QUÉ HACE ESTE ARCHIVO?
 * 1. Dibuja los cercos virtuales sobre el mapa satelital y actualiza la lista
 *    resumen de lotes registrados.
 * 2. Gestiona la Creación de Cercos (RF_1) con trazado de vértices y protección
 *    anti-doble-clic al guardar.
 * 3. Gestiona la Modificación de Cercos (RF_2) con arrastre de vértices y
 *    reversión automática si se cruzan las líneas.
 * 4. Gestiona la Eliminación de Cercos (RF_8) con confirmación y protección
 *    anti-doble-clic.
 * ============================================================================
 */


// ============================================================================
// 1. RENDERIZADO DE POLÍGONOS Y LISTA DE CERCOS EN EL MAPA
// ============================================================================

function dibujarCercosEnMapa(ajustarCamara = false) {
    capaCercosExistentes.clearLayers();

    listaCercosDatos.forEach(elemento => {
        if (cercoParaEliminar && elemento.properties.id === cercoParaEliminar.properties.id) return;
        if (cercoEnEdicion && elemento.properties.id === cercoEnEdicion.properties.id) return;

        // GeoJSON viene como [Longitud, Latitud] -> Leaflet requiere [Latitud, Longitud]
        const coordenadas = elemento.geometry.coordinates[0].map(coord => [coord[1], coord[0]]);
        const color = elemento.properties.color || '#2ecc71';

        const poligono = L.polygon(coordenadas, {
            color: color,
            fillColor: color,
            fillOpacity: 0.32,
            weight: 2.5
        }).addTo(capaCercosExistentes);

        const nombreSeguro = escaparHtml(elemento.properties.nombre);
        const hectareas = elemento.properties.area_hectareas
            ? ` · ${elemento.properties.area_hectareas} ha`
            : '';

        poligono.bindTooltip(
            `<strong>${nombreSeguro}</strong><span class="text-slate-500">${hectareas}</span>`,
            {
                permanent: true,
                direction: 'center',
                className: 'text-xs font-semibold px-2 py-0.5 rounded shadow-sm border border-slate-300 bg-white/95'
            }
        );

        poligono.idCerco = elemento.properties.id;
    });

    if (ajustarCamara && listaCercosDatos.length > 0 && modoActual === 'general') {
        mapa.fitBounds(capaCercosExistentes.getBounds(), { padding: [45, 45] });
    }
}

function renderizarResumenCercosGeneral() {
    const contenedor = document.getElementById('lista-resumen-cercos');
    const contador = document.getElementById('contador-lotes-general');
    if (!contenedor) return;

    if (contador) {
        contador.textContent = `${listaCercosDatos.length} ${listaCercosDatos.length === 1 ? 'lote' : 'lotes'}`;
    }

    if (listaCercosDatos.length === 0) {
        const ayudaExtra = modoSimulacionActivo
            ? 'Use <strong>Crear Cerco</strong> o el botón superior <strong>⚡ Cargar Demo</strong>.'
            : 'Use <strong>Crear Cerco</strong> para delimitar un potrero real en el campo.';

        contenedor.innerHTML = `
            <div class="p-3 bg-slate-50 border border-dashed border-slate-200 rounded-lg text-xs text-slate-500 text-center">
                No hay cercos registrados aún. ${ayudaExtra}
            </div>
        `;
        return;
    }

    contenedor.innerHTML = '';

    listaCercosDatos.forEach(cerco => {
        const props = cerco.properties;
        const badgeCritico = props.alerta_continua
            ? '<span class="text-[10px] text-red-600 font-bold" title="Perímetro Crítico (Alerta Continua)">🚨</span>'
            : '';

        const item = document.createElement('div');
        item.className = 'flex items-center justify-between p-2.5 border border-slate-200 rounded-lg hover:border-campo-400 hover:bg-slate-50 cursor-pointer transition-all text-xs';
        item.innerHTML = `
            <div class="flex items-center gap-2.5">
                <span class="w-3 h-3 rounded-full shrink-0" style="background:${escaparHtml(props.color)}"></span>
                <div>
                    <div class="font-semibold text-slate-800">${escaparHtml(props.nombre)} ${badgeCritico}</div>
                    <div class="text-[11px] text-slate-400">${props.area_hectareas || 0} ha · ${props.total_animales || 0} animales</div>
                </div>
            </div>
            <span class="text-slate-400 hover:text-campo-500" title="Enfocar lote en el mapa">🎯</span>
        `;

        item.onclick = () => enfocarCercoIndividual(cerco);
        contenedor.appendChild(item);
    });
}

function enfocarCercoIndividual(cercoFeature) {
    const coords = cercoFeature.geometry.coordinates[0].map(c => [c[1], c[0]]);
    const bounds = L.latLngBounds(coords);
    mapa.flyToBounds(bounds, { padding: [60, 60], duration: 1.2 });
}

function seleccionarColorPaleta(elemento, selectorClase, esEdicion = false) {
    document.querySelectorAll(selectorClase).forEach(circulo => {
        circulo.classList.remove('scale-125', 'ring-2', 'ring-slate-800');
    });

    elemento.classList.add('scale-125', 'ring-2', 'ring-slate-800');
    const color = elemento.getAttribute('data-color');

    if (esEdicion) {
        colorEdicionElegido = color;
        if (poligonoEdicionDinamico) {
            poligonoEdicionDinamico.setStyle({ color: color, fillColor: color });
        }
    } else {
        colorElegido = color;
        if (poligonoCerrado) {
            poligonoCerrado.setStyle({ color: color, fillColor: color });
        }
    }
}

function elegirColor(elemento) {
    seleccionarColorPaleta(elemento, '.circulo-color', false);
}

function elegirColorEdicion(elemento) {
    seleccionarColorPaleta(elemento, '.circulo-color-editar', true);
}


// ============================================================================
// 2. CREACIÓN DE CERCO VIRTUAL (RF_1) E INTERACCIÓN EN EL MAPA
// ============================================================================

mapa.on('click', function (evento) {
    // Caso A: Si el usuario está en la pestaña Simulador GPS, el clic envía telemetría
    if (seccionActual === 'telemetria') {
        const selectAnimal = document.getElementById('telemetria-select-animal');
        const idAnimal = selectAnimal ? selectAnimal.value : '';

        if (!idAnimal) {
            mostrarToast('Seleccione primero un animal en el panel izquierdo para simular su movimiento GPS.', 'info');
            return;
        }

        document.getElementById('telemetria-input-lat').value = evento.latlng.lat.toFixed(6);
        document.getElementById('telemetria-input-lng').value = evento.latlng.lng.toFixed(6);
        transmitirPosicionGps(parseInt(idAnimal, 10), evento.latlng.lat, evento.latlng.lng);
        return;
    }

    // Caso B: Si el usuario está en modo Crear Cerco, cada clic agrega un vértice
    if (seccionActual !== 'cercos' || modoActual !== 'crear' || trazadoFinalizado) return;

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
    verificarAvisoTopologiaCrear();
});

mapa.on('mousemove', function (evento) {
    if (seccionActual !== 'cercos' || modoActual !== 'crear' || trazadoFinalizado || puntosDibujo.length === 0) {
        return;
    }

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
    if (seccionActual !== 'cercos' || modoActual !== 'crear') return;
    L.DomEvent.preventDefault(evento);

    if (trazadoFinalizado) return;

    if (puntosDibujo.length <= 2) {
        mostrarToast('Debe marcar al menos 3 vértices antes de cerrar el cerco.', 'error');
        return;
    }

    if (poligonoTieneAutoInterseccion(puntosDibujo)) {
        mostrarToast('El perímetro tiene cruces de líneas. Use "Deshacer último vértice" para corregirlo.', 'error');
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

function verificarAvisoTopologiaCrear() {
    const alertaBox = document.getElementById('alerta-topologia-crear');
    if (!alertaBox) return;

    if (puntosDibujo.length >= 4 && poligonoTieneAutoInterseccion(puntosDibujo)) {
        alertaBox.classList.remove('hidden');
    } else {
        alertaBox.classList.add('hidden');
    }
}

function deshacerUltimoVertice() {
    if (modoActual !== 'crear' || puntosDibujo.length === 0) return;

    trazadoFinalizado = false;

    if (poligonoCerrado) {
        mapa.removeLayer(poligonoCerrado);
        poligonoCerrado = null;
    }

    puntosDibujo.pop();
    const ultimoMarcador = marcadoresVertices.pop();
    if (ultimoMarcador) mapa.removeLayer(ultimoMarcador);

    if (lineaGuiaDinamica) {
        mapa.removeLayer(lineaGuiaDinamica);
        lineaGuiaDinamica = null;
    }

    mapa.getContainer().style.cursor = 'crosshair';
    verificarAvisoTopologiaCrear();
}

/**
 * Envía el nuevo cerco a Supabase protegido con `ejecutarConBloqueo`
 * para que un doble clic nunca cree dos registros iguales.
 */
function guardarNuevoCerco() {
    const nombreLote = document.getElementById('campo-nuevo-nombre').value.trim();

    if (!nombreLote) {
        mostrarToast('Debe indicar un nombre para el lote.', 'error');
        return;
    }

    if (puntosDibujo.length <= 2) {
        mostrarToast('Debe trazar al menos 3 vértices en el mapa.', 'error');
        return;
    }

    if (poligonoTieneAutoInterseccion(puntosDibujo)) {
        mostrarToast('El perímetro no puede tener cruces de líneas (auto-intersección).', 'error');
        return;
    }

    const coordenadasGeoJson = puntosDibujo.map(punto => [punto[1], punto[0]]);
    coordenadasGeoJson.push(coordenadasGeoJson[0]);

    const cargaUtil = {
        nombre: nombreLote,
        color: colorElegido,
        alerta_continua: Boolean(document.getElementById('campo-nuevo-alerta-continua')?.checked),
        geometria: {
            type: 'Polygon',
            coordinates: [coordenadasGeoJson]
        }
    };

    ejecutarConBloqueo('guardar_cerco', 'boton-guardar-nuevo-cerco', () => {
        return peticionPostJson('/api/cercos/crear/', cargaUtil)
            .then(respuesta => respuesta.json())
            .then(resultado => {
                if (resultado.estado === 'exito') {
                    mostrarToast(resultado.mensaje, 'exito');
                    cambiarModo('general');
                    cargarCercos(true);
                } else {
                    mostrarToast(resultado.mensaje || 'Error al guardar el cerco.', 'error');
                }
            })
            .catch(() => {
                mostrarToast('Error al guardar, verifique su conexión con el servidor.', 'error');
            });
    }, '⏳ Guardando cerco...');
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

    const alertaBox = document.getElementById('alerta-topologia-crear');
    if (alertaBox) alertaBox.classList.add('hidden');
}


// ============================================================================
// 3. MODIFICACIÓN DE CERCO VIRTUAL (RF_2)
// ============================================================================

function poblarListaModificacion(filtroTexto = '') {
    const contenedor = document.getElementById('contenedor-lista-modificar');
    if (!contenedor) return;

    contenedor.innerHTML = '';

    if (listaCercosDatos.length === 0) {
        contenedor.innerHTML = '<p class="text-xs text-slate-400 py-2">No hay cercos registrados aún.</p>';
        return;
    }

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

        tarjeta.className = `tarjeta-elemento flex items-center justify-between p-3 border rounded-lg cursor-pointer transition-all text-sm ${
            estaSeleccionado
                ? 'border-campo-500 bg-campo-50 ring-1 ring-campo-500'
                : 'border-slate-200 hover:bg-campo-50/60 hover:border-campo-400'
        }`;

        tarjeta.innerHTML = `
            <div class="flex items-center gap-3">
                <span class="w-3.5 h-3.5 rounded-full shrink-0" style="background:${escaparHtml(cerco.properties.color)}"></span>
                <span class="font-semibold text-slate-800">${escaparHtml(cerco.properties.nombre)}</span>
            </div>
            <span class="text-xs text-slate-400">✏️</span>
        `;

        tarjeta.onclick = () => iniciarModificacionCerco(cerco, tarjeta);
        contenedor.appendChild(tarjeta);
    });
}

function filtrarListaModificacion() {
    const buscador = document.getElementById('campo-buscar-modificar');
    const valor = buscador ? buscador.value : '';
    poblarListaModificacion(valor);
}

function iniciarModificacionCerco(cerco, elementoTarjeta) {
    limpiarEdicion();
    cercoEnEdicion = cerco;
    colorEdicionElegido = cerco.properties.color || '#2ecc71';

    document.querySelectorAll('#contenedor-lista-modificar .tarjeta-elemento').forEach(t => {
        t.classList.remove('border-campo-500', 'bg-campo-50', 'ring-1', 'ring-campo-500');
    });
    elementoTarjeta.classList.add('border-campo-500', 'bg-campo-50', 'ring-1', 'ring-campo-500');

    const grupoNombre = document.getElementById('grupo-editar-nombre');
    const campoNombre = document.getElementById('campo-editar-nombre');
    const avisoModificar = document.getElementById('aviso-modificar');
    const btnGuardar = document.getElementById('boton-guardar-cambios');
    const btnDescartar = document.getElementById('boton-descartar-cambios');

    grupoNombre.classList.remove('hidden');
    grupoNombre.classList.add('flex');
    campoNombre.value = cerco.properties.nombre;

    const checkCritico = document.getElementById('campo-editar-alerta-continua');
    if (checkCritico) checkCritico.checked = Boolean(cerco.properties.alerta_continua);

    document.querySelectorAll('.circulo-color-editar').forEach(circulo => {
        if (circulo.getAttribute('data-color') === colorEdicionElegido) {
            circulo.classList.add('scale-125', 'ring-2', 'ring-slate-800');
        } else {
            circulo.classList.remove('scale-125', 'ring-2', 'ring-slate-800');
        }
    });

    avisoModificar.classList.remove('hidden');
    btnGuardar.classList.remove('hidden');
    if (btnDescartar) btnDescartar.classList.remove('hidden');

    const anilloCoordenadas = cerco.geometry.coordinates[0].slice(0, -1);
    puntosEdicion = anilloCoordenadas.map(coord => [coord[1], coord[0]]);

    poligonoEdicionDinamico = L.polygon(puntosEdicion, {
        color: colorEdicionElegido,
        fillColor: colorEdicionElegido,
        fillOpacity: 0.4,
        weight: 2.5,
        dashArray: '4, 4'
    }).addTo(mapa);

    dibujarCercosEnMapa();

    puntosEdicion.forEach((punto, indice) => {
        let ultimaPosicionValida = [...punto];

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

        marcador.on('dragend', function () {
            if (poligonoTieneAutoInterseccion(puntosEdicion)) {
                mostrarToast('Cruce de líneas detectado: se revirtió el vértice a su última posición válida.', 'error');
                puntosEdicion[indice] = [...ultimaPosicionValida];
                marcador.setLatLng(ultimaPosicionValida);
                poligonoEdicionDinamico.setLatLngs(puntosEdicion);
            } else {
                ultimaPosicionValida = [...puntosEdicion[indice]];
            }
        });

        marcadoresEdicion.push(marcador);
    });

    mapa.fitBounds(poligonoEdicionDinamico.getBounds(), { padding: [60, 60] });
}

function guardarModificacion() {
    if (!cercoEnEdicion) {
        mostrarToast('Seleccione un cerco antes de guardar cambios.', 'error');
        return;
    }

    const nombreModificado = document.getElementById('campo-editar-nombre').value.trim();

    if (!nombreModificado) {
        mostrarToast('El nombre del lote no puede quedar vacío.', 'error');
        return;
    }

    if (puntosEdicion.length <= 2) {
        mostrarToast('El polígono debe conservar al menos 3 vértices.', 'error');
        return;
    }

    if (poligonoTieneAutoInterseccion(puntosEdicion)) {
        mostrarToast('El perímetro no puede tener cruces de líneas (auto-intersección).', 'error');
        return;
    }

    const coordenadasGeoJson = puntosEdicion.map(punto => [punto[1], punto[0]]);
    coordenadasGeoJson.push(coordenadasGeoJson[0]);

    const idCercoEditar = cercoEnEdicion.properties.id;
    const cargaUtil = {
        nombre: nombreModificado,
        color: colorEdicionElegido,
        alerta_continua: Boolean(document.getElementById('campo-editar-alerta-continua')?.checked),
        geometria: {
            type: 'Polygon',
            coordinates: [coordenadasGeoJson]
        }
    };

    ejecutarConBloqueo('editar_cerco', 'boton-guardar-cambios', () => {
        return peticionPostJson(`/api/cercos/${idCercoEditar}/editar/`, cargaUtil)
            .then(async respuesta => {
                const datos = await respuesta.json();
                if (respuesta.status === 404) {
                    descartarModificacion();
                    sincronizarTodo();
                    throw new Error(datos.mensaje || 'El cerco ya no existe en la base de datos.');
                }
                if (!respuesta.ok || datos.estado !== 'exito') {
                    throw new Error(datos.mensaje || 'Error en el servidor');
                }
                return datos;
            })
            .then(resultado => {
                mostrarToast(resultado.mensaje, 'exito');
                if (resultado.alertas_generadas && resultado.alertas_generadas.length > 0) {
                    resultado.alertas_generadas.forEach(al => {
                        mostrarToast(al.mensaje, 'alerta_fuga', '🚨 Alerta por Reajuste de Perímetro');
                    });
                    reproducirSonidoAlerta();
                }
                descartarModificacion();
                sincronizarTodo();
            })
            .catch(error => {
                mostrarToast(error.message, 'error');
            });
    }, '⏳ Guardando cambios...');
}

function descartarModificacion() {
    limpiarEdicion();

    const grupoNombre = document.getElementById('grupo-editar-nombre');
    const avisoModificar = document.getElementById('aviso-modificar');
    const btnGuardar = document.getElementById('boton-guardar-cambios');
    const btnDescartar = document.getElementById('boton-descartar-cambios');

    if (grupoNombre) {
        grupoNombre.classList.add('hidden');
        grupoNombre.classList.remove('flex');
    }
    if (avisoModificar) avisoModificar.classList.add('hidden');
    if (btnGuardar) btnGuardar.classList.add('hidden');
    if (btnDescartar) btnDescartar.classList.add('hidden');

    document.querySelectorAll('#contenedor-lista-modificar .tarjeta-elemento').forEach(tarjeta => {
        tarjeta.classList.remove('border-campo-500', 'bg-campo-50', 'ring-1', 'ring-campo-500');
    });

    dibujarCercosEnMapa();
}

function volverAlMenu() {
    descartarModificacion();
    cambiarModo('general');
    cargarCercos();
}

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


// ============================================================================
// 4. ELIMINACIÓN DE CERCO VIRTUAL (RF_8)
// ============================================================================

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

        tarjeta.className = `tarjeta-elemento flex items-center justify-between p-3 border rounded-lg cursor-pointer transition-all text-sm ${
            estaSeleccionado
                ? 'border-red-500 bg-red-50 ring-1 ring-red-500'
                : 'border-slate-200 hover:bg-red-50/50 hover:border-red-400'
        }`;

        tarjeta.innerHTML = `
            <div class="flex items-center gap-3">
                <span class="w-3.5 h-3.5 rounded-full shrink-0" style="background:${escaparHtml(cerco.properties.color)}"></span>
                <div>
                    <div class="font-semibold text-slate-800">${escaparHtml(cerco.properties.nombre)}</div>
                    <div class="text-[11px] text-slate-400">${cerco.properties.total_animales || 0} animales asignados</div>
                </div>
            </div>
            <span class="text-xs text-red-500">🗑️</span>
        `;

        tarjeta.onclick = () => seleccionarCercoParaEliminar(cerco, tarjeta);
        contenedor.appendChild(tarjeta);
    });
}

function seleccionarCercoParaEliminar(cerco, elementoTarjeta) {
    limpiarEliminacionGrafica();
    cercoParaEliminar = cerco;

    document.querySelectorAll('#contenedor-lista-eliminar .tarjeta-elemento').forEach(t => {
        t.classList.remove('border-red-500', 'bg-red-50', 'ring-1', 'ring-red-500');
    });
    elementoTarjeta.classList.add('border-red-500', 'bg-red-50', 'ring-1', 'ring-red-500');

    const avisoEliminar = document.getElementById('aviso-eliminar');
    const btnConfirmar = document.getElementById('boton-confirmar-eliminar');
    const btnCancelar = document.getElementById('boton-cancelar-eliminar');

    if (avisoEliminar) avisoEliminar.classList.remove('hidden');
    if (btnConfirmar) btnConfirmar.classList.remove('hidden');
    if (btnCancelar) btnCancelar.classList.remove('hidden');

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

function ejecutarEliminacion() {
    if (!cercoParaEliminar) {
        mostrarToast('Debe seleccionar un lote para eliminar.', 'error');
        return;
    }

    const idCerco = cercoParaEliminar.properties.id;

    ejecutarConBloqueo('eliminar_cerco', 'boton-confirmar-eliminar', () => {
        return peticionPostJson(`/api/cercos/${idCerco}/eliminar/`)
            .then(async respuesta => {
                const datos = await respuesta.json();
                if (!respuesta.ok || datos.estado !== 'exito') {
                    throw new Error(datos.mensaje || 'Error al eliminar');
                }
                return datos;
            })
            .then(resultado => {
                mostrarToast(resultado.mensaje, 'exito');
                limpiarEliminacion();
                sincronizarTodo();
            })
            .catch(error => {
                mostrarToast('No se pudo eliminar el cerco: ' + error.message, 'error');
                sincronizarTodo();
            });
    }, '⏳ Eliminando...');
}

function cancelarEliminacion() {
    limpiarEliminacion();
    dibujarCercosEnMapa();
}

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
    const btnCancelar = document.getElementById('boton-cancelar-eliminar');

    if (avisoEliminar) avisoEliminar.classList.add('hidden');
    if (btnConfirmar) btnConfirmar.classList.add('hidden');
    if (btnCancelar) btnCancelar.classList.add('hidden');

    document.querySelectorAll('#contenedor-lista-eliminar .tarjeta-elemento').forEach(t => {
        t.classList.remove('border-red-500', 'bg-red-50', 'ring-1', 'ring-red-500');
    });
}

