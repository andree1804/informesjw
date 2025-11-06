'''from django.contrib import admin
from django.urls import path
from .views import guia_actividades_view

# Guardar la función original
original_get_urls = admin.site.get_urls

def custom_get_urls():
    custom_urls = [
        path(
            "guia-actividades/",
            admin.site.admin_view(guia_actividades_view),
            name="guia_actividades"
        ),
    ]
    # llamar a la original
    return custom_urls + original_get_urls()

# Reemplazar get_urls con la versión personalizada
admin.site.get_urls = custom_get_urls'''