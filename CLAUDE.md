# CLAUDE.md — Toyota Maintenance Scraper

This file provides guidance for AI assistants working on the Toyota Maintenance Scraper codebase.

## Project Overview

A production-focused Python web scraper that collects Toyota vehicle maintenance data from three public sources and exports structured data in JSONL and CSV formats.

**Data Sources**:
1. **Toyota PDFs** — Factory maintenance schedule PDFs from Toyota.com
2. **FuelEconomy.gov** — EPA public API for vehicle specs and fuel economy data
3. **Owner's Manual** — Standard service specs generated from known model data (no live scraping; authentication would be required for the real manuals)

**Output Files** (in `output/`):
- `maintenance_schedules.jsonl` / `.csv`
- `fueleconomy_vehicles.jsonl` / `.csv`
- `service_specs.jsonl` / `.csv`
- `scrape_summary.json`
- `.checkpoint.json` (internal, not committed)

---

## Repository Layout

```
Toyota-maintenance-scraper/
├── main.py                          # Root entrypoint (delegates to runner.py)
├── Makefile                         # Build, test, lint, run targets
├── requirements.txt                 # Python dependencies
├── README.md                        # User-facing documentation
├── STATUS.md                        # Project status and completion notes
├── config/
│   ├── scraper.json                 # Example JSON config
│   └── scraper.toml                 # Example TOML config
├── ops/
│   └── run_scraper.sh               # Production run script (Telegram notifications)
└── toyota-maintenance-scraper/      # Main application package
    ├── runner.py                    # CLI entrypoint & orchestration
    ├── config.py                    # ScraperConfig dataclass, constants, URL helpers
    ├── fetcher.py                   # HTTP client with rate limiting & retries
    ├── storage.py                   # JSONL/CSV output & checkpointing
    ├── README.md                    # Detailed technical documentation
    ├── parsers/
    │   ├── __init__.py
    │   ├── toyota_pdf.py            # Toyota PDF maintenance schedule parser
    │   ├── fueleconomy.py           # FuelEconomy.gov API parser
    │   └── owners_manual.py         # Owner's manual specs generator
    └── tests/
        ├── test_config.py           # Configuration validation tests
        ├── test_storage.py          # Storage & deduplication tests
        ├── test_parsers.py          # Parser unit tests
        └── test_runner_smoke.py     # End-to-end offline smoke test
```

**Note**: The package lives in `toyota-maintenance-scraper/` (with hyphens), which Python cannot import directly. `main.py` inserts that directory into `sys.path` so modules inside it can be imported normally.

---

## Development Setup

```bash
# Create virtualenv and install dependencies
make install        # Creates .venv and runs pip install -r requirements.txt

# Activate virtualenv (if running commands directly)
source .venv/bin/activate
```

**Python version**: 3.11+ required (uses `tomllib` from stdlib for TOML config).

**Optional system dependency**: `pdftotext` binary improves PDF extraction quality but is not required — the parser falls back to `pdfplumber`.

---

## Common Commands

```bash
make lint           # Syntax-check all Python files (py_compile)
make test           # Run full unittest suite
make smoke          # Quick offline smoke test (3 models, 2 years, no network)
make run            # Full live scrape (makes real network requests)
make clean          # Remove output/ directories and __pycache__
```

Running directly:
```bash
python main.py --smoke-test                           # Quick offline test
python main.py --models Camry RAV4 --years 2024       # Specific subset
python main.py --config config/scraper.json           # Load from file
python main.py --source toyota-pdf --offline -v       # Offline debug
python main.py --no-resume                            # Ignore checkpoint, start fresh
```

---

## Key Modules

### `config.py`
- `ScraperConfig` dataclass — validated configuration object
- `TOYOTA_MODELS` — list of 24 supported models
- `MODEL_YEAR_AVAILABILITY` — per-model year ranges (handles discontinued models)
- `get_model_years(model, years)` — filters years by model availability
- `get_toyota_pdf_url(model, year)` — primary PDF URL builder
- `get_toyota_assets_pdf_url(model, year)` — alternate/fallback PDF URL builder
- `load_config_file(path)` — loads JSON or TOML config files

### `fetcher.py`
- `Fetcher` class — synchronous HTTP client wrapping `httpx`
- Per-domain rate limiting with configurable jitter (default 0.3×)
- Exponential backoff retries via `tenacity`
- Methods: `fetch()`, `fetch_pdf()`, `fetch_json()`
- Use as context manager: `with Fetcher(config) as f:`

### `storage.py`
- `Storage` class — writes JSONL records and exports CSV
- Deduplication by configurable key fields (prevents duplicate records on resume)
- `Checkpoint` class — persists completed `source:model:year` keys to `.checkpoint.json`
- `Storage.write_summary()` — writes `scrape_summary.json` on completion

### `runner.py`
- `scrape_toyota_pdfs(config, fetcher, storage)` — iterates models/years, fetches PDFs
- `scrape_fueleconomy(config, fetcher, storage)` — queries EPA API
- `scrape_owners_manuals(config, storage)` — generates standard specs (no network)
- `run_scraper(config)` — main orchestration; handles checkpointing and source dispatch
- `main()` — `argparse`-based CLI; entry point from `main.py`

### `parsers/toyota_pdf.py`
- Parses Toyota PDF text into `MaintenanceSchedule` → `MaintenanceInterval` → `MaintenanceItem`
- Recognizes mileage intervals (5k–120k), months, and special operating conditions
- Falls back to a standard generated schedule when PDF parsing fails

### `parsers/fueleconomy.py`
- Calls the FuelEconomy.gov REST API; handles both JSON and XML responses
- Returns `VehicleSpec` dataclasses with engine, transmission, MPG, and emissions data

