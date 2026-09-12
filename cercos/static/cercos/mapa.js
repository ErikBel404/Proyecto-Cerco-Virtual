// 1. Inicializar mapa satelital ESRI
const mapa = L.map('visor-mapa', { zoomControl: true }).setView([-28.4696, -65.7852], 14);

L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 18,
    attribution: 'Tiles © Esri'
}).addTo(mapa);

// 2. Variables de estado del mapa y cercos existentes
let capaCercosExistentes = L.featureGroup().addTo(mapa);
let modoActual = 'general';
let colorElegido = '#2ecc71';

// 3. Variables exclusivas para el trazado del nuevo cerco
let puntosDibujo = [];
let marcadoresVertices = [];
let lineaGuiaDinamica = null;
let poligonoCerrado = null;
let trazadoFinalizado = false;

// 4. Token CSRF de seguridad para Django
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

// 5. Cargar y mostrar los cercos ya guardados en PostGIS
function cargarCercos() {
    fetch('/api/cercos/')
        .then(respuesta => respuesta.json())
        .then(datosGeoJson => {
            capaCercosExistentes.clearLayers();

            datosGeoJson.features.forEach(elemento => {
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
            });

            if (datosGeoJson.features.length > 0 && modoActual === 'general') {
                mapa.fitBounds(capaCercosExistentes.getBounds(), { padding: [40, 40] });
            }
        });
}

// 6. Control de cambio de paneles en la barra lateral
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

    limpiarTrazado();

    if (nuevoModo === 'crear') {
        document.getElementById('campo-nuevo-nombre').value = '';
        trazadoFinalizado = false;
        mapa.getContainer().style.cursor = 'crosshair';
    } else {
        mapa.getContainer().style.cursor = '';
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

    // Actualizar color en vivo si el polígono ya fue cerrado
    if (poligonoCerrado) {
        poligonoCerrado.setStyle({ color: colorElegido, fillColor: colorElegido });
    }
}

// =======================================================
// INTERACCIÓN DE DIBUJO CON EL RATÓN (RF_1)
// =======================================================

// A. CLIC IZQUIERDO: Colocar un nuevo vértice
mapa.on('click', function(evento) {
    if (modoActual !== 'crear') return;
    if (trazadoFinalizado) return;

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

// B. MOVIMIENTO DEL RATÓN: Guía elástica hacia el cursor
mapa.on('mousemove', function(evento) {
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

// C. CLIC DERECHO: Finalizar trazado y liberar el mouse
mapa.on('contextmenu', function(evento) {
    if (modoActual !== 'crear') return;

    L.DomEvent.preventDefault(evento);

    if (trazadoFinalizado) return;

    if (puntosDibujo.length <= 2) {
        alert('Debe marcar al menos 3 vértices con clic izquierdo antes de cerrar el cerco con clic derecho.');
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

// =======================================================
// PERSISTENCIA EN EL BACKEND (POSTGIS)
// =======================================================
function guardarNuevoCerco() {
    const nombreLote = document.getElementById('campo-nuevo-nombre').value.trim();

    if (!nombreLote) {
        alert('Debe indicar un nombre identificatorio para el lote.');
        return;
    }

    if (puntosDibujo.length <= 2) {
        alert('Debe trazar al menos 3 vértices en el mapa para constituir un lote.');
        return;
    }

    if (!trazadoFinalizado) {
        trazadoFinalizado = true;
        if (lineaGuiaDinamica) {
            mapa.removeLayer(lineaGuiaDinamica);
            lineaGuiaDinamica = null;
        }
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
        alert('Ocurrió un error al enviar las coordenadas al servidor.');
    });
}

// =======================================================
// RUTINA DE LIMPIEZA
// =======================================================
function limpiarTrazado() {
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

// Carga inicial al cargar el script
cargarCercos();