from django.contrib import admin
from django.shortcuts import render, redirect
from django.urls import path
from django.contrib import messages
from .models import Report, Person, Group, Privilege
from .forms import GroupSelectForm

class ReportAdmin(admin.ModelAdmin):
    change_list_template = "admin/reportes_por_grupo.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'reportes_por_grupo/',
                self.admin_site.admin_view(self.reportes_por_grupo),
                name="reportes_por_grupo"
            ),
        ]
        return custom_urls + urls

    def reportes_por_grupo(self, request):
        form = GroupSelectForm(request.GET or None)
        persons = []
        group_id = request.GET.get('group')
        selected_month = request.GET.get('month')
        selected_year = request.GET.get('year')

        if group_id and selected_month and selected_year:
            persons = list(Person.objects.filter(group_id=group_id))

            # Asociar los reportes existentes a las personas
            reports = Report.objects.filter(
                person__in=persons,
                month=selected_month,
                year=selected_year
            ).select_related('privilege')

            report_map = {r.person_id: r for r in reports}

            # Adjuntar los datos del reporte a cada persona
            for person in persons:
                report = report_map.get(person.id)
                if report:
                    person.existing_report = report
                else:
                    person.existing_report = None

        if request.method == "POST":
            # Obtener los valores seleccionados desde los inputs ocultos
            group_id = request.POST.get('group')
            selected_month = request.POST.get('month')
            selected_year = request.POST.get('year')
            total = int(request.POST.get('total', 0))

            try:
                group = Group.objects.get(pk=group_id)
            except Group.DoesNotExist:
                messages.error(request, "Grupo no encontrado.")
                return redirect(request.path)

            for i in range(total):
                person_id = request.POST.get(f'person_{i}')
                if not person_id:
                    continue

                try:
                    person = Person.objects.get(pk=person_id)
                    privilege = Privilege.objects.get(pk=int(request.POST.get(f'privilege_{i}')))
                    courses = int(request.POST.get(f'courses_{i}', 0))
                    hours = int(request.POST.get(f'hours_{i}', 0))
                    participated = f'participated_{i}' in request.POST

                    Report.objects.update_or_create(
                        person=person,
                        month=selected_month,
                        year=selected_year,
                        defaults={
                            'group': group,
                            'privilege': privilege,
                            'courses': courses,
                            'hours': hours,
                            'participated': participated
                        }
                    )
                except Exception as e:
                    messages.error(request, f"Error al guardar para ID {person_id}: {str(e)}")

            messages.success(request, "Datos guardados correctamente.")
            return redirect(f"{request.path}?group={group_id}&month={selected_month}&year={selected_year}")

        return render(request, 'admin/reportes_por_grupo.html', {
            'form': form,
            'persons': persons,
            'group_id': group_id,
            'mes_actual': selected_month,
            'año_actual': selected_year,
            'privilegios': Privilege.objects.all().order_by('-id'),
            'group': group_id,
            'month': selected_month,
            'year': selected_year,
        })

admin.site.register(Report, ReportAdmin)
admin.site.register(Group)
admin.site.register(Privilege)
admin.site.register(Person)