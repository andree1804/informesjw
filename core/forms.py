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

    MONTH_CHOICES_ = [
        ('1', 'Enero'), ('2', 'Febrero'), ('3', 'Marzo'),
        ('4', 'Abril'), ('5', 'Mayo'), ('6', 'Junio'),
        ('7', 'Julio'), ('8', 'Agosto'), ('9', 'Septiembre'),
        ('10', 'Octubre'), ('11', 'Noviembre'), ('12', 'Diciembre')
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

    month_ = forms.ChoiceField(
        choices=MONTH_CHOICES_,
        label="Mes",
        required=True
    )

    year_ = forms.ChoiceField(
        choices=[(y, y) for y in range(datetime.datetime.now().year, datetime.datetime.now().year + 6)],
        label="Año",
        required=True
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set default values for month and year
        now = datetime.datetime.now()
        
        # Set current month (convert to string to match your choices)
        self.fields['month_'].initial = str(now.month)
        
        # Set current year
        self.fields['year_'].initial = now.year