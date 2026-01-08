from django import forms
from .models import Group
from .models import Person
import datetime

class GroupSelectForm(forms.Form):
    '''MONTH_CHOICES = [
        ('Enero', 'Enero'), ('Febrero', 'Febrero'), ('Marzo', 'Marzo'),
        ('Abril', 'Abril'), ('Mayo', 'Mayo'), ('Junio', 'Junio'),
        ('Julio', 'Julio'), ('Agosto', 'Agosto'), ('Septiembre', 'Septiembre'),
        ('Octubre', 'Octubre'), ('Noviembre', 'Noviembre'), ('Diciembre', 'Diciembre')
    ]'''

    MONTH_CHOICES = [
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

    '''year = forms.ChoiceField(
        choices=[(y, y) for y in range(datetime.datetime.now().year, datetime.datetime.now().year + 6)],
        label="Año",
        required=True,
        initial=datetime.datetime.now().year
    )'''
    year = forms.ChoiceField(
        choices=[
            (y, y)
            for y in range(
                datetime.datetime.now().year - 5,
                datetime.datetime.now().year + 6
            )
        ],
        label="Año",
        required=True,
        initial=datetime.datetime.now().year
    )

    month_ = forms.ChoiceField(
        choices=MONTH_CHOICES,
        label="Mes",
        required=True
    )

    year_ = forms.ChoiceField(
        choices=[
            (y, y)
            for y in range(
                datetime.datetime.now().year - 5,
                datetime.datetime.now().year + 6
            )
        ],
        label="Año",
        required=True,
        initial=datetime.datetime.now().year
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set default values for month and year
        now = datetime.datetime.now()
        
        # Set current month (convert to string to match your choices)
        self.fields['month_'].initial = str(now.month)
        
        # Set current year
        self.fields['year_'].initial = now.year


class PersonForm(forms.ModelForm):
    # Define some default contact fields (will be extended in __init__)
    contact_name_0 = forms.CharField(required=False, label='Nombre del contacto #1')
    contact_phone_0 = forms.CharField(required=False, label='Teléfono del contacto #1')
    contact_name_1 = forms.CharField(required=False, label='Nombre del contacto #2')
    contact_phone_1 = forms.CharField(required=False, label='Teléfono del contacto #2')
    contact_name_2 = forms.CharField(required=False, label='Nombre del contacto #3')
    contact_phone_2 = forms.CharField(required=False, label='Teléfono del contacto #3')

    class Meta:
        model = Person
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        existing_contacts = self.instance.contacts if self.instance and self.instance.contacts else []
        total_contacts = max(3, len(existing_contacts))
        
        # Update initial data for existing contacts
        for i in range(total_contacts):
            if i < len(existing_contacts):
                self.fields[f'contact_name_{i}'].initial = existing_contacts[i].get('apoderado', '')
                self.fields[f'contact_phone_{i}'].initial = existing_contacts[i].get('telefono', '')

    def clean(self):
        cleaned_data = super().clean()
        contacts = []
        
        # Collect all contact data
        i = 0
        while True:
            name_field = f'contact_name_{i}'
            phone_field = f'contact_phone_{i}'
            
            if name_field not in self.fields:
                break
                
            name = cleaned_data.get(name_field, '').strip()
            phone = cleaned_data.get(phone_field, '').strip()
            
            if name or phone:
                contacts.append({
                    'apoderado': name,
                    'telefono': phone
                })
            i += 1
        
        self.instance.contacts = contacts
        return cleaned_data