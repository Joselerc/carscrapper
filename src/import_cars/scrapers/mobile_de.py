from __future__ import annotations
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from playwright.async_api import async_playwright
from selectolax.parser import HTMLParser

from ..config import ScraperSettings
from ..models import (
    Consumption,
    Location,
    NormalizedListing,
    Price,
    Registration,
    SearchResult,
    Seller,
)
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
            
            # El único método de scraping ahora es este.
            html = await self._fetch_results_page(context, page_number=page, page_size=page_size)
            
            if not html:
                await context.close()
                await browser.close()
                return SearchResult(listings=[], total_listings=0, result_page=page, has_next=False)

            data = await self._extract_listings_from_html(html, context)
            
            await context.close()
            await browser.close()
            
            return self._parse_response(data, page_number=page, page_size=page_size)

    async def _fetch_results_page(self, context, *, page_number: int, page_size: int) -> Optional[str]:
        """
        Navega a la página de resultados con Playwright y devuelve el contenido HTML.
        """
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
            await page.close()

        return html_content

    async def _extract_listings_from_html(self, html: str, context) -> Dict[str, Any]:
        tree = HTMLParser(html)
        items = []
        
        # Selector principal corregido, basado en tu inspección.
        listing_nodes = tree.css("a.vehicle-data")
        print(f"DEBUG: Encontrados {len(listing_nodes)} anuncios en la página de resultados.")

        for i, node in enumerate(listing_nodes):
            print(f"DEBUG: Procesando anuncio {i+1}/{len(listing_nodes)}...")
            url = node.attributes.get("href")
            if not url:
                print(f"DEBUG: Anuncio {i+1} saltado por no tener URL.")
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
            
            # --- Extracción de precios Bruto y Neto desde el listado ---
            price_node = node.css_first("div.vehicle-prices")
            price_bruto = None
            price_neto = None

            if price_node:
                price_lines = price_node.css("p")
                for p in price_lines:
                    text = p.text(strip=True)
                    price_match = re.search(r"([0-9\.,]+)", text)
                    if not price_match:
                        continue
                    
                    amount = float(price_match.group(1).replace(".", "").replace(",", "."))

                    if "bruto" in text.lower():
                        price_bruto = amount
                    elif "neto" in text.lower():
                        price_neto = amount
                    else: # Si no hay etiqueta, asumimos que es el precio principal (bruto)
                        if price_bruto is None:
                            price_bruto = amount

            # Calcular el precio faltante si es posible
            if price_bruto and not price_neto:
                price_neto = round(price_bruto / 1.19, 2)
            elif price_neto and not price_bruto:
                price_bruto = round(price_neto * 1.19, 2)

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

            # --- Fase 2: Scrapeo de la página de detalle ---
            detail_data = await self._scrape_detail_page(context, url)
            co2_emissions = detail_data.get("co2_emissions_g_km")

            items.append({
                "id": ad_id,
                "url": url,
                "title": title,
                "make": make,
                "model": model,
                "price_eur": price_bruto,
                "price_net_eur": price_neto,
                "mileageInKm": mileage,
                "firstRegistration": {"year": registration.year, "month": registration.month} if registration else None,
                "powerHp": power_hp,
                "powerKw": power_kw,
                "fuelType": fuel_type,
                "transmission": transmission,
                "bodyType": body_type,
                "doors": doors,
                "colorExterior": color_exterior,
                "co2Emissions": co2_emissions,
                "detail_data": detail_data, # Añadir los datos de detalle a la lista de items
            })
        
        if not items:
            print("ADVERTENCIA: No se encontraron anuncios en la página. Se ha guardado 'debug_page.html' y 'debug_screenshot.png' para revisión.")

        # Comprobar si hay un enlace a la página siguiente para la paginación
        next_page_node = tree.css_first("a.pagination--item[rel='next']")
        has_next = next_page_node is not None

        return {"result": {"items": items, "total": len(items), "pageInfo": {"hasNextPage": has_next}}}

    async def _scrape_detail_page(self, context, url: str) -> Dict[str, Any]:
        """
        Visita la página de detalle de un anuncio y extrae datos adicionales como
        especificaciones técnicas detalladas y información del vendedor, usando Selectolax para parsear.
        """
        page = await context.new_page()
        details = {}
        print(f"--- Visitando página de detalle: {url} ---")
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            html = await page.content()
            tree = HTMLParser(html)

            # --- Búsqueda robusta de secciones ---
            all_sections = tree.css("div.vip-details-block")
            tech_data_node = None
            description_node = None
            seller_node = None

            for section in all_sections:
                title_node = section.css_first("h3")
                if title_node:
                    title = title_node.text(strip=True)
                    if title == "Datos técnicos":
                        tech_data_node = section
                    elif title == "Descripción del vehículo":
                        description_node = section
                    elif title == "Distribuidor firma":
                        seller_node = section
            
            # 1. Parsear la tabla de "Datos técnicos"
            if tech_data_node:
                TECH_SPEC_MAP = {
                    "Primer registro": "first_registration",
                    "Combustible": "fuel_type",
                    "Kilometraje": "mileage_km",
                    "Potencia": "power_hp",
                    "Capacidad cúbica": "engine_displacement_cc",
                    "Número de asientos": "seats",
                    "Número de puertas": "doors",
                    "Color": "color_exterior",
                    "Emisiones de CO₂": "co2_emissions_g_km", # Clave flexible
                    "Consumo de combustible": "consumption_l_100km",
                    "Categoría": "body_type"
                }
                rows = tech_data_node.css("div.g-row")
                print(f"DEBUG: Encontradas {len(rows)} filas en datos técnicos.")
                for row in rows:
                    # Buscamos la clave en el primer span/p y el valor en el segundo
                    key_node = row.css_first("span:first-child, p:first-child")
                    value_node = row.css_first("span:last-child, p:last-child")
                    
                    if key_node and value_node:
                        key = key_node.text(strip=True)
                        value_text = value_node.text(strip=True)
                        
                        # Búsqueda flexible de claves
                        for map_key, field_name in TECH_SPEC_MAP.items():
                            if map_key in key:
                                # Limpieza y conversión de datos específicos
                                if "g/km" in value_text:
                                    match = re.search(r"(\d+)", value_text)
                                    details[field_name] = int(match.group(1)) if match else None
                                elif "l/100km" in value_text:
                                    match = re.search(r"([\d\.,]+)", value_text)
                                    if match:
                                        consumption_value = float(match.group(1).replace(",", "."))
                                        # Crear el objeto Consumption esperado por el modelo
                                        details[field_name] = Consumption(combined=consumption_value)
                                    else:
                                        details[field_name] = None
                                elif "cv" in value_text:
                                    match = re.search(r"\((\d+)\s*cv\)", value_text, re.IGNORECASE)
                                    details[field_name] = int(match.group(1)) if match else None
                                elif "ccm" in value_text:
                                    match = re.search(r"([\d\.]+)", value_text)
                                    details[field_name] = int(match.group(1).replace(".", "")) if match else None
                                elif field_name == "doors":
                                    # Coger solo el primer número si el formato es "4/5"
                                    match = re.search(r"(\d+)", value_text)
                                    details[field_name] = int(match.group(1)) if match else None
                                else:
                                    details[field_name] = value_text
                                break # Pasar a la siguiente fila una vez encontrada la clave
            else:
                print("DEBUG: No se encontró la sección de datos técnicos.")

            # 2. Parsear la descripción del vehículo
            if description_node:
                desc_text_node = description_node.css_first("div.description-text")
                if desc_text_node:
                    details["description"] = desc_text_node.text(strip=True)
                    print("DEBUG: Descripción extraída con éxito.")
            else:
                print("DEBUG: No se encontró la sección de descripción.")

            # 3. Parsear la información del vendedor
            if seller_node:
                name = seller_node.css_first("p").text(strip=True) if seller_node.css_first("p") else None
                
                phone_node = seller_node.css_first("ul.phone-numbers li")
                phone = None
                if phone_node:
                    phone_text = phone_node.text(strip=True)
                    match = re.search(r"(\+.*)", phone_text)
                    if match:
                        phone = match.group(1).strip()

                location_node = seller_node.css_first("div.g-row div:has(i.mde-icon-flag)")
                location_obj = None
                if location_node:
                    location_text = location_node.text(strip=True)
                    # Ejemplo: DE-74915 Waibstadt Alemania
                    match = re.match(r"([A-Z]{2})-(\d+)\s+(.+?)\s+(.+)", location_text)
                    if match:
                        country_code, postal_code, city, _ = match.groups()
                        location_obj = Location(
                            country_code=country_code,
                            postal_code=postal_code,
                            city=city,
                        )
                details["location"] = location_obj
                
                address_parts = [p.text(strip=True) for p in seller_node.css("p, span")]
                full_address = ", ".join(filter(None, address_parts[1:]))

                rating_value = None
                rating_count = None
                rating_node = seller_node.css_first("div.star-rating-s")
                if rating_node:
                    rating_value = float(rating_node.attributes.get('data-rating', 0.0))
                
                rating_count_node = seller_node.css_first("a.internal-link")
                if rating_count_node:
                    match = re.search(r"\((\d+)", rating_count_node.text())
                    if match:
                        rating_count = int(match.group(1))

                details["seller"] = Seller(
                    name=name,
                    rating=rating_value,
                    rating_count=rating_count,
                    phone=phone,
                )
                print("DEBUG: Información del vendedor extraída con éxito.")
            else:
                print("DEBUG: No se encontró la sección del vendedor.")

        except Exception as e:
            print(f"Error procesando página de detalle {url}: {e}")
        finally:
            await page.close()
            
        return details

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

        # Priorizar datos de la página de detalle si existen
        detail_data = node.get("detail_data", {})

        return NormalizedListing(
            listing_id=node.get("id"),
            source="mobile_de",
            url=node.get("url"),
            scraped_at=datetime.utcnow(),
            title=node.get("title"),
            make=node.get("make"),
            model=node.get("model"),
            price_eur=node.get("price_eur"),
            price_net_eur=node.get("price_net_eur"),
            price_original=Price(amount=node.get("price_eur"), currency_code="EUR") if node.get("price_eur") else None,
            mileage_km=node.get("mileageInKm"),
            first_registration=registration,
            power_hp=detail_data.get("power_hp", node.get("powerHp")),
            power_kw=node.get("powerKw"),
            fuel_type=detail_data.get("fuel_type", node.get("fuelType")),
            transmission=node.get("transmission"),
            body_type=detail_data.get("body_type", node.get("bodyType")),
            doors=detail_data.get("doors", node.get("doors")),
            seats=detail_data.get("seats"),
            color_exterior=detail_data.get("color_exterior", node.get("colorExterior")),
            co2_emissions_g_km=detail_data.get("co2_emissions_g_km"),
            consumption_l_100km=detail_data.get("consumption_l_100km"),
            description=detail_data.get("description"),
            seller=detail_data.get("seller"),
            location=detail_data.get("location"),
            engine_displacement_cc=detail_data.get("engine_displacement_cc"),
        )


__all__ = ["MobileDeScraper"]
