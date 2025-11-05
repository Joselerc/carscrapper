# Test exprés: ¿mobile.de sirve HTML con IDs por HTTP directo?
from curl_cffi import requests as cffi
from bs4 import BeautifulSoup
import re

LISTING_URL = "https://www.mobile.de/es/veh%C3%ADculos/buscar.html?isSearchRequest=true&ref=quickSearch&s=Car&vc=Car"

print("🔍 Probando curl_cffi con TLS fingerprinting...")
print(f"URL: {LISTING_URL}\n")

s = cffi.Session(impersonate="chrome", timeout=25)
r = s.get(LISTING_URL, headers={
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "accept-language": "es-ES,es;q=0.9"
})

print(f"✅ Status: {r.status_code}")
print(f"📄 Content-Type: {r.headers.get('content-type')}")
print(f"📦 HTML Size: {len(r.text)} bytes\n")

html = r.text

# Guardar HTML para inspección
with open("test_curl_cffi_output.html", "w", encoding="utf-8") as f:
    f.write(html)
print("💾 HTML guardado en: test_curl_cffi_output.html\n")

# Buscar IDs en hrefs
ids_href = set(re.findall(r"detalles\.html\?id=(\d{6,})", html))
print(f"🔗 IDs en href (detalles.html?id=): {len(ids_href)}")
if ids_href:
    print(f"   Primeros 10: {list(ids_href)[:10]}")

# Buscar IDs en atributos data-*
soup = BeautifulSoup(html, "lxml")
ids_data = set()
for tag in soup.select("[data-id],[data-classified-id],[onclick]"):
    for attr in ("data-id", "data-classified-id", "onclick"):
        v = tag.get(attr) or ""
        m = re.search(r"id=(\d{6,})", v)
        if m:
            ids_data.add(m.group(1))

print(f"📊 IDs en data-* / onclick: {len(ids_data)}")
if ids_data:
    print(f"   Primeros 10: {list(ids_data)[:10]}")

# Buscar __NEXT_DATA__
next_data = soup.select_one("#__NEXT_DATA__")
print(f"\n🔍 ¿Existe #__NEXT_DATA__? {'✅ SÍ' if next_data else '❌ NO'}")

# Buscar cualquier script con "id":"XXXXXXXX"
ids_json = set()
for script in soup.find_all("script"):
    if script.string:
        matches = re.findall(r'"id":"(\d{6,})"', script.string)
        ids_json.update(matches)

print(f"📜 IDs en scripts JSON: {len(ids_json)}")
if ids_json:
    print(f"   Primeros 10: {list(ids_json)[:10]}")

# RESULTADO FINAL
total_ids = len(ids_href | ids_data | ids_json)
print(f"\n{'='*60}")
print(f"📊 TOTAL IDs ÚNICOS ENCONTRADOS: {total_ids}")
print(f"{'='*60}")

if total_ids > 0:
    print("\n✅ ¡ÉXITO! Podemos usar solo HTTP (curl_cffi)")
    all_ids = sorted(ids_href | ids_data | ids_json)
    print(f"   IDs: {all_ids[:20]}")
else:
    print("\n❌ HTML CAPADO: mobile.de detecta bot")
    print("   → Necesitamos undetected-chromedriver (híbrido)")

