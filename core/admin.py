from django.contrib import admin
from django.shortcuts import render, redirect
from django.urls import path
from django.contrib import messages
from .models import Report, Person, Group, Privilege
from .forms import GroupSelectForm

from .models import PersonVirtual
from django import forms
from django.db.models import Sum
from collections import OrderedDict
from .forms import GroupSelectForm
from django.urls import reverse
from datetime import datetime
from io import BytesIO
from reportlab.pdfgen import canvas
from django.template.loader import render_to_string
from django.http import HttpResponse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.timezone import localtime
from django.utils.safestring import mark_safe

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import base64
import requests


class ReportAdmin(admin.ModelAdmin):
    change_list_template = "admin/reportes_por_grupo.html"

    def changelist_view(self, request, extra_context=None):
        #form = GroupSelectForm(request.GET or None)
        now = datetime.now()
        meses = [
            "enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
        ]

        nombre_mes = meses[now.month - 2]
        persons = []
        group_id = request.GET.get('group')
        selected_month = request.GET.get('month', str(nombre_mes.capitalize()))
        selected_year = request.GET.get('year', str(now.year))
        #current_month = request.GET.get('month_', str(now.month))
        #current_year = request.GET.get('year_', str(now.year))

        form = GroupSelectForm({
            'month': selected_month,
            'year': selected_year,
            **request.GET
        })

        if request.user.username != 'admin':
            groups = Group.objects.filter(name=request.user.username.capitalize()).first()
        else:
            groups = Group.objects.all()
        if group_id and selected_month and selected_year:
            if request.user.username != 'admin':
                persons = list(Person.objects.filter(group_id=groups.id).order_by('names'))
            else:
                persons = list(Person.objects.filter(group_id=group_id).order_by('names'))
            
            # Obtener los reportes ya existentes
            reports = Report.objects.filter(
                person__in=persons,
                month=selected_month,
                year=selected_year
            ).select_related('privilege')

            report_map = {r.person_id: r for r in reports}

            for person in persons:
                person.existing_report = report_map.get(person.id)

        if request.method == "POST":
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
                    courses_str = request.POST.get(f'courses_{i}', '0')
                    courses = int(courses_str) if courses_str.strip().isdigit() else 0
                    hours_str = request.POST.get(f'hours_{i}', '0')
                    hours = int(hours_str) if hours_str.strip().isdigit() else 0
                    #courses = int(request.POST.get(f'courses_{i}', 0))
                    #hours = int(request.POST.get(f'hours_{i}', 0))
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

        if request.user.username != 'admin':
            form.fields['group'].initial = groups.id if groups else None
            form.fields['group'].choices = [
                (groups.id, groups.name) if groups else ('', '---')
            ]
        context = {
            'form': form,
            'persons': persons,
            'group_id': group_id,
            'mes_actual': selected_month,
            'año_actual': selected_year,
            'privilegios': Privilege.objects.all().order_by('id'),
            'group': group_id,
            'month': selected_month,
            'year': selected_year,
        }

        if extra_context:
            context.update(extra_context)

        return render(request, self.change_list_template, context)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'consolidado/',
                self.admin_site.admin_view(ConsolidatedAdmin(Report, self.admin_site).changelist_view),
                name='report_consolidated'
            ),
        ]
        return custom_urls + urls


