"""
CLI mejorado para scraping con filtros y exportación
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import List, Optional

import orjson
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Configurar console para Windows
console = Console(force_terminal=True, legacy_windows=False)

from .exporters import ExcelExporter, CSVExporter
from .filters import UnifiedFilters, FuelType, Transmission, SortBy, PriceRange, YearRange, MileageRange, PowerRange
from .scrapers import CochesNetScraper, MobileDeScraper, MobileDeHttpScraper

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = typer.Typer(help="Scraper CLI avanzado para mobile.de y coches.net con filtros y exportación")


def _parse_fuel_types(fuel_types_str: Optional[str]) -> Optional[List[FuelType]]:
    """Parsea tipos de combustible desde string separado por comas"""
    if not fuel_types_str:
        return None
    
    fuel_map = {
        "gasolina": FuelType.GASOLINE,
        "gasoline": FuelType.GASOLINE,
        "diesel": FuelType.DIESEL,
        "electrico": FuelType.ELECTRIC,
        "electric": FuelType.ELECTRIC,
        "hibrido": FuelType.HYBRID,
        "hybrid": FuelType.HYBRID,
        "lpg": FuelType.LPG,
        "cng": FuelType.CNG,
    }
    
    types = []
    for fuel_str in fuel_types_str.lower().split(","):
        fuel_str = fuel_str.strip()
        if fuel_str in fuel_map:
            types.append(fuel_map[fuel_str])
        else:
            console.print(f"[yellow]Advertencia: Tipo de combustible desconocido '{fuel_str}' ignorado[/yellow]")
    
    return types if types else None


def _parse_transmissions(transmissions_str: Optional[str]) -> Optional[List[Transmission]]:
    """Parsea tipos de transmisión desde string separado por comas"""
    if not transmissions_str:
        return None
    
    trans_map = {
        "manual": Transmission.MANUAL,
        "automatico": Transmission.AUTOMATIC,
        "automatic": Transmission.AUTOMATIC,
        "semiautomatico": Transmission.SEMI_AUTOMATIC,
        "semi_automatic": Transmission.SEMI_AUTOMATIC,
    }
    
    types = []
    for trans_str in transmissions_str.lower().split(","):
        trans_str = trans_str.strip()
        if trans_str in trans_map:
            types.append(trans_map[trans_str])
        else:
            console.print(f"[yellow]Advertencia: Tipo de transmisión desconocido '{trans_str}' ignorado[/yellow]")
    
    return types if types else None


def _parse_sort_by(sort_str: Optional[str]) -> SortBy:
    """Parsea criterio de ordenación"""
    if not sort_str:
        return SortBy.RELEVANCE
    
    sort_map = {
        "relevancia": SortBy.RELEVANCE,
        "relevance": SortBy.RELEVANCE,
        "precio_asc": SortBy.PRICE_LOW_TO_HIGH,
        "price_asc": SortBy.PRICE_LOW_TO_HIGH,
        "precio_desc": SortBy.PRICE_HIGH_TO_LOW,
        "price_desc": SortBy.PRICE_HIGH_TO_LOW,
        "año_desc": SortBy.YEAR_NEW_TO_OLD,
        "year_desc": SortBy.YEAR_NEW_TO_OLD,
        "año_asc": SortBy.YEAR_OLD_TO_NEW,
        "year_asc": SortBy.YEAR_OLD_TO_NEW,
        "km_asc": SortBy.MILEAGE_LOW_TO_HIGH,
        "mileage_asc": SortBy.MILEAGE_LOW_TO_HIGH,
        "km_desc": SortBy.MILEAGE_HIGH_TO_LOW,
        "mileage_desc": SortBy.MILEAGE_HIGH_TO_LOW,
    }
    
    return sort_map.get(sort_str.lower(), SortBy.RELEVANCE)


async def _scrape_with_filters(
    scraper_class,
    filters: UnifiedFilters,
    limit: Optional[int] = None,
    export_format: Optional[str] = None,
    export_filename: Optional[str] = None,
) -> None:
    """Ejecuta scraping con filtros y opcionalmente exporta resultados"""
    
    scraper = scraper_class()
    
    # Detectar nombre del source
    if scraper_class == MobileDeScraper or scraper_class == MobileDeHttpScraper:
        source_name = "mobile.de"
    else:
        source_name = "coches.net"
    
    console.print(f"[blue]Scrapeando {source_name}...[/blue]")
    
    try:
        # Detectar si el scraper es async o sync
        import inspect
        if inspect.iscoroutinefunction(scraper.search):
            result = await scraper.search(query=filters, limit=limit)
        else:
            # Scraper síncrono (como MobileDeHttpScraper)
            result = scraper.search(query=filters, limit=limit)
        
        if not result.listings:
            console.print(f"[yellow]No se encontraron resultados para los filtros especificados en {source_name}[/yellow]")
            return
        
        console.print(f"[green]Encontrados {len(result.listings)} anuncios en {source_name}[/green]")
        
        # Mostrar tabla resumen
        table = Table(title=f"Resumen de resultados - {source_name}")
        table.add_column("Campo", style="cyan")
        table.add_column("Valor", style="magenta")
        
        table.add_row("Total anuncios", str(len(result.listings)))
        table.add_row("Página actual", str(result.result_page))
        table.add_row("Anuncios por página", str(result.result_page_size))
        table.add_row("Hay más páginas", "Sí" if result.has_next else "No")
        
        if result.listings:
            prices = [l.price_eur for l in result.listings if l.price_eur]
            if prices:
                table.add_row("Precio promedio", f"{sum(prices)/len(prices):,.0f} EUR")
                table.add_row("Precio mínimo", f"{min(prices):,.0f} EUR")
                table.add_row("Precio máximo", f"{max(prices):,.0f} EUR")
        
        console.print(table)
        
        # Exportar si se especifica formato
        if export_format:
            if export_format.lower() == "excel":
                exporter = ExcelExporter()
                filepath = exporter.export_listings(result.listings, export_filename)
                console.print(f"[green]Exportado a Excel: {filepath}[/green]")
            elif export_format.lower() == "csv":
                exporter = CSVExporter()
                filepath = exporter.export_listings(result.listings, export_filename)
                console.print(f"[green]Exportado a CSV: {filepath}[/green]")
            else:
                console.print(f"[red]Formato de exportación no soportado: {export_format}[/red]")
        else:
            # Mostrar JSON en consola si no hay exportación
            for listing in result.listings[:5]:  # Solo mostrar primeros 5 para no saturar
                print(orjson.dumps(listing.model_dump(mode="json"), option=orjson.OPT_INDENT_2).decode("utf-8"))
            
            if len(result.listings) > 5:
                console.print(f"[dim]... y {len(result.listings) - 5} anuncios más[/dim]")
                console.print("[dim]Usa --export-format para guardar todos los resultados[/dim]")
                
    except Exception as e:
        console.print(f"[red]Error durante el scraping: {e}[/red]")
        logger.exception("Error detallado:")


@app.command("mobile-de")
def mobile_de(
    # Paginación
    page: int = typer.Option(1, min=1, help="Número de página"),
    page_size: int = typer.Option(24, min=1, max=200, help="Resultados por página"),
    limit: Optional[int] = typer.Option(None, help="Máximo de anuncios a devolver"),
    
    # Filtros básicos
    make: Optional[str] = typer.Option(None, help="Marca del vehículo (ej: BMW, Mercedes-Benz)"),
    model: Optional[str] = typer.Option(None, help="Modelo del vehículo"),
    
    # Rangos de precios
    min_price: Optional[float] = typer.Option(None, help="Precio mínimo en EUR"),
    max_price: Optional[float] = typer.Option(None, help="Precio máximo en EUR"),
    
    # Rangos de años
    min_year: Optional[int] = typer.Option(None, help="Año mínimo"),
    max_year: Optional[int] = typer.Option(None, help="Año máximo"),
    
    # Rangos de kilometraje
    min_mileage: Optional[int] = typer.Option(None, help="Kilometraje mínimo"),
    max_mileage: Optional[int] = typer.Option(None, help="Kilometraje máximo"),
    
    # Rangos de potencia
    min_power: Optional[int] = typer.Option(None, help="Potencia mínima en HP"),
    max_power: Optional[int] = typer.Option(None, help="Potencia máxima en HP"),
    
    # Características
    fuel_types: Optional[str] = typer.Option(None, help="Tipos de combustible separados por comas (gasolina,diesel,electrico,hibrido)"),
    transmissions: Optional[str] = typer.Option(None, help="Tipos de transmisión separados por comas (manual,automatico,semiautomatico)"),
    
    # Ubicación
    country: Optional[str] = typer.Option(None, help="Código de país (ej: DE, ES)"),
    
    # Vendedor
    dealer_only: bool = typer.Option(False, help="Solo concesionarios"),
    private_only: bool = typer.Option(False, help="Solo particulares"),
    
    # Ordenación
    sort_by: Optional[str] = typer.Option(None, help="Ordenar por (relevancia,precio_asc,precio_desc,año_desc,año_asc,km_asc,km_desc)"),
    
    # Exportación
    export_format: Optional[str] = typer.Option(None, help="Formato de exportación (excel, csv)"),
    export_filename: Optional[str] = typer.Option(None, help="Nombre del archivo de exportación"),
) -> None:
    """Scraper para mobile.de con filtros avanzados"""
    
    # Construir filtros
    filters = UnifiedFilters(
        page=page,
        page_size=page_size,
        make=make,
        model=model,
        price_range=PriceRange(min_price=min_price, max_price=max_price) if min_price or max_price else None,
        year_range=YearRange(min_year=min_year, max_year=max_year) if min_year or max_year else None,
        mileage_range=MileageRange(min_mileage=min_mileage, max_mileage=max_mileage) if min_mileage or max_mileage else None,
        power_range=PowerRange(min_power_hp=min_power, max_power_hp=max_power) if min_power or max_power else None,
        fuel_types=_parse_fuel_types(fuel_types),
        transmissions=_parse_transmissions(transmissions),
        country_code=country,
        dealer_only=dealer_only if dealer_only else None,
        private_only=private_only if private_only else None,
        sort_by=_parse_sort_by(sort_by),
    )
    
    # Usar el nuevo scraper HTTP (más rápido)
    asyncio.run(_scrape_with_filters(MobileDeHttpScraper, filters, limit, export_format, export_filename))


@app.command("coches-net")
def coches_net(
    # Paginación
    page: int = typer.Option(1, min=1, help="Número de página"),
    page_size: int = typer.Option(30, min=1, max=200, help="Resultados por página"),
    limit: Optional[int] = typer.Option(None, help="Máximo de anuncios a devolver"),
    
    # Filtros básicos
    make: Optional[str] = typer.Option(None, help="Marca del vehículo (ej: BMW, Mercedes-Benz)"),
    model: Optional[str] = typer.Option(None, help="Modelo del vehículo"),
    
    # Rangos de precios
    min_price: Optional[float] = typer.Option(None, help="Precio mínimo en EUR"),
    max_price: Optional[float] = typer.Option(None, help="Precio máximo en EUR"),
    
    # Rangos de años
    min_year: Optional[int] = typer.Option(None, help="Año mínimo"),
    max_year: Optional[int] = typer.Option(None, help="Año máximo"),
    
    # Rangos de kilometraje
    min_mileage: Optional[int] = typer.Option(None, help="Kilometraje mínimo"),
    max_mileage: Optional[int] = typer.Option(None, help="Kilometraje máximo"),
    
    # Rangos de potencia
    min_power: Optional[int] = typer.Option(None, help="Potencia mínima en HP"),
    max_power: Optional[int] = typer.Option(None, help="Potencia máxima en HP"),
    
    # Características
    fuel_types: Optional[str] = typer.Option(None, help="Tipos de combustible separados por comas (gasolina,diesel,electrico,hibrido)"),
    transmissions: Optional[str] = typer.Option(None, help="Tipos de transmisión separados por comas (manual,automatico,semiautomatico)"),
    
    # Vendedor
    dealer_only: bool = typer.Option(False, help="Solo concesionarios"),
    private_only: bool = typer.Option(False, help="Solo particulares"),
    
    # Ordenación
    sort_by: Optional[str] = typer.Option(None, help="Ordenar por (relevancia,precio_asc,precio_desc,año_desc,año_asc,km_asc,km_desc)"),
    
    # Exportación
    export_format: Optional[str] = typer.Option(None, help="Formato de exportación (excel, csv)"),
    export_filename: Optional[str] = typer.Option(None, help="Nombre del archivo de exportación"),
) -> None:
    """Scraper para coches.net con filtros avanzados"""
    
    # Construir filtros
    filters = UnifiedFilters(
        page=page,
        page_size=page_size,
        make=make,
        model=model,
        price_range=PriceRange(min_price=min_price, max_price=max_price) if min_price or max_price else None,
        year_range=YearRange(min_year=min_year, max_year=max_year) if min_year or max_year else None,
        mileage_range=MileageRange(min_mileage=min_mileage, max_mileage=max_mileage) if min_mileage or max_mileage else None,
        power_range=PowerRange(min_power_hp=min_power, max_power_hp=max_power) if min_power or max_power else None,
        fuel_types=_parse_fuel_types(fuel_types),
        transmissions=_parse_transmissions(transmissions),
        dealer_only=dealer_only if dealer_only else None,
        private_only=private_only if private_only else None,
        sort_by=_parse_sort_by(sort_by),
    )
    
    asyncio.run(_scrape_with_filters(CochesNetScraper, filters, limit, export_format, export_filename))


@app.command("compare")
def compare(
    # Filtros básicos (aplicados a ambas fuentes)
    make: Optional[str] = typer.Option(None, help="Marca del vehículo"),
    model: Optional[str] = typer.Option(None, help="Modelo del vehículo"),
    min_price: Optional[float] = typer.Option(None, help="Precio mínimo en EUR"),
    max_price: Optional[float] = typer.Option(None, help="Precio máximo en EUR"),
    min_year: Optional[int] = typer.Option(None, help="Año mínimo"),
    max_year: Optional[int] = typer.Option(None, help="Año máximo"),
    
    # Configuración
    limit: Optional[int] = typer.Option(50, help="Máximo de anuncios por fuente"),
    export_filename: Optional[str] = typer.Option(None, help="Nombre del archivo de comparación"),
) -> None:
    """Compara precios entre mobile.de y coches.net con los mismos filtros"""
    
    async def _compare():
        # Construir filtros comunes
        filters = UnifiedFilters(
            make=make,
            model=model,
            price_range=PriceRange(min_price=min_price, max_price=max_price) if min_price or max_price else None,
            year_range=YearRange(min_year=min_year, max_year=max_year) if min_year or max_year else None,
        )
        
        console.print("[bold blue]Comparando precios entre mobile.de y coches.net...[/bold blue]")
        
        # Scraper ambas fuentes en paralelo
        mobile_scraper = MobileDeScraper()
        coches_scraper = CochesNetScraper()
        
        mobile_result, coches_result = await asyncio.gather(
            mobile_scraper.search(query=filters, limit=limit),
            coches_scraper.search(query=filters, limit=limit),
            return_exceptions=True
        )
        
        # Procesar resultados
        all_listings = []
        
        if isinstance(mobile_result, Exception):
            console.print(f"[red]Error en mobile.de: {mobile_result}[/red]")
        else:
            all_listings.extend(mobile_result.listings)
            console.print(f"[green]mobile.de: {len(mobile_result.listings)} anuncios[/green]")
        
        if isinstance(coches_result, Exception):
            console.print(f"[red]Error en coches.net: {coches_result}[/red]")
        else:
            all_listings.extend(coches_result.listings)
            console.print(f"[green]coches.net: {len(coches_result.listings)} anuncios[/green]")
        
        if not all_listings:
            console.print("[yellow]No se encontraron anuncios en ninguna fuente[/yellow]")
            return
        
        # Exportar comparación
        exporter = ExcelExporter()
        filename = export_filename or f"comparacion_precios_{make or 'todos'}_{model or 'modelos'}"
        filepath = exporter.export_listings(all_listings, filename)
        
        console.print(f"[green]Comparación exportada a: {filepath}[/green]")
        
        # Mostrar estadísticas
        mobile_listings = [l for l in all_listings if l.source == "mobile_de"]
        coches_listings = [l for l in all_listings if l.source == "coches_net"]
        
        table = Table(title="Comparación de Precios")
        table.add_column("Fuente", style="cyan")
        table.add_column("Anuncios", style="magenta")
        table.add_column("Precio Promedio", style="green")
        table.add_column("Precio Mínimo", style="yellow")
        table.add_column("Precio Máximo", style="red")
        
        for source_name, listings in [("mobile.de", mobile_listings), ("coches.net", coches_listings)]:
            if listings:
                prices = [l.price_eur for l in listings if l.price_eur]
                if prices:
                    table.add_row(
                        source_name,
                        str(len(listings)),
                        f"{sum(prices)/len(prices):,.0f} EUR",
                        f"{min(prices):,.0f} EUR",
                        f"{max(prices):,.0f} EUR"
                    )
                else:
                    table.add_row(source_name, str(len(listings)), "N/A", "N/A", "N/A")
            else:
                table.add_row(source_name, "0", "N/A", "N/A", "N/A")
        
        console.print(table)
    
    asyncio.run(_compare())


@app.command("filtros")
def show_filters():
    """Muestra todas las opciones de filtro disponibles para coches.net y mobile.de"""
    console.print("\n[bold blue]OPCIONES DE FILTRO DISPONIBLES[/bold blue]\n")
    
    # Marcas disponibles
    console.print("[bold green]MARCAS DISPONIBLES:[/bold green]")
    marcas = [
        "Audi", "BMW", "Mercedes-Benz", "Volkswagen", "Ford", "Toyota", "Nissan", 
        "Hyundai", "Kia", "Peugeot", "Renault", "Citroën", "Opel", "Seat", 
        "Skoda", "Fiat", "Honda", "Mazda", "Volvo", "Jaguar", "Land-Rover", 
        "Porsche", "Mini", "Smart", "Jeep", "Chevrolet", "Cadillac", "Chrysler",
        "Dodge", "Tesla", "Lexus", "Infiniti", "Subaru", "Suzuki", "Mitsubishi",
        "MG", "BYD", "Cupra", "Dacia", "Corvette"
    ]
    
    # Mostrar marcas en columnas
    table = Table(show_header=False, box=None, padding=(0, 2))
    for i in range(0, len(marcas), 4):
        row = marcas[i:i+4]
        while len(row) < 4:
            row.append("")
        table.add_row(*row)
    console.print(table)
    
    # Tipos de combustible
    console.print("\n[bold green]TIPOS DE COMBUSTIBLE:[/bold green]")
    console.print("• gasolina, diesel, electrico, hibrido, lpg, cng")
    
    # Tipos de transmisión
    console.print("\n[bold green]TIPOS DE TRANSMISION:[/bold green]")
    console.print("• manual, automatica")
    
    # Rangos de filtros
    console.print("\n[bold green]RANGOS DE PRECIO:[/bold green]")
    console.print("• --min-price: Precio mínimo en EUR (ej: 5000)")
    console.print("• --max-price: Precio máximo en EUR (ej: 50000)")
    
    console.print("\n[bold green]RANGOS DE AÑO:[/bold green]")
    console.print("• --min-year: Año mínimo (ej: 2010)")
    console.print("• --max-year: Año máximo (ej: 2023)")
    
    console.print("\n[bold green]RANGOS DE KILOMETRAJE:[/bold green]")
    console.print("• --min-mileage: Kilometraje mínimo (ej: 10000)")
    console.print("• --max-mileage: Kilometraje máximo (ej: 150000)")
    
    console.print("\n[bold green]RANGOS DE POTENCIA:[/bold green]")
    console.print("• --min-power: Potencia mínima en HP (ej: 100)")
    console.print("• --max-power: Potencia máxima en HP (ej: 300)")
    
    # Opciones de vendedor
    console.print("\n[bold green]TIPO DE VENDEDOR:[/bold green]")
    console.print("• --dealer-only: Solo concesionarios")
    console.print("• --private-only: Solo particulares")
    
    # Opciones de ordenación
    console.print("\n[bold green]ORDENACION:[/bold green]")
    console.print("• --sort-by: relevancia, precio, año, kilometraje")
    
    # Opciones de exportación
    console.print("\n[bold green]EXPORTACION:[/bold green]")
    console.print("• --export-format: excel, csv")
    console.print("• --export-filename: nombre_archivo.xlsx")
    
    # Ejemplos de uso
    console.print("\n[bold yellow]EJEMPLOS DE USO:[/bold yellow]")
    console.print("\n[dim]# Mercedes-Benz entre 2015-2020, máximo 30k EUR, solo automáticos:[/dim]")
    console.print("[cyan]python -m src.import_cars.cli coches-net --make \"Mercedes-Benz\" --min-year 2015 --max-year 2020 --max-price 30000 --transmissions automatica --export-format excel --export-filename mercedes.xlsx[/cyan]")
    
    console.print("\n[dim]# BMW diésel, máximo 100k km, solo concesionarios:[/dim]")
    console.print("[cyan]python -m src.import_cars.cli coches-net --make \"BMW\" --fuel-types diesel --max-mileage 100000 --dealer-only --limit 20[/cyan]")
    
    console.print("\n[dim]# Comparar precios entre coches.net y mobile.de:[/dim]")
    console.print("[cyan]python -m src.import_cars.cli compare --make \"Audi\" --model \"A4\" --min-year 2018[/cyan]")


if __name__ == "__main__":
    app()