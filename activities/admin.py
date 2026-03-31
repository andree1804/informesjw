from django.contrib import admin
from django.urls import path
from .views import guia_actividades_view, guia_actividades2_view, guia_actividades3_view, guia_mes_completo_view

# Guardar la función original
original_get_urls = admin.site.get_urls

def custom_get_urls():
    custom_urls = [
        path(
            "guia-actividades/",
            admin.site.admin_view(guia_actividades_view),
            name="guia_actividades"
        ),
        path(
            "guia-actividades2/",
            admin.site.admin_view(guia_actividades2_view),
            name="guia_actividades2"
        ),
        path(
            "guia-actividades3/",
            admin.site.admin_view(guia_actividades3_view),
            name="guia_actividades3"
        ),
        path(
            "guia-mes-completo/",
            admin.site.admin_view(guia_mes_completo_view),
            name="guia_mes_completo"
        ),
    ]
    # llamar a la original
    return custom_urls + original_get_urls()

# Reemplazar get_urls con la versión personalizada
admin.site.get_urls = custom_get_urls