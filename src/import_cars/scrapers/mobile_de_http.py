"""
Scraper HTTP para mobile.de usando curl_cffi
Mucho más rápido que Playwright (sin navegador)
"""
import html
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from curl_cffi import requests as cffi
from selectolax.parser import HTMLParser

from ..config import ScraperSettings
from ..filters import UnifiedFilters
from ..models import (
    Consumption,
    Location,
    Price,
    Registration,
    SearchResult,
    NormalizedListing,
)
from ..utils import build_mobile_de_search_url


class MobileDeHttpScraper:
    """Scraper HTTP rápido para mobile.de usando curl_cffi"""

    def __init__(self, settings: Optional[ScraperSettings] = None):
        self.settings = settings or ScraperSettings()
        self.source = "mobile_de"
        
        # Crear sesión con fingerprint TLS de Chrome real
        self.session = cffi.Session(
            impersonate="chrome",
            timeout=30,
        )
        
        # Headers realistas
        self.headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "accept-language": "es-ES,es;q=0.9",
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        }

    def _build_search_url(self, filters: UnifiedFilters, page: int = 1) -> str:
        """Construir URL de búsqueda con filtros usando el URL builder"""
        return build_mobile_de_search_url(filters, page)

    def search(self, query: Optional[UnifiedFilters] = None, limit: Optional[int] = None) -> SearchResult:
        """Buscar anuncios con filtros"""
        filters = query or UnifiedFilters()
        all_listings = []
        page = 1
        
        print(f"🔍 Iniciando búsqueda HTTP en mobile.de...")
        
        while True:
            url = self._build_search_url(filters, page)
            print(f"📄 Página {page}: {url}")
            
            # Obtener HTML de la página de listado
            response = self.session.get(url, headers=self.headers)
            response.raise_for_status()
            
            # Extraer IDs de anuncios
            ids = self._extract_ids_from_listing(response.text)
            print(f"   ✓ {len(ids)} IDs encontrados")
            
            if not ids:
                print("   ⚠️  No se encontraron más anuncios")
                break
            
            # Obtener detalles de cada anuncio
            listings = self._fetch_details_parallel(ids, max_workers=10)
            all_listings.extend(listings)
            
            print(f"   ✓ {len(listings)} anuncios procesados (Total: {len(all_listings)})")
            
            # Verificar límite
            if limit and len(all_listings) >= limit:
                all_listings = all_listings[:limit]
                break
            
            # Verificar si hay más páginas
            has_next = self._has_next_page(response.text)
            if not has_next:
                print("   ℹ️  No hay más páginas")
                break
            
            page += 1
        
        print(f"\n✅ Scraping completado: {len(all_listings)} anuncios")
        
        return SearchResult(
            listings=all_listings,
            total_listings=len(all_listings),
            result_page=page,
            has_next=False,
        )

    def _extract_ids_from_listing(self, html_content: str) -> List[str]:
        """Extraer IDs de anuncios del HTML de listado"""
        # Buscar patrón: detalles.html?id=XXXXXXXX
        ids = set(re.findall(r"detalles\.html\?id=(\d{6,})", html_content))
        return list(ids)

    def _has_next_page(self, html_content: str) -> bool:
        """Verificar si hay página siguiente"""
        tree = HTMLParser(html_content)
        next_link = tree.css_first('a[rel="next"]')
        return next_link is not None

    def _fetch_details_parallel(self, ids: List[str], max_workers: int = 10) -> List[NormalizedListing]:
        """Obtener detalles de múltiples anuncios en paralelo"""
        listings = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_id = {executor.submit(self._fetch_detail, id_): id_ for id_ in ids}
            
            for future in as_completed(future_to_id):
                try:
                    listing = future.result()
                    if listing:
                        listings.append(listing)
                except Exception as e:
                    id_ = future_to_id[future]
                    print(f"      ⚠️  Error en ID {id_}: {e}")
        
        return listings

    def _fetch_detail(self, vehicle_id: str) -> Optional[NormalizedListing]:
        """Obtener detalles de un anuncio específico"""
        url = f"https://www.mobile.de/es/veh%C3%ADculos/detalles.html?id={vehicle_id}"
        
        try:
            response = self.session.get(url, headers=self.headers)
            response.raise_for_status()
            
            return self._parse_detail_page(response.text, vehicle_id, url)
        
        except Exception as e:
            print(f"      ⚠️  Error obteniendo detalle {vehicle_id}: {e}")
            return None

    def _parse_detail_page(self, html_content: str, vehicle_id: str, url: str) -> Optional[NormalizedListing]:
        """Parsear página de detalle completa"""
        tree = HTMLParser(html.unescape(html_content))
        
        # Título - h2.typography_headline__yJCAO
        title = None
        title_node = tree.css_first('h2.typography_headline__yJCAO')
        if title_node:
            title = title_node.text(strip=True)
        
        # Subtítulo/Modelo - div.MainCtaBox_subTitle__wYybO
        subtitle = None
        subtitle_node = tree.css_first('div.MainCtaBox_subTitle__wYybO')
        if subtitle_node:
            subtitle = subtitle_node.text(strip=True)
        
        # Precio - div.MainPriceArea_mainPrice__xCkfs
        price_eur = None
        price_node = tree.css_first('div.MainPriceArea_mainPrice__xCkfs')
        if not price_node:
            price_node = tree.css_first('span[data-testid="prime-price"]')
        if not price_node:
            price_node = tree.css_first('span.PriceLabel_mainPrice__3SZut')
        if price_node:
            price_text = price_node.text(strip=True)
            # Eliminar espacios no separables y extraer números
            price_match = re.search(r"([0-9\.]+)", price_text.replace("\u00A0", "").replace(" ", ""))
            if price_match:
                # Formato alemán: punto como separador de miles, sin decimales
                price_eur = float(price_match.group(1).replace(".", ""))
        
        # Extraer datos de KeyFeatures (mileage, power, fuel, transmission, first_registration, previous_owners)
        tech_data = self._extract_key_features(tree)
        
        # Marca del título
        make = None
        if title:
            make = title.split()[0] if title.split() else None
        
        # Modelo: combinar título + subtítulo
        model = None
        if title and subtitle:
            # Título sin la marca
            title_without_make = " ".join(title.split()[1:]) if len(title.split()) > 1 else ""
            model = f"{title_without_make} {subtitle}".strip()
        elif title:
            model = " ".join(title.split()[1:]) if len(title.split()) > 1 else title
        
        # Registro
        registration = None
        if tech_data.get("first_registration"):
            reg_match = re.match(r"(\d{1,2})/(\d{4})", tech_data["first_registration"])
            if reg_match:
                month, year = reg_match.groups()
                registration = Registration(year=int(year), month=int(month))
        
        # Precio neto (estimado)
        price_net_eur = None
        if price_eur:
            vat_rate = 1.19  # IVA alemán por defecto
            price_net_eur = round(price_eur / vat_rate, 2)
        
        # Preparar consumo (convertir float a objeto Consumption si existe)
        consumption = None
        if tech_data.get("consumption_l_100km"):
            consumption = Consumption(combined=tech_data["consumption_l_100km"])
        
        # Preparar metadata con pegatina de emisiones
        from ..models import ListingMetadata
        metadata = ListingMetadata()
        if tech_data.get("emissions_sticker"):
            metadata.environment_badge = tech_data["emissions_sticker"]
        
        return NormalizedListing(
            listing_id=vehicle_id,
            source=self.source,
            url=url,
            scraped_at=datetime.now(),
            title=f"{title} {subtitle}".strip() if subtitle else title,
            make=make,
            model=model,
            price_eur=price_eur,
            price_net_eur=price_net_eur,
            price_original=Price(amount=price_eur, currency_code="EUR") if price_eur else None,
            mileage_km=tech_data.get("mileage_km"),
            first_registration=registration,
            fuel_type=tech_data.get("fuel_type"),
            transmission=tech_data.get("transmission"),
            power_hp=tech_data.get("power_hp"),
            power_kw=tech_data.get("power_kw"),
            engine_displacement_cc=tech_data.get("cubic_capacity_ccm"),
            co2_emissions_g_km=tech_data.get("co2_emissions_g_km"),
            consumption_l_100km=consumption,
            description=tech_data.get("description"),
            doors=tech_data.get("doors"),
            color_exterior=tech_data.get("color_exterior"),
            previous_owners=tech_data.get("previous_owners"),
            metadata=metadata,
        )

    def _extract_key_features(self, tree: HTMLParser) -> Dict[str, Any]:
        """Extraer datos de KeyFeatures usando los selectores específicos"""
        data = {}
        
        # Kilometraje - div[data-testid="vip-key-features-list-item-mileage"]
        mileage_node = tree.css_first('div[data-testid="vip-key-features-list-item-mileage"] div.KeyFeatures_value__8LVNc')
        if mileage_node:
            km_text = mileage_node.text(strip=True)
            km_match = re.search(r"(\d{1,3}(?:\.\d{3})*)", km_text)
            if km_match:
                data["mileage_km"] = int(km_match.group(1).replace(".", ""))
        
        # Potencia - div[data-testid="vip-key-features-list-item-power"]
        power_node = tree.css_first('div[data-testid="vip-key-features-list-item-power"] div.KeyFeatures_value__8LVNc')
        if power_node:
            power_text = power_node.text(strip=True)
            # Formato: "162 kW (220 cv)"
            kw_match = re.search(r"(\d+)\s*kW\s*\((\d+)\s*cv\)", power_text, re.I)
            if kw_match:
                data["power_kw"] = int(kw_match.group(1))
                data["power_hp"] = int(kw_match.group(2))
        
        # Combustible - div[data-testid="vip-key-features-list-item-fuel"]
        fuel_node = tree.css_first('div[data-testid="vip-key-features-list-item-fuel"] div.KeyFeatures_value__8LVNc')
        if fuel_node:
            data["fuel_type"] = fuel_node.text(strip=True)
        
        # Transmisión - div[data-testid="vip-key-features-list-item-transmission"]
        transmission_node = tree.css_first('div[data-testid="vip-key-features-list-item-transmission"] div.KeyFeatures_value__8LVNc')
        if transmission_node:
            trans_text = transmission_node.text(strip=True)
            if "manual" in trans_text.lower():
                data["transmission"] = "Manual"
            elif "automát" in trans_text.lower():
                data["transmission"] = "Automático"
            else:
                data["transmission"] = trans_text
        
        # Primera matriculación - div[data-testid="vip-key-features-list-item-firstRegistration"]
        first_reg_node = tree.css_first('div[data-testid="vip-key-features-list-item-firstRegistration"] div.KeyFeatures_value__8LVNc')
        if first_reg_node:
            data["first_registration"] = first_reg_node.text(strip=True)
        
        # Propietarios anteriores - div[data-testid="vip-key-features-list-item-numberOfPreviousOwners"]
        owners_node = tree.css_first('div[data-testid="vip-key-features-list-item-numberOfPreviousOwners"] div.KeyFeatures_value__8LVNc')
        if owners_node:
            owners_text = owners_node.text(strip=True)
            owners_match = re.search(r"(\d+)", owners_text)
            if owners_match:
                data["previous_owners"] = int(owners_match.group(1))
        
        # CO2 - dt[data-testid="envkv.co2Emissions-item"] + dd siguiente
        co2_dt = tree.css_first('dt[data-testid="envkv.co2Emissions-item"]')
        if co2_dt:
            # El dd viene inmediatamente después del dt
            parent = co2_dt.parent
            if parent:
                children = list(parent.iter())
                try:
                    dt_index = children.index(co2_dt)
                    # El siguiente elemento debería ser el dd
                    if dt_index + 1 < len(children):
                        dd_node = children[dt_index + 1]
                        if dd_node.tag == 'dd':
                            co2_text = dd_node.text(strip=True)
                            # Formato: "139 g/km"
                            co2_match = re.search(r"(\d+)\s*g/km", co2_text, re.I)
                            if co2_match:
                                data["co2_emissions_g_km"] = int(co2_match.group(1))
                except (ValueError, AttributeError):
                    pass
        
        # Consumo - dt[data-testid="envkv.consumptionDetails.fuel-item"] + dd siguiente
        consumption_dt = tree.css_first('dt[data-testid="envkv.consumptionDetails.fuel-item"]')
        if consumption_dt:
            parent = consumption_dt.parent
            if parent:
                children = list(parent.iter())
                try:
                    dt_index = children.index(consumption_dt)
                    if dt_index + 1 < len(children):
                        dd_node = children[dt_index + 1]
                        if dd_node.tag == 'dd':
                            cons_text = dd_node.text(strip=True)
                            # Formato: "6,0 l/100km"
                            cons_match = re.search(r"(\d+[,.]?\d*)\s*l/100\s*km", cons_text, re.I)
                            if cons_match:
                                data["consumption_l_100km"] = float(cons_match.group(1).replace(",", "."))
                except (ValueError, AttributeError):
                    pass
        
        # Cilindrada - dt[data-testid="cubicCapacity-item"] + dd siguiente
        cubic_dt = tree.css_first('dt[data-testid="cubicCapacity-item"]')
        if cubic_dt:
            parent = cubic_dt.parent
            if parent:
                children = list(parent.iter())
                try:
                    dt_index = children.index(cubic_dt)
                    if dt_index + 1 < len(children):
                        dd_node = children[dt_index + 1]
                        if dd_node.tag == 'dd':
                            cubic_text = dd_node.text(strip=True)
                            # Formato: "1.984 ccm" o "1.984 cm³"
                            cubic_match = re.search(r"(\d{1,3}(?:\.\d{3})*)", cubic_text)
                            if cubic_match:
                                data["cubic_capacity_ccm"] = int(cubic_match.group(1).replace(".", ""))
                except (ValueError, AttributeError):
                    pass
        
        # Pegatina de emisiones - dt[data-testid="emissionsSticker-item"] + dd siguiente
        sticker_dt = tree.css_first('dt[data-testid="emissionsSticker-item"]')
        if sticker_dt:
            parent = sticker_dt.parent
            if parent:
                children = list(parent.iter())
                try:
                    dt_index = children.index(sticker_dt)
                    if dt_index + 1 < len(children):
                        dd_node = children[dt_index + 1]
                        if dd_node.tag == 'dd':
                            sticker_text = dd_node.text(strip=True)
                            # Formato: "4 (Verde)"
                            data["emissions_sticker"] = sticker_text
                except (ValueError, AttributeError):
                    pass
        
        # Descripción del vehículo - div[data-testid="vip-vehicle-description-text"]
        desc_node = tree.css_first('div[data-testid="vip-vehicle-description-text"]')
        if desc_node:
            # Obtener HTML completo y procesar
            desc_html = desc_node.html
            # Convertir <br> a saltos de línea
            desc_text = re.sub(r"<br\s*/?>", "\n", desc_html)
            # Eliminar tags HTML
            desc_text = re.sub(r"<[^>]+>", "", desc_text)
            # Decodificar entidades HTML
            desc_text = html.unescape(desc_text)
            data["description"] = desc_text.strip()
        
        # Si no se encontró CO2 con el selector específico, buscar en texto general
        full_text = tree.text(strip=True)
        if "co2_emissions_g_km" not in data:
            co2_match = re.search(r"(\d+)\s*g/km", full_text, re.I)
            if co2_match:
                data["co2_emissions_g_km"] = int(co2_match.group(1))
        
        # Si no se encontró consumo, buscar en texto general
        if "consumption_l_100km" not in data:
            cons_match = re.search(r"(\d+[,.]?\d*)\s*l/100\s*km", full_text, re.I)
            if cons_match:
                data["consumption_l_100km"] = float(cons_match.group(1).replace(",", "."))
        
        # Puertas
        doors_match = re.search(r"(\d)\s*Puertas", full_text, re.I)
        if doors_match:
            data["doors"] = int(doors_match.group(1))
        
        # Color exterior
        color_match = re.search(r"Color exterior[:\s]+([A-Za-zñáéíóú\s]+?)(?:\n|Tapizado|Interior|$)", full_text, re.I)
        if color_match:
            data["color_exterior"] = color_match.group(1).strip()
        
        return data

