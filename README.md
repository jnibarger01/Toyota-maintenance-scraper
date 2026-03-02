# Toyota Maintenance Scraper

Production-focused Toyota maintenance data scraper with CLI, checkpointing, offline fallback, and CSV/JSONL export.

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

## Project Layout

- `main.py` - repository entrypoint (delegates to app runner)
- `toyota-maintenance-scraper/runner.py` - primary CLI
- `toyota-maintenance-scraper/config.py` - models, URL patterns, config loader (JSON/TOML)
- `toyota-maintenance-scraper/fetcher.py` - HTTP layer (rate-limit/retry)
- `toyota-maintenance-scraper/parsers/` - source-specific parsers
- `toyota-maintenance-scraper/storage.py` - JSONL/CSV + checkpointing
- `toyota-maintenance-scraper/tests/` - unit/smoke tests

## Setup

```bash
cd /home/jace/Toyota-maintenance-scraper/toyota-maintenance-scraper
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
# run from repo root
python main.py --smoke-test --offline

# run app directly
python runner.py --smoke-test
python runner.py --models Camry RAV4 --years 2023 2024
python runner.py --source fueleconomy
python runner.py --no-resume
```

### Config file support

```bash
python runner.py --config config/scraper.json
python runner.py --config config/scraper.toml --models Camry --years 2024
```

Example `scraper.json`:

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

## Output

- `maintenance_schedules.jsonl/.csv`
- `fueleconomy_vehicles.jsonl/.csv`
- `service_specs.jsonl/.csv`
- `scrape_summary.json`
- `.checkpoint.json`

## Verification

```bash
python -m unittest discover -s tests -v
python runner.py --smoke-test --offline --no-resume
```
