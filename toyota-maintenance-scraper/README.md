# Toyota Maintenance Data Scraper

Production-ready Python scraper for Toyota vehicle maintenance data from three sources:

1. **Toyota.com Maintenance PDFs** - Factory maintenance schedules
2. **FuelEconomy.gov API** - Vehicle specs and fuel economy (official EPA data)
3. **Owner's Manual Specs** - Fluid types, capacities, and service specifications

## Quick Start

```bash
cd toyota-maintenance-scraper

# Install dependencies
pip install -r requirements.txt --break-system-packages

# Smoke test (3 models, 2 years - ~2 minutes)
python runner.py --smoke-test

# Full scrape (all models, 2018-2025 - ~15 minutes)
python runner.py
```

## Scope

| Dimension | Value |
|-----------|-------|
| Years | 2018-2025 (8 years) |
| Models | 24 Toyota models |
| Sources | 3 (Toyota PDFs, FuelEconomy.gov, Owner's Manuals) |
| Estimated Records | ~500 maintenance schedules, ~1500 vehicle specs |

## Output Files

```
output/
├── maintenance_schedules.jsonl    # Toyota maintenance intervals
├── maintenance_schedules.csv      # CSV export
├── fueleconomy_vehicles.jsonl     # EPA vehicle data
├── fueleconomy_vehicles.csv       # CSV export
├── service_specs.jsonl            # Fluid specs and capacities
├── service_specs.csv              # CSV export
└── scrape_summary.json            # Run statistics
```

## Usage Examples

```bash
# Specific models and years
python runner.py --models Camry RAV4 Tacoma --years 2022 2023 2024

# Single source
python runner.py --source fueleconomy

# Multiple sources
python runner.py --source toyota-pdf --source fueleconomy

# Custom rate limit (slower for politeness)
python runner.py --rate-limit 2.0

# Start fresh (ignore checkpoint)
python runner.py --no-resume

# Verbose output
python runner.py -v
```

## Data Schema

### Maintenance Schedule (`maintenance_schedules.jsonl`)

```json
{
  "source": "toyota-pdf",
  "model": "Camry",
  "year": 2024,
  "intervals": [
    {
      "mileage": 5000,
      "months": 6,
      "items": [
        {"name": "Rotate tires", "required": true, "special_conditions": null}
      ],
      "special_operating_items": [
        {"name": "Replace engine oil", "required": true, "special_conditions": "dust"}
      ]
    }
  ],
  "source_url": "https://www.toyota.com/...",
  "scraped_at": "2024-01-15T10:30:00Z"
}
```

### FuelEconomy Vehicle (`fueleconomy_vehicles.jsonl`)

```json
{
  "source": "fueleconomy",
  "make": "Toyota",
  "model": "Camry",
  "year": 2024,
  "vehicle_id": 47123,
  "engine_displacement": 2.5,
  "cylinders": 4,
  "transmission": "Automatic (S8)",
  "drive": "Front-Wheel Drive",
  "fuel_type": "Regular Gasoline",
  "mpg_city": 28,
  "mpg_highway": 39,
  "mpg_combined": 32,
  "vehicle_class": "Midsize Cars",
  "annual_fuel_cost": 1750,
  "co2_tailpipe": 296.0,
  "scraped_at": "2024-01-15T10:30:00Z"
}
```

### Service Specs (`service_specs.jsonl`)

```json
{
  "source": "owners-manual-standard",
  "model": "Camry",
  "year": 2024,
  "engine_oil_capacity": "4.8 quarts with filter",
  "engine_oil_type": "0W-20 synthetic",
  "coolant_type": "Toyota Super Long Life Coolant",
  "transmission_fluid": "Toyota ATF WS",
  "brake_fluid": "DOT 3",
  "fluids": [
    {"name": "Engine Oil", "type": "0W-20 synthetic", "capacity": "4.8 quarts"}
  ],
  "scraped_at": "2024-01-15T10:30:00Z"
}
```

## Architecture

```
toyota-maintenance-scraper/
├── config.py              # Models, years, URL patterns
├── fetcher.py             # HTTP client (rate limiting, retries)
├── parsers/
│   ├── toyota_pdf.py      # Toyota.com PDF parser
│   ├── fueleconomy.py     # FuelEconomy.gov API parser
│   └── owners_manual.py   # Standard specs generator
├── storage.py             # JSONL/CSV output + checkpointing
└── runner.py              # CLI entrypoint
```

## Rate Limits & Compliance

- **Toyota.com**: 1 request/second (conservative, respects robots.txt)
- **FuelEconomy.gov**: 2 requests/second (public government API)
- Automatic retry with exponential backoff on 429/5xx errors
- Jittered delays to avoid thundering herd

## Checkpointing

The scraper automatically saves progress to `.checkpoint.json`. If interrupted, it resumes from the last completed model/year. Use `--no-resume` to start fresh.

## Known Limitations

1. **Toyota Owner's Manuals**: Require VIN-based authentication; scraper generates standard specs based on model category instead
2. **Toyota PDF parsing**: Some older PDFs have inconsistent formatting; falls back to standard schedule
3. **Model coverage**: Some models (e.g., C-HR) discontinued; scraper handles year availability automatically

## Next Improvements

1. Add SQLite output option for complex queries
2. Implement parallel fetching (asyncio) for faster scrapes
3. Add diff detection for schedule changes between years
4. Export to Excel with formatted tables
5. Add web UI for browsing results
