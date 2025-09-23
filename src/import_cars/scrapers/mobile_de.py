from __future__ import annotations
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from playwright.async_api import async_playwright
from selectolax.parser import HTMLParser

from ..config import ScraperSettings
from ..models import NormalizedListing, Price, Registration, SearchResult
from .base import BaseScraper

# La única URL que usaremos. Directa, sin ambigüedades.
SEARCH_URL = "https://www.mobile.de/es/categor%C3%ADa/veh%C3%ADculo/vhc:car,dmg:false"


class MobileDeScraper(BaseScraper):
    """
    Scraper para mobile.de que opera 100% con Playwright, navegando
    directamente a la página de resultados y parseando el HTML.
    """

    async def search(self, *, query: Dict[str, Any], limit: Optional[int] = None) -> SearchResult:
        page = int(query.get("page", 1))
        page_size = int(query.get("page_size", 24))
        
        # El único método de scraping ahora es este.
        html = await self._fetch_results_page(page_number=page, page_size=page_size)
        
        if not html:
            # Si no obtenemos HTML, devolvemos un resultado vacío.
            return SearchResult(listings=[], total_listings=0, result_page=page, has_next=False)

        data = self._extract_listings_from_html(html)
        return self._parse_response(data, page_number=page, page_size=page_size)

    async def _fetch_results_page(self, *, page_number: int, page_size: int) -> Optional[str]:
        """
        Navega a la página de resultados con Playwright y devuelve el contenido HTML.
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.settings.headless,
                channel=self.settings.playwright_channel,
                slow_mo=self.settings.playwright_slow_mo or None,
            )
            context = await browser.new_context(
                locale="es-ES",
                user_agent=self.settings.user_agent,
                viewport={"width": 1920, "height": 1080},
                extra_http_headers={"Accept-Language": "es-ES,es;q=0.9"},
            )
            page = await context.new_page()

            url = f"{SEARCH_URL},pgn:{page_number},pgs:{page_size}"
            
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # Aceptar cookies
                try:
                    button = page.locator("button:has-text('Aceptar')")
                    await button.wait_for(state="visible", timeout=7000)
                    await button.click()
                except Exception:
                    pass # Si no hay banner, asumimos que no es necesario

                # ESPERA SIMPLE: Pausa fija para permitir la carga de elementos dinámicos.
                await page.wait_for_timeout(3000)

                html_content = await page.content()

            except Exception as e:
                print(f"Error durante la navegación con Playwright: {e}")
                await page.screenshot(path="debug_screenshot.png", full_page=True)
                with open("debug_page.html", "w", encoding="utf-8") as f:
                    f.write(await page.content())
                html_content = None
            finally:
                await context.close()
                await browser.close()

            return html_content

    def _extract_listings_from_html(self, html: str) -> Dict[str, Any]:
        tree = HTMLParser(html)
        items = []
        
        # Selector principal corregido, basado en tu inspección.
        for node in tree.css("a.vehicle-data"):
            url = node.attributes.get("href")
            if not url:
                continue
            
            # Convertir URL relativa en absoluta
            if url.startswith("/"):
                url = f"https://www.mobile.de{url}"

            ad_id_match = re.search(r"/(\d+)\.html", url)
            ad_id = ad_id_match.group(1) if ad_id_match else None

            title = node.css_first("h3.vehicle-title").text(strip=True) if node.css_first("h3.vehicle-title") else None
            
            # --- Extracción de Marca y Modelo ---
            make = None
            model = None
            if title:
                # Lista de marcas conocidas para mejorar la precisión
                known_makes = [
                    "Mercedes-Benz", "BMW", "Audi", "Volkswagen", "Opel", "Ford", "Porsche",
                    "Skoda", "SEAT", "Renault", "Peugeot", "Citroën", "Fiat", "Toyota",
                    "Nissan", "Mazda", "Honda", "Hyundai", "Kia", "Volvo", "Tesla"
                ]
                # Limpiar el título de prefijos comunes como "Nuevo"
                clean_title = re.sub(r"^(Nuevo|New)\s*", "", title, flags=re.IGNORECASE).strip()
                
                for m in known_makes:
                    if clean_title.lower().startswith(m.lower()):
                        make = m
                        # El modelo es lo que sigue a la marca
                        model_part = clean_title[len(m):].strip()
                        # Tomamos las primeras palabras como modelo, evitando textos largos
                        model = " ".join(model_part.split()[:3])
                        break
            
            price_text = node.css_first(".vehicle-prices").text(strip=True) if node.css_first(".vehicle-prices") else ""
            price_match = re.search(r"([0-9\.,]+)", price_text)
            amount = float(price_match.group(1).replace(".", "").replace(",", ".")) if price_match else None

            details_node = node.css_first("div.vehicle-information")
            details_text = details_node.text(separator=" ", strip=True) if details_node else ""
            
            mileage_match = re.search(r"([0-9\.,]+)\s*km", details_text, re.IGNORECASE)
            mileage = int(mileage_match.group(1).replace(".", "").replace(",", "")) if mileage_match else None
            
            reg_match = re.search(r"(\d{2}/\d{4})", details_text)
            registration = None
            if reg_match:
                m_str, y_str = reg_match.group(1).split("/")
                registration = Registration(year=int(y_str), month=int(m_str))

            # Power (kW and HP) - Coger kW es más robusto y luego se convierte a CV
            power_kw_match = re.search(r"(\d+)\s*kW", details_text, re.IGNORECASE)
            power_kw = int(power_kw_match.group(1)) if power_kw_match else None
            power_hp = int(power_kw * 1.35962) if power_kw else None

            # --- Especificaciones técnicas ---
            tech_specs_text = ""
            tech_specs_node = node.css_first("div.vehicle-techspecs")
            if tech_specs_node:
                tech_specs_text = tech_specs_node.text(separator=" ", strip=True)

            fuel_type = None
            transmission = None
            body_type = None
            color_exterior = None
            doors = None

            if tech_specs_text:
                # Fuel Type & Transmission por palabras clave
                fuel_types = ["Diesel", "Gasolina", "Eléctrico", "Híbrido"]
                transmissions_map = {
                    "Cambio automático": "Automatic",
                    "Automático": "Automatic",
                    "Semiautomático": "Semi-automatic",
                    "Manual": "Manual"
                }

                for ft in fuel_types:
                    if re.search(r'\b' + ft + r'\b', tech_specs_text, re.IGNORECASE):
                        fuel_type = ft
                        break

                for es_term, en_term in transmissions_map.items():
                    if re.search(r'\b' + es_term + r'\b', tech_specs_text, re.IGNORECASE):
                        transmission = en_term
                        break

                # Body Type
                tech_parts = [p.strip() for p in tech_specs_text.split(',') if p.strip()]
                if tech_parts:
                    potential_body_type = tech_parts[0]
                    # Asegurarse de no coger un tipo de combustible o transmisión como carrocería
                    if potential_body_type not in (fuel_type or "") and potential_body_type not in transmissions_map:
                        body_type = potential_body_type

                # Color y Puertas con Regex
                color_match = re.search(r"Color exterior:\s*([^,]+)", tech_specs_text, re.IGNORECASE)
                if color_match:
                    color_exterior = color_match.group(1).strip()

                doors_match = re.search(r"Número de puertas:\s*(\d+)", tech_specs_text)
                if doors_match:
                    doors = int(doors_match.group(1))

            items.append({
                "id": ad_id,
                "url": url,
                "title": title,
                "make": make,
                "model": model,
                "price": {"amount": amount},
                "mileageInKm": mileage,
                "firstRegistration": {"year": registration.year, "month": registration.month} if registration else None,
                "powerHp": power_hp,
                "powerKw": power_kw,
                "fuelType": fuel_type,
                "transmission": transmission,
                "bodyType": body_type,
                "doors": doors,
                "colorExterior": color_exterior,
            })
        
        if not items:
            print("ADVERTENCIA: No se encontraron anuncios en la página. Se ha guardado 'debug_page.html' y 'debug_screenshot.png' para revisión.")

        # Comprobar si hay un enlace a la página siguiente para la paginación
        next_page_node = tree.css_first("a.pagination--item[rel='next']")
        has_next = next_page_node is not None

        return {"result": {"items": items, "total": len(items), "pageInfo": {"hasNextPage": has_next}}}

    def _parse_response(self, data: Dict[str, Any], *, page_number: int, page_size: int) -> SearchResult:
        search_data = data.get("result", {})
        listings_data = search_data.get("items", [])
        
        listings = [self._to_listing(item) for item in listings_data if self._to_listing(item) is not None]

        return SearchResult(
            listings=listings,
            total_listings=search_data.get("total"),
            result_page=page_number,
            result_page_size=len(listings),
            has_next=search_data.get("pageInfo", {}).get("hasNextPage", False),
        )

    def _to_listing(self, node: Dict[str, Any]) -> Optional[NormalizedListing]:
        price_info = node.get("price") or {}
        amount = price_info.get("amount")

        reg_info = node.get("firstRegistration")
        registration = Registration(year=reg_info["year"], month=reg_info["month"]) if reg_info else None

        return NormalizedListing(
            listing_id=node.get("id"),
            source="mobile_de",
            url=node.get("url"),
            scraped_at=datetime.utcnow(),
            title=node.get("title"),
            make=node.get("make"),
            model=node.get("model"),
            price_eur=amount,
            price_original=Price(amount=amount, currency_code="EUR") if amount else None,
            mileage_km=node.get("mileageInKm"),
            first_registration=registration,
            power_hp=node.get("powerHp"),
            power_kw=node.get("powerKw"),
            fuel_type=node.get("fuelType"),
            transmission=node.get("transmission"),
            body_type=node.get("bodyType"),
            doors=node.get("doors"),
            color_exterior=node.get("colorExterior"),
        )


__all__ = ["MobileDeScraper"]
