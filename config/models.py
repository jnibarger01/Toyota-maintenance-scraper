"""
Toyota model definitions for 2018-2025.

Model codes are used in PDF URLs: T-MMS-{YY}{Model}.pdf
Some models have different names in the PDF system vs marketing.
"""

# PDF URL pattern discovered from Toyota site
PDF_URL_TEMPLATE = "https://www.toyota.com/content/dam/toyota/brochures/pdf/{year}/T-MMS-{yy}{model_code}.pdf"
PDF_URL_TEMPLATE_ALT = "https://assets.sia.toyota.com/publications/en/omms-s/T-MMS-{yy}{model_code}/pdf/T-MMS-{yy}{model_code}.pdf"

# Model definitions with PDF codes and year ranges
# Format: "Display Name": {"code": "PDF_CODE", "years": [start, end], "variants": [...]}
TOYOTA_MODELS = {
    # Sedans
    "Camry": {
        "code": "Camry",
        "years": [2018, 2025],
        "variants": ["Camry", "CamryAWD", "CamryHybrid"],
    },
    "Corolla": {
        "code": "Corolla",
        "years": [2018, 2025],
        "variants": ["Corolla", "CorollaHybrid"],
    },
    "Avalon": {
        "code": "Avalon",
        "years": [2018, 2024],  # Discontinued after 2024
        "variants": ["Avalon", "AvalonHybrid"],
    },
    "Crown": {
        "code": "Crown",
        "years": [2023, 2025],
        "variants": ["Crown"],
    },
    "Prius": {
        "code": "Prius",
        "years": [2018, 2025],
        "variants": ["Prius", "PriusPrime"],
    },
    
    # SUVs/Crossovers
    "RAV4": {
        "code": "RAV4",
        "years": [2018, 2025],
        "variants": ["RAV4", "RAV4Hybrid", "RAV4Prime"],
    },
    "Highlander": {
        "code": "Highlander",
        "years": [2018, 2025],
        "variants": ["Highlander", "HighlanderHybrid"],
    },
    "Grand Highlander": {
        "code": "GrandHighlander",
        "years": [2024, 2025],
        "variants": ["GrandHighlander", "GrandHighlanderHybrid"],
    },
    "4Runner": {
        "code": "4Runner",
        "years": [2018, 2025],
        "variants": ["4Runner"],
    },
    "Sequoia": {
        "code": "Sequoia",
        "years": [2018, 2025],
        "variants": ["Sequoia"],
    },
    "Land Cruiser": {
        "code": "LandCruiser",
        "years": [2018, 2025],
        "variants": ["LandCruiser"],
    },
    "Venza": {
        "code": "Venza",
        "years": [2021, 2025],
        "variants": ["Venza"],
    },
    "Corolla Cross": {
        "code": "CorollaCross",
        "years": [2022, 2025],
        "variants": ["CorollaCross", "CorollaCrossHybrid"],
    },
    "Crown Signia": {
        "code": "CrownSignia",
        "years": [2025, 2025],
        "variants": ["CrownSignia"],
    },
    "bZ4X": {
        "code": "bZ4X",
        "years": [2023, 2025],
        "variants": ["bZ4X"],
    },
    
    # Trucks
    "Tacoma": {
        "code": "Tacoma",
        "years": [2018, 2025],
        "variants": ["Tacoma"],
    },
    "Tundra": {
        "code": "Tundra",
        "years": [2018, 2025],
        "variants": ["Tundra", "TundraHybrid"],
    },
    
    # Minivan
    "Sienna": {
        "code": "Sienna",
        "years": [2018, 2025],
        "variants": ["Sienna"],
    },
    
    # Sports
    "GR86": {
        "code": "GR86",
        "years": [2022, 2025],
        "variants": ["GR86"],
    },
    "GR Supra": {
        "code": "Supra",
        "years": [2020, 2025],
        "variants": ["Supra"],
    },
    "GR Corolla": {
        "code": "GRCorolla",
        "years": [2023, 2025],
        "variants": ["GRCorolla"],
    },
    
    # Fuel Cell
    "Mirai": {
        "code": "Mirai",
        "years": [2018, 2025],
        "variants": ["Mirai"],
    },
}


def get_pdf_url(model: str, year: int) -> str:
    """Generate PDF URL for a model/year combination."""
    if model not in TOYOTA_MODELS:
        raise ValueError(f"Unknown model: {model}")
    
    model_info = TOYOTA_MODELS[model]
    if year < model_info["years"][0] or year > model_info["years"][1]:
        raise ValueError(f"{model} not available for year {year}")
    
    yy = str(year)[2:]  # 2024 -> "24"
    code = model_info["code"]
    
    return PDF_URL_TEMPLATE.format(year=year, yy=yy, model_code=code)


def get_all_model_years(start_year: int = 2018, end_year: int = 2025) -> list[tuple[str, int]]:
    """Get all valid model/year combinations."""
    combinations = []
    for model, info in TOYOTA_MODELS.items():
        for year in range(max(start_year, info["years"][0]), min(end_year, info["years"][1]) + 1):
            combinations.append((model, year))
    return combinations


def get_models_for_year(year: int) -> list[str]:
    """Get all models available for a specific year."""
    return [
        model for model, info in TOYOTA_MODELS.items()
        if info["years"][0] <= year <= info["years"][1]
    ]


# FuelEconomy.gov model name mappings (their names differ slightly)
FUELECONOMY_MODEL_MAP = {
    "4Runner": "4Runner",
    "Avalon": "Avalon",
    "Avalon Hybrid": "Avalon Hybrid",
    "bZ4X": "bZ4X",
    "Camry": "Camry",
    "Camry AWD": "Camry AWD",
    "Camry Hybrid": "Camry Hybrid",
    "Corolla": "Corolla",
    "Corolla Cross": "Corolla Cross",
    "Corolla Cross Hybrid": "Corolla Cross Hybrid",
    "Corolla Hybrid": "Corolla Hybrid",
    "Crown": "Crown",
    "Crown Signia": "Crown Signia",
    "GR Corolla": "GR Corolla",
    "GR Supra": "GR Supra",
    "GR86": "GR 86",
    "Grand Highlander": "Grand Highlander",
    "Grand Highlander Hybrid": "Grand Highlander Hybrid",
    "Highlander": "Highlander",
    "Highlander Hybrid": "Highlander Hybrid",
    "Land Cruiser": "Land Cruiser",
    "Mirai": "Mirai",
    "Prius": "Prius",
    "Prius Prime": "Prius Prime",
    "RAV4": "RAV4",
    "RAV4 Hybrid": "RAV4 Hybrid",
    "RAV4 Prime": "RAV4 Prime",
    "Sequoia": "Sequoia",
    "Sienna": "Sienna",
    "Tacoma": "Tacoma",
    "Tundra": "Tundra",
    "Tundra Hybrid": "Tundra Hybrid",
    "Venza": "Venza",
}
