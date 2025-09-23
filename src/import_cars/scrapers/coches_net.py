from __future__ import annotations

import asyncio
import copy
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..config import ScraperSettings, get_settings
from ..http.session import StealthSession, stealth_context
from ..models import Financing, ListingMetadata, Location, NormalizedListing, Price, Registration, SearchResult, Seller
from .base import BaseScraper
from ..bootstrap.coches_net import CochesNetBootstrap


def _sanitize_headers(headers: Dict[str, str]) -> Dict[str, str]:
    sanitized: Dict[str, str] = {}
    for key, value in headers.items():
        lk = key.lower()
        if lk in {"content-length", "cookie", "host"}:
            continue
        if key.startswith(":"):
            continue
        sanitized[key] = value
    return sanitized


def _set_nested(data: Dict[str, Any], path: List[str], value: Any) -> None:
    current = data
    for key in path[:-1]:
        if isinstance(current, dict):
            current = current.setdefault(key, {})
        else:
            return
    if isinstance(current, dict):
        current[path[-1]] = value


class CochesNetScraper(BaseScraper):
    def __init__(self, *, settings: Optional[ScraperSettings] = None) -> None:
        super().__init__(settings=settings)
        self._bootstrap = CochesNetBootstrap(settings=self.settings)

    async def search(self, *, query: Dict[str, Any], limit: Optional[int] = None) -> SearchResult:
        template = await self._bootstrap.ensure(force=query.get("force_bootstrap", False))
        query_params = copy.deepcopy(template.query or {})
        if query_params is None:
            query_params = {}
        page_number = int(query.get("page", int(query_params.get("page", 1))))
        page_size = int(query.get("page_size", int(query_params.get("pageSize", 24))))
        query_params["page"] = str(page_number)
        query_params["pageSize"] = str(page_size)

        overrides: Dict[str, Any] = query.get("overrides", {})
        for key, value in overrides.items():
            query_params[key] = value

        response_data = await self._execute_request(
            template=template.to_json(),
            query_params=query_params,
            payload=template.payload if template.method.upper() == "POST" else None,
        )
        return self._parse_response(response_data, page_number=page_number, page_size=page_size)

    async def _execute_request(
        self,
        *,
        template: Dict[str, Any],
        query_params: Dict[str, Any],
        payload: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        async with stealth_context(settings=self.settings) as session:
            self._preload_cookies(session, template.get("cookies", []))
            headers = _sanitize_headers(template.get("headers", {}))

            def _call() -> Dict[str, Any]:
                method = template.get("method", "GET").upper()
                if method == "POST":
                    response = session.post(template["url"], json=payload, params=query_params, headers=headers)
                else:
                    response = session.get(template["url"], params=query_params, headers=headers)
                return response.json()

            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, _call)

    @staticmethod
    def _preload_cookies(session: StealthSession, cookies: List[Dict[str, Any]]) -> None:
        jar = session._session.cookies  # pylint: disable=protected-access
        for cookie in cookies:
            jar.set(
                name=cookie.get("name"),
                value=cookie.get("value"),
                domain=cookie.get("domain"),
                path=cookie.get("path", "/"),
            )

    def _parse_response(
        self,
        data: Dict[str, Any],
        *,
        page_number: int,
        page_size: int,
    ) -> SearchResult:
        ads = data.get("ads") or data.get("items") or data.get("results") or []
        listings: List[NormalizedListing] = []
        for ad in ads:
            if not isinstance(ad, dict):
                continue
            listing = self._to_listing(ad)
            if listing:
                listings.append(listing)
        pagination = data.get("pagination") or data.get("metadata", {}).get("pagination", {})
        total = pagination.get("total") or pagination.get("totalResults") or data.get("total")
        has_next = pagination.get("hasNext")
        if has_next is None and total is not None:
            has_next = page_number * page_size < total
        return SearchResult(
            listings=listings,
            total_listings=total,
            result_page=page_number,
            result_page_size=page_size,
            has_next=has_next,
        )

    def _to_listing(self, ad: Dict[str, Any]) -> Optional[NormalizedListing]:
        listing_id = str(ad.get("id") or ad.get("advertId") or ad.get("code") or "")
        if not listing_id:
            return None
        url = ad.get("url") or ad.get("canonicalUrl") or ad.get("detailUrl")
        if not url:
            return None
        price_info = ad.get("price") or ad.get("prices") or {}
        amount = price_info.get("price") or price_info.get("amount") or price_info.get("value")
        currency = price_info.get("currency") or price_info.get("currencyCode") or "EUR"
        price_original = None
        price_eur = None
        if amount is not None:
            price_original = Price(amount=float(amount), currency_code=currency)
            if currency.upper() == "EUR":
                price_eur = float(amount)

        mileage = ad.get("kms") or ad.get("kilometers") or ad.get("mileage")
        registration = None
        first_reg = ad.get("firstRegistration") or ad.get("firstRegistrationDate")
        if isinstance(first_reg, str):
            parts = first_reg.split("-")
            try:
                year = int(parts[0])
            except (ValueError, IndexError):
                year = None
            month = None
            if len(parts) > 1:
                try:
                    month = int(parts[1])
                except ValueError:
                    month = None
            if year:
                registration = Registration(year=year, month=month)
        elif isinstance(first_reg, dict):
            year = first_reg.get("year")
            month = first_reg.get("month")
            if year:
                registration = Registration(year=int(year), month=int(month) if month else None)

        seller_block = ad.get("dealer") or ad.get("seller") or {}
        seller = Seller(
            type=seller_block.get("type") or seller_block.get("sellerType"),
            name=seller_block.get("name") or seller_block.get("dealerName"),
            rating=seller_block.get("rating"),
            rating_count=seller_block.get("ratingCount") or seller_block.get("reviews"),
            phone=seller_block.get("phone") or seller_block.get("phoneNumber"),
            email=seller_block.get("email"),
            dealer_id=str(seller_block.get("id")) if seller_block.get("id") else None,
        ) if seller_block else None

        location_block = ad.get("location") or seller_block.get("location", {}) if seller_block else {}
        location = Location(
            country_code=location_block.get("country") or location_block.get("countryCode"),
            region=location_block.get("region") or location_block.get("province"),
            city=location_block.get("city"),
            postal_code=location_block.get("postalCode") or location_block.get("zip"),
            latitude=location_block.get("latitude"),
            longitude=location_block.get("longitude"),
        ) if location_block else None

        images = []
        image_block = ad.get("images") or ad.get("photos") or []
        if isinstance(image_block, list):
            for img in image_block:
                if isinstance(img, dict):
                    url_candidate = img.get("url") or img.get("uri") or img.get("href")
                else:
                    url_candidate = img
                if url_candidate:
                    images.append(url_candidate)

        features = ad.get("equipments") or ad.get("features") or []
        if isinstance(features, dict):
            features = [value for group in features.values() for value in group]

        financing_block = ad.get("financing") or {}
        financing = Financing(
            available=bool(financing_block.get("available")),
            amount=float(financing_block.get("monthlyPayment")) if financing_block.get("monthlyPayment") else None,
            rate=float(financing_block.get("interestRate")) if financing_block.get("interestRate") else None,
            duration_months=financing_block.get("term") or financing_block.get("duration"),
        ) if financing_block else None

        metadata = ListingMetadata(
            advert_type=ad.get("category"),
            vehicle_id=ad.get("vehicleId") or ad.get("vehicleCode"),
            publish_date=self._parse_datetime(ad.get("publishDate")),
            update_date=self._parse_datetime(ad.get("updateDate")),
            certified=ad.get("certified") or ad.get("isCertified"),
            delivery_options=ad.get("delivery"),
        )

        return NormalizedListing(
            listing_id=listing_id,
            source="coches_net",
            url=url,
            scraped_at=datetime.utcnow(),
            title=ad.get("title") or ad.get("headline"),
            make=ad.get("make") or ad.get("brand"),
            model=ad.get("model"),
            version=ad.get("version") or ad.get("trim"),
            price_eur=price_eur,
            price_original=price_original,
            vat_deductible=ad.get("vatDeductible") or ad.get("vat"),
            mileage_km=int(mileage) if mileage is not None else None,
            first_registration=registration,
            fuel_type=ad.get("fuelType") or ad.get("fuel"),
            transmission=ad.get("transmission") or ad.get("gearbox"),
            power_hp=ad.get("powerHP") or ad.get("powerHp") or ad.get("power"),
            power_kw=ad.get("powerKW") or ad.get("powerKw"),
            body_type=ad.get("bodyType") or ad.get("category"),
            doors=ad.get("doors"),
            seats=ad.get("seats"),
            color_exterior=ad.get("colour") or ad.get("color"),
            color_interior=ad.get("interiorColour") or ad.get("interior"),
            emission_class=ad.get("emissionClass"),
            co2_emissions_g_km=ad.get("co2") or ad.get("co2Emission"),
            features=features if isinstance(features, list) else [],
            description=ad.get("description"),
            images=images,
            location=location,
            seller=seller,
            metadata=metadata,
            import_ready_score=None,
        )

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None


__all__ = ["CochesNetScraper"]
