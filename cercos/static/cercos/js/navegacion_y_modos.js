/**
 * ============================================================================
 * MÓDULO 5: NAVEGACIÓN, SINCRONIZACIÓN SUPABASE Y MODOS DE OPERACIÓN
 * Archivo: cercos/static/cercos/js/navegacion_y_modos.js
 * ============================================================================
 * ¿QUÉ HACE ESTE ARCHIVO?
 * 1. Sincroniza cercos, animales y alertas desde el backend (Supabase/PostGIS).
 * 2. Gestiona el cambio de secciones principales y sub-modos del panel lateral.
 * 3. Alterna limpiamente entre `📡 Modo Real (Node-RED)` y `🧪 Modo Simulación`,
 *    asegurando que al volver a Modo Real no queden vacas ni cercos de prueba.
 * 4. Ejecuta el polling inteligente cada 5 segundos para reflejar en vivo las
 *    actualizaciones enviadas por Node-RED.
 * ============================================================================
 */


// ============================================================================
// 1. SINCRONIZACIÓN CON EL BACKEND (SUPABASE / POSTGIS)
// ============================================================================

function obtenerParametroModo() {
    return modoSimulacionActivo ? 'simulacion' : 'real';
}

function cargarCercos(ajustarCamara = false) {
    return fetch(`/api/cercos/?modo=${obtenerParametroModo()}`)
        .then(respuesta => respuesta.json())
        .then(datosGeoJson => {
            listaCercosDatos = datosGeoJson.features || [];
            dibujarCercosEnMapa(ajustarCamara);
            renderizarResumenCercosGeneral();
            poblarListaModificacion();
            poblarListaEliminar();
            actualizarSelectoresCercosGanado();
        })
        .catch(error => console.error('Error al cargar cercos:', error));
}

function cargarAnimales() {
    return fetch(`/api/animales/?modo=${obtenerParametroModo()}`)
        .then(respuesta => respuesta.json())
        .then(datos => {
            listaAnimalesDatos = datos.animales || [];

            if (datos.alertas_nuevas && datos.alertas_nuevas.length > 0) {
                datos.alertas_nuevas.forEach(al => {
                    mostrarToast(al.mensaje, 'alerta_fuga', '🚨 ¡ALERTA DESDE COLLAR / NODE-RED!');
                });
                reproducirSonidoAlerta();
                cargarAlertasYProfugos();
            }

            dibujarAnimalesEnMapa();
            renderizarListaGanado();
            actualizarSelectorTelemetria();
            actualizarBadgesSuperiores();
        })
        .catch(error => console.error('Error al cargar animales:', error));
}

function cargarAlertasYProfugos() {
    return fetch(`/api/alertas/?modo=${obtenerParametroModo()}`)
        .then(respuesta => respuesta.json())
        .then(datos => {
            listaAlertasDatos = datos.alertas_activas || [];
            renderizarPanelProfugos(datos.animales_profugos || [], listaAlertasDatos);
            actualizarBadgesSuperiores(datos.total_profugos);
        })
        .catch(error => console.error('Error al cargar alertas:', error));
}

function sincronizarTodo(ajustarCamara = false) {
    return Promise.all([
        cargarCercos(ajustarCamara),
        cargarAnimales(),
        cargarAlertasYProfugos()
    ]);
}

function actualizarBadgesSuperiores(totalProfugosOverride = null) {
    const badgeGanado = document.getElementById('badge-total-ganado');
    if (badgeGanado) {
        badgeGanado.textContent = listaAnimalesDatos.length;
    }

    const totalProfugos = totalProfugosOverride !== null
        ? totalProfugosOverride
        : listaAnimalesDatos.filter(a => a.estado_fuga).length;

    const badgeProfugos = document.getElementById('badge-profugos');
    if (badgeProfugos) {
        badgeProfugos.textContent = totalProfugos;
        if (totalProfugos > 0) {
            badgeProfugos.classList.remove('hidden');
        } else {
            badgeProfugos.classList.add('hidden');
        }
    }
}


// ============================================================================
// 2. NAVEGACIÓN ENTRE SECCIONES Y SUB-PANELES
// ============================================================================

function cambiarSeccionPrincipal(nuevaSeccion) {
    seccionActual = nuevaSeccion;

    if (nuevaSeccion !== 'cercos') {
        cambiarModo('general');
    }

    if (nuevaSeccion !== 'ganado') {
        cerrarFormularioNuevoAnimal();
    }

    document.querySelectorAll('.seccion-principal').forEach(sec => {
        sec.classList.add('hidden');
        sec.classList.remove('flex');
    });

    const secActiva = document.getElementById(`seccion-${nuevaSeccion}`);
    if (secActiva) {
        secActiva.classList.remove('hidden');
        secActiva.classList.add('flex');
    }

    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.classList.remove('text-campo-400', 'border-b-2', 'border-campo-400', 'font-semibold');
    });

    const tabActivo = document.getElementById(`nav-${nuevaSeccion}`);
    if (tabActivo) {
        tabActivo.classList.add('text-campo-400', 'border-b-2', 'border-campo-400', 'font-semibold');
    }

    if (nuevaSeccion === 'telemetria') {
        mapa.getContainer().style.cursor = 'crosshair';
    } else if (modoActual !== 'crear') {
        mapa.getContainer().style.cursor = '';
    }

    if (nuevaSeccion === 'ganado') {
        cargarAnimales();
    } else if (nuevaSeccion === 'alertas') {
        cargarAlertasYProfugos();
    }
}

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


