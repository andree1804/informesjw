from django.shortcuts import render

from django.http import JsonResponse
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import re

from datetime import datetime, timedelta

# Diccionario de meses en español
MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
]

def format_date_spanish(fecha):
    """
    Convierte una fecha '2025-09-29' en el formato usado por jw.org:
    - Si los meses son distintos: '29-de-septiembre-a-5-de-octubre-de-2025'
    - Si los meses son iguales: '6-a-12-de-octubre-de-2025'
    """
    fecha_inicio = datetime.strptime(fecha, "%Y-%m-%d")
    fecha_fin = fecha_inicio + timedelta(days=6)

    mes_inicio = MESES[fecha_inicio.month - 1]
    mes_fin = MESES[fecha_fin.month - 1]

    if mes_inicio == mes_fin:
        # Formato corto → 6-a-12-de-octubre-de-2025
        return f"{fecha_inicio.day}-a-{fecha_fin.day}-de-{mes_fin}-de-{fecha_fin.year}"
    else:
        # Formato largo → 29-de-septiembre-a-5-de-octubre-de-2025
        return (
            f"{fecha_inicio.day}-de-{mes_inicio}-a-"
            f"{fecha_fin.day}-de-{mes_fin}-de-{fecha_fin.year}"
        )

def build_url(fecha):
    """
    Construye la URL de la guía de actividades para la semana correspondiente a la fecha dada.
    """
    fecha_segmento = format_date_spanish(fecha)
    fecha_inicio = datetime.strptime(fecha, "%Y-%m-%d")
    mes_inicio = MESES[fecha_inicio.month - 1]
    mes_fin = MESES[(fecha_inicio + timedelta(days=6)).month - 1]
    year = fecha_inicio.year

    # Determinar el segmento bimestral
    if mes_inicio == mes_fin:
        bimonth_segment = f"{mes_inicio}-{year}-mwb"
    else:
        bimonth_segment = f"{mes_inicio}-{mes_fin}-{year}-mwb"

    # Construir la URL
    base_url = "https://www.jw.org/es/biblioteca/guia-actividades-reunion-testigos-jehova"
    return f"{base_url}/{bimonth_segment}/Vida-y-Ministerio-Cristianos-{fecha_segmento}/"

# Ejemplo de uso
fecha = "2025-10-06"
url = build_url(fecha)
print(url)


import re

