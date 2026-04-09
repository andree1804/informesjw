from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from core.models import Person
from django.contrib import admin  # <-- ESTA ES LA QUE ACTIVA EL SIDEBAR

# =====================================================================
# VISTA 1: LISTADO DE REVISTAS
# =====================================================================
@staff_member_required
def guia_actividades_view(request):
    url_base_jw = "https://www.jw.org"
    url_principal = f"{url_base_jw}/es/biblioteca/guia-actividades-reunion-testigos-jehova/"

    context = admin.site.each_context(request)

    try:
        response = requests.get(url_principal, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        context.update({"content": f"Error: {e}"})
        return render(request, "admin/guia_actividades.html", context)

    h2_target = soup.find("h2", string=lambda t: t and "GUÍA DE ACTIVIDADES" in t.upper())
    
    html_final = ""
    if h2_target:
        for sibling in h2_target.find_next_siblings():
            if sibling.name == "h2": break
            
            divs = sibling.find_all("div", class_="publicationDesc")
            for div in divs:
                link_jw = div.find("a")["href"] if div.find("a") else ""
                if link_jw.startswith('/'): 
                    link_jw = url_base_jw + link_jw
                
                if link_jw:
                    new_link = f"/admin/guia-mes-completo/?url_jw={link_jw}"
                    if div.find("a"):
                        div.find("a")["href"] = new_link
                
                html_final += div.prettify()

    context.update({
        "content": html_final or "<p>No hay datos</p>",
        "title": "Guía de Actividades"
    })

    return render(request, "admin/guia_actividades.html", context)


# =====================================================================
# VISTA 2: GENERADOR DEL MES COMPLETO (CON CÁLCULO DE VIERNES)
# =====================================================================
@staff_member_required
def guia_mes_completo_view(request):
    url_revista = request.GET.get('url_jw')
    if not url_revista:
        return render(request, "admin/error.html", {"error": "No se proporcionó la URL de la revista."})

    base_url = "https://www.jw.org"
    reuniones_mes = []

    partes = url_revista.strip('/').split('/')
    ultimo_segmento = partes[-1]
    periodo = ultimo_segmento.replace('-mwb', '')

    # --- FUNCIÓN PARA OBTENER EL VIERNES DE LA SEMANA ---
    def obtener_viernes_fecha(rango_texto):
        meses = {
            'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
            'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
        }
        try:
            # Convertimos a minúsculas para evitar fallos de coincidencia
            rango_texto = rango_texto.lower()
            
            # Buscamos el primer número y el primer mes que aparezca en la cadena
            match_dia = re.search(r'(\d+)', rango_texto)
            # Buscamos el mes que está inmediatamente después del primer "de" o al final
            match_mes = re.search(r'de\s+([a-z]+)', rango_texto)
            
            if match_dia and match_mes:
                dia_lunes = int(match_dia.group(1))
                mes_nombre_inicio = match_mes.group(1)
                mes_num = meses.get(mes_nombre_inicio, 1)
                
                anio = datetime.now().year # Año actual según tu entorno
                
                # Creamos la fecha del lunes de esa semana
                fecha_lunes = datetime(anio, mes_num, dia_lunes)
                
                # Sumamos 4 días para llegar al viernes
                fecha_viernes = fecha_lunes + timedelta(days=4)
                
                # Para el nombre del mes de salida, verificamos si el viernes cayó en un mes distinto
                # (Caso: 27 de julio -> viernes 31 de julio | Caso: 29 de diciembre -> viernes 2 de enero)
                nombre_mes_final = [k for k, v in meses.items() if v == fecha_viernes.month][0]
                
                return f"{fecha_viernes.day} de {nombre_mes_final}"
        except Exception as e:
            print(f"Error en fecha: {e}")
        return ""

    try:
        res_indice = requests.get(url_revista, timeout=20)
        res_indice.raise_for_status()
        soup_indice = BeautifulSoup(res_indice.text, "html.parser")
        
        toc = soup_indice.find("div", class_="toc cms-clearfix")
        if not toc:
            return render(request, "admin/error.html", {"error": "No se encontró el índice de semanas."})

        links_semanas = []
        for a in toc.find_all("a", href=True):
            if "mwb" in a['href'] and "reuniones" not in a['href']:
                full_url = base_url + a['href'] if a['href'].startswith('/') else a['href']
                if full_url not in links_semanas:
                    links_semanas.append(full_url)

        for url_s in links_semanas:
            res_s = requests.get(url_s, timeout=30)
            soup_s = BeautifulSoup(res_s.text, "html.parser")
            article = soup_s.find("article", id="article")
            if not article: continue

            fecha = article.find("h1").get_text(strip=True) if article.find("h1") else "Fecha"
            texto = article.find("h2").get_text(strip=True) if article.find("h2") else ""
            
            # Calcular el viernes basado en la fecha del h1
            viernes_calculado = obtener_viernes_fecha(fecha)

            reloj_reunion = datetime.strptime("18:05", "%H:%M")

            programa = {
                "inicio": {"cancion": "", "intro": ""}, 
                "tesoros": [], 
                "maestros": [], 
                "vida_cancion": "", 
                "vida": [], 
                "conclusion": {"cancion": "", "intro": "", "hora": ""}
            }

            def procesar_horario(minutos_str):
                nonlocal reloj_reunion
                hora_formateada = reloj_reunion.strftime("%I:%M").lstrip("0")
                try:
                    minutos = int(minutos_str) + 1 if minutos_str else 0
                except ValueError:
                    minutos = 0
                reloj_reunion += timedelta(minutes=minutos)
                return hora_formateada

            for h3 in article.find_all("h3"):
                texto_h3 = h3.get_text(" ", strip=True)
                
                if "Canción" in texto_h3 and not programa["inicio"]["cancion"] and "introducción" in texto_h3.lower():
                    partes = texto_h3.split('|')
                    programa["inicio"] = {
                        "cancion": partes[0].strip(),
                        "intro": partes[1].strip() if len(partes) > 1 else "Palabras de introducción"
                    }
                    continue

                if "Canción" in texto_h3 and "introducción" not in texto_h3.lower() and "conclusión" not in texto_h3.lower():
                    hora_actual = reloj_reunion.strftime("%I:%M").lstrip("0")
                    programa["vida_cancion"] = {"cantico": texto_h3, "hora": hora_actual}
                    reloj_reunion += timedelta(minutes=5)
                    continue

                if "conclusión" in texto_h3.lower():
                    partes = texto_h3.split('|')
                    programa["conclusion"] = {
                        "cancion": partes[0].strip(),
                        "intro": partes[1].strip() if len(partes) > 1 else "Palabras de conclusión",
                        "hora": procesar_horario("0") 
                    }
                    continue

                match = re.search(r'^(\d+\.)\s*(.*)', texto_h3)
                if match:
                    numero_str = match.group(1)
                    titulo_completo = match.group(2)
                    extra_info = ""
                    div_detalle = h3.find_next_sibling("div")
                    if div_detalle:
                        extra_info = div_detalle.get_text(" ", strip=True)

                    tiempo_match = re.search(r'\((\d+)\s*mins?\.?\)', texto_h3 + " " + extra_info)
                    if tiempo_match:
                        tiempo = tiempo_match.group(1)
                    else:
                        segundo_intento = re.search(r'\((\d+)\)', texto_h3)
                        tiempo = segundo_intento.group(1) if segundo_intento else "5"

                    titulo_limpio = titulo_completo.replace(f"({tiempo})", "").strip()
                    descripcion = extra_info.replace(f"({tiempo})", "").replace("min.", "").strip()

                    data = {"numero": numero_str, "titulo": titulo_limpio, "tiempo": tiempo, "descripcion": descripcion}

                    try:
                        n = int(numero_str.replace(".", ""))
                        if n <= 3:
                            data["hora"] = procesar_horario(tiempo)
                            programa["tesoros"].append(data)
                        elif 4 <= n <= 6:
                            data["hora"] = procesar_horario(tiempo)
                            programa["maestros"].append(data)
                        else:
                            data["hora"] = procesar_horario(int(tiempo)-1) 
                            programa["vida"].append(data)
                    except ValueError:
                        continue

            reuniones_mes.append({
                "id": re.sub(r'\W+', '', fecha),
                "fecha": fecha,
                "viernes": viernes_calculado,  # <--- AGREGADO
                "texto": texto,
                "programa": programa
            })

    except Exception as e:
        return render(request, "admin/error.html", {"error": f"Error procesando el mes: {str(e)}"})

    def obtener_lista_nombres_completos(queryset):
        tuplas = queryset.values_list('names', 'paternal_surname').distinct()
        return [" ".join([texto for texto in tupla if texto]) for tupla in tuplas]

    ancianos = obtener_lista_nombres_completos(Person.objects.filter(privileges_permanent__name="Anciano").exclude(privilege__name="-"))
    ancianos_y_siervos = obtener_lista_nombres_completos(Person.objects.filter(privileges_permanent__name__in=["Anciano", "Siervo Ministerial"]).exclude(privilege__name="-"))
    varones_bautizados = obtener_lista_nombres_completos(Person.objects.filter(gender=True, baptism__isnull=False).exclude(privilege__name="-"))
    mujeres = obtener_lista_nombres_completos(Person.objects.filter(gender=False).exclude(privilege__name="-"))
    hombres = obtener_lista_nombres_completos(Person.objects.filter(gender=True).exclude(privilege__name="-"))

    contexto = {
        "reuniones": reuniones_mes, 
        "periodo": periodo,
        "ancianos_list": ancianos,
        "ancianos_y_siervos_list": ancianos_y_siervos,
        "varones_list": varones_bautizados,
        "mujeres_list": mujeres,
        "hombres_list": hombres
    }

    return render(request, "admin/guia_mes_completo.html", contexto)