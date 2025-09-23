# ImportCars Scrapers

Scrapper ultra eficiente para extraer anuncios de **mobile.de** y **coches.net**, con énfasis en:

- Fingerprints HTTP realistas (`curl_cffi` + `tls-client`).
- Bootstrap automático de cookies/tokens vía Playwright.
- Normalización a un modelo único (`NormalizedListing`).
- CLI rápida para búsquedas y exportación JSON.

## Requisitos

- Python 3.11+
- `pip install -e .` para instalar dependencias.
- `playwright install chrome` (primer uso) para disponer del navegador que se usará en modo stealth.

## Uso rápido

```bash
python -m import_cars.cli mobile-de --page 1 --page-size 50
python -m import_cars.cli coches-net --page 1 --override make=seat --override province=barcelona
```

La primera ejecución abrirá Playwright (en headless) para capturar cookies y la plantilla de petición; se cachea en `~/.cache/import_cars/`.

## Personalización

- Variables de entorno con prefijo `IMPORT_CARS_` (ver `src/import_cars/config.py`).
- `--override clave=valor` permite modificar dinámicamente variables del payload/query sin tocar código.

## Roadmap

1. Completar normalización de consumos/CO₂ con fuentes externas.
2. Añadir exportadores (Parquet, PostgreSQL, Kafka).
3. Motor de scoring para detectar oportunidades de importación.

## Legal

Revisa los Términos de Servicio de cada portal antes de ejecutar scraping a gran escala.
