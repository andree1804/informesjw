from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

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
        # Buscamos los divs de publicaciones
        for sibling in h2_target.find_next_siblings():
            if sibling.name == "h2": break
            
            divs = sibling.find_all("div", class_="publicationDesc")
            for div in divs:
                # Extraemos el enlace original de JW
                link_jw = div.find("a")["href"] if div.find("a") else ""
                if link_jw.startswith('/'): link_jw = url_base_jw + link_jw
                
                # REESCRITURA DEL ENLACE: 
                # Ahora el enlace enviará la URL de JW a tu otra vista de Django
                if link_jw:
                    new_link = f"/admin/guia-actividades2/?url_jw={link_jw}"
                    if div.find("a"):
                        div.find("a")["href"] = new_link
                
                html_final += div.prettify()

    return render(request, "admin/guia_actividades.html", {"content": html_final or "<p>No hay datos</p>"})



@staff_member_required
def guia_actividades2_view(request):
    # Capturamos la URL que viene desde la primera vista
    # Si no viene ninguna, usamos una por defecto para evitar errores
    url_seleccionada = request.GET.get('url_jw')
    
    if not url_seleccionada:
        return render(request, "admin/guia_actividades2.html", {
            "content": "<p style='color:orange;'>Por favor, seleccione una revista de la lista anterior.</p>"
        })

    try:
        response = requests.get(url_seleccionada, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        return render(request, "admin/guia_actividades2.html", {"content": f"Error: {e}"})

    toc_container = soup.find("div", class_="toc cms-clearfix")

    if toc_container:
        base_url = "https://www.jw.org"
        
        # En guia_actividades2_view, dentro del bucle de corregir enlaces:
        for a in toc_container.find_all("a", href=True):
            original_href = a['href']
            if original_href.startswith('/'):
                full_url = base_url + original_href
                # REESCRITURA: En lugar de ir a JW, va a tu vista 3
                a['href'] = f"/admin/guia-actividades3/?url_semana={full_url}"
        
        # Corregir imágenes
        for img in toc_container.find_all("img", src=True):
            if img['src'].startswith('/'):
                img['src'] = base_url + img['src']

        html_content = toc_container.decode_contents()
    else:
        html_content = "<p>No se encontró el índice.</p>"

    return render(request, "admin/guia_actividades2.html", {"content": html_content})


@staff_member_required
def guia_actividades3_view(request):
    # Capturamos la URL dinámica
    url = request.GET.get('url_semana')
    
    if not url:
        return render(request, "admin/error.html", {"error": "No se proporcionó una URL de semana válida."})
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        return render(request, "admin/error.html", {"error": str(e)})

    article = soup.find("article", id="article")
    if not article:
        return render(request, "admin/error.html", {"error": "No se pudo encontrar el contenido del artículo."})

    fecha = article.find("h1").get_text(strip=True) if article.find("h1") else "Fecha"
    # Capturamos el texto del año/semana si existe
    texto = article.find("h2").get_text(strip=True) if article.find("h2") else ""

    # 1. Configuramos la hora de inicio base
    # Usamos 18:06 para formato 24h interno (6:06 PM)
    reloj_reunion = datetime.strptime("18:05", "%H:%M")

    programa = {
        "inicio": {"cancion": "", "intro": ""}, 
        "tesoros": [], 
        "maestros": [], 
        "vida_cancion": "", 
        "vida": [], 
        "conclusion": {"cancion": "", "intro": ""}
    }


    # Función auxiliar para obtener la hora actual y sumar los minutos
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
        
        # 1. CANCIÓN INICIAL
        if "Canción" in texto_h3 and not programa["inicio"]["cancion"] and "introducción" in texto_h3.lower():
            partes = texto_h3.split('|')
            programa["inicio"] = {
                "cancion": partes[0].strip(),
                "intro": partes[1].strip() if len(partes) > 1 else ""
            }
            continue

        # 2. CANCIÓN INTERMEDIA (VIDA CRISTIANA)
        if "Canción" in texto_h3 and "introducción" not in texto_h3.lower() and "conclusión" not in texto_h3.lower():
            programa["vida_cancion"] = texto_h3
            continue

        # 3. CONCLUSIÓN
        if "conclusión" in texto_h3.lower():
            partes = texto_h3.split('|')
            programa["conclusion"] = {
                "cancion": partes[0].strip(),
                "intro": partes[1].strip() if len(partes) > 1 else "",
                "hora": procesar_horario(tiempo) # 1 min de intro
            }
            continue
        
        # 4. PUNTOS NUMERADOS
        match = re.search(r'^(\d+\.)\s*(.*)', texto_h3)
        if match:
            numero_str = match.group(1)
            titulo_completo = match.group(2)
            
            # Buscar descripción en el siguiente div
            extra_info = ""
            div_detalle = h3.find_next_sibling("div")
            if div_detalle:
                extra_info = div_detalle.get_text(" ", strip=True)

            # Extraer tiempo (ej. 10 min.)
            tiempo_match = re.search(r'\((\d+)\s*mins?\.?\)', texto_h3 + " " + extra_info)

            if tiempo_match:
                # .group(1) captura solo lo que está en el primer paréntesis de la regex: (\d+)
                tiempo = tiempo_match.group(1) 
            else:
                # Si falla el anterior, intentamos buscar cualquier número dentro de paréntesis 
                # por si el formato cambió a solo (10)
                segundo_intento = re.search(r'\((\d+)\)', texto_h3)
                tiempo = segundo_intento.group(1) if segundo_intento else ""
            
            titulo_limpio = titulo_completo.replace(f"({tiempo})", "").strip()
            descripcion = extra_info.replace(f"({tiempo})", "").strip()

            data = {
                "numero": numero_str,
                "titulo": titulo_limpio,
                "tiempo": tiempo,
                "descripcion": descripcion,
                "hora": procesar_horario(tiempo) # <--- AQUÍ SE SUMA
            }

            try:
                n = int(numero_str.replace(".", ""))
                if n <= 3: programa["tesoros"].append(data)
                elif 4 <= n <= 6: programa["maestros"].append(data)
                else: programa["vida"].append(data)
            except ValueError: 
                continue

    return render(request, "admin/guia_actividades3.html", {
        "fecha": fecha, 
        "texto": texto, 
        "programa": programa
    })


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

        # 2. Procesar cada semana con la lógica de guia_actividades3
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
                        "hora": procesar_horario("0") # 1 min de intro final
                    }
                    continue

                # D. PUNTOS NUMERADOS (LA LÓGICA QUE PEDISTE)
                match = re.search(r'^(\d+\.)\s*(.*)', texto_h3)
                if match:
                    numero_str = match.group(1)
                    titulo_completo = match.group(2)
                    
                    # EXTRAER DESCRIPCIÓN (Igual que en guia_actividades3)
                    extra_info = ""
                    div_detalle = h3.find_next_sibling("div")
                    if div_detalle:
                        extra_info = div_detalle.get_text(" ", strip=True)

                    # EXTRAER TIEMPO
                    tiempo_match = re.search(r'\((\d+)\s*mins?\.?\)', texto_h3 + " " + extra_info)
                    if tiempo_match:
                        tiempo = tiempo_match.group(1)
                    else:
                        segundo_intento = re.search(r'\((\d+)\)', texto_h3)
                        tiempo = segundo_intento.group(1) if segundo_intento else "5"

                    # LIMPIEZA
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
                        
                        # 2. Asignamos la hora según la sección
                        if n <= 3:
                            data["hora"] = procesar_horario(tiempo)
                            programa["tesoros"].append(data)
                        elif 4 <= n <= 6:
                            data["hora"] = procesar_horario(tiempo)
                            programa["maestros"].append(data)
                        else:
                            # Aquí aplicas tu lógica de resta solo para la sección VIDA
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

    return render(request, "admin/guia_mes_completo.html", {"reuniones": reuniones_mes, "periodo": periodo})