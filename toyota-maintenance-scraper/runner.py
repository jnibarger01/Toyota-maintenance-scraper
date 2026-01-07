#!/usr/bin/env python3
"""
Toyota Maintenance Data Scraper - CLI Runner

Scrapes maintenance schedules and vehicle data from:
1. Toyota.com Warranty & Maintenance PDFs
2. FuelEconomy.gov API
3. Toyota Owner's Manual PDFs (standard specs)

Usage:
    python runner.py                    # Full scrape
    python runner.py --smoke-test       # Quick test (3 models, 2 years)
    python runner.py --source fueleconomy  # Single source
    python runner.py --models Camry RAV4 --years 2023 2024
"""
import argparse
import logging
import sys
import subprocess
from datetime import datetime
from typing import List, Optional

from config import (
    ScraperConfig, TOYOTA_MODELS, YEARS,
    get_model_years, get_toyota_pdf_url, get_toyota_assets_pdf_url
)
from fetcher import Fetcher
from parsers import ToyotaPDFParser, FuelEconomyParser, OwnersManualParser
from storage import Storage, Checkpoint

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def extract_pdf_text(pdf_content: bytes) -> Optional[str]:
    """
    Extract text from PDF using pdftotext.
    
    Falls back to basic text extraction if pdftotext not available.
    """
    import tempfile
    import os
    
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(pdf_content)
        pdf_path = f.name
    
    try:
        # Try pdftotext first
        result = subprocess.run(
            ["pdftotext", "-layout", pdf_path, "-"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    finally:
        os.unlink(pdf_path)
    
    return None


def scrape_toyota_pdfs(
    config: ScraperConfig,
    fetcher: Fetcher,
    storage: Storage,
    checkpoint: Checkpoint,
) -> int:
    """
    Scrape Toyota maintenance PDFs.
    
    Returns number of schedules collected.
    """
    logger.info("Starting Toyota PDF scrape...")
    parser = ToyotaPDFParser()
    schedules = []
    
    for model in config.models:
        model_years = get_model_years(model)
        valid_years = [y for y in config.years if y in model_years]
        
        for year in valid_years:
            if checkpoint.is_completed("toyota-pdf", model, year):
                logger.debug(f"Skipping completed: {year} {model}")
                continue
            
            logger.info(f"Fetching {year} Toyota {model} maintenance PDF...")
            
            # Try primary URL
            url = get_toyota_pdf_url(model, year)
            result = fetcher.fetch_pdf(url)
            
            # Try alternate URL if primary fails
            if not result.success or not result.content:
                alt_url = get_toyota_assets_pdf_url(model, year)
                logger.debug(f"Trying alternate URL: {alt_url}")
                result = fetcher.fetch_pdf(alt_url)
                url = alt_url
            
            if result.success and result.content:
                # Extract text from PDF
                text = extract_pdf_text(result.content)
                
                if text:
                    schedule = parser.parse_pdf_text(text, model, year, url)
                else:
                    # Fall back to standard schedule
                    logger.warning(f"Could not parse PDF text for {year} {model}, using standard schedule")
                    schedule = parser.get_standard_schedule(model, year, url)
                
                schedules.append(schedule.to_dict())
            else:
                # Generate standard schedule
                logger.warning(f"PDF not available for {year} {model}, generating standard schedule")
                schedule = parser.get_standard_schedule(model, year, url)
                schedules.append(schedule.to_dict())
            
            checkpoint.mark_completed("toyota-pdf", model, year)
    
    # Write results
    if schedules:
        storage.write_jsonl(
            "maintenance_schedules.jsonl",
            schedules,
            key_fields=["source", "model", "year"],
        )
    
    return len(schedules)


def scrape_fueleconomy(
    config: ScraperConfig,
    fetcher: Fetcher,
    storage: Storage,
    checkpoint: Checkpoint,
) -> int:
    """
    Scrape FuelEconomy.gov API.
    
    Returns number of vehicles collected.
    """
    logger.info("Starting FuelEconomy.gov scrape...")
    parser = FuelEconomyParser(fetcher)
    
    # Map our model names to FuelEconomy model patterns
    model_patterns = []
    for model in config.models:
        display_name = TOYOTA_MODELS.get(model, model)
        model_patterns.append(display_name)
    
    vehicles = parser.fetch_all_toyota_vehicles(
        years=config.years,
        models=model_patterns if model_patterns else None,
    )
    
    # Write results
    if vehicles:
        records = [v.to_dict() for v in vehicles]
        storage.write_jsonl(
            "fueleconomy_vehicles.jsonl",
            records,
            key_fields=["vehicle_id"],
        )
    
    return len(vehicles)


def scrape_owners_manuals(
    config: ScraperConfig,
    storage: Storage,
    checkpoint: Checkpoint,
) -> int:
    """
    Generate owner's manual specs (standard specs since manuals are authenticated).
    
    Returns number of specs generated.
    """
    logger.info("Generating owner's manual specs...")
    parser = OwnersManualParser()
    specs = []
    
    for model in config.models:
        model_years = get_model_years(model)
        valid_years = [y for y in config.years if y in model_years]
        
        for year in valid_years:
            if checkpoint.is_completed("owners-manual", model, year):
                continue
            
            display_name = TOYOTA_MODELS.get(model, model)
            url = parser.get_owners_manual_url(model, year)
            
            spec = parser.get_standard_specs(display_name, year, url)
            specs.append(spec.to_dict())
            
            checkpoint.mark_completed("owners-manual", model, year)
    
    # Write results
    if specs:
        storage.write_jsonl(
            "service_specs.jsonl",
            specs,
            key_fields=["source", "model", "year"],
        )
    
    return len(specs)


def run_scraper(
    config: ScraperConfig,
    sources: Optional[List[str]] = None,
    resume: bool = True,
) -> dict:
    """
    Run the scraper with given configuration.
    
    Args:
        config: Scraper configuration
        sources: Which sources to scrape (None = all)
        resume: Resume from checkpoint
        
    Returns:
        Summary statistics
    """
    storage = Storage(config.output_dir)
    checkpoint = Checkpoint(config.output_dir)
    
    if not resume:
        checkpoint.clear()
    
    checkpoint.start_session()
    
    stats = {
        "started_at": datetime.utcnow().isoformat(),
        "config": {
            "years": config.years,
            "models": config.models,
        },
        "results": {},
    }
    
    all_sources = ["toyota-pdf", "fueleconomy", "owners-manual"]
    active_sources = sources if sources else all_sources
    
    with Fetcher(
        rate_limit=config.rate_limit,
        timeout=config.timeout,
        max_retries=config.max_retries,
    ) as fetcher:
        
        if "toyota-pdf" in active_sources:
            count = scrape_toyota_pdfs(config, fetcher, storage, checkpoint)
            stats["results"]["toyota-pdf"] = count
        
        if "fueleconomy" in active_sources:
            count = scrape_fueleconomy(config, fetcher, storage, checkpoint)
            stats["results"]["fueleconomy"] = count
        
        if "owners-manual" in active_sources:
            count = scrape_owners_manuals(config, storage, checkpoint)
            stats["results"]["owners-manual"] = count
    
    stats["completed_at"] = datetime.utcnow().isoformat()
    
    # Export to CSV
    logger.info("Exporting to CSV...")
    for jsonl_file in ["maintenance_schedules.jsonl", "fueleconomy_vehicles.jsonl", "service_specs.jsonl"]:
        try:
            storage.export_to_csv(jsonl_file)
        except Exception as e:
            logger.warning(f"Could not export {jsonl_file}: {e}")
    
    # Save summary
    storage.write_json("scrape_summary.json", stats)
    
    return stats


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Toyota Maintenance Data Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Run quick test with minimal data",
    )
    
    parser.add_argument(
        "--source",
        choices=["toyota-pdf", "fueleconomy", "owners-manual"],
        action="append",
        help="Specific source(s) to scrape (can repeat)",
    )
    
    parser.add_argument(
        "--models",
        nargs="+",
        help="Specific model(s) to scrape",
    )
    
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        help="Specific year(s) to scrape",
    )
    
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Output directory (default: output)",
    )
    
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Start fresh, ignore checkpoint",
    )
    
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=1.0,
        help="Seconds between requests (default: 1.0)",
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output",
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Build configuration
    if args.smoke_test:
        config = ScraperConfig.smoke_test()
    else:
        config = ScraperConfig(
            years=args.years or YEARS,
            models=args.models or list(TOYOTA_MODELS.keys()),
            rate_limit=args.rate_limit,
            output_dir=args.output_dir,
        )
    
    # Validate models
    invalid_models = [m for m in config.models if m not in TOYOTA_MODELS]
    if invalid_models:
        logger.warning(f"Unknown models: {invalid_models}")
        logger.info(f"Valid models: {list(TOYOTA_MODELS.keys())}")
    
    logger.info(f"Configuration: {len(config.years)} years, {len(config.models)} models")
    logger.info(f"Output directory: {config.output_dir}")
    
    # Run scraper
    try:
        stats = run_scraper(
            config,
            sources=args.source,
            resume=not args.no_resume,
        )
        
        # Print summary
        print("\n" + "=" * 50)
        print("SCRAPE COMPLETE")
        print("=" * 50)
        for source, count in stats["results"].items():
            print(f"  {source}: {count} records")
        print(f"\nOutput: {config.output_dir}/")
        print("=" * 50)
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Scraper failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