def parse_vmc_html(soup):
    """
    Convierte el HTML de jw.org en JSON estructurado como el PDF:
    - Primer <h3> → Apertura (cancion, oracion, introduccion)
    - <h3> con 'Palabras de conclusión' → Clausura (conclusion, cancion, oracion)
    - Primer <h3> con <a> después de 'NUESTRA VIDA CRISTIANA' → Cancion
    - Los demás <h3> intermedios → TESOROS, MAESTROS, VIDA CRISTIANA
    - Ignora el último subtema de 'NUESTRA VIDA CRISTIANA' si contiene 
      'Vida y Ministerio Cristianos' o no tiene contenido.
    Solo toma el primer <p> de cada subtema o sección.
    """

    data = {
        "Apertura": {"cancion": "", "oracion": "", "introduccion": ""},
        "TESOROS DE LA BIBLIA": [],
        "SEAMOS MEJORES MAESTROS": [],
        "NUESTRA VIDA CRISTIANA": [],
        "Cancion": "",
        "Clausura": {"conclusion": "", "cancion": "", "oracion": ""}
    }

    subtema_count = 1
    h3_tags = soup.find_all("h3")
    if not h3_tags:
        return data

    primer_h3 = h3_tags[0]
    cancion_extraida = False
    seccion_actual = None

    secciones = {
        "TESOROS DE LA BIBLIA": "tesoros",
        "SEAMOS MEJORES MAESTROS": "maestros",
        "NUESTRA VIDA CRISTIANA": "vida cristiana"
    }

    for elem in soup.find_all(["h2", "h3"]):
        texto = elem.get_text(strip=True)
        if not texto:
            continue

        # --- APERTURA ---
        if elem is primer_h3:
            texto_h3 = ''.join(elem.stripped_strings)
            a_tag = elem.find("a")

            data["Apertura"]["cancion"] = a_tag.get_text(strip=True) if a_tag else ""
            data["Apertura"]["oracion"] = "Oración" if "oración" in texto_h3.lower() else ""
            match_intro = re.search(r'palabras de introducci[oó]n', texto_h3, re.IGNORECASE)
            data["Apertura"]["introduccion"] = match_intro.group(0) if match_intro else ""
            continue

        # --- CLAUSURA ---
        if re.search(r'palabras de conclusi[oó]n', texto, re.IGNORECASE):
            data["Clausura"]["conclusion"] = "Palabras de conclusión"
            a_tag = elem.find("a")
            data["Clausura"]["cancion"] = a_tag.get_text(strip=True) if a_tag else ""
            data["Clausura"]["oracion"] = "Oración" if "oración" in texto.lower() else ""
            continue

        # --- SECCIONES PRINCIPALES ---
        if elem.name == "h2":
            for key, valor in secciones.items():
                if valor in texto.lower():
                    seccion_actual = key
                    break
            continue

        # --- SUBTEMAS ---
        if elem.name == "h3" and seccion_actual:
            # Canción de transición (después de NUESTRA VIDA CRISTIANA)
            if seccion_actual == "NUESTRA VIDA CRISTIANA" and not cancion_extraida:
                a_tag = elem.find("a")
                if a_tag:
                    data["Cancion"] = a_tag.get_text(strip=True)
                    cancion_extraida = True
                    continue

            # Extraer contenido del subtema
            subtema = {"numero": subtema_count, "titulo": texto, "contenido": []}
            sibling = elem.find_next_sibling()

            while sibling and sibling.name not in ["h2", "h3"]:
                if sibling.name == "p":
                    subtema["contenido"].append(sibling.get_text(strip=True))
                    break
                if sibling.name == "div":
                    p_tag = sibling.find("p")
                    if p_tag:
                        subtema["contenido"].append(p_tag.get_text(strip=True))
                        break
                sibling = sibling.find_next_sibling()

            # --- Ignorar el último subtema vacío o genérico ---
            titulo_lower = subtema["titulo"].lower()
            if seccion_actual == "NUESTRA VIDA CRISTIANA" and (
                "vida y ministerio cristianos" in titulo_lower or not subtema["contenido"]
            ):
                continue  # no agregarlo

            data[seccion_actual].append(subtema)
            subtema_count += 1

    return data


def vida_ministerio(request, fecha):
    try:
        # Validar fecha
        datetime.strptime(fecha, "%Y-%m-%d")
    except ValueError:
        return JsonResponse({"error": "Formato de fecha inválido. Use YYYY-MM-DD"}, status=400)

    rango = format_date_spanish(fecha)

    # Construir URL dinámica
    fecha_inicio = datetime.strptime(fecha, "%Y-%m-%d")
    mes_inicio = MESES[fecha_inicio.month-1]
    mes_fin = MESES[(fecha_inicio + timedelta(days=6)).month-1]
    anio = fecha_inicio.year

    periodo = f"{mes_inicio}-{mes_fin}-{anio}-mwb"

    url = (
        f"https://www.jw.org/es/biblioteca/guia-actividades-reunion-testigos-jehova/"
        f"{periodo}/Vida-y-Ministerio-Cristianos-{rango}/"
    )

    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        return JsonResponse({"error": f"No se pudo obtener la página: {e}"}, status=500)

    soup = BeautifulSoup(resp.content, "html.parser")

    titulo = soup.find("h1").get_text(strip=True) if soup.find("h1") else ""

    data = {
        "titulo": titulo,
        "fecha_inicio": fecha,
        "fecha_fin": (fecha_inicio + timedelta(days=6)).strftime("%Y-%m-%d"),
        "url_fuente": url,
        "secciones": parse_vmc_html(soup)
    }

    return JsonResponse(data, json_dumps_params={"ensure_ascii": False, "indent": 2})
