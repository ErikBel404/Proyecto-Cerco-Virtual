/**
 * ============================================================================
 * MÓDULO 1: ESTADO GLOBAL, MAPA BASE, UBICACIÓN Y UTILIDADES
 * Archivo: cercos/static/cercos/js/estado_y_utilidades.js
 * ============================================================================
 * ¿QUÉ HACE ESTE ARCHIVO?
 * 1. Inicializa el visor satelital Leaflet y permite cambiar la Ubicación Base
 *    del campo (San Fernando del Valle, Belén, Tinogasta, Andalgalá o cualquier
 *    localidad buscada por nombre o coordenadas).
 * 2. Define las variables de estado compartidas por todos los módulos.
 * 3. Implementa el bloqueo Anti-Doble-Clic (`ejecutarConBloqueo`) con tiempo de
 *    enfriamiento para evitar que un doble clic cree dos cercos o dos animales.
 * 4. Provee las funciones de notificaciones Toast, alerta sonora y validación
 *    matemática de cruces de líneas (auto-intersección de polígonos).
 * ============================================================================
 */


// ============================================================================
// 1. CONFIGURACIÓN DE UBICACIÓN BASE DEL CAMPO (CON PERSISTENCIA LOCAL)
// ============================================================================

const UBICACION_POR_DEFECTO = {
    latitud: -28.4696,
    longitud: -65.7852,
    nombre: 'Capital (SFV de Catamarca)'
};

const ZOOM_INICIAL = 14;

/**
 * Recupera la última ubicación base elegida por el productor desde `localStorage`,
 * o usa San Fernando del Valle de Catamarca si aún no eligió otra localidad.
 */
function obtenerUbicacionBaseGuardada() {
    try {
        const guardado = localStorage.getItem('smartherd_ubicacion_base');
        if (guardado) {
            const parsed = JSON.parse(guardado);
            if (typeof parsed.latitud === 'number' && typeof parsed.longitud === 'number') {
                if (typeof parsed.nombre === 'string') {
                    parsed.nombre = parsed.nombre.replace(/\s*\/?\s*INTA\s*/gi, ' ').trim();
                }
                return parsed;
            }
        }
    } catch (e) {
        // Si localStorage está bloqueado, usar ubicación por defecto
    }
    return { ...UBICACION_POR_DEFECTO };
}

let ubicacionBaseActual = obtenerUbicacionBaseGuardada();


// ============================================================================
// 2. INICIALIZACIÓN DEL MAPA SATELITAL LEAFLET
// ============================================================================

const mapa = L.map('visor-mapa', { zoomControl: true }).setView(
    [ubicacionBaseActual.latitud, ubicacionBaseActual.longitud],
    ZOOM_INICIAL
);

L.tileLayer(
    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    {
        maxZoom: 18,
        attribution: 'Tiles © Esri — Proyecto SmartHerd (UNCA)'
    }
).addTo(mapa);

// Capas independientes para polígonos de cercos y marcadores de vacas
let capaCercosExistentes = L.featureGroup().addTo(mapa);
let capaAnimalesMapa = L.featureGroup().addTo(mapa);


// ============================================================================
// 3. ESTADO COMPARTIDO DE LA APLICACIÓN
// ============================================================================

// Datos sincronizados desde PostgreSQL / Supabase
let listaCercosDatos = [];
let listaAnimalesDatos = [];
let listaAlertasDatos = [];

// Estado de navegación y Modo Operativo
// - modoSimulacionActivo = false -> Modo Real (Node-RED / Supabase)
// - modoSimulacionActivo = true  -> Modo Simulación (Pruebas y Demo)
let seccionActual = 'cercos';
let modoActual = 'general';
let modoSimulacionActivo = false;
let arrastrandoAnimal = false;

// Colores seleccionados para creación y edición de cercos
let colorElegido = '#2ecc71';
let colorEdicionElegido = '#2ecc71';

// Estado temporal del modo Crear Cerco (RF_1)
let puntosDibujo = [];
let marcadoresVertices = [];
let lineaGuiaDinamica = null;
let poligonoCerrado = null;
let trazadoFinalizado = false;

// Estado temporal del modo Modificar Cerco (RF_2)
let cercoEnEdicion = null;
let puntosEdicion = [];
let marcadoresEdicion = [];
let poligonoEdicionDinamico = null;