### `parsers/owners_manual.py`
- Generates `ServiceSpec` objects from hardcoded model categories (no live scraping)
- Trucks get larger oil capacities; hybrids get 0W-16 oil type

---

## Configuration Reference

Both JSON and TOML formats are supported. Example (`config/scraper.json`):

```json
{
  "years": [2024, 2025],
  "models": ["Camry", "RAV4"],
  "rate_limit": 1.0,
  "timeout": 30,
  "max_retries": 3,
  "output_dir": "output",
  "offline": false,
  "source": ["toyota-pdf", "fueleconomy", "owners-manual"]
}
```

Valid `source` values: `toyota-pdf`, `fueleconomy`, `owners-manual`.

CLI flags override config file values. All fields are optional and have defaults (see `ScraperConfig.default()`).

---

## Testing

Tests use the standard `unittest` library — no pytest required.

```bash
# Run all tests
python -m unittest discover toyota-maintenance-scraper/tests

# Run a single test file
python -m unittest toyota-maintenance-scraper.tests.test_parsers
```

**Test files**:
- `test_config.py` — validates `ScraperConfig` construction, file loading, model/year filtering
- `test_storage.py` — JSONL deduplication and CSV flattening logic
- `test_parsers.py` — unit tests for PDF text parsing, EPA API response normalization, and spec generation (uses inline fixture strings, not network calls)
- `test_runner_smoke.py` — end-to-end offline run with `--offline --smoke-test`

All tests must pass in offline mode. Network calls are gated by `config.offline`.

---

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`) runs on every push to `main` and on pull requests:

1. Syntax check (`py_compile`) on all `.py` files
2. Full unittest suite
3. Offline smoke test

Tested on Python 3.11 and 3.12.

---

## Data Schema

### `maintenance_schedules` records
| Field | Type | Description |
|---|---|---|
| `source` | str | `"toyota-pdf"` or `"toyota-standard"` |
| `model` | str | e.g. `"Camry"` |
| `year` | int | Model year |
| `intervals` | list | List of `MaintenanceInterval` dicts |
| `source_url` | str | URL the PDF was fetched from |
| `scraped_at` | str | ISO 8601 UTC timestamp |
| `data_source_type` | str | `"pdf_parsed"` or `"standard_generated"` |

### `fueleconomy_vehicles` records
| Field | Type | Description |
|---|---|---|
| `source` | str | `"fueleconomy"` |
| `vehicle_id` | int | EPA vehicle ID |
| `make` / `model` / `year` | str/int | Vehicle identity |
| `engine_displacement` | float | Liters |
| `cylinders` | int | |
| `transmission` | str | |
| `drive` | str | e.g. `"Front-Wheel Drive"` |
| `fuel_type` | str | |
| `mpg_city` / `mpg_highway` / `mpg_combined` | int | |
| `annual_fuel_cost` | int | USD |
| `co2_tailpipe` | float | g/mile |
| `scraped_at` | str | ISO 8601 UTC timestamp |

### `service_specs` records
| Field | Type | Description |
|---|---|---|
| `source` | str | `"owners-manual-standard"` |
| `model` / `year` | str/int | Vehicle identity |
| `engine_oil_capacity` | str | e.g. `"4.8 quarts with filter"` |
| `engine_oil_type` | str | e.g. `"0W-20 synthetic"` |
| `transmission_fluid` | str | `"Toyota ATF WS"` |
| `brake_fluid` | str | `"DOT 3"` |
| `fluids` | list | Detailed `FluidSpec` dicts |
| `scraped_at` | str | ISO 8601 UTC timestamp |

---

## Conventions

- **Timestamps**: Always UTC, ISO 8601 format (`datetime.utcnow().isoformat() + "Z"`).
- **Dataclasses**: Core data structures use `@dataclass` with `to_dict()` methods for JSON serialization.
- **Error handling**: Individual model/year failures are logged and skipped; they do not abort the full run.
- **Graceful degradation**: PDF parse failures fall back to a standard generated schedule automatically.
- **Logging**: Use `logging.getLogger(__name__)`. Verbose/debug mode is enabled with `-v`.
- **Rate limiting**: Default 1 req/sec for Toyota domains; FuelEconomy.gov respects the same default. Add jitter to avoid thundering-herd patterns.
- **Checkpointing**: The `source:model:year` key format is used throughout to track completed work.

---

## Compliance & Scope

- Only scrapes **public** data sources (no authentication, no login bypass).
- Respects rate limits and uses conservative request pacing (1 req/sec default).
- Exponential backoff on HTTP 429 and 5xx responses.
- No API keys or credentials required for any current data source.
- Do not commit the `output/` directory (it is gitignored).

---

## Known Limitations

1. **Owner's Manuals**: Full manual PDFs are behind authentication. The `owners-manual` source generates standard specs from hardcoded model data instead.
2. **PDF Parsing**: Inconsistent or old PDF layouts may fall back to a standard generated schedule rather than parsed intervals.
3. **Live Validation**: The full live run (all 24 models × 8 years × 3 sources) has not been validated against production URLs — individual live scrapes should be tested before running at scale.
4. **Async**: The fetcher is synchronous (`httpx` blocking mode). A full async rewrite could speed up large runs.

---

## Suggested Next Steps

- Validate live Toyota PDF URLs and FuelEconomy.gov API calls against real network responses
- Add fixture-based parser tests using real PDF samples
- Consider `pydantic` for stricter schema validation on scraped records
- Consider async fetching (`httpx.AsyncClient`) for faster full-scale runs
