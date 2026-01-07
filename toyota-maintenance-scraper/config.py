"""
Configuration for Toyota maintenance data scraper.
"""
from dataclasses import dataclass
from typing import List, Dict, Optional

# Years to scrape
YEARS = list(range(2018, 2026))  # 2018-2025

# Toyota models (comprehensive list for 2018-2025)
# Format: internal_name -> display_name
TOYOTA_MODELS: Dict[str, str] = {
    # Cars
    "Camry": "Camry",
    "Corolla": "Corolla",
    "CorollaHatchback": "Corolla Hatchback",
    "Avalon": "Avalon",
    "Prius": "Prius",
    "PriusPrime": "Prius Prime",
    "Mirai": "Mirai",
    "GR86": "GR86",
    "GRSupra": "GR Supra",
    "Crown": "Crown",
    
    # SUVs & Crossovers
    "RAV4": "RAV4",
    "RAV4Prime": "RAV4 Prime",
    "Highlander": "Highlander",
    "HighlanderHybrid": "Highlander Hybrid",
    "GrandHighlander": "Grand Highlander",
    "4Runner": "4Runner",
    "Sequoia": "Sequoia",
    "Venza": "Venza",
    "CHR": "C-HR",
    "CorollaCross": "Corolla Cross",
    "bZ4X": "bZ4X",
    "LandCruiser": "Land Cruiser",
    
    # Trucks
    "Tacoma": "Tacoma",
    "Tundra": "Tundra",
    
    # Vans
    "Sienna": "Sienna",
}

# Model availability by year (some models weren't available all years)
MODEL_YEAR_AVAILABILITY: Dict[str, List[int]] = {
    "Camry": list(range(2018, 2026)),
    "Corolla": list(range(2018, 2026)),
    "CorollaHatchback": list(range(2019, 2026)),
    "Avalon": list(range(2018, 2025)),  # Discontinued 2025
    "Prius": list(range(2018, 2026)),
    "PriusPrime": list(range(2018, 2026)),
    "Mirai": list(range(2018, 2026)),
    "GR86": list(range(2022, 2026)),  # Launched 2022
    "GRSupra": list(range(2020, 2026)),  # Launched 2020
    "Crown": list(range(2023, 2026)),  # Launched 2023
    "RAV4": list(range(2018, 2026)),
    "RAV4Prime": list(range(2021, 2026)),  # Launched 2021
    "Highlander": list(range(2018, 2026)),
    "HighlanderHybrid": list(range(2018, 2026)),
    "GrandHighlander": list(range(2024, 2026)),  # Launched 2024
    "4Runner": list(range(2018, 2026)),
    "Sequoia": list(range(2018, 2026)),
    "Venza": list(range(2021, 2026)),  # Relaunched 2021
    "CHR": list(range(2018, 2023)),  # Discontinued in US
    "CorollaCross": list(range(2022, 2026)),  # Launched 2022
    "bZ4X": list(range(2023, 2026)),  # Launched 2023
    "LandCruiser": list(range(2018, 2022)) + list(range(2024, 2026)),  # Gap 2022-2023
    "Tacoma": list(range(2018, 2026)),
    "Tundra": list(range(2018, 2026)),
    "Sienna": list(range(2018, 2026)),
}

# URL patterns
TOYOTA_PDF_BASE = "https://www.toyota.com/content/dam/toyota/brochures/pdf"
TOYOTA_ASSETS_BASE = "https://assets.sia.toyota.com/publications/en/omms-s"

# FuelEconomy.gov API
FUELECONOMY_API_BASE = "https://www.fueleconomy.gov/ws/rest"

@dataclass
class ScraperConfig:
    """Runtime configuration for the scraper."""
    years: List[int]
    models: List[str]
    rate_limit: float = 1.0  # requests per second
    timeout: int = 30
    max_retries: int = 3
    output_dir: str = "output"
    
    @classmethod
    def default(cls) -> "ScraperConfig":
        return cls(
            years=YEARS,
            models=list(TOYOTA_MODELS.keys())
        )
    
    @classmethod
    def smoke_test(cls) -> "ScraperConfig":
        """Minimal config for testing."""
        return cls(
            years=[2023, 2024],
            models=["Camry", "RAV4", "Tacoma"]
        )


def get_model_years(model: str) -> List[int]:
    """Get valid years for a model."""
    return MODEL_YEAR_AVAILABILITY.get(model, YEARS)


def get_toyota_pdf_url(model: str, year: int) -> str:
    """
    Generate Toyota maintenance PDF URL.
    
    Pattern: https://www.toyota.com/content/dam/toyota/brochures/pdf/{year}/T-MMS-{yy}{Model}.pdf
    Example: https://www.toyota.com/content/dam/toyota/brochures/pdf/2024/T-MMS-24Camry.pdf
    """
    yy = str(year)[2:]  # Last 2 digits of year
    return f"{TOYOTA_PDF_BASE}/{year}/T-MMS-{yy}{model}.pdf"


def get_toyota_assets_pdf_url(model: str, year: int) -> str:
    """
    Alternative Toyota assets URL pattern.
    
    Pattern: https://assets.sia.toyota.com/publications/en/omms-s/T-MMS-{yy}{Model}/pdf/T-MMS-{yy}{Model}.pdf
    """
    yy = str(year)[2:]
    doc_id = f"T-MMS-{yy}{model}"
    return f"{TOYOTA_ASSETS_BASE}/{doc_id}/pdf/{doc_id}.pdf"
