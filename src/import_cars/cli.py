from __future__ import annotations

import asyncio
from typing import Dict, Optional

import orjson
import typer

from .scrapers import CochesNetScraper, MobileDeScraper

app = typer.Typer(help="Scraper CLI para mobile.de y coches.net")


def _parse_overrides(values: Optional[list[str]]) -> Dict[str, str]:
    overrides: Dict[str, str] = {}
    if not values:
        return overrides
    for item in values:
        if "=" not in item:
            raise typer.BadParameter(f"Formato inválido para override: '{item}'. Usa clave=valor")
        key, value = item.split("=", 1)
        overrides[key] = value
    return overrides


async def _run_mobile_de(
    page: int,
    page_size: int,
    limit: Optional[int],
    overrides: Dict[str, str],
    force_bootstrap: bool,
) -> None:
    scraper = MobileDeScraper()
    result = await scraper.search(
        query={
            "page": page,
            "page_size": page_size,
            "overrides": overrides,
            "force_bootstrap": force_bootstrap,
        },
        limit=limit,
    )
    for listing in result.listings:
        print(orjson.dumps(listing.model_dump(mode="json"), option=orjson.OPT_INDENT_2).decode("utf-8"))


async def _run_coches_net(
    page: int,
    page_size: int,
    limit: Optional[int],
    overrides: Dict[str, str],
    force_bootstrap: bool,
) -> None:
    scraper = CochesNetScraper()
    result = await scraper.search(
        query={
            "page": page,
            "page_size": page_size,
            "overrides": overrides,
            "force_bootstrap": force_bootstrap,
        },
        limit=limit,
    )
    for listing in result.listings:
        print(orjson.dumps(listing, option=orjson.OPT_INDENT_2).decode("utf-8"))


@app.command("mobile-de")
def mobile_de(
    page: int = typer.Option(1, min=1, help="Número de página"),
    page_size: int = typer.Option(24, min=1, max=200, help="Resultados por página"),
    limit: Optional[int] = typer.Option(None, help="Máximo de anuncios a devolver"),
    override: Optional[list[str]] = typer.Option(None, help="Sobrescribir payload con clave=valor (puede repetirse)"),
    force_bootstrap: bool = typer.Option(False, help="Ignora cache y fuerza a capturar cookies/plantilla"),
) -> None:
    overrides = _parse_overrides(override)
    asyncio.run(_run_mobile_de(page, page_size, limit, overrides, force_bootstrap))


@app.command("coches-net")
def coches_net(
    page: int = typer.Option(1, min=1, help="Número de página"),
    page_size: int = typer.Option(30, min=1, max=200, help="Resultados por página"),
    limit: Optional[int] = typer.Option(None, help="Máximo de anuncios a devolver"),
    override: Optional[list[str]] = typer.Option(None, help="Sobrescribir query con clave=valor (puede repetirse)"),
    force_bootstrap: bool = typer.Option(False, help="Ignora cache y fuerza a capturar cookies/plantilla"),
) -> None:
    overrides = _parse_overrides(override)
    asyncio.run(_run_coches_net(page, page_size, limit, overrides, force_bootstrap))


if __name__ == "__main__":
    app()
