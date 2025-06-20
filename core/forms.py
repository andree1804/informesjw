from django import forms
from .models import Group
import datetime

class GroupSelectForm(forms.Form):
    MONTH_CHOICES = [
        ('Enero', 'Enero'), ('Febrero', 'Febrero'), ('Marzo', 'Marzo'),
        ('Abril', 'Abril'), ('Mayo', 'Mayo'), ('Junio', 'Junio'),
        ('Julio', 'Julio'), ('Agosto', 'Agosto'), ('Septiembre', 'Septiembre'),
        ('Octubre', 'Octubre'), ('Noviembre', 'Noviembre'), ('Diciembre', 'Diciembre')
    ]

    group = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        label="Grupo",
        required=True
    )

    month = forms.ChoiceField(
        choices=MONTH_CHOICES,
        label="Mes",
        required=True
    )

    year = forms.ChoiceField(
        choices=[(y, y) for y in range(datetime.datetime.now().year, datetime.datetime.now().year + 6)],
        label="Año",
        required=True
    )