@admin.register(PersonVirtual)
class MeetingAttendanceAdmin(admin.ModelAdmin):
    list_display = ('formatted_date', 'in_person', 'virtual', 'total_attendance')
    list_filter = ('meeting_date',)
    date_hierarchy = 'meeting_date'
    change_list_template = 'admin/meeting_attendance_change_list.html'
    
    def changelist_view(self, request, extra_context=None):
        # Obtener el mes y año actual
        now = datetime.now()
        current_month = request.GET.get('month_', str(now.month))
        current_year = request.GET.get('year_', str(now.year))
        
        # Si no hay parámetros GET, redirigir con los valores por defecto
        if not request.GET.get('month_') and not request.GET.get('year_'):
            base_url = reverse('admin:core_personvirtual_changelist')
            return redirect(f'{base_url}?year_={current_year}&month_={current_month}')
        
        form = GroupSelectForm({
            'month': current_month,
            'year': current_year,
            **request.GET
        })
        
        # Resto de tu lógica existente...
        registros = PersonVirtual.objects.filter(
            meeting_date__month=current_month,
            meeting_date__year=current_year
        ).order_by('meeting_date')

        meses = OrderedDict()
        for reg in registros:
            fecha = reg.meeting_date
            mes = fecha.strftime("%B") if fecha else "Sin fecha"
            if mes not in meses:
                meses[mes] = {'registros': [], 'subtotal': 0}
            meses[mes]['registros'].append(reg)
            total = (reg.in_person or 0) + (reg.virtual or 0)
            meses[mes]['subtotal'] += total

        totales = PersonVirtual.objects.aggregate(
            total_in_person=Sum('in_person'),
            total_virtual=Sum('virtual')
        )
        total_general = (totales['total_in_person'] or 0) + (totales['total_virtual'] or 0)

        context = {
            'meses': meses,
            'total_in_person': totales['total_in_person'] or 0,
            'total_virtual': totales['total_virtual'] or 0,
            'total_general': total_general,
            'form': form,
        }

        if extra_context:
            context.update(extra_context)

        return render(request, self.change_list_template, context)

    def formatted_date(self, obj):
        return obj.meeting_date.strftime("%A-%d") if obj.meeting_date else "-"
    formatted_date.short_description = 'Fecha'
    
    def total_attendance(self, obj):
        return (obj.in_person or 0) + (obj.virtual or 0)
    total_attendance.short_description = 'Total'

    def save_model(self, request, obj, form, change):
        if obj.in_person is None:
            obj.in_person = 0
        if obj.virtual is None:
            obj.virtual = 0
        super().save_model(request, obj, form, change)

    '''def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('add-image/', self.admin_site.admin_view(self.add_image), name='personvirtual_add'),
        ]
        return custom_urls + urls
    
    @csrf_exempt
    def add_image(self, request):
        if request.method == 'POST' and request.FILES.get('image'):
            try:
                # 1. Configuración Roboflow
                api_key = "9pl2Yoxz8KxtvOIJ7SY4"
                workspace = "andree1804"
                model_name = "yolov8-person-detection"
                version = "7"

                # 1. Construir URL
                url = f"https://detect.roboflow.com/{model_name}/{version}?api_key={api_key}"

                # 2. Leer la imagen desde request.FILES
                image_file = request.FILES['image']

                # 3. Enviar POST con el archivo como multipart/form-data
                response = requests.post(
                    url,
                    files={"file": image_file},
                    data={"confidence": "0.5", "overlap": "0.3"},
                    timeout=10
                )
                
                # 4. Procesar respuesta
                if response.status_code == 200:
                    predictions = response.json().get('predictions', [])
                    return JsonResponse({
                        'success': True,
                        'count': len(predictions)
                    })
                else:
                    return JsonResponse({
                        'success': False,
                        'error': f"Error {response.status_code}: {response.text}"
                    })
                    
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': str(e)
                })
        
        return JsonResponse({
            'success': False,
            'error': 'No se recibió imagen válida'
        })'''


