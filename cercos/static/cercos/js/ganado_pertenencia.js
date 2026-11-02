/**
 * ============================================================================
 * MÓDULO 3: GESTIÓN DE GANADO Y PERTENENCIA A CERCOS (RF-08, RF-09, RF-10)
 * Archivo: cercos/static/cercos/js/ganado_pertenencia.js
 * ============================================================================
 * ¿QUÉ HACE ESTE ARCHIVO?
 * 1. Dibuja cada animal (`🐄`) sobre el mapa satelital (verde = dentro del lote,
 *    rojo pulsante = fuera del lote, gris = sin cerco asignado).
 * 2. Renderiza las tarjetas de ganado y sus filtros de búsqueda en el panel lateral.
 * 3. Ejecuta las operaciones de Asignar Cerco (RF-08), Cambiar Cerco (RF-09) y
 *    Desvincular de Cerco (RF-10) con protección anti-doble-clic.
 * 4. Permite crear o eliminar animales de prueba cuando está activo el
 *    Modo Simulación.
 * ============================================================================
 */


// ============================================================================
// 1. RENDERIZADO DE MARCADORES DE ANIMALES EN EL MAPA
// ============================================================================

function dibujarAnimalesEnMapa() {
    capaAnimalesMapa.clearLayers();

    listaAnimalesDatos.forEach(animal => {
        if (animal.latitud === null || animal.longitud === null) return;

        const enFuga = animal.estado_fuga;
        const sinCerco = !animal.cerco_id;

        let claseColor = 'bg-emerald-600 border-white';
        if (enFuga) {
            claseColor = 'bg-red-600 border-yellow-300 marcador-fuga-pulso';
        } else if (sinCerco) {
            claseColor = 'bg-slate-600 border-white';
        }

        const iconoAnimal = L.divIcon({
            className: 'marcador-animal-custom',
            html: `
                <div class="w-8 h-8 rounded-full border-2 shadow-lg flex items-center justify-center text-sm ${claseColor}"
                     title="${escaparHtml(animal.nombre)} (${escaparHtml(animal.id_hardware)})">
                    🐄
                </div>
            `,
            iconSize: [32, 32],
            iconAnchor: [16, 16]
        });

        // En Modo Real (Node-RED), draggable es false para evitar mover vacas por accidente
        const marcador = L.marker([animal.latitud, animal.longitud], {
            icon: iconoAnimal,
            draggable: modoSimulacionActivo
        }).addTo(capaAnimalesMapa);

        const estadoBadge = enFuga
            ? `<span class="text-red-600 font-bold">🚨 FUERA DEL CERCO (${escaparHtml(animal.hora_fuga_corta || '')})</span>`
            : sinCerco
                ? `<span class="text-slate-500 font-semibold">⚪ Sin cerco asignado</span>`
                : `<span class="text-emerald-600 font-semibold">✅ Dentro de ${escaparHtml(animal.cerco_nombre)}</span>`;

        const piePopup = modoSimulacionActivo
            ? `<div class="text-[11px] text-amber-600 font-medium">🧪 Modo Simulación: Arrastre el ícono para probar GPS.</div>`
            : `<div class="text-[11px] text-slate-400">📡 Telemetría GPS (${escaparHtml(animal.fecha_ultima_posicion || 'En espera')}).</div>`;

        marcador.bindPopup(`
            <div class="text-xs leading-relaxed min-w-[190px]">
                <div class="font-bold text-slate-800 text-sm">${escaparHtml(animal.nombre)}</div>
                <div class="text-slate-500 mb-1">Collar: <code>${escaparHtml(animal.id_hardware)}</code> · ${escaparHtml(animal.especie)}</div>
                <div class="mb-1.5">${estadoBadge}</div>
                ${piePopup}
            </div>
        `);

        if (modoSimulacionActivo) {
            marcador.on('dragstart', function () {
                arrastrandoAnimal = true;
            });

            marcador.on('dragend', function (evento) {
                arrastrandoAnimal = false;
                const nuevaPos = evento.target.getLatLng();
                transmitirPosicionGps(animal.id, nuevaPos.lat, nuevaPos.lng);
            });
        }
    });
}


