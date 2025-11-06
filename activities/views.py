'''from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
import requests
from bs4 import BeautifulSoup

@staff_member_required
def guia_actividades_view(request):
    """
    Extrae y muestra solo los divs con class="publicationDesc"
    que están debajo del H2 'GUÍA DE ACTIVIDADES'.
    """
    url = "https://www.jw.org/es/biblioteca/guia-actividades-reunion-testigos-jehova/"

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except Exception as e:
        return render(request, "admin/guia_actividades.html", {
            "content": f"<p style='color:red;'>Error al obtener la página: {e}</p>"
        })

    soup = BeautifulSoup(response.text, "html.parser")

    guia_section_divs = []
    h2_target = None

    # Encontrar el h2 con "GUÍA DE ACTIVIDADES"
    for h2 in soup.find_all("h2"):
        if "GUÍA DE ACTIVIDADES" in h2.text.upper():
            h2_target = h2
            break

    if h2_target:
        # Iterar sobre los siguientes siblings hasta el próximo h2
        for sibling in h2_target.find_next_siblings():
            if sibling.name == "h2":
                break  # detenerse si aparece otro h2
            divs = sibling.find_all("div", class_="publicationDesc")
            guia_section_divs.extend(divs)

    if guia_section_divs:
        html_content = "".join([div.prettify() for div in guia_section_divs])
    else:
        html_content = "<p>No se encontraron publicaciones.</p>"

    return render(request, "admin/guia_actividades.html", {"content": html_content})'''