from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from core.models import Person
from django.contrib import admin  # <-- ESTA ES LA QUE ACTIVA EL SIDEBAR
from django.core.cache import cache  # Importación necesaria
import hashlib
from concurrent.futures import ThreadPoolExecutor # Necesario para la mejora de velocidad

# =====================================================================
# VISTA 1: LISTADO DE REVISTAS
# =====================================================================
@staff_member_required
def guia_actividades_view(request):
    url_base_jw = "https://www.jw.org"
    url_principal = f"{url_base_jw}/es/biblioteca/guia-actividades-reunion-testigos-jehova/"
    
    # Usaremos una sola clave de caché
    cache_key = "guia_actividades_final_v5"
    html_final = cache.get(cache_key)
    
    context = admin.site.each_context(request)

    # 1. Si la caché existe, la enviamos DE INMEDIATO (0.1 segundos)
    if html_final:
        context.update({"content": html_final, "title": "Guía de Actividades"})
        return render(request, "admin/guia_actividades.html", context)

    # 2. Si NO hay caché (solo pasará la primera vez o cada 6 horas), hacemos el scraping
    try:
        # Headers para que parezca un navegador y JW no nos ponga en "cola" de espera
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'es-ES,es;q=0.9',
        }
        
        response = requests.get(url_principal, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        h2_target = soup.find("h2", string=lambda t: t and "GUÍA DE ACTIVIDADES" in t.upper())
        
        temp_html = ""
        if h2_target:
            for sibling in h2_target.find_next_siblings():
                if sibling.name == "h2": break
                divs = sibling.find_all("div", class_="publicationDesc")
                for div in divs:
                    a_tag = div.find("a")
                    if a_tag and a_tag.has_attr("href"):
                        link_jw = a_tag["href"]
                        if link_jw.startswith('/'): 
                            link_jw = url_base_jw + link_jw
                        a_tag["href"] = f"/admin/guia-mes-completo/?url_jw={link_jw}"
                    temp_html += div.prettify()
        
        html_final = temp_html or "<p>No hay datos</p>"
        
        # 3. Guardamos en caché por 24 HORAS (86400 segundos)
        # Esto significa que solo verás la demora de 15s una vez cada 24 horas.
        cache.set(cache_key, html_final, 86400)

    except Exception as e:
        html_final = f"<p>Error cargando datos: {e}</p>"

    context.update({
        "content": html_final,
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

    # --- FUNCIONALIDAD DE CACHÉ ---
    cache_key = f"guia_mes_{hashlib.md5(url_revista.encode()).hexdigest()}"
    cached_data = cache.get(cache_key)
    
    if cached_data:
        reuniones_mes = cached_data['reuniones_mes']
        periodo = cached_data['periodo']
    else:
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
                rango_texto = rango_texto.lower()
                match_dia = re.search(r'(\d+)', rango_texto)
                match_mes = re.search(r'de\s+([a-z]+)', rango_texto)
                if match_dia and match_mes:
                    dia_lunes = int(match_dia.group(1))
                    mes_nombre_inicio = match_mes.group(1)
                    mes_num = meses.get(mes_nombre_inicio, 1)
                    anio = datetime.now().year 
                    fecha_lunes = datetime(anio, mes_num, dia_lunes)
                    fecha_viernes = fecha_lunes + timedelta(days=4)
                    nombre_mes_final = [k for k, v in meses.items() if v == fecha_viernes.month][0]
                    return f"{fecha_viernes.day} de {nombre_mes_final}"
            except Exception as e:
                print(f"Error en fecha: {e}")
            return ""

        # --- FUNCIÓN ATÓMICA PARA SCRAPING DE UNA SEMANA (MEJORA) ---
        def extraer_datos_semana(url_s):
            try:
                res_s = requests.get(url_s, timeout=15)
                soup_s = BeautifulSoup(res_s.text, "html.parser")
                article = soup_s.find("article", id="article")
                if not article: return None

                fecha_h1 = article.find("h1").get_text(strip=True) if article.find("h1") else "Fecha"
                texto_h2 = article.find("h2").get_text(strip=True) if article.find("h2") else ""
                viernes_calc = obtener_viernes_fecha(fecha_h1)
                
                # Reloj interno por cada hilo de semana
                reloj_local = datetime.strptime("18:05", "%H:%M")

                prog = {
                    "inicio": {"cancion": "", "intro": ""}, 
                    "tesoros": [], "maestros": [], "vida_cancion": "", 
                    "vida": [], "conclusion": {"cancion": "", "intro": "", "hora": ""}
                }

                def proc_h(min_str, r_reunion):
                    h_form = r_reunion.strftime("%I:%M").lstrip("0")
                    try:
                        m = int(min_str) + 1 if min_str else 0
                    except: m = 0
                    return h_form, r_reunion + timedelta(minutes=m)

                for h3 in article.find_all("h3"):
                    t_h3 = h3.get_text(" ", strip=True)
                    if "Canción" in t_h3 and not prog["inicio"]["cancion"] and "introducción" in t_h3.lower():
                        partes_t = t_h3.split('|')
                        prog["inicio"] = {"cancion": partes_t[0].strip(), "intro": partes_t[1].strip() if len(partes_t)>1 else "Palabras de introducción"}
                    elif "Canción" in t_h3 and "introducción" not in t_h3.lower() and "conclusión" not in t_h3.lower():
                        prog["vida_cancion"] = {"cantico": t_h3, "hora": reloj_local.strftime("%I:%M").lstrip("0")}
                        reloj_local += timedelta(minutes=5)
                    elif "conclusión" in t_h3.lower():
                        partes_t = t_h3.split('|')
                        h_f, _ = proc_h("0", reloj_local)
                        prog["conclusion"] = {"cancion": partes_t[0].strip(), "intro": partes_t[1].strip() if len(partes_t)>1 else "Palabras de conclusión", "hora": h_f}
                    else:
                        match_t = re.search(r'^(\d+\.)\s*(.*)', t_h3)
                        if match_t:
                            num_s = match_t.group(1)
                            div_det = h3.find_next_sibling("div")
                            e_info = div_det.get_text(" ", strip=True) if div_det else ""
                            t_m = re.search(r'\((\d+)\s*mins?\.?\)', t_h3 + " " + e_info)
                            tie = t_m.group(1) if t_m else "5"
                            
                            dat = {"numero": num_s, "titulo": match_t.group(2).replace(f"({tie})", "").strip(), "tiempo": tie, "descripcion": e_info.replace(f"({tie})", "").replace("min.", "").strip()}
                            
                            n = int(num_s.replace(".", ""))
                            if n <= 3:
                                dat["hora"], reloj_local = proc_h(tie, reloj_local)
                                prog["tesoros"].append(dat)
                            elif 4 <= n <= 6:
                                dat["hora"], reloj_local = proc_h(tie, reloj_local)
                                prog["maestros"].append(dat)
                            else:
                                dat["hora"], reloj_local = proc_h(int(tie)-1, reloj_local)
                                prog["vida"].append(dat)

                return {
                    "id": re.sub(r'\W+', '', fecha_h1),
                    "fecha": fecha_h1,
                    "viernes": viernes_calc,
                    "texto": texto_h2,
                    "programa": prog,
                    "url_original": url_s # Para mantener el orden
                }
            except Exception as e:
                print(f"Error en semana {url_s}: {e}")
                return None

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

            # --- EJECUCIÓN EN PARALELO ---
            # Usamos máximo 5 hilos (un mes suele tener 4 o 5 semanas)
            with ThreadPoolExecutor(max_workers=10) as executor:
                resultados_brutos = list(executor.map(extraer_datos_semana, links_semanas))

            # Limpiamos resultados nulos y ordenamos según la lista de links original
            reuniones_mes = [r for r in resultados_brutos if r is not None]
            reuniones_mes.sort(key=lambda x: links_semanas.index(x['url_original']))

            # Guardamos en caché
            cache.set(cache_key, {'reuniones_mes': reuniones_mes, 'periodo': periodo}, 86400)

        except Exception as e:
            return render(request, "admin/error.html", {"error": f"Error procesando el mes: {str(e)}"})

    # --- LISTAS DE PERSONAS (Siempre actualizadas desde DB) ---
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