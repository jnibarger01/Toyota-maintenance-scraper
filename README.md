# Toyota Maintenance Scraper

Production-focused Toyota maintenance data scraper with CLI, checkpointing, offline fallback, SQLite persistence, and CSV/JSONL export.

## Aegis (Safety & Compliance)

- **Source boundaries**: only public sources are used:
  - Toyota public maintenance PDFs
  - FuelEconomy.gov public API
  - Non-authenticated owner-manual endpoint patterns (no login bypass)
- **No credential scraping**: project does not automate authenticated owner portals.
- **Rate limiting & retries**: conservative default pacing + exponential backoff.
- **Secrets risk**: no API keys required. Still avoid committing local outputs containing private notes.
- **Legal guardrails**:
  - Respect site terms/robots and request pacing.
  - Do not circumvent access controls.
  - Use results for research/maintenance planning, not misrepresentation of OEM guidance.

## Features

- Multi-source scraping (`toyota-pdf`, `fueleconomy`, `owners-manual`)
- JSONL output with dedupe by configurable key fields
- CSV export for analysis/spreadsheets
- SQLite upsert storage (`dataset + dedupe_key` uniqueness)
- Session checkpointing for resumable runs
- Offline mode for local/fallback generation

## Project Layout

- `main.py` - repository entrypoint (delegates to app runner)
- `toyota-maintenance-scraper/runner.py` - primary CLI
- `toyota-maintenance-scraper/config.py` - models, URL patterns, config loader (JSON/TOML)
- `toyota-maintenance-scraper/fetcher.py` - HTTP layer (rate-limit/retry)
- `toyota-maintenance-scraper/parsers/` - source-specific parsers
- `toyota-maintenance-scraper/storage.py` - JSONL/CSV + SQLite + checkpointing
- `toyota-maintenance-scraper/tests/` - unit/smoke tests

## Setup

```bash
cd /home/jace/Toyota-maintenance-scraper
make install
```

## Usage

```bash
# quick smoke test (offline)
python main.py --smoke-test --offline

# run specific models/years
python toyota-maintenance-scraper/runner.py --models Camry RAV4 --years 2023 2024

# run one source
python toyota-maintenance-scraper/runner.py --source fueleconomy

# run multiple sources (repeat --source)
python toyota-maintenance-scraper/runner.py --source toyota-pdf --source fueleconomy

# fresh run without checkpoint resume
python toyota-maintenance-scraper/runner.py --no-resume

# custom sqlite location
python toyota-maintenance-scraper/runner.py --sqlite-path /tmp/toyota-maintenance.db
```

## Config File Support

```bash
python main.py --config config/scraper.json
python main.py --config config/scraper.toml --models Camry --years 2024
```

Example `config/scraper.json`:

```json
{
  "years": [2024, 2025],
  "models": ["Camry", "RAV4"],
  "rate_limit": 1.0,
  "timeout": 30,
  "max_retries": 3,
  "output_dir": "output",
  "sqlite_path": "scraper.db",
  "offline": false,
  "source": ["toyota-pdf", "fueleconomy", "owners-manual"]
}
```

## Output Artifacts

- `maintenance_schedules.jsonl` / `maintenance_schedules.csv`
- `fueleconomy_vehicles.jsonl` / `fueleconomy_vehicles.csv`
- `service_specs.jsonl` / `service_specs.csv`
- `scrape_summary.json`
- `.checkpoint.json`
- `scraper.db` (SQLite, default under output dir)

## Verification

```bash
make test
python main.py --smoke-test --offline --no-resume
```