// Estado temporal del modo Eliminar Cerco (RF_8)
let cercoParaEliminar = null;
let poligonoResaltadoEliminar = null;


// ============================================================================
// 4. PROTECCIÓN ANTI-DOBLE-CLIC Y BLOQUEO DE ENVÍOS REPETIDOS
// ============================================================================

const registroBloqueosAccion = {};

/**
 * ¿QUÉ HACE `ejecutarConBloqueo` Y POR QUÉ ESTÁ AQUÍ?
 * Evita que si el usuario hace doble clic rápido en "Guardar Cerco", "Guardar Animal"
 * o "Cargar Demo" se envíen dos peticiones seguidas a Supabase creando registros duplicados.
 *
 * - Bloquea la acción mientras la promesa está en curso + un tiempo extra de seguridad (`cooldownMs`).
 * - Deshabilita visualmente el botón (`disabled = true`) y muestra un texto de espera.
 */
function ejecutarConBloqueo(claveAccion, idBoton, funcionPromesa, textoEspera = '⏳ Procesando...', cooldownMs = 1800) {
    const ahora = Date.now();

    if (registroBloqueosAccion[claveAccion] && ahora < registroBloqueosAccion[claveAccion]) {
        return;
    }

    // Bloquear preventivamente durante al menos 4 segundos mientras inicia la petición
    registroBloqueosAccion[claveAccion] = ahora + 4000;

    const boton = idBoton ? document.getElementById(idBoton) : null;
    const textoOriginal = boton ? boton.innerHTML : '';

    if (boton) {
        boton.disabled = true;
        boton.innerHTML = textoEspera;
    }

    Promise.resolve()
        .then(() => funcionPromesa())
        .finally(() => {
            registroBloqueosAccion[claveAccion] = Date.now() + cooldownMs;

            setTimeout(() => {
                registroBloqueosAccion[claveAccion] = 0;
                if (boton) {
                    boton.disabled = false;
                    boton.innerHTML = textoOriginal;
                }
            }, cooldownMs);
        });
}


// ============================================================================
// 5. CAMBIO Y BÚSQUEDA DE UBICACIÓN BASE (BELÉN, TINOGASTA, BUSCADOR LIBRE)
// ============================================================================

/**
 * Actualiza la ubicación base del campo, la guarda en `localStorage` y mueve
 * suavemente la cámara del mapa hacia esas coordenadas.
 */
function fijarUbicacionBase(latitud, longitud, nombreLugar, moverCamara = true) {
    ubicacionBaseActual = {
        latitud: parseFloat(latitud),
        longitud: parseFloat(longitud),
        nombre: nombreLugar
    };

    try {
        localStorage.setItem('smartherd_ubicacion_base', JSON.stringify(ubicacionBaseActual));
    } catch (e) {
        // Ignorar si el navegador restringe localStorage
    }

    const etiqueta = document.getElementById('etiqueta-ubicacion-base');
    if (etiqueta) {
        etiqueta.textContent = nombreLugar;
    }

    if (moverCamara) {
        mapa.flyTo([ubicacionBaseActual.latitud, ubicacionBaseActual.longitud], ZOOM_INICIAL, {
            duration: 1.3
        });
    }
}

/**
 * Se ejecuta cuando el usuario elige una localidad del selector desplegable
 * (San Fernando del Valle, Belén, Tinogasta, Andalgalá, Santa María, etc.).
 */
function cambiarLocalidadPredefinida(valorOpcion) {
    if (!valorOpcion) return;

    const [coordsTxt, nombreLugar] = valorOpcion.split('|');
    const [latStr, lngStr] = coordsTxt.split(',');
    const lat = parseFloat(latStr);
    const lng = parseFloat(lngStr);

    if (!isNaN(lat) && !isNaN(lng)) {
        fijarUbicacionBase(lat, lng, nombreLugar || 'Ubicación seleccionada', true);
        mostrarToast(`Mapa centrado en ${nombreLugar}.`, 'info', '📍 Ubicación Base Actualizada');
    }
}

/**
 * Permite escribir cualquier localidad (ej: "Belén, Catamarca", "Pomán", "Londres, Catamarca")
 * o un par de coordenadas ("-27.6494, -67.0289") y centrar allí el mapa.
 */
