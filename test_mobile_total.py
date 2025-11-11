"""Test para extraer el total de resultados de mobile.de"""
from curl_cffi import requests
from selectolax.parser import HTMLParser
import re

# URL de prueba con filtros del Escenario 6
url = "https://www.mobile.de/es/veh%C3%ADculos/buscar.html?isSearchRequest=true&ref=quickSearch&s=Car&vc=Car&ms=3500%3B49%3B&p=25000%3A55000&fr=2016%3A2021&ft=DIESEL&pw=147%3A257&tr=AUTOMATIC_GEAR"

session = requests.Session(impersonate="chrome")
response = session.get(url)

tree = HTMLParser(response.text)

# Buscar el contador de resultados en diferentes ubicaciones posibles
print("Buscando contador de resultados...")

# Opción 1: En el título o header
title = tree.css_first('title')
if title:
    print(f"\n1. Título: {title.text()}")

# Opción 2: En algún span o div con el número
for node in tree.css('span, div, h1, h2'):
    text = node.text(strip=True)
    # Buscar patrones como "824 resultados" o "824 BMW X5"
    if re.search(r'\d{2,}\s*(resultado|BMW|anuncio|vehículo)', text, re.IGNORECASE):
        print(f"\n2. Posible contador: {text}")
        print(f"   Clases: {node.attributes.get('class', 'N/A')}")
        print(f"   ID: {node.attributes.get('id', 'N/A')}")

# Opción 3: En el JSON embebido
scripts = tree.css('script')
for script in scripts:
    script_text = script.text()
    if 'totalCount' in script_text or 'resultCount' in script_text or 'numResults' in script_text:
        # Extraer un fragmento
        lines = script_text.split('\n')
        for line in lines:
            if 'total' in line.lower() or 'count' in line.lower():
                print(f"\n3. En script: {line.strip()[:200]}")
                break

print("\n\n=== Guardando HTML completo para análisis ===")
with open("mobile_de_search_page.html", "w", encoding="utf-8") as f:
    f.write(response.text)
print("Guardado en: mobile_de_search_page.html")

