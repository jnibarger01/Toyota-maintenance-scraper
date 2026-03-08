"""
Configuration for Toyota maintenance data scraper.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any
import json

try:  # Python 3.11+
    import tomllib  # type: ignore
except Exception:  # pragma: no cover
    tomllib = None

YEARS = list(range(2018, 2027))

TOYOTA_MODELS: Dict[str, str] = {
    "Camry": "Camry", "Corolla": "Corolla", "CorollaHatchback": "Corolla Hatchback",
    "Avalon": "Avalon", "Prius": "Prius", "PriusPrime": "Prius Prime", "Mirai": "Mirai",
    "GR86": "GR86", "GRSupra": "GR Supra", "Crown": "Crown",
    "RAV4": "RAV4", "RAV4Prime": "RAV4 Prime", "Highlander": "Highlander",
    "HighlanderHybrid": "Highlander Hybrid", "GrandHighlander": "Grand Highlander",
    "4Runner": "4Runner", "Sequoia": "Sequoia", "Venza": "Venza", "CHR": "C-HR",
    "CorollaCross": "Corolla Cross", "bZ4X": "bZ4X", "LandCruiser": "Land Cruiser",
    "Tacoma": "Tacoma", "Tundra": "Tundra", "Sienna": "Sienna",
}

MODEL_YEAR_AVAILABILITY: Dict[str, List[int]] = {
    "Camry": list(range(2018, 2027)), "Corolla": list(range(2018, 2027)),
    "CorollaHatchback": list(range(2019, 2027)), "Avalon": list(range(2018, 2025)),
    "Prius": list(range(2018, 2027)), "PriusPrime": list(range(2018, 2027)),
    "Mirai": list(range(2018, 2027)), "GR86": list(range(2022, 2027)),
    "GRSupra": list(range(2020, 2027)), "Crown": list(range(2023, 2027)),
    "RAV4": list(range(2018, 2027)), "RAV4Prime": list(range(2021, 2027)),
    "Highlander": list(range(2018, 2027)), "HighlanderHybrid": list(range(2018, 2027)),
    "GrandHighlander": list(range(2024, 2027)), "4Runner": list(range(2018, 2027)),
    "Sequoia": list(range(2018, 2027)), "Venza": list(range(2021, 2027)),
    "CHR": list(range(2018, 2023)), "CorollaCross": list(range(2022, 2027)),
    "bZ4X": list(range(2023, 2027)), "LandCruiser": list(range(2018, 2022)) + list(range(2024, 2027)),
    "Tacoma": list(range(2018, 2027)), "Tundra": list(range(2018, 2027)), "Sienna": list(range(2018, 2027)),
}

TOYOTA_PDF_BASE = "https://www.toyota.com/content/dam/toyota/brochures/pdf"
TOYOTA_ASSETS_BASE = "https://assets.sia.toyota.com/publications/en/omms-s"
FUELECONOMY_API_BASE = "https://www.fueleconomy.gov/ws/rest"


@dataclass
class ScraperConfig:
    years: List[int]
    models: List[str]
    rate_limit: float = 1.0
    timeout: int = 30
    max_retries: int = 3
    output_dir: str = "output"
    offline: bool = False
    source: List[str] = field(default_factory=list)

    def validate(self) -> None:
        if not self.years:
            raise ValueError("years cannot be empty")
        if not self.models:
            raise ValueError("models cannot be empty")
        if self.rate_limit <= 0:
            raise ValueError("rate_limit must be > 0")
        if self.timeout <= 0:
            raise ValueError("timeout must be > 0")
        if self.max_retries < 1:
            raise ValueError("max_retries must be >= 1")
        invalid_models = [m for m in self.models if m not in TOYOTA_MODELS]
        if invalid_models:
            raise ValueError(f"Unknown model(s): {invalid_models}")
        out_of_scope_years = [y for y in self.years if y not in YEARS]
        if out_of_scope_years:
            raise ValueError(f"Unsupported year(s): {out_of_scope_years}. Supported range: {YEARS[0]}-{YEARS[-1]}")

    @classmethod
    def default(cls) -> "ScraperConfig":
        return cls(years=YEARS, models=list(TOYOTA_MODELS.keys()))

    @classmethod
    def smoke_test(cls) -> "ScraperConfig":
        return cls(years=[2023, 2024], models=["Camry", "RAV4", "Tacoma"])

    @classmethod
    def from_file(cls, path: str) -> "ScraperConfig":
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        if p.suffix.lower() == ".json":
            data: Dict[str, Any] = json.loads(p.read_text())
        elif p.suffix.lower() in {".toml", ".tml"}:
            if tomllib is None:
                raise RuntimeError("TOML config requires Python 3.11+ tomllib")
            data = tomllib.loads(p.read_text())
        else:
            raise ValueError("Config file must be .json or .toml")
        if "scraper" in data and isinstance(data["scraper"], dict):
            data = data["scraper"]
        cfg = cls(
            years=data.get("years", YEARS),
            models=data.get("models", list(TOYOTA_MODELS.keys())),
            rate_limit=float(data.get("rate_limit", 1.0)),
            timeout=int(data.get("timeout", 30)),
            max_retries=int(data.get("max_retries", 3)),
            output_dir=str(data.get("output_dir", "output")),
            offline=bool(data.get("offline", False)),
            source=list(data.get("source", [])),
        )
        cfg.validate()
        return cfg


def get_model_years(model: str) -> List[int]:
    return MODEL_YEAR_AVAILABILITY.get(model, YEARS)


def get_toyota_pdf_url(model: str, year: int) -> str:
    yy = str(year)[2:]
    return f"{TOYOTA_PDF_BASE}/{year}/T-MMS-{yy}{model}.pdf"


def get_toyota_assets_pdf_url(model: str, year: int) -> str:
    yy = str(year)[2:]
    doc_id = f"T-MMS-{yy}{model}"
    return f"{TOYOTA_ASSETS_BASE}/{doc_id}/pdf/{doc_id}.pdf"