function buscarUbicacionPorNombre() {
    const input = document.getElementById('campo-buscar-lugar');
    const consulta = input ? input.value.trim() : '';

    if (!consulta) {
        mostrarToast('Escriba el nombre de una localidad (ej: Belén) o coordenadas lat,lng.', 'info');
        return;
    }

    // 1. Verificar si ingresó coordenadas numéricas directas: "-27.64, -67.02"
    const partesCoord = consulta.split(',').map(p => p.trim());
    if (partesCoord.length === 2 && !isNaN(parseFloat(partesCoord[0])) && !isNaN(parseFloat(partesCoord[1]))) {
        const lat = parseFloat(partesCoord[0]);
        const lng = parseFloat(partesCoord[1]);
        fijarUbicacionBase(lat, lng, `Coord (${lat.toFixed(3)}, ${lng.toFixed(3)})`, true);
        mostrarToast(`Ubicación fijada en (${lat.toFixed(4)}, ${lng.toFixed(4)}).`, 'exito');
        return;
    }

    // 2. Geocodificación abierta mediante OpenStreetMap Nominatim
    ejecutarConBloqueo('buscar_lugar', 'boton-buscar-lugar', () => {
        const url = `https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(consulta)}`;

        return fetch(url, { headers: { 'Accept-Language': 'es' } })
            .then(r => r.json())
            .then(resultados => {
                if (!resultados || resultados.length === 0) {
                    mostrarToast('No se encontró esa localidad. Pruebe agregando ", Catamarca" o ", Argentina".', 'error');
                    return;
                }

                const lugar = resultados[0];
                const lat = parseFloat(lugar.lat);
                const lng = parseFloat(lugar.lon);
                const nombreCorto = (lugar.display_name || consulta).split(',').slice(0, 2).join(', ');

                fijarUbicacionBase(lat, lng, nombreCorto, true);
                mostrarToast(`Ubicación base fijada en: ${nombreCorto}`, 'exito', '📍 Campo Localizado');
            })
            .catch(() => {
                mostrarToast('No se pudo consultar el geocodificador. Use el selector de localidades o coordenadas.', 'error');
            });
    }, '⏳', 1000);
}

/**
 * Sincroniza la etiqueta visual del selector al iniciar la página.
 */
function inicializarEtiquetaUbicacionBase() {
    const etiqueta = document.getElementById('etiqueta-ubicacion-base');
    if (etiqueta && ubicacionBaseActual.nombre) {
        etiqueta.textContent = ubicacionBaseActual.nombre;
    }

    const selector = document.getElementById('selector-localidad-base');
    if (selector) {
        for (const opt of selector.options) {
            if (opt.value.includes(ubicacionBaseActual.nombre)) {
                selector.value = opt.value;
                break;
            }
        }
    }
}

/**
 * Enfoca todos los cercos creados en el mapa o vuelve a la Ubicación Base actual.
 */
function enfocarCercos() {
    if (capaCercosExistentes && capaCercosExistentes.getLayers().length > 0) {
        mapa.flyToBounds(capaCercosExistentes.getBounds(), {
            padding: [50, 50],
            duration: 1.3
        });
    } else {
        mapa.flyTo([ubicacionBaseActual.latitud, ubicacionBaseActual.longitud], ZOOM_INICIAL, {
            duration: 1.3
        });
    }
}

// Botón flotante 🎯 en la esquina superior derecha del mapa
const controlEnfoque = L.control({ position: 'topright' });
controlEnfoque.onAdd = function () {
    const contenedor = L.DomUtil.create('div', 'leaflet-bar');
    const boton = L.DomUtil.create('a', '', contenedor);

    boton.innerHTML = '🎯';
    boton.href = '#';
    boton.title = 'Enfocar cercos virtuales o volver a la ubicación base';
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


// ============================================================================
// 6. UTILIDADES DE SEGURIDAD (CSRF, XSS), TOASTS Y SONIDO DE ALERTA
// ============================================================================

/**
 * Sanitiza texto antes de insertarlo en HTML para prevenir ataques XSS.
 */
function escaparHtml(texto) {
    if (texto === null || texto === undefined) return '';
    return String(texto)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

/**
 * Obtiene el token CSRF de Django desde las cookies del navegador.
 */
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

/**
 * Envía una petición HTTP POST con formato JSON y el token CSRF de Django incluido,
 * evitando repetir encabezados `headers` y `JSON.stringify` en cada módulo.
 */
function peticionPostJson(url, datos = {}) {
    return fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': tokenCsrf
        },
        body: JSON.stringify(datos)
    });
}

