/**
 * ============================================================================
 * MÓDULO 4: TELEMETRÍA GPS Y MONITOR DE ANIMALES PRÓFUGOS (RF_3 A RF_7)
 * Archivo: cercos/static/cercos/js/telemetria_y_alertas.js
 * ============================================================================
 * ¿QUÉ HACE ESTE ARCHIVO?
 * 1. Envía coordenadas GPS a PostGIS (`/api/telemetria/procesar/`) para evaluar
 *    `ST_Contains` y muestra el resultado en el panel de Telemetría.
 * 2. Renderiza el listado en tiempo real de Animales Prófugos (RF_6, RF_7) y la
 *    bitácora de incidentes activos (RF_5).
 * ============================================================================
 */


// ============================================================================
// 1. SIMULACIÓN E INGESTA DE TELEMETRÍA GPS (RF_3, RF_4)
// ============================================================================

function actualizarSelectorTelemetria() {
    const select = document.getElementById('telemetria-select-animal');
    if (!select) return;

    const valorPrevio = select.value;
    select.innerHTML = '<option value="">-- Seleccione un animal --</option>';

    listaAnimalesDatos.forEach(a => {
        const loteTxt = a.cerco_nombre ? `Lote: ${a.cerco_nombre}` : 'Sin cerco';
        const opt = document.createElement('option');
        opt.value = String(a.id);
        opt.textContent = `${a.id_hardware} — ${a.nombre} (${loteTxt})`;
        select.appendChild(opt);
    });

    if (valorPrevio && [...select.options].some(o => o.value === valorPrevio)) {
        select.value = valorPrevio;
    } else if (listaAnimalesDatos.length > 0 && !valorPrevio) {
        select.value = String(listaAnimalesDatos[0].id);
    }
}

function seleccionarAnimalTelemetria() {
    const select = document.getElementById('telemetria-select-animal');
    const idAnimal = select && select.value ? parseInt(select.value, 10) : null;
    if (!idAnimal) return;

    const animal = listaAnimalesDatos.find(a => a.id === idAnimal);
    if (animal && animal.latitud !== null) {
        document.getElementById('telemetria-input-lat').value = animal.latitud.toFixed(6);
        document.getElementById('telemetria-input-lng').value = animal.longitud.toFixed(6);
        enfocarAnimalEnMapa(animal.id);
    }
}

function enviarTelemetriaManual() {
    const select = document.getElementById('telemetria-select-animal');
    const idAnimal = select && select.value ? parseInt(select.value, 10) : null;
    const lat = parseFloat(document.getElementById('telemetria-input-lat').value);
    const lng = parseFloat(document.getElementById('telemetria-input-lng').value);

    if (!idAnimal) {
        mostrarToast('Seleccione un animal.', 'error');
        return;
    }

    if (isNaN(lat) || isNaN(lng)) {
        mostrarToast('Ingrese coordenadas numéricas válidas de latitud y longitud.', 'error');
        return;
    }

    transmitirPosicionGps(idAnimal, lat, lng);
}

/**
 * Envía una coordenada GPS a PostGIS y procesa la respuesta espacial (`ST_Contains`).
 */
function transmitirPosicionGps(idAnimal, latitud, longitud) {
    ejecutarConBloqueo(`telemetria_${idAnimal}`, null, () => {
        return peticionPostJson('/api/telemetria/procesar/', {
            animal_id: idAnimal,
            latitud: latitud,
            longitud: longitud
        })
            .then(r => r.json())
            .then(res => {
                if (res.estado !== 'exito') {
                    mostrarToast(res.mensaje || 'Error al procesar telemetría.', 'error');
                    return;
                }

                mostrarResultadoTelemetriaEnPanel(res);

                if (res.alerta_emitida && res.alerta) {
                    mostrarToast(res.alerta.mensaje, 'alerta_fuga', '🚨 ¡ALERTA DE FUGA DETECTADA!');
                    reproducirSonidoAlerta();
                } else if (!res.dentro_del_cerco && res.suprimida_por_antispam) {
                    mostrarToast(
                        `${res.animal.nombre} sigue fuera del cerco (notificación silenciada por ventana anti-spam de 5 min).`,
                        'info',
                        '🛡️ Control Anti-Spam Activo'
                    );
                } else {
                    mostrarToast(res.mensaje, 'exito');
                }

                sincronizarTodo();
            })
            .catch(() => mostrarToast('Error de conexión al transmitir telemetría.', 'error'));
    }, '⏳', 600);
}

function mostrarResultadoTelemetriaEnPanel(res) {
    const box = document.getElementById('resultado-telemetria-box');
    if (!box) return;

    box.classList.remove(
        'hidden',
        'bg-emerald-50',
        'border-emerald-300',
        'bg-red-50',
        'border-red-300',
        'bg-slate-50',
        'border-slate-300'
    );
    box.classList.add('flex');

    if (res.sin_cerco_asignado) {
        box.classList.add('bg-slate-50', 'border-slate-300', 'text-slate-700');
        box.innerHTML = `
            <strong>⚪ Posición actualizada (Sin Cerco Asignado)</strong>
            <span><code>${escaparHtml(res.animal.id_hardware)}</code> no tiene un lote asignado para evaluar contención.</span>
        `;
    } else if (res.dentro_del_cerco) {
        box.classList.add('bg-emerald-50', 'border-emerald-300', 'text-emerald-900');
        box.innerHTML = `
            <strong>✅ PostGIS ST_Contains = TRUE (Dentro del Cerco)</strong>
            <span><code>${escaparHtml(res.animal.nombre)}</code> está seguro dentro de <strong>${escaparHtml(res.animal.cerco_nombre)}</strong>.</span>
        `;
    } else {
        box.classList.add('bg-red-50', 'border-red-300', 'text-red-900');
        box.innerHTML = `
            <strong>🚨 PostGIS ST_Contains = FALSE (¡Fuera de Límite!)</strong>
            <span><code>${escaparHtml(res.animal.nombre)}</code> vulneró el perímetro de <strong>${escaparHtml(res.animal.cerco_nombre)}</strong>.</span>
        `;
    }
}


