# 🚗 Ejemplos de Uso - Import Cars Scraper

Este documento muestra ejemplos prácticos de cómo usar el scraper con el nuevo sistema de filtros y exportación.

## Instalación de Dependencias

```bash
pip install -e .
```

## Comandos Básicos

### 1. Scraping Básico

```bash
# mobile.de - primeros 10 anuncios
python -m src.import_cars.cli mobile-de --limit 10

# coches.net - primeros 10 anuncios  
python -m src.import_cars.cli coches-net --limit 10
```

### 2. Filtros por Marca y Modelo

```bash
# BMW Serie 3 en mobile.de
python -m src.import_cars.cli mobile-de --make "BMW" --model "Serie 3" --limit 20

# Mercedes-Benz Clase C en coches.net
python -m src.import_cars.cli coches-net --make "Mercedes-Benz" --model "Clase C" --limit 20
```

### 3. Filtros por Precio

```bash
# Coches entre 15,000 y 30,000 EUR en mobile.de
python -m src.import_cars.cli mobile-de --min-price 15000 --max-price 30000 --limit 50

# Coches de menos de 20,000 EUR en coches.net
python -m src.import_cars.cli coches-net --max-price 20000 --limit 50
```

### 4. Filtros por Año

```bash
# Coches del 2020 en adelante
python -m src.import_cars.cli mobile-de --min-year 2020 --limit 30

# Coches entre 2018 y 2022
python -m src.import_cars.cli coches-net --min-year 2018 --max-year 2022 --limit 30
```

### 5. Filtros por Combustible

```bash
# Solo coches eléctricos
python -m src.import_cars.cli mobile-de --fuel-types "electrico" --limit 20

# Diesel e híbridos
python -m src.import_cars.cli coches-net --fuel-types "diesel,hibrido" --limit 30
```

### 6. Filtros por Transmisión

```bash
# Solo automáticos
python -m src.import_cars.cli mobile-de --transmissions "automatico" --limit 25

# Manuales y semiautomáticos
python -m src.import_cars.cli coches-net --transmissions "manual,semiautomatico" --limit 25
```

### 7. Filtros por Potencia y Kilometraje

```bash
# Coches con más de 200 HP y menos de 50,000 km
python -m src.import_cars.cli mobile-de --min-power 200 --max-mileage 50000 --limit 20

# Coches con menos de 100,000 km
python -m src.import_cars.cli coches-net --max-mileage 100000 --limit 40
```

### 8. Filtros por Ubicación y Vendedor

```bash
# Solo coches en Alemania de concesionarios
python -m src.import_cars.cli mobile-de --country "DE" --dealer-only --limit 30

# Solo particulares en coches.net
python -m src.import_cars.cli coches-net --private-only --limit 30
```

### 9. Ordenación

```bash
# Ordenar por precio (menor a mayor)
python -m src.import_cars.cli mobile-de --sort-by "precio_asc" --limit 20

# Ordenar por año (más nuevo a más viejo)
python -m src.import_cars.cli coches-net --sort-by "año_desc" --limit 20
```

## Exportación a Excel/CSV

### 10. Exportar a Excel

```bash
# Exportar BMW a Excel
python -m src.import_cars.cli mobile-de --make "BMW" --export-format excel --export-filename "bmw_mobile_de" --limit 100

# Exportar coches eléctricos a Excel
python -m src.import_cars.cli coches-net --fuel-types "electrico" --export-format excel --export-filename "electricos_coches_net" --limit 50
```

### 11. Exportar a CSV

```bash
# Exportar Mercedes a CSV
python -m src.import_cars.cli mobile-de --make "Mercedes-Benz" --export-format csv --limit 100

# Exportar coches baratos a CSV
python -m src.import_cars.cli coches-net --max-price 15000 --export-format csv --export-filename "coches_baratos" --limit 200
```

## Comparación entre Fuentes

### 12. Comparar Precios