// ============================================================================
// 2. LISTADO DE GANADO Y FILTROS EN EL PANEL LATERAL
// ============================================================================

function actualizarSelectoresCercosGanado() {
    const selectFiltro = document.getElementById('filtro-cerco-ganado');
    const selectNuevo = document.getElementById('nuevo-animal-cerco');

    if (selectFiltro) {
        const valorActual = selectFiltro.value || 'todos';
        selectFiltro.innerHTML = `
            <option value="todos">📋 Todos los animales (${listaAnimalesDatos.length})</option>
            <option value="sin_cerco">⚪ Animales sin cerco asignado (RF-08)</option>
        `;

        listaCercosDatos.forEach(c => {
            const opt = document.createElement('option');
            opt.value = String(c.properties.id);
            opt.textContent = `🟢 Lote: ${c.properties.nombre}`;
            selectFiltro.appendChild(opt);
        });

        if ([...selectFiltro.options].some(o => o.value === valorActual)) {
            selectFiltro.value = valorActual;
        }
    }

    if (selectNuevo) {
        selectNuevo.innerHTML = '<option value="">-- Dejar sin cerco asignado inicialmente --</option>';

        listaCercosDatos.forEach(c => {
            const opt = document.createElement('option');
            opt.value = String(c.properties.id);
            opt.textContent = `Asignar a: ${c.properties.nombre}`;
            selectNuevo.appendChild(opt);
        });
    }
}

function renderizarListaGanado() {
    const contenedor = document.getElementById('contenedor-lista-ganado');
    if (!contenedor) return;

    const filtroCerco = (document.getElementById('filtro-cerco-ganado')?.value) || 'todos';
    const textoBusqueda = (document.getElementById('buscador-ganado')?.value || '').toLowerCase().trim();

    const filtrados = listaAnimalesDatos.filter(a => {
        if (filtroCerco === 'sin_cerco' && a.cerco_id !== null) return false;
        if (filtroCerco !== 'todos' && filtroCerco !== 'sin_cerco' && String(a.cerco_id) !== filtroCerco) return false;

        if (textoBusqueda) {
            const coincideId = a.id_hardware.toLowerCase().includes(textoBusqueda);
            const coincideNombre = a.nombre.toLowerCase().includes(textoBusqueda);
            return coincideId || coincideNombre;
        }
        return true;
    });

    if (filtroCerco !== 'todos' && filtroCerco !== 'sin_cerco') {
        const cercoObj = listaCercosDatos.find(c => String(c.properties.id) === filtroCerco);
        if (cercoObj) enfocarCercoIndividual(cercoObj);
    }

    if (filtrados.length === 0) {
        contenedor.innerHTML = `
            <div class="p-4 text-center text-xs text-slate-400 border border-dashed border-slate-200 rounded-lg">
                No hay animales que coincidan con el filtro seleccionado.
            </div>
        `;
        return;
    }

    contenedor.innerHTML = '';

    filtrados.forEach(animal => {
        const opcionesCercos = listaCercosDatos.map(c => {
            const seleccionado = c.properties.id === animal.cerco_id ? 'selected' : '';
            return `<option value="${c.properties.id}" ${seleccionado}>${escaparHtml(c.properties.nombre)}</option>`;
        }).join('');

        const badgeEstado = animal.estado_fuga
            ? `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-red-100 text-red-700 border border-red-300">🚨 En Fuga</span>`
            : animal.cerco_id
                ? `<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-800">✅ Seguro</span>`
                : `<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-100 text-slate-600">⚪ Sin Cerco</span>`;

        const card = document.createElement('div');
        card.className = `p-3 border rounded-lg flex flex-col gap-2 text-xs transition-all ${
            animal.estado_fuga ? 'border-red-300 bg-red-50/40' : 'border-slate-200 bg-white hover:border-campo-400'
        }`;

        card.innerHTML = `
            <div class="flex items-start justify-between gap-2">
                <div>
                    <div class="font-bold text-slate-800 flex items-center gap-1.5">
                        <span>🐄 ${escaparHtml(animal.nombre)}</span>
                    </div>
                    <div class="text-[11px] text-slate-500 mt-0.5">
                        Collar: <code class="font-semibold text-slate-700">${escaparHtml(animal.id_hardware)}</code> · ${escaparHtml(animal.especie)}
                    </div>
                </div>
                <div class="flex items-center gap-1">
                    ${badgeEstado}
                    ${animal.latitud !== null ? `<button onclick="enfocarAnimalEnMapa(${animal.id})" title="Enfocar en mapa" class="p-1 hover:bg-slate-100 rounded">🎯</button>` : ''}
                    ${modoSimulacionActivo ? `<button onclick="eliminarAnimalRegistrado(${animal.id}, '${escaparHtml(animal.id_hardware)}')" title="Eliminar animal de prueba" class="p-1 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded">🗑️</button>` : ''}
                </div>
            </div>

            <!-- Controles de Asignación (RF-08), Reasignación (RF-09) y Desvinculación (RF-10) -->
            <div class="flex items-center gap-1.5 pt-2 border-t border-slate-100">
                <select id="select-cerco-animal-${animal.id}" class="flex-1 px-2 py-1 text-xs border border-slate-300 rounded bg-white focus:outline-none focus:border-campo-500">
                    <option value="">-- Seleccionar lote --</option>
                    ${opcionesCercos}
                </select>
                <button id="btn-asignar-animal-${animal.id}" onclick="ejecutarAsignacionCerco(${animal.id})" class="px-2.5 py-1 bg-campo-500 hover:bg-emerald-600 disabled:opacity-50 text-white font-semibold rounded text-[11px] transition-colors">
                    ${animal.cerco_id ? 'Cambiar' : 'Asignar'}
                </button>
                ${animal.cerco_id ? `
                    <button id="btn-quitar-animal-${animal.id}" onclick="ejecutarDesvinculacionCerco(${animal.id})" title="Desvincular de cerco (RF-10)" class="px-2 py-1 bg-amber-50 hover:bg-amber-100 disabled:opacity-50 text-amber-800 border border-amber-200 font-semibold rounded text-[11px] transition-colors">
                        Quitar
                    </button>
                ` : ''}
            </div>
        `;

        contenedor.appendChild(card);
    });
}


