from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from core.models import Person

# =====================================================================
# VISTA 1: LISTADO DE REVISTAS (MODIFICADA PARA SALTAR A LA VISTA FINAL)
# =====================================================================
@staff_member_required
def guia_actividades_view(request):
    url_base_jw = "https://www.jw.org"
    url_principal = f"{url_base_jw}/es/biblioteca/guia-actividades-reunion-testigos-jehova/"

    try:
        response = requests.get(url_principal, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        return render(request, "admin/guia_actividades.html", {"content": f"Error: {e}"})

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
                
                # REESCRITURA: Ahora el enlace manda directo a generar el mes completo
                if link_jw:
                    new_link = f"/admin/guia-mes-completo/?url_jw={link_jw}"
                    if div.find("a"):
                        div.find("a")["href"] = new_link
                
                html_final += div.prettify()

    return render(request, "admin/guia_actividades.html", {"content": html_final or "<p>No hay datos</p>"})


# =====================================================================
# VISTA 2: GENERADOR DEL MES COMPLETO (REVISADA)
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

    try:
        # 1. Obtener el índice de la revista para sacar todas las semanas
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

        # 2. Procesar cada semana
        for url_s in links_semanas:
            res_s = requests.get(url_s, timeout=30)
            soup_s = BeautifulSoup(res_s.text, "html.parser")
            article = soup_s.find("article", id="article")
            if not article: continue

            fecha = article.find("h1").get_text(strip=True) if article.find("h1") else "Fecha"
            texto = article.find("h2").get_text(strip=True) if article.find("h2") else ""
            
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
                
                # A. CANCIÓN INICIAL E INTRO
                if "Canción" in texto_h3 and not programa["inicio"]["cancion"] and "introducción" in texto_h3.lower():
                    partes = texto_h3.split('|')
                    programa["inicio"] = {
                        "cancion": partes[0].strip(),
                        "intro": partes[1].strip() if len(partes) > 1 else "Palabras de introducción"
                    }
                    continue

                # B. CANCIÓN INTERMEDIA
                if "Canción" in texto_h3 and "introducción" not in texto_h3.lower() and "conclusión" not in texto_h3.lower():
                    hora_actual = reloj_reunion.strftime("%I:%M").lstrip("0")
                    programa["vida_cancion"] = {"cantico": texto_h3, "hora": hora_actual}
                    reloj_reunion += timedelta(minutes=5)
                    continue

                # C. CONCLUSIÓN
                if "conclusión" in texto_h3.lower():
                    partes = texto_h3.split('|')
                    programa["conclusion"] = {
                        "cancion": partes[0].strip(),
                        "intro": partes[1].strip() if len(partes) > 1 else "Palabras de conclusión",
                        "hora": procesar_horario("0") 
                    }
                    continue

                # D. PUNTOS NUMERADOS
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

                    data = {
                        "numero": numero_str,
                        "titulo": titulo_limpio,
                        "tiempo": tiempo,
                        "descripcion": descripcion,
                    }

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
                "texto": texto,
                "programa": programa
            })

    except Exception as e:
        return render(request, "admin/error.html", {"error": f"Error procesando el mes: {str(e)}"})

    # --- NUEVA SECCIÓN: FILTRADO DE PERSONAS SEGÚN TUS REGLAS ---
    from core.models import Person  # Asegúrate de importar tu modelo
    
    # 1. Ancianos (Presidentes y Vida Cristiana)
    ancianos = list(Person.objects.filter(privileges_permanent__name="Anciano").values_list('names', flat=True).distinct())
    
    # 2. Ancianos y Siervos Ministeriales (Tesoros y Lector)
    ancianos_y_siervos = list(Person.objects.filter(privileges_permanent__name__in=["Anciano", "Siervo Ministerial"]).values_list('names', flat=True).distinct())
    
    # 3. Varones bautizados (Lectura de la biblia y Oraciones)
    varones_bautizados = list(Person.objects.filter(gender=True, baptism__isnull=False).values_list('names', flat=True).distinct())
    
    # 4. Mujeres (Seamos mejores maestros - Preferencia)
    mujeres = list(Person.objects.filter(gender=False).values_list('names', flat=True).distinct())
    
    # 5. Hombres (Seamos mejores maestros - Secundario)
    hombres = list(Person.objects.filter(gender=True).values_list('names', flat=True).distinct())

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