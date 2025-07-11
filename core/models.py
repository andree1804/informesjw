from django.db import models
from django.core.validators import MinValueValidator

class Group(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Privilege(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class PrivilegePermanent(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Person(models.Model):
    GENDER_CHOICES = [
        (True, 'Hombre'),
        (False, 'Mujer'),
    ]

    HOPE_CHOICES = [
        (True, 'Ungido'),
        (False, 'Muchedumbre'),
    ]
    names = models.CharField(max_length=100)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    privilege = models.ForeignKey(Privilege, on_delete=models.CASCADE)
    privileges_permanent = models.ManyToManyField(PrivilegePermanent, null=True, blank=True)
    birth = models.DateField("Fecha de nacimiento", null=True, blank=True)
    baptism = models.DateField("Fecha de bautismo", null=True, blank=True)
    gender = models.BooleanField(choices=GENDER_CHOICES, default=False)
    hope = models.BooleanField(choices=HOPE_CHOICES, default=False)

    def __str__(self):
        return f"{self.names}"


class Report(models.Model):
    MONTH_CHOICES = [
        ('1', 'Enero'), ('2', 'Febrero'), ('3', 'Marzo'),
        ('4', 'Abril'), ('5', 'Mayo'), ('6', 'Junio'),
        ('7', 'Julio'), ('8', 'Agosto'), ('9', 'Septiembre'),
        ('10', 'Octubre'), ('11', 'Noviembre'), ('12', 'Diciembre')
    ]
    person = models.ForeignKey('Person', on_delete=models.CASCADE)
    group = models.ForeignKey('Group', on_delete=models.CASCADE)
    privilege = models.ForeignKey('Privilege', on_delete=models.CASCADE)
    courses = models.IntegerField()
    hours = models.IntegerField()
    participated = models.BooleanField(default=False)
    month = models.CharField(max_length=20, choices=MONTH_CHOICES)
    year = models.IntegerField()
    note = models.CharField(max_length=250, null=True, blank=True)


    class Meta:
        verbose_name = "Informe de servicio"
        verbose_name_plural = "Informes de servicio"
        unique_together = ('person', 'month', 'year')

    def __str__(self):
        return f"Reporte de {self.person} - {self.month} {self.year}"


class PersonVirtual(models.Model):
    in_person = models.PositiveIntegerField(
        "Asistencia Presencial",
        blank=True,
        validators=[MinValueValidator(0)]
    )
    virtual = models.PositiveIntegerField(
        "Asistencia Zoom",
        blank=True,
        validators=[MinValueValidator(0)]
    )
    meeting_date = models.DateField("Fecha de reunión")
    
    class Meta:
        verbose_name = "Asistencia a reunión"
        verbose_name_plural = "Asistencias a reuniones"
        ordering = ['-meeting_date']
        unique_together = (('meeting_date',),)
    
    def __str__(self):
        return f"Presencial: {self.in_person}, Virtual: {self.virtual} - {self.meeting_date}"
    
    @property
    def total(self):
        return self.in_person + self.virtual