```bash
# Comparar BMW Serie 3 entre ambas fuentes
python -m src.import_cars.cli compare --make "BMW" --model "Serie 3" --limit 50

# Comparar coches entre 20k-40k EUR
python -m src.import_cars.cli compare --min-price 20000 --max-price 40000 --limit 100 --export-filename "comparacion_20k_40k"

# Comparar coches del 2021
python -m src.import_cars.cli compare --min-year 2021 --max-year 2021 --limit 75
```

## Casos de Uso Avanzados

### 13. Búsqueda de Oportunidades de Importación

```bash
# Buscar coches alemanes baratos para importar
python -m src.import_cars.cli mobile-de \
  --country "DE" \
  --max-price 25000 \
  --min-year 2019 \
  --fuel-types "diesel,gasolina" \
  --transmissions "automatico" \
  --dealer-only \
  --sort-by "precio_asc" \
  --export-format excel \
  --export-filename "oportunidades_importacion" \
  --limit 200

# Comparar con mercado español
python -m src.import_cars.cli coches-net \
  --max-price 35000 \
  --min-year 2019 \
  --fuel-types "diesel,gasolina" \
  --transmissions "automatico" \
  --sort-by "precio_asc" \
  --export-format excel \
  --export-filename "mercado_espanol_comparacion" \
  --limit 200
```

### 14. Análisis por Marca Específica

```bash
# Análisis completo de Audi
python -m src.import_cars.cli compare \
  --make "Audi" \
  --min-year 2018 \
  --limit 150 \
  --export-filename "analisis_audi_completo"

# Tesla en ambos mercados
python -m src.import_cars.cli compare \
  --make "Tesla" \
  --limit 100 \
  --export-filename "tesla_comparacion"
```

### 15. Filtros Combinados Complejos

```bash
# SUVs premium alemanes
python -m src.import_cars.cli mobile-de \
  --make "BMW" \
  --country "DE" \
  --min-price 40000 \
  --max-price 80000 \
  --min-year 2020 \
  --fuel-types "gasolina,hibrido" \
  --transmissions "automatico" \
  --min-power 250 \
  --dealer-only \
  --sort-by "año_desc" \
  --export-format excel \
  --limit 100

# Coches económicos eficientes
python -m src.import_cars.cli coches-net \
  --max-price 15000 \
  --min-year 2017 \
  --fuel-types "diesel,hibrido" \
  --max-mileage 80000 \
  --sort-by "precio_asc" \
  --export-format csv \
  --export-filename "economicos_eficientes" \
  --limit 150
```

## Estructura de Archivos Exportados

Los archivos Excel/CSV contienen campos unificados:

- **Identificación**: listing_id, source, url, scraped_at
- **Vehículo**: title, make, model, year, month
- **Precios**: price_gross_eur, price_net_eur, original_price, original_currency
- **Técnico**: mileage_km, power_hp, power_kw, engine_displacement_cc
- **Características**: fuel_type, transmission, body_type, doors, seats, color_exterior
- **Emisiones**: co2_emissions_g_km, consumption_*_l_100km
- **Ubicación**: country_code, region, province, city, postal_code
- **Vendedor**: seller_type, seller_name, seller_rating, seller_phone
- **Metadatos**: publish_date, certified, exportable

## Consejos para UI Futura

El sistema está diseñado para facilitar la integración con una interfaz web:

1. **Filtros Estructurados**: Todos los filtros están tipados y validados
2. **Respuestas Consistentes**: Formato unificado independiente de la fuente
3. **Exportación Flexible**: Múltiples formatos con nombres personalizables
4. **Paginación**: Control completo sobre páginas y tamaños
5. **Comparación**: Funcionalidad nativa para comparar fuentes

Los campos de filtros pueden mapearse directamente a controles de UI:
- Dropdowns para marcas, combustibles, transmisiones
- Sliders para rangos de precios, años, potencia
- Checkboxes para opciones booleanas
- Inputs numéricos para límites específicos
