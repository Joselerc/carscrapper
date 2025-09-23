# Data Schema Targets

## Campos nucleares
- `listing_id`: identificador único estable en el portal (string)
- `source`: `{mobile_de|coches_net}`
- `url`: enlace absoluto a la ficha del anuncio
- `scraped_at`: timestamp ISO8601 (UTC) de extracción
- `title`: título libre mostrado en el portal
- `make`: marca normalizada (string)
- `model`: modelo normalizado (string)
- `version`: nivel de acabado / submodelo textual
- `price_eur`: precio principal convertido a EUR (float)
- `price_original`: struct con `{amount, currency_code}`
- `vat_deductible`: bool o `null` si no aplica
- `mileage_km`: kilometraje en km (`int`)
- `first_registration`: struct `{year, month}`
- `production_year`: año de fabricación si se aporta
- `fuel_type`: enumeración (diesel, gasolina, híbrido, eléctrico, etc.)
- `transmission`: enumeración (manual, automática, cvt, etc.)
- `power_hp` y `power_kw`: potencia declarada
- `engine_displacement_cc`: cilindrada
- `body_type`: hatchback, berlina, suv, etc.
- `doors`: nº de puertas
- `seats`: nº de plazas
- `color_exterior` y `color_interior`
- `interior_material`: cuero, tela...
- `emission_class`: Euro 6d, Euro 5, etc.
- `co2_emissions_g_km`: entero o `null`
- `consumption_l_100km`: struct `{combined, urban, highway}`
- `features`: lista de strings (equipamiento)
- `description`: texto del anuncio
- `images`: lista ordenada de URLs absolutas
- `location`: struct `{country_code, region, province, city, postal_code, latitude, longitude}`
- `seller`: struct `{type (dealer, private), name, rating, rating_count, phone, email, vat_number}`
- `warranty_months`: duración restante si se informa
- `inspection_valid_until`: ITV/TÜV
- `previous_owners`: nº de propietarios anteriores
- `service_history`: bool si libro sellado / historial completo
- `accident_free`: bool si el portal lo certifica
- `import_ready_score`: placeholder para etapas posteriores

## Campos específicos Mobile.de
- `mobile_de.advert_type` (Privat, Händler, etc.)
- `mobile_de.vehicle_id`: UUID numérico que aparece en URLs internas
- `mobile_de.parsed_packages`: lista de paquetes (Business, Premium)
- `mobile_de.price_history`: última bajada, fecha
- `mobile_de.environment_badge`: etiqueta ambiental alemana
- `mobile_de.hsn_tsn`: código homologación alemana
- `mobile_de.delivery_options`: export-ready, envío, etc.

## Campos específicos Coches.net
- `coches_net.ad_id`: identificador numérico
- `coches_net.publish_date` y `coches_net.update_date`
- `coches_net.certified` (programa certificado coches.net)
- `coches_net.financing`: struct `{available, amount, rate, duration}`
- `coches_net.dealer_id` y datos de concesionario (código interno)
- `coches_net.delivery_peninsula`: info de envío a península/islas

## Reglas de normalización
- Convertir todas las unidades a sistema métrico (km, kW, L/100km).
- Normalizar `make`/`model` usando catálogo propio (pendiente).
- Mantener la moneda original en `price_original` y guardar tipo de IVA si se expone.
- Strings limpias de espacios y HTML, respetando caracteres ASCII.

## Fuentes complementarias (fase posterior)
- Catálogos técnicos (KBA, IDIADA, JATO) para rellenar huecos de emisiones/consumo.
- APIs públicas de datos técnicos (ej. https://api.monster.com) sólo si licencia lo permite.
- Librería propia de correlación VIN ↔ especificaciones.
