from django.core.management.base import BaseCommand
from django.conf import settings
import os
import csv
import re
from datetime import datetime
from pdfminer.high_level import extract_text  # Nueva dependencia para PDFs estáticos

class Command(BaseCommand):
    help = 'Procesa PDFs de publicadores y genera CSV con todos los campos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='publicadores_consolidado.csv',
            help='Nombre del archivo CSV de salida'
        )

    def handle(self, *args, **options):
        input_folder = os.path.join(settings.BASE_DIR, 'cards/pdfs')
        output_csv = os.path.join(settings.BASE_DIR, 'cards', options['output'])

        if not os.path.exists(input_folder):
            self.stderr.write(self.style.ERROR(f'No existe la carpeta: {input_folder}'))
            return

        self.stdout.write(self.style.SUCCESS(f'\nProcesando PDFs en: {input_folder}'))

        all_data = []
        for filename in sorted(os.listdir(input_folder)):
            if filename.lower().endswith('.pdf'):
                pdf_path = os.path.join(input_folder, filename)
                self.stdout.write(f'Procesando: {filename}...', ending='\r')
                
                nombre_publicador = os.path.splitext(filename)[0].replace('_', ' ')
                data = self._procesar_pdf(pdf_path, nombre_publicador)
                if data:
                    all_data.extend(data)

        if all_data:
            self._generar_csv(all_data, output_csv)
        else:
            self.stderr.write(self.style.ERROR('\nNo se encontraron datos válidos'))

    def _procesar_pdf(self, pdf_path, nombre_publicador):
        try:
            # Extraer texto del PDF
            text = extract_text(pdf_path)
            
            # Procesar datos personales
            datos_personales = {
                'Nombre': nombre_publicador,  # Usamos el nombre del archivo como fallback
                'Fecha de nacimiento': '',
                'Fecha de bautismo': '',
                'Hombre/Mujer': '',
                'Otras ovejas/Ungido': '',
                'Anciano/Siervo/Precursor regular': []
            }
            
            # Buscar datos en el texto
            if "Nombre:" in text:
                # Extraer nombre después de "Nombre:"
                nombre_match = re.search(r"Nombre:\s*(.*?)(?:\n|$)", text)
                if nombre_match and nombre_match.group(1).strip():
                    datos_personales['Nombre'] = nombre_match.group(1).strip()
            
            # Buscar checkboxes marcados
            checkbox_mapping = {
                'Anciano': r"☒\s*Anciano|Anciano\s*☒",
                'Siervo ministerial': r"☒\s*Siervo ministerial|Siervo ministerial\s*☒",
                'Precursor regular': r"☒\s*Precursor regular|Precursor regular\s*☒"
            }
            
            for rol, pattern in checkbox_mapping.items():
                if re.search(pattern, text, re.IGNORECASE):
                    datos_personales['Anciano/Siervo/Precursor regular'].append(rol)
            
            # Procesar datos mensuales
            meses = [
                'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
                'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                'Julio', 'Agosto'
            ]
            
            datos_mensuales = []
            for mes in meses:
                # Buscar participación (☒ en la columna)
                participacion = 'Sí' if f"| {mes}    | ☒" in text else 'No'
                
                # Buscar precursor auxiliar (☒ en la columna)
                precursor = 'Sí' if f"| ☒    |" in text.split(mes)[1].split('\n')[0] else 'No'
                
                datos_mensuales.append({
                    'Mes': mes,
                    'Participacion': participacion,
                    'Cursos': '0',  # No visible en el ejemplo
                    'Precursor_auxiliar': precursor,
                    'Horas': '0',  # No visible en el ejemplo
                    'Notas': ''     # No visible en el ejemplo
                })
            
            return self._combinar_datos(datos_personales, datos_mensuales)
            
        except Exception as e:
            self.stderr.write(f'\n⚠️ Error en {os.path.basename(pdf_path)}: {str(e)}')
            return []

    def _combinar_datos(self, personales, mensuales):
        registros = []
        for mes in mensuales:
            registros.append({
                'Nombre': personales['Nombre'],
                'Fecha de nacimiento': personales['Fecha de nacimiento'],
                'Fecha de bautismo': personales['Fecha de bautismo'],
                'Hombre/Mujer': personales['Hombre/Mujer'],
                'Otras ovejas/Ungido': personales['Otras ovejas/Ungido'],
                'Anciano/Siervo/Precursor regular': ', '.join(personales['Anciano/Siervo/Precursor regular']) or 'Publicador',
                'Año de servicio': mes['Mes'],
                'Participacion en el ministerio': mes['Participacion'],
                'Cursos biblicos': mes['Cursos'],
                'Precursor auxiliar': mes['Precursor_auxiliar'],
                'Horas': mes['Horas'],
                'Notas': mes['Notas']
            })
        return registros

    def _generar_csv(self, data, output_path):
        fieldnames = [
            'Nombre', 'Fecha de nacimiento', 'Fecha de bautismo',
            'Hombre/Mujer', 'Otras ovejas/Ungido',
            'Anciano/Siervo/Precursor regular', 'Año de servicio',
            'Participacion en el ministerio', 'Cursos biblicos',
            'Precursor auxiliar', 'Horas', 'Notas'
        ]
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        
        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Archivo CSV generado exitosamente: {output_path}\n'
            f'📄 Total de registros: {len(data)}'
        ))