// ============================================================================
// 3. ALTA EN SIMULACIÓN Y OPERACIONES DE PERTENENCIA (CON ANTI-DOBLE-CLIC)
// ============================================================================

function alternarFormularioNuevoAnimal() {
    if (!modoSimulacionActivo) return;
    const form = document.getElementById('formulario-nuevo-animal');
    if (!form) return;

    form.classList.toggle('hidden');
    form.classList.toggle('flex');
}

function cerrarFormularioNuevoAnimal() {
    const form = document.getElementById('formulario-nuevo-animal');
    if (form) {
        form.classList.add('hidden');
        form.classList.remove('flex');
    }
}

/**
 * Crea un animal en Modo Simulación protegido con `ejecutarConBloqueo`
 * para que un doble clic nunca dispare dos altas simultáneas.
 */
function guardarNuevoAnimal() {
    if (!modoSimulacionActivo) {
        mostrarToast('El alta rápida desde el panel solo está habilitada en Modo Simulación.', 'error');
        return;
    }

    const idHardware = document.getElementById('nuevo-animal-hardware').value.trim();
    const nombre = document.getElementById('nuevo-animal-nombre').value.trim();
    const cercoId = document.getElementById('nuevo-animal-cerco').value;

    if (!idHardware || !nombre) {
        mostrarToast('Complete el ID del collar y el nombre del animal.', 'error');
        return;
    }

    ejecutarConBloqueo('guardar_animal', 'boton-guardar-nuevo-animal', () => {
        return peticionPostJson('/api/animales/crear/', {
            id_hardware: idHardware,
            nombre: nombre,
            especie: 'Bovino',
            cerco_id: cercoId ? parseInt(cercoId, 10) : null
        })
            .then(r => r.json())
            .then(res => {
                if (res.estado === 'exito') {
                    mostrarToast(res.mensaje, 'exito');
                    document.getElementById('nuevo-animal-hardware').value = '';
                    document.getElementById('nuevo-animal-nombre').value = '';
                    document.getElementById('nuevo-animal-cerco').value = '';
                    cerrarFormularioNuevoAnimal();
                    sincronizarTodo();
                } else {
                    mostrarToast(res.mensaje || 'Error al registrar animal.', 'error');
                }
            })
            .catch(() => mostrarToast('Error de conexión al registrar el animal.', 'error'));
    }, '⏳ Guardando animal...');
}

