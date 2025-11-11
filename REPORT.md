# Mobile.de Models Extraction Report

## Execution Summary

- **Date**: 2025-11-05 17:19:43
- **Duration**: 103.20 seconds (1.72 minutes)
- **Total makes processed**: 172
- **Successful**: 172 (100.0%)
- **Failed**: 0 (0.0% if > 0 else 0%)
- **Total models extracted**: 2,589

## Configuration

- **API Endpoint**: `https://www.mobile.de/consumer/next/api/model-options`
- **Throttle delay**: 500ms between requests
- **Max retries**: 3
- **Execution mode**: Serial (no concurrency)

## Verification (Top Makes)

- [OK] **Mercedes-Benz** (ID: 17200): 341 models
- [OK] **BMW** (ID: 3500): 162 models
- [OK] **Audi** (ID: 1900): 59 models
- [OK] **Volkswagen** (ID: 25200): 83 models
- [OK] **Toyota** (ID: 24100): 56 models

## Data Cleaning Decisions

1. **"Todo" entries excluded**: All entries with `value=""` or label "Todo"/"All" were excluded as they represent "all models" option
2. **Non-numeric IDs excluded**: Model IDs that couldn't be converted to integers were skipped
3. **"OTROS" brand excluded**: Make ID 1400 ("Otros") was excluded as it's not a real manufacturer
4. **Aliases not duplicated**: Only unique make IDs were fetched (aliases like "VW"/"VOLKSWAGEN" share the same ID)

## Output

- **File**: `{OUTPUT_FILE}`
- **Format**: JSON with make IDs as keys, arrays of models as values
- **Structure**: `{{"make_id": [{{"id": model_id, "name": "Model Name"}}, ...]}}`

## Next Steps

To re-run this extraction:

```bash
python scripts/fetch_mobilede_models.py
```

To use the models in the scraper, import from:

```python
from import_cars.data.mobile_de_models import MOBILE_DE_MODELS_BY_MAKE
```
