# Toyota Maintenance Data Scraper

A production-ready scraper that collects Toyota vehicle maintenance schedules from three official sources.

## Data Sources

| Source | Data Type | Method |
|--------|-----------|--------|
| Toyota Warranty & Maintenance PDFs | Maintenance schedules, intervals, service items | PDF download + parsing |
| FuelEconomy.gov API | Vehicle specs (engine, MPG, drivetrain) | REST API |
| Toyota Owner's Manuals | Supplementary maintenance details | PDF download + parsing |

## Coverage

- **Models**: All Toyota models (2018-2025)
- **Data Points**: 
  - Service intervals (5k, 10k, 15k... to 120k miles)
  - Maintenance items per interval
  - Special operating condition services
  - Engine/drivetrain specifications
  - Fuel economy data

## Project Structure

```
toyota-maintenance-scraper/
├── config/
│   ├── models.py          # Toyota model definitions 2018-2025
│   └── settings.py        # Rate limits, paths, headers
├── scrapers/
│   ├── __init__.py
│   ├── toyota_pdf.py      # Toyota maintenance PDF scraper
│   ├── fueleconomy.py     # FuelEconomy.gov API client
│   └── base.py            # Base scraper class
├── parsers/
│   ├── __init__.py
│   └── maintenance_pdf.py # PDF text → structured data
├── storage/
│   ├── __init__.py
│   └── writer.py          # JSONL/CSV output
├── data/
│   └── pdfs/              # Downloaded PDFs (gitignored)
├── output/
│   ├── maintenance.jsonl  # Primary output
│   └── maintenance.csv    # CSV export
├── main.py                # CLI entrypoint
├── requirements.txt
└── README.md
```

## Installation

```bash
cd toyota-maintenance-scraper
pip install -r requirements.txt
```

## Usage

```bash
# Full scrape (all models, all years)
python main.py

# Smoke test (3 models, 1 year)
python main.py --smoke-test

# Specific model/year
python main.py --model Camry --year 2024

# Skip PDF download (use cached)
python main.py --use-cache
```

## Output Schema

```json
{
  "make": "Toyota",
  "model": "Camry",
  "year": 2024,
  "engine": "2.5L 4-Cylinder",
  "drivetrain": "FWD",
  "fuel_type": "Regular Gasoline",
  "mpg_city": 28,
  "mpg_highway": 39,
  "maintenance_schedule": [
    {
      "interval_miles": 5000,
      "interval_months": 6,
      "items": [
        {"service": "Rotate tires", "category": "standard"},
        {"service": "Inspect brake pads/discs", "category": "standard"},
        {"service": "Replace engine oil and filter", "category": "special_condition", "condition": "dusty_roads"}
      ]
    }
  ],
  "source_pdf_url": "https://www.toyota.com/...",
  "scraped_at": "2026-01-07T12:00:00Z"
}
```

## Rate Limits

- Toyota PDFs: 1 req/sec (conservative)
- FuelEconomy.gov API: 2 req/sec (public API)

## Compliance

- Respects robots.txt where applicable
- Uses official public APIs and documents
- No authentication bypass
- Conservative rate limiting