class ConsolidatedAdmin(admin.ModelAdmin):
    list_display = ('person', 'group', 'privilege', 'month', 'year')
    list_filter = ('month', 'year', 'group', 'privilege')
    search_fields = ('person__name',)
    
    change_list_template = 'admin/reports_consolidated.html'
    
    def changelist_view(self, request, extra_context=None):
        if 'generate_report' in request.GET:
            month = request.GET.get('month')
            year = request.GET.get('year')

            month_list = {
                'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
                'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
                'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
            }

            month_int = month_list[month.lower()]
            
            # Obtener datos consolidados
            reports = Report.objects.filter(month=month, year=year)
            person_virtual = PersonVirtual.objects.filter(meeting_date__month=month_int, meeting_date__year=year)

            # Filtrar solo sábados y domingos
            fines_de_semana = [
                pv for pv in person_virtual
                if pv.meeting_date.weekday() in (5, 6)
            ]

            # Calcular asistencia total en fines de semana
            total_asistencia = sum(
                (pv.in_person or 0) + (pv.virtual or 0)
                for pv in fines_de_semana
            )

            # Calcular asistencia promedio
            cantidad_reuniones = len(fines_de_semana)
            asistencia_promedio = (
                total_asistencia / cantidad_reuniones
                if cantidad_reuniones > 0 else 0
            )
            
            # Calcular estadísticas
            stats = {
                'publicadores': {
                    'count': reports.filter(privilege__name='Publicador', participated=True).count(),
                    'courses': reports.filter(privilege__name='Publicador').aggregate(Sum('courses'))['courses__sum'] or 0,
                },
                'auxiliares': {
                    'count': reports.filter(privilege__name='Auxiliar', participated=True).count(),
                    'hours': reports.filter(privilege__name='Auxiliar').aggregate(Sum('hours'))['hours__sum'] or 0,
                    'courses': reports.filter(privilege__name='Auxiliar').aggregate(Sum('courses'))['courses__sum'] or 0,
                },
                'regulares': {
                    'count': reports.filter(privilege__name='PR', participated=True).count(),
                    'hours': reports.filter(privilege__name='PR').aggregate(Sum('hours'))['hours__sum'] or 0,
                    'courses': reports.filter(privilege__name='PR').aggregate(Sum('courses'))['courses__sum'] or 0,
                },
                'total_activos': reports.filter(participated=True).count(),
                'asistencia_promedio': round(asistencia_promedio, 1),
                'month': month,
                'year': year,
                'updated_by': request.user.get_full_name(),
                'updated_date': date_format(localtime(), format='j \d\e F \d\e Y', use_l10n=True)
            }
            
            if request.GET.get('format') == 'pdf':
                return self.generate_pdf_report(stats)
            else:
                extra_context = {'stats': stats}
        
        return super().changelist_view(request, extra_context=extra_context)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'reportes_por_grupo/',
                self.admin_site.admin_view(ReportAdmin(Report, self.admin_site).changelist_view),
                name='reportes_por_grupo'
            ),
        ]
        return custom_urls + urls
    
    def generate_pdf_report(self, stats):
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="informe_{stats["month"]}_{stats["year"]}.pdf"'
        
        buffer = BytesIO()
        p = canvas.Canvas(buffer)
        
        # Configuración inicial
        p.setTitle(f"Informe Consolidado - {stats['month']} {stats['year']}")
        
        # Encabezado
        p.setFont("Helvetica-Bold", 16)
        p.drawString(100, 800, "Informes de la congregación - Pedregal")
        p.setFont("Helvetica", 12)
        p.drawString(100, 750, "PREDICACIÓN Y ASISTENCIA A LAS REUNIONES")
        
        # Fecha y actualización
        p.drawString(100, 730, f"{stats['month']} de {stats['year']}")
        p.drawString(100, 715, f"Actualizado por: {stats['updated_by']}")
        p.drawString(100, 700, f"Actualizado el: {stats['updated_date']}")
        
        # Totales
        p.drawString(100, 685, "Todos los publicadores activos")
        p.drawString(400, 685, str(stats['total_activos']))
        # Asistencia promedio solo fin de semana
        p.drawString(100, 670, "Promedio asistencia a reuniones de fin de semana")
        p.drawString(400, 670, str(stats['asistencia_promedio']))

        # Publicadores
        p.setFont("Helvetica-Bold", 14)
        p.drawString(100, 650, "Publicadores")
        p.setFont("Helvetica", 12)
        p.drawString(120, 635, "Cantidad de informes")
        p.drawString(400, 635, str(stats['publicadores']['count']))
        p.drawString(120, 620, "Cursos bíblicos")
        p.drawString(400, 620, str(stats['publicadores']['courses']))
        
        # Precursores auxiliares
        p.setFont("Helvetica-Bold", 14)
        p.drawString(100, 590, "Precursores auxiliares")
        p.setFont("Helvetica", 12)
        p.drawString(120, 575, "Cantidad de informes")
        p.drawString(400, 575, str(stats['auxiliares']['count']))
        p.drawString(120, 560, "Horas")
        p.drawString(400, 560, str(stats['auxiliares']['hours']))
        p.drawString(120, 545, "Cursos bíblicos")
        p.drawString(400, 545, str(stats['auxiliares']['courses']))
        
        # Precursores regulares
        p.setFont("Helvetica-Bold", 14)
        p.drawString(100, 515, "Precursores regulares")
        p.setFont("Helvetica", 12)
        p.drawString(120, 500, "Cantidad de informes")
        p.drawString(400, 500, str(stats['regulares']['count']))
        p.drawString(120, 485, "Horas")
        p.drawString(400, 485, str(stats['regulares']['hours']))
        p.drawString(120, 470, "Cursos bíblicos")
        p.drawString(400, 470, str(stats['regulares']['courses']))
        
        p.showPage()
        p.save()
        
        pdf = buffer.getvalue()
        buffer.close()
        response.write(pdf)
        
        return response


admin.site.register(Report, ReportAdmin)
admin.site.register(Group)
admin.site.register(Privilege)
admin.site.register(Person)