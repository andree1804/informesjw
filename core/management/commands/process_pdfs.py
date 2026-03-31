from django.core.management.base import BaseCommand
from django.conf import settings
from pdfrw import PdfReader, PdfDict, PdfName, PdfObject
import os
import csv
import re
from datetime import datetime

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
        input_folder = os.path.join(settings.BASE_DIR, 'cards', 'pdfs')  # Ajustado para que apunte a cards/pdfs
        output_csv = os.path.join(settings.BASE_DIR, 'cards', options['output']) # Ajustado para que el CSV se guarde en cards/

        if not os.path.exists(input_folder):
            self.stderr.write(self.style.ERROR(f'No existe la carpeta: {input_folder}'))
            return

        self.stdout.write(self.style.SUCCESS(f'\nProcesando PDFs en: {input_folder}'))

        all_data = []
        for filename in sorted(os.listdir(input_folder)):
            if filename.lower().endswith('.pdf'):
                pdf_path = os.path.join(input_folder, filename)
                self.stdout.write(f'Procesando: {filename}...', ending='\r')

                # No extraemos el nombre del publicador del filename para datos personales,
                # ya que esperamos que esté en el PDF.
                data = self._procesar_pdf(pdf_path)
                if data:
                    all_data.extend(data)

        if all_data:
            self._generar_csv(all_data, output_csv)
        else:
            self.stderr.write(self.style.ERROR('\nNo se encontraron datos válidos'))

    def _procesar_pdf(self, pdf_path):
        try:
            reader = PdfReader(pdf_path)
            if hasattr(reader, 'Root') and hasattr(reader.Root, 'AcroForm'):
                reader.Root.AcroForm.update(PdfDict(NeedAppearances=PdfObject('true')))

            annotations = self._obtener_todas_anotaciones(reader)
            datos_personales = self._extraer_datos_personales(annotations)
            datos_mensuales = self._extraer_datos_mensuales(annotations)

            return self._combinar_datos(datos_personales, datos_mensuales)

        except Exception as e:
            self.stderr.write(f'\n⚠️ Error en {os.path.basename(pdf_path)}: {str(e)}')
            return []

    def _obtener_todas_anotaciones(self, reader):
        annotations = []
        for page in reader.pages:
            if '/Annots' in page:
                annotations.extend(page['/Annots'])
        return annotations

    def _extraer_valor_campo(self, annotation):
        # Esta función extrae el valor de un campo de formulario PDF
        # Puede variar dependiendo de cómo el PDF almacena los valores.
        # Para campos de texto, generalmente es '/V'.
        # Para CheckBox, el estado 'Yes' indica que está marcado.

        value = annotation.get('/V')
        if value is not None:
            return str(value).replace('þÿ', '').strip()
        
        # Para CheckBoxes, el estado 'AS' indica la apariencia del campo
        # Si es '/Yes', está marcado.
        if annotation.get('/AS') == PdfName('Yes'):
            return 'Yes'
        
        return ''


    def _extraer_datos_personales(self, annotations):
        datos = {
            'Nombre': '',
            'Fecha de nacimiento': '',
            'Fecha de bautismo': '',
            'Hombre/Mujer': '',
            'Otras ovejas/Ungido': '',
            'Anciano/Siervo/Precursor regular': []
        }

        for annotation in annotations:
            try:
                field_raw = annotation.get('/T')
                if not field_raw:
                    continue

                field = field_raw.to_unicode().replace('þÿ', '').strip()
                field_value = self._extraer_valor_campo(annotation)
                appearance = annotation.get('/AS') # Para checkboxes

                if field == '900_1_Text_SanSerif':
                    datos['Nombre'] = field_value
                elif field == '900_2_Text_SanSerif':
                    datos['Fecha de nacimiento'] = self._formatear_fecha(field_value)
                elif field == '900_5_Text_SanSerif':
                    datos['Fecha de bautismo'] = self._formatear_fecha(field_value)
                elif field == '900_4_CheckBox' and appearance == PdfName('Yes'):
                    datos['Hombre/Mujer'] = 'Mujer'
                elif field == '900_3_CheckBox' and appearance == PdfName('Yes'):
                    datos['Hombre/Mujer'] = 'Hombre'
                elif field == '900_7_CheckBox' and appearance == PdfName('Yes'):
                    datos['Otras ovejas/Ungido'] = 'Ungido'
                elif field == '900_6_CheckBox' and appearance == PdfName('Yes'):
                    datos['Otras ovejas/Ungido'] = 'Otras ovejas'
                elif field == '900_8_CheckBox' and appearance == PdfName('Yes'):
                    datos['Anciano/Siervo/Precursor regular'].append('Anciano')
                elif field == '900_9_CheckBox' and appearance == PdfName('Yes'):
                    datos['Anciano/Siervo/Precursor regular'].append('Siervo ministerial')
                elif field == '900_10_CheckBox' and appearance == PdfName('Yes'):
                    datos['Anciano/Siervo/Precursor regular'].append('Precursor regular')
                elif field == '900_11_CheckBox' and appearance == PdfName('Yes'):
                    datos['Anciano/Siervo/Precursor regular'].append('Precursor especial')
                elif field == '900_12_CheckBox' and appearance == PdfName('Yes'):
                    datos['Anciano/Siervo/Precursor regular'].append('Misionero')

            except Exception as e:
                self.stderr.write(f"⚠️ Error procesando campo personal: {field_raw.to_unicode() if field_raw else 'N/A'}: {str(e)}")
                continue

        datos['Anciano/Siervo/Precursor regular'] = ', '.join(datos['Anciano/Siervo/Precursor regular']) or 'Publicador'
        return datos

    def _extraer_datos_mensuales(self, annotations):
        meses_map = {
            20: 'Septiembre', 21: 'Octubre', 22: 'Noviembre', 23: 'Diciembre',
            24: 'Enero', 25: 'Febrero', 26: 'Marzo', 27: 'Abril',
            28: 'Mayo', 29: 'Junio', 30: 'Julio', 31: 'Agosto'
        }

        datos_mensuales_dict = {}

        for annotation in annotations:
            field_raw = annotation.get('/T')
            if not field_raw:
                continue

            field = field_raw.to_unicode().replace('þÿ', '').strip()
            
            # Usar una expresión regular más robusta para extraer el número de mes
            mes_match = re.search(r'90[1-5]_(\d+)_', field)
            if not mes_match:
                continue

            mes_key = int(mes_match.group(1)) # Esto es el número tal cual aparece en el nombre del campo

            if mes_key not in meses_map:
                continue

            mes_nombre = meses_map[mes_key]
            
            if mes_nombre not in datos_mensuales_dict:
                datos_mensuales_dict[mes_nombre] = {
                    'Mes': mes_nombre,
                    'Participacion': 'No',
                    'Cursos': '',
                    'Precursor_auxiliar': 'No',
                    'Horas': '',
                    'Notas': ''
                }

            registro = datos_mensuales_dict[mes_nombre]

            field_value = self._extraer_valor_campo(annotation)
            appearance = annotation.get('/AS') # Para checkboxes

            if field.startswith('901_') and appearance == PdfName('Yes'):
                registro['Participacion'] = '☑'
            elif field.startswith('902_'):
                registro['Cursos'] = field_value if field_value else ''
            elif field.startswith('903_') and appearance == PdfName('Yes'):
                registro['Precursor_auxiliar'] = '☑'
            elif field.startswith('904_'):
                registro['Horas'] = field_value if field_value else ''
            elif field.startswith('905_'):
                registro['Notas'] = field_value if field_value else ''
        
        # Convertir el diccionario a una lista de registros, ordenados por mes.
        # Es importante tener un orden consistente para los meses.
        # Dado que los meses_map tienen claves numéricas ordenadas, podemos usar eso.
        ordered_meses = sorted(meses_map.keys())
        datos_mensuales_list = [datos_mensuales_dict[meses_map[key]] for key in ordered_meses if meses_map[key] in datos_mensuales_dict]

        return datos_mensuales_list


    def _combinar_datos(self, personales, mensuales):
        registros = []
        for mes_data in mensuales: # Renombrado para evitar conflicto con el dict 'meses_map'
            registros.append({
                'Nombre': personales['Nombre'],
                'Fecha de nacimiento': personales['Fecha de nacimiento'],
                'Fecha de bautismo': personales['Fecha de bautismo'],
                'Hombre/Mujer': personales['Hombre/Mujer'],
                'Otras ovejas/Ungido': personales['Otras ovejas/Ungido'],
                'Anciano/Siervo/Precursor regular': personales['Anciano/Siervo/Precursor regular'],
                'Año de servicio': mes_data['Mes'],
                'Participacion en el ministerio': mes_data['Participacion'],
                'Cursos biblicos': mes_data['Cursos'],
                'Precursor auxiliar': mes_data['Precursor_auxiliar'],
                'Horas': mes_data['Horas'],
                'Notas': mes_data['Notas']
            })
        return registros

    def _formatear_fecha(self, valor):
        if not valor:
            return ''

        str_valor = str(valor).strip() # Asegurarse de que sea string

        try:
            for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%m/%d/%Y', '%d-%m-%Y'):
                try:
                    fecha = datetime.strptime(str_valor, fmt)
                    return fecha.strftime('%d/%m/%Y')
                except ValueError:
                    continue
            return str_valor # Si no se puede parsear, devuelve el valor original
        except Exception as e:
            self.stderr.write(f"⚠️ Error formateando fecha '{str_valor}': {str(e)}")
            return str_valor

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
