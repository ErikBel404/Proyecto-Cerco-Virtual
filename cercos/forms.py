"""
Formularios de validación de entrada para Cercos, Animales y Telemetría GPS.
"""

import re
from django import forms
from .models import CercoVirtual, Animal

HEX_COLOR_REGEX = re.compile(r'^#[0-9a-fA-F]{6}$')


class CercoVirtualForm(forms.ModelForm):
    """Valida nombre único, color hexadecimal y modo de alerta de un cerco (`RF_1`, `RF_2`)."""
    class Meta:
        model = CercoVirtual
        fields = ['nombre', 'color', 'alerta_continua']

    def clean_nombre(self):
        nombre = (self.cleaned_data.get('nombre') or '').strip()
        if len(nombre) < 2:
            raise forms.ValidationError('El nombre del lote debe tener al menos 2 caracteres.')

        qs = CercoVirtual.objects.filter(nombre__iexact=nombre)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(f'Ya existe un cerco registrado con el nombre «{nombre}».')
        return nombre

    def clean_color(self):
        color = (self.cleaned_data.get('color') or '#2ecc71').strip()
        if not HEX_COLOR_REGEX.match(color):
            raise forms.ValidationError('El color debe estar en formato hexadecimal válido (ej: #2ecc71).')
        return color


class AnimalForm(forms.ModelForm):
    """Valida el alta de un animal monitoreado y normaliza su `id_hardware` a mayúsculas."""
    cerco_id = forms.IntegerField(required=False)
    latitud = forms.FloatField(required=False, min_value=-90.0, max_value=90.0)
    longitud = forms.FloatField(required=False, min_value=-180.0, max_value=180.0)

    class Meta:
        model = Animal
        fields = ['id_hardware', 'nombre', 'especie']

    def clean_id_hardware(self):
        id_hw = (self.cleaned_data.get('id_hardware') or '').strip().upper()
        if not id_hw:
            raise forms.ValidationError('El ID de collar/hardware es obligatorio.')

        qs = Animal.objects.filter(id_hardware__iexact=id_hw)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(f'Ya existe un animal registrado con el collar {id_hw}.')
        return id_hw

    def clean_nombre(self):
        nombre = (self.cleaned_data.get('nombre') or '').strip()
        if not nombre:
            raise forms.ValidationError('Debe ingresar un nombre o identificación para el animal.')
        return nombre


class TelemetriaGPSForm(forms.Form):
    """Valida las coordenadas GPS (`latitud`, `longitud`) y el identificador del collar (`RF_3`)."""
    id_hardware = forms.CharField(required=False, max_length=50)
    animal_id = forms.IntegerField(required=False)
    latitud = forms.FloatField(required=True, min_value=-90.0, max_value=90.0)
    longitud = forms.FloatField(required=True, min_value=-180.0, max_value=180.0)

    def clean(self):
        cleaned_data = super().clean()
        id_hw = (cleaned_data.get('id_hardware') or '').strip()
        if not id_hw and not cleaned_data.get('animal_id'):
            raise forms.ValidationError('Debe especificar el id_hardware del collar o el animal_id.')
        cleaned_data['id_hardware'] = id_hw
        return cleaned_data
