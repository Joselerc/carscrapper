"""
Script to fetch all car models for each make from mobile.de

Usage:
    python scripts/fetch_mobilede_models.py

Output:
    - data/mobilede_models_by_make.json
    - REPORT.md (execution summary)
"""

import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import sys

# Add parent directory to path to import from src
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    print("❌ curl_cffi not installed. Installing...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "curl_cffi"], check=True)
    from curl_cffi import requests as cffi_requests

from src.import_cars.data.mobile_de_makes import MOBILE_DE_MAKES

# Configuration
API_URL = "https://www.mobile.de/consumer/next/api/model-options"
OUTPUT_FILE = Path("data/mobilede_models_by_make.json")
REPORT_FILE = Path("REPORT.md")
MAX_RETRIES = 3
THROTTLE_MS = 500  # milliseconds between requests
MAX_CONCURRENT = 1  # Serial execution to avoid rate limiting
HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "es-ES,es;q=0.9,en;q=0.8",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mobilede_models_fetch.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ModelFetcher:
    def __init__(self):
        self.session = cffi_requests.Session(
            impersonate="chrome",
            timeout=30
        )
        self.results: Dict[str, List[Dict[str, any]]] = {}
        self.errors: Dict[str, str] = {}
        self.stats = {
            "total_makes": 0,
            "successful": 0,
            "failed": 0,
            "total_models": 0,
            "start_time": None,
            "end_time": None,
        }

    def fetch_models_for_make(self, make_id: int, make_name: str, retry: int = 0) -> Optional[List[Dict]]:
        """Fetch models for a specific make ID"""
        try:
            url = f"{API_URL}/{make_id}"
            logger.info(f"Fetching models for {make_name} (ID: {make_id})...")
            
            response = self.session.get(url, headers=HEADERS)
            response.raise_for_status()
            
            data = response.json()
            
            # Check if response is valid
            if not isinstance(data, list):
                # Sometimes the API returns just a count (integer) instead of a list
                logger.warning(f"[!] {make_name}: API returned {type(data).__name__} instead of list (probably no models)")
                return []
            
            # Parse and clean the response
            models = []
            
            def extract_models(items):
                """Recursively extract models from items, including nested optgroups"""
                extracted = []
                for item in items:
                    # Check if this is an optgroup with nested items (FIRST, before checking value/label)
                    if "items" in item or "optgroupLabel" in item:
                        # Recursively extract from nested items
                        extracted.extend(extract_models(item.get("items", [])))
                        continue
                    
                    value = item.get("value", "")
                    label = item.get("label", "").strip()
                    
                    # Skip "Todo" (all models) entry and group entries
                    if value == "" or label.lower() in ["todo", "all", "alle", "beliebig"]:
                        continue
                    
                    # Skip entries that are groups themselves (e.g., "Serie 1 (Todos)")
                    if item.get("isGroup", False):
                        continue
                    
                    # This is a regular model entry
                    # Try to convert value to integer
                    try:
                        model_id = int(value)
                        extracted.append({
                            "id": model_id,
                            "name": label
                        })
                    except (ValueError, TypeError):
                        # Skip entries with group- prefix and other non-numeric IDs
                        if not value.startswith("group-"):
                            logger.warning(f"Skipping non-numeric model ID '{value}' for {make_name}")
                        continue
                
                return extracted
            
            models = extract_models(data)
            
            logger.info(f"[OK] {make_name}: {len(models)} models")
            return models
            
        except cffi_requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                # Rate limited
                if retry < MAX_RETRIES:
                    wait_time = (2 ** retry) * 2  # Exponential backoff: 2s, 4s, 8s
                    logger.warning(f"Rate limited on {make_name}. Retrying in {wait_time}s... (attempt {retry + 1}/{MAX_RETRIES})")
                    time.sleep(wait_time)
                    return self.fetch_models_for_make(make_id, make_name, retry + 1)
                else:
                    logger.error(f"[X] {make_name}: Rate limit exceeded after {MAX_RETRIES} retries")
                    raise
            else:
                logger.error(f"[X] {make_name}: HTTP {e.response.status_code}")
                raise
                
        except Exception as e:
            if retry < MAX_RETRIES:
                wait_time = (2 ** retry) * 1
                logger.warning(f"Error on {make_name}: {str(e)}. Retrying in {wait_time}s... (attempt {retry + 1}/{MAX_RETRIES})")
                time.sleep(wait_time)
                return self.fetch_models_for_make(make_id, make_name, retry + 1)
            else:
                logger.error(f"[X] {make_name}: {str(e)} (after {MAX_RETRIES} retries)")
                raise

    def fetch_all_models(self):
        """Fetch models for all makes"""
        logger.info("="*60)
        logger.info("Starting mobile.de models extraction")
        logger.info("="*60)
        
        self.stats["start_time"] = datetime.now()
        
        # Get unique make IDs (remove aliases)
        unique_makes = {}
        for make_name, make_id in MOBILE_DE_MAKES.items():
            if make_id not in unique_makes:
                unique_makes[make_id] = make_name
        
        self.stats["total_makes"] = len(unique_makes)
        logger.info(f"Total unique makes to process: {len(unique_makes)}")
        
        # Exclude "Otros" (ID: 1400) - not a real manufacturer
        if 1400 in unique_makes:
            logger.info("Excluding 'OTROS' (ID: 1400) - not a real manufacturer")
            del unique_makes[1400]
            self.stats["total_makes"] -= 1
        
        # Fetch models for each make
        for idx, (make_id, make_name) in enumerate(unique_makes.items(), 1):
            logger.info(f"\n[{idx}/{len(unique_makes)}] Processing {make_name}...")
            
            try:
                models = self.fetch_models_for_make(make_id, make_name)
                
                if models:
                    self.results[str(make_id)] = models
                    self.stats["successful"] += 1
                    self.stats["total_models"] += len(models)
                else:
                    logger.warning(f"[!] {make_name}: No models found")
                    self.results[str(make_id)] = []
                    self.stats["successful"] += 1
                    
            except Exception as e:
                self.errors[make_name] = str(e)
                self.stats["failed"] += 1
                logger.error(f"[X] Failed to fetch {make_name}: {str(e)}")
            
            # Throttle between requests
            if idx < len(unique_makes):
                time.sleep(THROTTLE_MS / 1000.0)
        
        self.stats["end_time"] = datetime.now()
        
    def save_results(self):
        """Save results to JSON file"""
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n[OK] Results saved to: {OUTPUT_FILE}")
        logger.info(f"   File size: {OUTPUT_FILE.stat().st_size / 1024:.2f} KB")
        
    def generate_report(self):
        """Generate execution report"""
        duration = (self.stats["end_time"] - self.stats["start_time"]).total_seconds()
        
        report = f"""# Mobile.de Models Extraction Report

## Execution Summary

- **Date**: {self.stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')}
- **Duration**: {duration:.2f} seconds ({duration/60:.2f} minutes)
- **Total makes processed**: {self.stats['total_makes']}
- **Successful**: {self.stats['successful']} ({self.stats['successful']/self.stats['total_makes']*100:.1f}%)
- **Failed**: {self.stats['failed']} ({self.stats['failed']/self.stats['total_makes']*100:.1f}% if > 0 else 0%)
- **Total models extracted**: {self.stats['total_models']:,}

## Configuration

- **API Endpoint**: `{API_URL}`
- **Throttle delay**: {THROTTLE_MS}ms between requests
- **Max retries**: {MAX_RETRIES}
- **Execution mode**: Serial (no concurrency)

## Verification (Top Makes)

"""
        # Add verification for major brands
        major_brands = {
            "17200": "Mercedes-Benz",
            "3500": "BMW",
            "1900": "Audi",
            "25200": "Volkswagen",
            "24100": "Toyota",
        }
        
        for make_id, make_name in major_brands.items():
            if make_id in self.results:
                count = len(self.results[make_id])
                status = "[OK]" if count > 30 else "[!]"
                report += f"- {status} **{make_name}** (ID: {make_id}): {count} models\n"
            else:
                report += f"- [X] **{make_name}** (ID: {make_id}): NOT FOUND\n"
        
        # Add errors section if any
        if self.errors:
            report += f"\n## Errors ({len(self.errors)})\n\n"
            for make_name, error in self.errors.items():
                report += f"- **{make_name}**: {error}\n"
        
        # Add data cleaning notes
        report += """
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
"""
        
        with open(REPORT_FILE, 'w', encoding='utf-8') as f:
            f.write(report)
        
        logger.info(f"[OK] Report saved to: {REPORT_FILE}")
        
        # Print summary to console
        print("\n" + "="*60)
        print("EXTRACTION COMPLETE")
        print("="*60)
        print(f"[OK] Successfully processed: {self.stats['successful']}/{self.stats['total_makes']} makes")
        print(f"[#] Total models extracted: {self.stats['total_models']:,}")
        print(f"[T] Duration: {duration:.2f}s")
        if self.stats['failed'] > 0:
            print(f"[X] Failed: {self.stats['failed']} makes")
        print(f"[F] Output: {OUTPUT_FILE}")
        print(f"[R] Report: {REPORT_FILE}")
        print("="*60)


def main():
    fetcher = ModelFetcher()
    
    try:
        fetcher.fetch_all_models()
        fetcher.save_results()
        fetcher.generate_report()
        
    except KeyboardInterrupt:
        logger.warning("\n[!] Interrupted by user")
        if fetcher.results:
            logger.info("Saving partial results...")
            fetcher.save_results()
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"[X] Fatal error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()