/**
 * Muestra una notificación emergente (Toast) en la esquina superior derecha (RF_5).
 */
function mostrarToast(mensaje, tipo = 'exito', titulo = '') {
    const contenedor = document.getElementById('contenedor-toasts');
    if (!contenedor) return;

    const estilos = {
        exito: 'bg-emerald-900/95 border-emerald-500 text-white',
        error: 'bg-red-900/95 border-red-500 text-white',
        alerta_fuga: 'bg-red-700 border-2 border-yellow-300 text-white shadow-2xl',
        info: 'bg-slate-800/95 border-slate-500 text-white'
    };

    const iconos = {
        exito: '✅',
        error: '⚠️',
        alerta_fuga: '🚨',
        info: 'ℹ️'
    };

    const toast = document.createElement('div');
    toast.className = `pointer-events-auto flex items-start gap-3 p-3.5 rounded-lg border-l-4 shadow-lg transition-all duration-300 ${estilos[tipo] || estilos.info}`;
    toast.innerHTML = `
        <span class="text-lg leading-none mt-0.5">${iconos[tipo] || 'ℹ️'}</span>
        <div class="flex-1 text-xs leading-relaxed">
            ${titulo ? `<strong class="block font-bold text-sm mb-0.5">${escaparHtml(titulo)}</strong>` : ''}
            <span>${escaparHtml(mensaje)}</span>
        </div>
        <button class="text-white/70 hover:text-white text-xs font-bold ml-1" onclick="this.parentElement.remove()">✕</button>
    `;

    contenedor.appendChild(toast);

    const duracion = tipo === 'alerta_fuga' ? 8000 : 4500;
    setTimeout(() => {
        if (toast.parentElement) toast.remove();
    }, duracion);
}

/**
 * Reproduce un aviso sonoro sintetizado cuando un animal se fuga del cerco.
 */
function reproducirSonidoAlerta() {
    try {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtx) return;

        const ctx = new AudioCtx();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.type = 'sine';
        osc.frequency.setValueAtTime(660, ctx.currentTime);
        osc.frequency.setValueAtTime(880, ctx.currentTime + 0.15);

        gain.gain.setValueAtTime(0.08, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);

        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.4);
    } catch (e) {
        // Ignorar si el navegador bloquea el audio automático
    }
}


// ============================================================================
// 7. VALIDACIÓN GEOMÉTRICA DE AUTO-INTERSECCIÓN (CRUCE DE LÍNEAS)
// ============================================================================

/**
 * Comprueba si dos segmentos [p1, p2] y [p3, p4] se cortan entre sí.
 */
function segmentosSeCruzan(p1, p2, p3, p4) {
    function orientacion(a, b, c) {
        return (b[1] - a[1]) * (c[0] - b[0]) - (b[0] - a[0]) * (c[1] - b[1]);
    }

    const o1 = orientacion(p1, p2, p3);
    const o2 = orientacion(p1, p2, p4);
    const o3 = orientacion(p3, p4, p1);
    const o4 = orientacion(p3, p4, p2);

    return ((o1 > 0 && o2 < 0) || (o1 < 0 && o2 > 0)) &&
        ((o3 > 0 && o4 < 0) || (o3 < 0 && o4 > 0));
}

/**
 * Devuelve `true` si el polígono tiene lados que se cruzan formando un 8.
 */
function poligonoTieneAutoInterseccion(puntos) {
    const n = puntos.length;
    if (n < 4) return false;

    for (let i = 0; i < n; i++) {
        const a1 = puntos[i];
        const a2 = puntos[(i + 1) % n];

        for (let j = i + 2; j < n; j++) {
            if (i === 0 && j === n - 1) continue;

            const b1 = puntos[j];
            const b2 = puntos[(j + 1) % n];

            if (segmentosSeCruzan(a1, a2, b1, b2)) {
                return true;
            }
        }
    }
    return false;
}

