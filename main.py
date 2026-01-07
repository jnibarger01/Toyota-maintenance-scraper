#!/usr/bin/env python3
"""
Toyota Maintenance Data Scraper - CLI Entrypoint

Scrapes Toyota maintenance schedules from:
1. Toyota Warranty & Maintenance PDFs
2. FuelEconomy.gov API (vehicle specs)

Usage:
    python main.py                    # Full scrape
    python main.py --smoke-test       # Quick test (3 models)
    python main.py --model Camry      # Single model
    python main.py --year 2024        # Single year
    python main.py --use-cache        # Skip PDF downloads
"""
import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from tqdm import tqdm

from config import (
    settings,
    TOYOTA_MODELS,
    get_all_model_years,
    OUTPUT_JSONL,
    OUTPUT_CSV,
    VEHICLE_SPECS_JSONL,
    VEHICLE_SPECS_CSV,
)
from scrapers import ToyotaPDFScraper, FuelEconomyScraper
from parsers import parse_maintenance_pdf
from storage import JSONLWriter, CSVWriter, jsonl_to_csv, merge_data


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format=settings.LOG_FORMAT,
)
logger = logging.getLogger(__name__)


def scrape_maintenance_pdfs(
    models: list[tuple[str, int]],
    use_cache: bool = False,
) -> list[dict]:
    """
    Download and parse Toyota maintenance PDFs.
    
    Args:
        models: List of (model, year) tuples
        use_cache: Skip downloading if PDF exists
        
    Returns:
        List of parsed maintenance schedule dicts
    """
    results = []
    
    with ToyotaPDFScraper() as scraper:
        for model, year in tqdm(models, desc="Downloading PDFs"):
            try:
                pdf_path = scraper.download_pdf(model, year, force=not use_cache)
                
                if pdf_path and pdf_path.exists():
                    schedule = parse_maintenance_pdf(pdf_path, model, year)
                    if schedule.intervals:
                        results.append(schedule.to_dict())
                        logger.info(f"Parsed {model} {year}: {len(schedule.intervals)} intervals")
                    else:
                        logger.warning(f"No intervals found for {model} {year}")
                else:
                    logger.warning(f"PDF not available for {model} {year}")
                    
            except Exception as e:
                logger.error(f"Failed to process {model} {year}: {e}")
    
    return results


def scrape_vehicle_specs(
    models: list[tuple[str, int]],
) -> list[dict]:
    """
    Fetch vehicle specs from FuelEconomy.gov.
    
    Args:
        models: List of (model, year) tuples
        
    Returns:
        List of vehicle spec dicts
    """
    results = []
    seen = set()
    
    with FuelEconomyScraper() as scraper:
        for model, year in tqdm(models, desc="Fetching specs"):
            key = (model, year)
            if key in seen:
                continue
            seen.add(key)
            
            try:
                vehicles = scraper.scrape(model, year)
                results.extend(vehicles)
                logger.info(f"Got {len(vehicles)} variants for {year} {model}")
            except Exception as e:
                logger.warning(f"Failed to get specs for {model} {year}: {e}")
    
    return results


def run_smoke_test():
    """Run quick test with subset of models."""
    logger.info("=== SMOKE TEST MODE ===")
    
    # Test with 3 popular models, latest year only
    test_models = [
        ("Camry", 2024),
        ("RAV4", 2024),
        ("Tacoma", 2024),
    ]
    
    logger.info(f"Testing with {len(test_models)} models")
    
    # Test PDF scraping
    logger.info("\n--- Testing PDF scraping ---")
    maintenance = scrape_maintenance_pdfs(test_models, use_cache=False)
    logger.info(f"Parsed {len(maintenance)} maintenance schedules")
    
    if maintenance:
        sample = maintenance[0]
        logger.info(f"Sample: {sample['model']} {sample['year']}")
        logger.info(f"  Intervals: {len(sample['maintenance_schedule'])}")
        if sample['maintenance_schedule']:
            first = sample['maintenance_schedule'][0]
            logger.info(f"  First interval: {first['interval_miles']} miles")
            logger.info(f"  Items: {len(first['items'])}")
    
    # Test FuelEconomy.gov API
    logger.info("\n--- Testing FuelEconomy.gov API ---")
    specs = scrape_vehicle_specs(test_models)
    logger.info(f"Fetched {len(specs)} vehicle specs")
    
    if specs:
        sample = specs[0]
        logger.info(f"Sample: {sample.get('year')} {sample.get('model')}")
        logger.info(f"  Engine: {sample.get('engine_displacement')}L {sample.get('cylinders')}-cyl")
        logger.info(f"  MPG: {sample.get('mpg_city')}/{sample.get('mpg_highway')}")
    
    logger.info("\n=== SMOKE TEST COMPLETE ===")
    return maintenance, specs


