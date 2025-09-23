# Arquitectura del scrapper

## Objetivos de diseño
- Precisar extracción paralela con control fino de concurrencia.
- Minimizar bloqueos anti-bot usando fingerprints Chrome (`tls-client` + `curl_cffi`).
- Disponer de plan B con Playwright para bootstrap de cookies / tokens.
- Normalizar datos en un modelo Pydantic único.

## Capas
1. **HTTP** (`import_cars.http.session`)
   - `AsyncHttpClient`: para endpoints abiertos o JSON una vez obtenidas cookies.
   - `StealthSession`: sincronizado con impersonación TLS Chrome.
   - Proxies opcionales y reintentos exponenciales.
2. **Scrapers** (`import_cars.scrapers`)
   - `BaseScraper`: interfaz común con paginación y `gather` paralelo.
   - `MobileDeScraper`: resolverá búsqueda GraphQL / JSON.
   - `CochesNetScraper`: resolverá API REST interna.
3. **Normalización** (`import_cars.models`)
   - Pydantic para asegurar tipos y conversión de unidades.
4. **CLI** (`import_cars.cli`) [pendiente]
   - Comandos `search mobile-de`, `search coches-net` con filtros básicos y salida JSONL.
5. **Persistencia** [pendiente]
   - Hooks para enviar a Kafka, S3 o base de datos.

## Flujo Mobile.de
1. Bootstrap (una vez por sesión):
   - Abrir contexto Playwright opcional → obtener cookies `bm_sz`, `ak_bmsc`.
   - Guardar cookies en `cookies_path`.
2. Scraping en lote:
   - Construir payload GraphQL `webSearch` con filtros solicitados.
   - Usar `StealthSession` para POST hacia `https://www.mobile.de/graphql`.
   - Parsear `results.edges` → normalizar.

## Flujo Coches.net
1. Primer acceso con `StealthSession` a `/segunda-mano/` para recibir cookies y encontrar token `x-device-id`.
2. Solicitar `https://www.coches.net/api/vehicles/search` (endpoint interno) con querystring.
3. Parsear `ads` (listado) y `metadata.pagination`.

## Optimización
- Uso de `selectolax` para parseo HTML cuando sea necesario (más veloz que BeautifulSoup).
- Pre-cálculo de campos derivados (kW ↔ HP, conversión €).
- Reutilización de sesiones para mantener cookies y HTTP/2 multiplexing.

## Pendientes
- Extraer automáticamente plantillas de payload (se hará en la implementación de los scrapers).
- Añadir caching opcional (Redis / SQLite) si fuera necesario.
