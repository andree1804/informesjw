from django.db import models

from django.contrib.auth.models import Group

class GuiaActividades(Group):
    class Meta:
        proxy = True  # <--- ¡ESTO ES LO VITAL! No crea tabla en la Base de Datos.
        verbose_name = "Vida y Ministerio Cristianos"
        verbose_name_plural = "Vida y Ministerio Cristianos"