// ============================================================================
// 2. CENTRO DE MONITOREO DE FUGAS / ANIMALES PRÓFUGOS (RF_6, RF_7)
// ============================================================================

function renderizarPanelProfugos(animalesProfugos, alertasActivas) {
    const contenedorProfugos = document.getElementById('contenedor-lista-profugos');
    const contenedorAlertas = document.getElementById('contenedor-historial-alertas');
    const contadorPanel = document.getElementById('contador-profugos-panel');

    if (contadorPanel) {
        contadorPanel.textContent = animalesProfugos.length;
    }

    if (contenedorProfugos) {
        if (animalesProfugos.length === 0) {
            contenedorProfugos.innerHTML = `
                <div class="p-4 bg-emerald-50/70 border border-emerald-200 rounded-lg text-center text-xs text-emerald-800">
                    ✅ <strong>No hay animales fuera del cerco actualmente.</strong>
                    <p class="text-[11px] text-emerald-600 mt-0.5">Todo el ganado monitoreado se encuentra dentro de sus perímetros.</p>
                </div>
            `;
        } else {
            contenedorProfugos.innerHTML = '';

            animalesProfugos.forEach(animal => {
                const card = document.createElement('div');
                card.className = 'p-3 bg-red-50 border-l-4 border-red-600 rounded-r-lg shadow-sm flex flex-col gap-2 text-xs';
                card.innerHTML = `
                    <div class="flex items-start justify-between">
                        <div>
                            <div class="font-bold text-red-900 text-sm">🚨 ${escaparHtml(animal.nombre)}</div>
                            <div class="text-[11px] text-red-700">
                                ID Collar: <strong>${escaparHtml(animal.id_hardware)}</strong> · Lote: <strong>${escaparHtml(animal.cerco_nombre || 'N/A')}</strong>
                            </div>
                        </div>
                        <span class="bg-red-600 text-white text-[10px] font-bold px-2 py-0.5 rounded">FUERA</span>
                    </div>
                    <div class="text-[11px] text-red-800 bg-white/80 px-2 py-1 rounded border border-red-200">
                        ⏱️ Hora exacta de salida: <strong>${escaparHtml(animal.fecha_hora_fuga || 'Reciente')}</strong>
                    </div>
                    <div class="flex items-center gap-2 pt-1">
                        <button onclick="enfocarAnimalEnMapa(${animal.id})" class="flex-1 py-1.5 bg-red-600 hover:bg-red-700 text-white font-semibold rounded text-[11px] transition-colors">
                            🎯 Ubicar en Mapa
                        </button>
                        ${modoSimulacionActivo ? `
                        <button onclick="reingresarAnimalAlCerco(${animal.id}, ${animal.cerco_id})" class="px-2.5 py-1.5 bg-white hover:bg-emerald-50 text-emerald-700 border border-emerald-300 font-semibold rounded text-[11px] transition-colors" title="Simular retorno del animal al centro del lote">
                            ↩️ Retornar (Sim)
                        </button>
                        ` : ''}
                    </div>
                `;
                contenedorProfugos.appendChild(card);
            });
        }
    }

    if (contenedorAlertas) {
        if (alertasActivas.length === 0) {
            contenedorAlertas.innerHTML = '<p class="text-xs text-slate-400 text-center py-2">Sin incidentes pendientes de revisión.</p>';
        } else {
            contenedorAlertas.innerHTML = '';

            alertasActivas.forEach(al => {
                const item = document.createElement('div');
                item.className = 'p-2.5 bg-slate-50 border border-slate-200 rounded flex items-start justify-between gap-2 text-[11px]';
                item.innerHTML = `
                    <div>
                        <div class="font-semibold text-slate-800">${escaparHtml(al.mensaje)}</div>
                        <div class="text-slate-400 mt-0.5">${escaparHtml(al.fecha_hora_salida)}</div>
                    </div>
                    <button onclick="marcarAlertaResuelta(${al.id})" title="Descartar / Marcar como revisada" class="px-2 py-1 bg-white hover:bg-slate-100 text-slate-600 border border-slate-300 rounded font-semibold shrink-0">
                        ✓
                    </button>
                `;
                contenedorAlertas.appendChild(item);
            });
        }
    }
}

function reingresarAnimalAlCerco(idAnimal, idCerco) {
    const cerco = listaCercosDatos.find(c => c.properties.id === idCerco);
    if (!cerco) return;

    const coords = cerco.geometry.coordinates[0].slice(0, -1);
    const latMedia = coords.reduce((acc, c) => acc + c[1], 0) / coords.length;
    const lngMedia = coords.reduce((acc, c) => acc + c[0], 0) / coords.length;

    transmitirPosicionGps(idAnimal, latMedia, lngMedia);
}

function marcarAlertaResuelta(idAlerta) {
    ejecutarConBloqueo(`resolver_alerta_${idAlerta}`, null, () => {
        return peticionPostJson(`/api/alertas/${idAlerta}/resolver/`)
            .then(r => r.json())
            .then(res => {
                if (res.estado === 'exito') {
                    mostrarToast('Incidente marcado como revisado.', 'info');
                    cargarAlertasYProfugos();
                }
            });
    }, '⏳', 800);
}

