"""
==============================================================================
CAPA DE VALIDACIÓN Y FORMULARIOS: cercos/forms.py
==============================================================================
¿QUÉ HACE ESTE ARCHIVO?
Centraliza la validación y limpieza (sanitización) de todos los datos que
entran desde el navegador o desde el nodo IoT GPS antes de tocar los modelos
o la base de datos.

Usar `forms.py` de Django garantiza:
1. Mensajes de error claros y uniformes en español.
2. Normalización de datos (ej. quitar espacios sobrantes, pasar IDs de collar
a mayúsculas).
3. Prevención de errores de integridad en PostgreSQL.
==============================================================================
"""

import re
from django import forms
from .models import CercoVirtual, Animal

# Expresión regular para validar colores hexadecimales tipo #2ecc71
HEX_COLOR_REGEX = re.compile(r'^#[0-9a-fA-F]{6}$')


class CercoVirtualForm(forms.ModelForm):
    """
    Valida los atributos no geométricos de un Cerco Virtual (nombre, color y modo de alerta)
    para los casos de uso Crear Cerco (RF_1) y Modificar Cerco (RF_2).
    """
    class Meta:
        model = CercoVirtual
        fields = ['nombre', 'color', 'alerta_continua']

    def clean_nombre(self):
        """
        Verifica que el nombre del lote no esté vacío, tenga al menos 2 caracteres
        y no esté duplicado en otro cerco existente (evita registros duplicados por doble clic).
        """
        nombre = (self.cleaned_data.get('nombre') or '').strip()
        if not nombre:
            raise forms.ValidationError(
                'Debe ingresar un nombre para el lote.')
        if len(nombre) < 2:
            raise forms.ValidationError(
                'El nombre del lote debe tener al menos 2 caracteres.')

        qs = CercoVirtual.objects.filter(nombre__iexact=nombre)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(
                f'Ya existe un cerco virtual registrado con el nombre «{nombre}».')
        return nombre

    def clean_color(self):
        """
        Verifica que el color elegido respete el formato hexadecimal #RRGGBB
        para evitar inyecciones de estilo en Leaflet.
        """
        color = (self.cleaned_data.get('color') or '#2ecc71').strip()
        if not HEX_COLOR_REGEX.match(color):
            raise forms.ValidationError(
                'El color debe estar en formato hexadecimal válido (ej: #2ecc71).')
        return color


class AnimalForm(forms.ModelForm):
    """
    Valida el alta o modificación de un Animal monitoreado y su collar GPS.
    """
    cerco_id = forms.IntegerField(required=False)
    latitud = forms.FloatField(required=False, min_value=-90.0, max_value=90.0)
    longitud = forms.FloatField(
        required=False, min_value=-180.0, max_value=180.0)

    class Meta:
        model = Animal
        fields = ['id_hardware', 'nombre', 'especie']

    def clean_id_hardware(self):
        """
        Normaliza el ID de hardware a mayúsculas (ej. 'collar-101' -> 'COLLAR-101')
        y comprueba que no esté duplicado en otro animal.
        """
        id_hw = (self.cleaned_data.get('id_hardware') or '').strip().upper()
        if not id_hw:
            raise forms.ValidationError(
                'El ID de collar/hardware es obligatorio.')
        qs = Animal.objects.filter(id_hardware__iexact=id_hw)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(
                f'Ya existe un animal registrado con el collar {id_hw}.')
        return id_hw

    def clean_nombre(self):
        """Verifica que el animal tenga un nombre o número de caravana válido."""
        nombre = (self.cleaned_data.get('nombre') or '').strip()
        if not nombre:
            raise forms.ValidationError(
                'Debe ingresar un nombre o identificación para el animal.')
        return nombre


class TelemetriaGPSForm(forms.Form):
    """
    Valida la estructura de la trama de telemetría GPS recibida en `POST /api/telemetria/procesar/`.
    Implementa el Control de Integridad de la Trama del Caso de Uso "Procesar Ubicación"
    (Camino Alternativo 2: Datos corruptos o incompletos).
    """
    id_hardware = forms.CharField(required=False, max_length=50)
    animal_id = forms.IntegerField(required=False)
    latitud = forms.FloatField(
        required=True,
        min_value=-90.0,
        max_value=90.0,
        error_messages={
            'required': 'La latitud es obligatoria en la trama GPS.',
            'invalid': 'La latitud debe ser un número decimal válido.',
            'min_value': 'La latitud debe estar entre -90 y 90 grados.',
            'max_value': 'La latitud debe estar entre -90 y 90 grados.',
        }
    )
    longitud = forms.FloatField(
        required=True,
        min_value=-180.0,
        max_value=180.0,
        error_messages={
            'required': 'La longitud es obligatoria en la trama GPS.',
            'invalid': 'La longitud debe ser un número decimal válido.',
            'min_value': 'La longitud debe estar entre -180 y 180 grados.',
            'max_value': 'La longitud debe estar entre -180 y 180 grados.',
        }
    )

    def clean(self):
        """
        Exige que la trama identifique al animal ya sea por `id_hardware` (cuando
        envía el Gateway IoT de Electrónica) o por `animal_id` (desde el simulador web).
        """
        cleaned_data = super().clean()
        id_hw = (cleaned_data.get('id_hardware') or '').strip()
        animal_id = cleaned_data.get('animal_id')
        if not id_hw and not animal_id:
            raise forms.ValidationError(
                'Debe especificar el id_hardware del collar o el animal_id.')
        cleaned_data['id_hardware'] = id_hw
        return cleaned_data
