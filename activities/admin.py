from django.contrib import admin
from django.urls import path
from .views import guia_actividades_view, guia_actividades2_view, guia_actividades3_view, guia_mes_completo_view
from .models import GuiaActividades
from django.shortcuts import redirect
from django.urls import reverse

# Guardar la función original
original_get_urls = admin.site.get_urls

@admin.register(GuiaActividades)
class GuiaActividadesAdmin(admin.ModelAdmin):
    
    # Este método controla qué pasa cuando entras al modelo en el admin
    def changelist_view(self, request, extra_context=None):
        # Redirige directamente a la URL de tu herramienta
        return redirect(reverse('guia_mes'))
        
    # Bloqueamos los permisos para que nadie intente "añadir" o "borrar" este modelo falso
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

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