def main():
    parser = argparse.ArgumentParser(
        description="Toyota Maintenance Data Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Run quick test with 3 models",
    )
    parser.add_argument(
        "--model",
        type=str,
        help="Scrape specific model only (e.g., 'Camry')",
    )
    parser.add_argument(
        "--year",
        type=int,
        help="Scrape specific year only (e.g., 2024)",
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=2018,
        help="Start year for range (default: 2018)",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=2025,
        help="End year for range (default: 2025)",
    )
    parser.add_argument(
        "--use-cache",
        action="store_true",
        help="Use cached PDFs if available",
    )
    parser.add_argument(
        "--skip-specs",
        action="store_true",
        help="Skip FuelEconomy.gov API calls",
    )
    parser.add_argument(
        "--skip-pdfs",
        action="store_true",
        help="Skip PDF downloading/parsing",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Smoke test mode
    if args.smoke_test:
        maintenance, specs = run_smoke_test()
        return 0
    
    # Build model/year list
    if args.model and args.year:
        models = [(args.model, args.year)]
    elif args.model:
        model_info = TOYOTA_MODELS.get(args.model)
        if not model_info:
            logger.error(f"Unknown model: {args.model}")
            logger.info(f"Available models: {', '.join(TOYOTA_MODELS.keys())}")
            return 1
        models = [
            (args.model, year) 
            for year in range(args.start_year, args.end_year + 1)
            if model_info["years"][0] <= year <= model_info["years"][1]
        ]
    elif args.year:
        models = [
            (model, args.year)
            for model, info in TOYOTA_MODELS.items()
            if info["years"][0] <= args.year <= info["years"][1]
        ]
    else:
        models = get_all_model_years(args.start_year, args.end_year)
    
    logger.info(f"Scraping {len(models)} model/year combinations")
    logger.info(f"Year range: {args.start_year}-{args.end_year}")
    
    start_time = datetime.now(timezone.utc)
    
    # Scrape maintenance PDFs
    if not args.skip_pdfs:
        logger.info("\n=== Scraping Maintenance PDFs ===")
        maintenance_data = scrape_maintenance_pdfs(models, use_cache=args.use_cache)
        
        # Write maintenance data
        maintenance_writer = JSONLWriter(
            OUTPUT_JSONL,
            key_fn=lambda r: f"{r['model']}_{r['year']}",
        )
        written = maintenance_writer.write_many(maintenance_data)
        logger.info(f"Wrote {written} maintenance records to {OUTPUT_JSONL}")
    
    # Scrape vehicle specs
    if not args.skip_specs:
        logger.info("\n=== Fetching Vehicle Specs ===")
        specs_data = scrape_vehicle_specs(models)
        
        # Write specs data
        specs_writer = JSONLWriter(
            VEHICLE_SPECS_JSONL,
            key_fn=lambda r: f"{r.get('model', '')}_{r.get('year', '')}_{r.get('vehicle_id', '')}",
        )
        written = specs_writer.write_many(specs_data)
        logger.info(f"Wrote {written} vehicle specs to {VEHICLE_SPECS_JSONL}")
    
    # Generate CSV exports
    logger.info("\n=== Generating CSV Exports ===")
    
    if OUTPUT_JSONL.exists():
        jsonl_to_csv(OUTPUT_JSONL, OUTPUT_CSV)
    
    if VEHICLE_SPECS_JSONL.exists():
        jsonl_to_csv(VEHICLE_SPECS_JSONL, VEHICLE_SPECS_CSV)
    
    # Merge data if both sources available
    if OUTPUT_JSONL.exists() and VEHICLE_SPECS_JSONL.exists():
        merged_path = settings.OUTPUT_DIR / "maintenance_with_specs.jsonl"
        merge_data(OUTPUT_JSONL, VEHICLE_SPECS_JSONL, merged_path)
        jsonl_to_csv(merged_path, settings.OUTPUT_DIR / "maintenance_with_specs.csv")
    
    # Summary
    elapsed = datetime.now(timezone.utc) - start_time
    logger.info(f"\n=== COMPLETE ===")
    logger.info(f"Elapsed time: {elapsed}")
    logger.info(f"Output files:")
    logger.info(f"  {OUTPUT_JSONL}")
    logger.info(f"  {OUTPUT_CSV}")
    if not args.skip_specs:
        logger.info(f"  {VEHICLE_SPECS_JSONL}")
        logger.info(f"  {VEHICLE_SPECS_CSV}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
