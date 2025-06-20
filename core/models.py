from django.db import models

class Group(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Privilege(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Person(models.Model):
    names = models.CharField(max_length=100)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    privilege = models.ForeignKey(Privilege, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.names}"


class Report(models.Model):
    MONTH_CHOICES = [
        ('Enero', 'Enero'), ('Febrero', 'Febrero'), ('Marzo', 'Marzo'),
        ('Abril', 'Abril'), ('Mayo', 'Mayo'), ('Junio', 'Junio'),
        ('Julio', 'Julio'), ('Agosto', 'Agosto'), ('Septiembre', 'Septiembre'),
        ('Octubre', 'Octubre'), ('Noviembre', 'Noviembre'), ('Diciembre', 'Diciembre')
    ]
    person = models.ForeignKey('Person', on_delete=models.CASCADE)
    group = models.ForeignKey('Group', on_delete=models.CASCADE)
    privilege = models.ForeignKey('Privilege', on_delete=models.CASCADE)
    courses = models.IntegerField()
    hours = models.IntegerField()
    participated = models.BooleanField(default=False)
    month = models.CharField(max_length=20, choices=MONTH_CHOICES)
    year = models.IntegerField()

    class Meta:
        unique_together = ('person', 'month', 'year')

    def __str__(self):
        return f"Reporte de {self.person} - {self.month} {self.year}"