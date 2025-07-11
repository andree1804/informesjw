from django.contrib import admin
from django.shortcuts import render, redirect
from django.urls import path
from django.contrib import messages
from .models import Report, Person, Group, Privilege, PrivilegePermanent
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
import calendar
import locale

from django.shortcuts import get_object_or_404
from pdfrw import PdfReader, PdfWriter, PdfDict, PdfObject, PdfName
import os
import tempfile
import zipfile

from django.conf import settings
#import requests


class ReportAdmin(admin.ModelAdmin):
    change_list_template = "admin/reportes_por_grupo.html"

    def changelist_view(self, request, extra_context=None):
        now = datetime.now()
        if now.month == 1:  # Si es enero
            previous_year = now.year - 1
        else:
            previous_year = now.year

        previous_month = now.month - 1
        persons = []
        group_id = request.GET.get('group')
        selected_month = request.GET.get('month', previous_month)
        selected_year = request.GET.get('year', previous_year)

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
                if person.existing_report:
                    person.privilege = person.existing_report.privilege  # <--- esta línea es CLAVE

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
                    privilege_id = request.POST.get(f'privilege_{i}')
                    privilege = Privilege.objects.get(pk=int(privilege_id)) if privilege_id else None

                    courses_str = request.POST.get(f'courses_{i}', '0')
                    hours_str = request.POST.get(f'hours_{i}', '0')
                    courses = int(courses_str) if courses_str.strip().isdigit() else 0
                    hours = int(hours_str) if hours_str.strip().isdigit() else 0
                    participated = f'participated_{i}' in request.POST
                    note = request.POST.get(f'note_{i}', '')

                    report, created = Report.objects.get_or_create(
                        person=person,
                        month=selected_month,
                        year=selected_year,
                        defaults={
                            'group': group,
                            'privilege': privilege,
                            'courses': courses,
                            'hours': hours,
                            'participated': participated,
                            'note': note
                        }
                    )

                    if not created:
                        report.group = group
                        report.privilege = privilege
                        report.courses = courses
                        report.hours = hours
                        report.participated = participated
                        report.note = note
                        report.save()
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
            **self.admin_site.each_context(request),
            'form': form,
            'persons': persons,
            'group_id': group_id,
            'mes_actual': selected_month,
            'año_actual': selected_year,
            'privilegios': Privilege.objects.all().order_by('id'),
            'group': group_id,
            'month': selected_month,
            'year': selected_year,
            'opts': self.model._meta,  # Necesario para el admin
            'title': 'Informes de servicio',
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
            path(
                'generar-pdf/',
                self.admin_site.admin_view(self.generar_pdf),
                name='report_generar_pdf',
            ),
        ]
        return custom_urls + urls

    def fill_pdf(self, person, reports, template_path, output_path):
        template = PdfReader(template_path)

        # Activar renderizado visual de campos
        if template.Root.AcroForm:
            template.Root.AcroForm.update(PdfDict(NeedAppearances=PdfObject('true')))

        for page in template.pages:
            annotations = page['/Annots']
            if not annotations:
                continue

            for annotation in annotations:
                field_raw = annotation.get('/T')
                if not field_raw:
                    continue

                # Decodificar UTF-16 (quitar þÿ)
                field = field_raw.to_unicode().replace('þÿ', '').strip()
                
                # Campos individuales
                if field == '900_1_Text_SanSerif':
                    annotation.update(PdfDict(V=person.names))
                if field == '900_2_Text_SanSerif' and person.birth:
                    annotation.update(PdfDict(V=str(person.birth)))
                if field == '900_3_CheckBox' and person.gender == True:
                    annotation.update(PdfDict(AS=PdfName('Yes')))
                if field == '900_4_CheckBox' and person.gender == False:
                    annotation.update(PdfDict(AS=PdfName('Yes')))
                if field == '900_5_Text_SanSerif' and person.baptism:
                    annotation.update(PdfDict(V=str(person.baptism)))
                if field == '900_6_CheckBox' and person.hope == False:
                    annotation.update(PdfDict(AS=PdfName('Yes')))
                if field == '900_7_CheckBox' and person.hope == True:
                    annotation.update(PdfDict(AS=PdfName('Yes')))

                for priv in person.privileges_permanent.all():
                    if field == '900_8_CheckBox' and priv.name == 'Anciano':
                        annotation.update(PdfDict(AS=PdfName('Yes')))
                    if field == '900_9_CheckBox' and priv.name == 'Siervo Ministerial':
                        annotation.update(PdfDict(AS=PdfName('Yes')))
                    if field == '900_10_CheckBox' and priv.name == 'Precursor Regular':
                        annotation.update(PdfDict(AS=PdfName('Yes')))
                    if field == '900_11_CheckBox' and priv.name == 'Precursor Especial':
                        annotation.update(PdfDict(AS=PdfName('Yes')))
                    if field == '900_12_CheckBox' and priv.name == 'Misionero':
                        annotation.update(PdfDict(AS=PdfName('Yes')))
                if field == '900_13_Text_C_SanSerif':
                    annotation.update(PdfDict(V=f"{(reports[0].year)-1}-{int(reports[0].year)}"))

                # Meses dinámicos
                for report in reports:
                    #m = int(report.month)
                    total_hours = sum(int(r.hours or 0) for r in reports)
                    if int(report.month) == 9:
                        m = 1
                    elif int(report.month) == 10:
                        m = 2
                    elif int(report.month) == 11:
                        m = 3
                    elif int(report.month) == 12:
                        m = 4
                    elif int(report.month) == 8:
                        m = 12
                    elif int(report.month) == 7:
                        m = 11
                    elif int(report.month) == 6:
                        m = 10
                    elif int(report.month) == 5:
                        m = 9
                    elif int(report.month) == 4:
                        m = 8
                    elif int(report.month) == 3:
                        m = 7
                    elif int(report.month) == 2:
                        m = 6
                    elif int(report.month) == 1:
                        m = 5

                    if field == f'901_{20 + m - 1}_CheckBox' and report.participated:
                        annotation.update(PdfDict(AS=PdfName('Yes')))
                    elif field == f'902_{20 + m - 1}_Text_C_SanSerif' and report.courses > 0:
                        annotation.update(PdfDict(V=str(report.courses)))
                    elif field == f'903_{20 + m - 1}_CheckBox' and report.privilege.name == 'Auxiliar':
                        annotation.update(PdfDict(AS=PdfName('Yes')))
                    elif field == f'904_{20 + m - 1}_S21_Value' and report.hours > 0:
                        annotation.update(PdfDict(V=str(report.hours)))
                    elif field == f'905_{20 + m - 1}_Text_SanSerif' and report.note:
                        annotation.update(PdfDict(V=str(report.note)))

                if field == '904_32_S21_Value' and total_hours > 0:
                    annotation.update(PdfDict(V=str(total_hours)))  # o el valor dinámico que desees

        PdfWriter().write(output_path, template)

    def generar_pdf(self, request):
        person_id = request.GET.get('person')
        group_id = request.GET.get('group')
        month = request.GET.get('month')
        year = request.GET.get('year')

        template_path = os.path.join(settings.BASE_DIR, 'publisher_cards/pdf_base.pdf')  # <-- actualiza la ruta

        if person_id:
            person = get_object_or_404(Person, pk=person_id)
            reports = Report.objects.filter(person=person, year=year).order_by('month')

            output_path = os.path.join(tempfile.gettempdir(), f"tarjeta_{person.id}.pdf")
            self.fill_pdf(person, list(reports), template_path, output_path)

            with open(output_path, 'rb') as f:
                response = HttpResponse(f.read(), content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename=tarjeta_{person.names}.pdf'
                return response

        elif group_id:
            group = get_object_or_404(Group, pk=group_id)
            persons = Person.objects.filter(group=group).order_by('names')

            temp_dir = tempfile.mkdtemp()
            zip_filename = os.path.join(temp_dir, f"tarjetas_grupo_{group.id}.zip")


            year = int(year)
            if int(month) >= 9:
                years = [year, year + 1]
            else:
                years = [year - 1, year]

            print(years)

            with zipfile.ZipFile(zip_filename, 'w') as zipf:
                for person in persons:
                    reports = Report.objects.filter(person=person, year__in=years).order_by('month')
                    if reports.exists():
                        pdf_path = os.path.join(temp_dir, f"{person.names}.pdf")
                        self.fill_pdf(person, list(reports), template_path, pdf_path)
                        zipf.write(pdf_path, arcname=f"{person.names}.pdf")

            with open(zip_filename, 'rb') as f:
                response = HttpResponse(f.read(), content_type='application/zip')
                response['Content-Disposition'] = f'attachment; filename=tarjetas_{group.name}.zip'
                return response

        else:
            return HttpResponse("Debes enviar al menos 'person' o 'group' en la URL.", status=400)


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
            **self.admin_site.each_context(request),
            'meses': meses,
            'total_in_person': totales['total_in_person'] or 0,
            'total_virtual': totales['total_virtual'] or 0,
            'total_general': total_general,
            'form': form,
            'opts': self.model._meta,  # Necesario para el admin
            'title': 'Asistencia a las reuniones'
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


class ConsolidatedAdmin(admin.ModelAdmin):
    list_display = ('person', 'group', 'privilege', 'month', 'year')
    list_filter = ('month', 'year', 'group', 'privilege')
    search_fields = ('person__name',)
    
    change_list_template = 'admin/reports_consolidated.html'
    
    def changelist_view(self, request, extra_context=None):
        if 'generate_report' in request.GET:
            month = request.GET.get('month')
            year = request.GET.get('year')
            
            # Obtener datos consolidados
            reports = Report.objects.filter(month=month, year=year)
            person_virtual = PersonVirtual.objects.filter(meeting_date__month=month, meeting_date__year=year)

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
        #locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
        MESES_ES = [
            "enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
        ]
        month_es = MESES_ES[int(stats['month']) - 1]

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="informe_{stats["month"]}_{stats["year"]}.pdf"'
        
        buffer = BytesIO()
        p = canvas.Canvas(buffer)
        
        # Configuración inicial
        p.setTitle(f"Informe Consolidado - {month_es} {stats['year']}")
        
        # Encabezado
        p.setFont("Helvetica-Bold", 16)
        p.drawString(100, 800, "Informes de la congregación - Pedregal")
        p.setFont("Helvetica", 12)
        p.drawString(100, 750, "PREDICACIÓN Y ASISTENCIA A LAS REUNIONES")
        
        # Fecha y actualización
        p.drawString(100, 730, f"{month_es.capitalize()} de {stats['year']}")
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
admin.site.register(PrivilegePermanent)
admin.site.register(Person)