// ============================================================================
// 3. DEMO Y ALTERNANCIA ENTRE MODO REAL (NODE-RED) Y MODO SIMULACIÓN
// ============================================================================

/**
 * Carga los 2 lotes y 4 animales de demostración alrededor de la Ubicación Base
 * actualmente seleccionada (ej. Capital, Belén, Tinogasta, etc.).
 */
function cargarEscenarioDemo() {
    ejecutarConBloqueo('cargar_demo', 'boton-cargar-demo', () => {
        return peticionPostJson('/api/demo/cargar/', {
            latitud: ubicacionBaseActual.latitud,
            longitud: ubicacionBaseActual.longitud
        })
            .then(r => r.json())
            .then(res => {
                if (res.estado === 'exito') {
                    mostrarToast(
                        `${res.mensaje} (${ubicacionBaseActual.nombre})`,
                        'exito',
                        '🌱 Escenario Demo Listo'
                    );
                    sincronizarTodo(true);
                }
            })
            .catch(() => mostrarToast('Error al cargar el escenario de demostración.', 'error'));
    }, '⏳ Cargando...');
}

function limpiarEscenarioDemo() {
    if (!confirm('¿Desea borrar de la base de datos los 2 lotes y las 4 vacas de demostración?')) {
        return;
    }

    ejecutarConBloqueo('limpiar_demo', 'boton-limpiar-demo', () => {
        return peticionPostJson('/api/demo/limpiar/')
            .then(r => r.json())
            .then(res => {
                if (res.estado === 'exito') {
                    mostrarToast(res.mensaje, 'info', '🧹 Demo Limpiada');
                    sincronizarTodo(true);
                }
            })
            .catch(() => mostrarToast('Error al limpiar el escenario de demostración.', 'error'));
    }, '⏳ Limpiando...');
}

function _actualizarBotonesModoOperacion(esSimulacion) {
    const btnModo = document.getElementById('boton-modo-operacion');
    const txtModo = document.getElementById('texto-modo-operacion');
    const controlesDemo = document.getElementById('controles-demo-simulacion');
    const navTelemetria = document.getElementById('item-nav-telemetria');
    const btnNuevoAnimalPanel = document.getElementById('boton-nuevo-animal-panel');

    if (txtModo) {
        txtModo.textContent = esSimulacion ? '🧪 Modo Simulación (Pruebas)' : '📡 Modo Real (Node-RED)';
    }
    if (btnModo) {
        btnModo.classList.toggle('bg-campo-900', !esSimulacion);
        btnModo.classList.toggle('text-emerald-300', !esSimulacion);
        btnModo.classList.toggle('border-emerald-700/70', !esSimulacion);
        btnModo.classList.toggle('bg-amber-900/90', esSimulacion);
        btnModo.classList.toggle('text-amber-200', esSimulacion);
        btnModo.classList.toggle('border-amber-500', esSimulacion);
    }
    if (controlesDemo) {
        controlesDemo.classList.toggle('hidden', !esSimulacion);
        controlesDemo.classList.toggle('flex', esSimulacion);
    }
    if (navTelemetria) navTelemetria.classList.toggle('hidden', !esSimulacion);
    if (btnNuevoAnimalPanel) btnNuevoAnimalPanel.classList.toggle('hidden', !esSimulacion);
}

function _vaciarCapasVisualesMapa() {
    listaCercosDatos = [];
    listaAnimalesDatos = [];
    listaAlertasDatos = [];
    capaCercosExistentes.clearLayers();
    capaAnimalesMapa.clearLayers();
    renderizarResumenCercosGeneral();
    renderizarListaGanado();
    renderizarPanelProfugos([], []);
    actualizarBadgesSuperiores(0);
}

function alternarModoSimulacion() {
    modoSimulacionActivo = !modoSimulacionActivo;
    arrastrandoAnimal = false;

    mapa.closePopup();
    cambiarModo('general');
    cerrarFormularioNuevoAnimal();

    const resBox = document.getElementById('resultado-telemetria-box');
    if (resBox) resBox.classList.add('hidden');

    const filtroGanado = document.getElementById('filtro-cerco-ganado');
    if (filtroGanado) filtroGanado.value = 'todos';

    const buscadorGanado = document.getElementById('buscador-ganado');
    if (buscadorGanado) buscadorGanado.value = '';

    _actualizarBotonesModoOperacion(modoSimulacionActivo);

    if (modoSimulacionActivo) {
        mostrarToast('Modo Simulación activado: use "⚡ Cargar Demo" o "+ Nuevo (Sim)" para probar.', 'info', '🧪 Modo Laboratorio Activo');
        sincronizarTodo(false);
        return;
    }

    if (seccionActual === 'telemetria') {
        cambiarSeccionPrincipal('cercos');
    }

    _vaciarCapasVisualesMapa();
    peticionPostJson('/api/demo/limpiar/')
        .then(() => {
            mostrarToast('Modo Real activo: mostrando únicamente registros reales.', 'exito', '📡 Monitoreo Real Activo');
            sincronizarTodo(true);
        })
        .catch(() => sincronizarTodo(true));
}


// ============================================================================
// 4. ARRANQUE INICIAL Y POLLING INTELIGENTE CON SUPABASE (CADA 5 SEGUNDOS)
// ============================================================================

inicializarEtiquetaUbicacionBase();
sincronizarTodo(true);

setInterval(() => {
    if (modoActual === 'general' && !arrastrandoAnimal && !document.hidden) {
        cargarAnimales();
    }
}, 5000);