function ejecutarAsignacionCerco(idAnimal) {
    const selector = document.getElementById(`select-cerco-animal-${idAnimal}`);
    const cercoId = selector ? selector.value : '';

    if (!cercoId) {
        mostrarToast('Seleccione un cerco virtual en la lista desplegable.', 'error');
        return;
    }

    ejecutarConBloqueo(`asignar_${idAnimal}`, `btn-asignar-animal-${idAnimal}`, () => {
        return peticionPostJson(`/api/animales/${idAnimal}/asignar-cerco/`, { cerco_id: parseInt(cercoId, 10) })
            .then(async r => {
                const datos = await r.json();
                if (!r.ok || datos.estado !== 'exito') {
                    if (datos.codigo === 'cerco_no_disponible') sincronizarTodo();
                    throw new Error(datos.mensaje || 'Error al asignar cerco.');
                }
                return datos;
            })
            .then(res => {
                mostrarToast(res.mensaje, 'exito');
                if (res.alerta) {
                    mostrarToast(res.alerta.mensaje, 'alerta_fuga', '🚨 Animal Fuera del Lote Asignado');
                    reproducirSonidoAlerta();
                }
                sincronizarTodo();
            })
            .catch(err => mostrarToast(err.message, 'error'));
    }, '⏳');
}

function ejecutarDesvinculacionCerco(idAnimal) {
    if (!confirm('¿Confirmar desvinculación? El animal quedará sin cerco asignado y sin monitoreo espacial activo (RF-10).')) {
        return;
    }

    ejecutarConBloqueo(`quitar_${idAnimal}`, `btn-quitar-animal-${idAnimal}`, () => {
        return peticionPostJson(`/api/animales/${idAnimal}/desvincular-cerco/`)
            .then(r => r.json())
            .then(res => {
                if (res.estado === 'exito') {
                    mostrarToast(res.mensaje, 'info');
                    sincronizarTodo();
                } else {
                    mostrarToast(res.mensaje || 'Error al desvincular.', 'error');
                }
            })
            .catch(() => mostrarToast('Error de conexión al desvincular.', 'error'));
    }, '⏳');
}

function eliminarAnimalRegistrado(idAnimal, idHardware) {
    if (!confirm(`¿Seguro que desea eliminar permanentemente el animal ${idHardware} de la base de datos?`)) {
        return;
    }

    ejecutarConBloqueo(`eliminar_animal_${idAnimal}`, null, () => {
        return peticionPostJson(`/api/animales/${idAnimal}/eliminar/`)
            .then(r => r.json())
            .then(res => {
                if (res.estado === 'exito') {
                    mostrarToast(res.mensaje, 'info');
                    sincronizarTodo();
                } else {
                    mostrarToast(res.mensaje || 'Error al eliminar animal.', 'error');
                }
            })
            .catch(() => mostrarToast('Error de conexión al eliminar animal.', 'error'));
    });
}

function enfocarAnimalEnMapa(idAnimal) {
    const animal = listaAnimalesDatos.find(a => a.id === idAnimal);
    if (!animal || animal.latitud === null) return;

    if (animal.cerco_id) {
        const cerco = listaCercosDatos.find(c => c.properties.id === animal.cerco_id);
        if (cerco) {
            const coords = cerco.geometry.coordinates[0].map(c => [c[1], c[0]]);
            coords.push([animal.latitud, animal.longitud]);
            mapa.flyToBounds(L.latLngBounds(coords), { padding: [70, 70], duration: 1.2 });
            return;
        }
    }

    mapa.flyTo([animal.latitud, animal.longitud], 16, { duration: 1.2 });
}

