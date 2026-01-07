"""
Parser for Toyota Owner's Manual PDFs.

Owner's manuals contain detailed maintenance tables with specific part numbers,
fluid capacities, and service specifications not found in the basic maintenance guide.
"""
import re
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class FluidSpec:
    """Fluid specification."""
    name: str
    type: str
    capacity: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class ServiceSpec:
    """Service specification from owner's manual."""
    source: str
    model: str
    year: int
    
    # Fluid capacities
    engine_oil_capacity: Optional[str] = None
    engine_oil_type: Optional[str] = None
    coolant_capacity: Optional[str] = None
    coolant_type: Optional[str] = None
    transmission_fluid: Optional[str] = None
    brake_fluid: Optional[str] = None
    
    # Tire specs
    tire_pressure_front: Optional[str] = None
    tire_pressure_rear: Optional[str] = None
    tire_size: Optional[str] = None
    
    # Battery
    battery_type: Optional[str] = None
    
    # Other fluids
    fluids: List[FluidSpec] = None
    
    # Metadata
    source_url: str = ""
    scraped_at: str = ""
    
    def __post_init__(self):
        if self.fluids is None:
            self.fluids = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        d["fluids"] = [asdict(f) for f in self.fluids]
        return d


class OwnersManualParser:
    """
    Parser for Toyota Owner's Manual PDFs.
    
    Owner's manuals follow a consistent structure with:
    - Maintenance data section
    - Fluid capacities table
    - Tire pressure specifications
    - Part numbers for filters, fluids, etc.
    """
    
    # Standard Toyota fluid specifications by era
    FLUID_SPECS = {
        # 2018-2025 typical specs
        "default": {
            "engine_oil_type": "0W-20 synthetic",
            "coolant_type": "Toyota Super Long Life Coolant",
            "transmission_fluid": "Toyota ATF WS",
            "brake_fluid": "DOT 3",
        },
        # 4-cylinder engines
        "4cyl": {
            "engine_oil_capacity": "4.8 quarts with filter",
        },
        # V6 engines
        "v6": {
            "engine_oil_capacity": "6.4 quarts with filter",
        },
        # Trucks
        "truck": {
            "engine_oil_capacity": "7.5-8.5 quarts with filter",
        },
    }
    
    # Oil type patterns
    OIL_PATTERNS = {
        r"0W-?20": "0W-20",
        r"0W-?16": "0W-16",
        r"5W-?30": "5W-30",
    }
    
    def __init__(self):
        self.source = "owners-manual"
    
    def parse_manual_text(self, text: str, model: str, year: int, url: str) -> ServiceSpec:
        """
        Parse extracted owner's manual text.
        
        Args:
            text: Raw text extracted from PDF
            model: Vehicle model name
            year: Model year
            url: Source URL
            
        Returns:
            ServiceSpec object
        """
        spec = ServiceSpec(
            source=self.source,
            model=model,
            year=year,
            source_url=url,
            scraped_at=datetime.utcnow().isoformat() + "Z",
        )
        
        # Extract oil capacity
        oil_cap_match = re.search(
            r"engine oil.*?(?:with filter|w/filter).*?(\d+\.?\d*)\s*(?:qt|quart|L|liter)",
            text, re.IGNORECASE | re.DOTALL
        )
        if oil_cap_match:
            spec.engine_oil_capacity = f"{oil_cap_match.group(1)} quarts with filter"
        
        # Extract oil type
        for pattern, oil_type in self.OIL_PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE):
                spec.engine_oil_type = oil_type
                break
        
        # Extract coolant capacity
        coolant_match = re.search(
            r"coolant.*?capacity.*?(\d+\.?\d*)\s*(?:qt|quart|L|liter)",
            text, re.IGNORECASE | re.DOTALL
        )
        if coolant_match:
            spec.coolant_capacity = f"{coolant_match.group(1)} quarts"
        
        # Extract tire pressure
        tire_pressure_match = re.search(
            r"tire.*?pressure.*?(\d{2})\s*psi.*?front.*?(\d{2})\s*psi.*?rear",
            text, re.IGNORECASE | re.DOTALL
        )
        if tire_pressure_match:
            spec.tire_pressure_front = f"{tire_pressure_match.group(1)} psi"
            spec.tire_pressure_rear = f"{tire_pressure_match.group(2)} psi"
        
        # Extract tire size
        tire_size_match = re.search(
            r"tire size.*?(P?\d{3}/\d{2}R\d{2})",
            text, re.IGNORECASE
        )
        if tire_size_match:
            spec.tire_size = tire_size_match.group(1)
        
        return spec
    
    def get_standard_specs(self, model: str, year: int, url: str = "") -> ServiceSpec:
        """
        Generate standard specs based on model type.
        
        Used when PDF parsing fails - returns typical specs for the model category.
        """
        # Determine vehicle category
        trucks = ["Tacoma", "Tundra"]
        v6_models = ["Highlander", "4Runner", "Sequoia", "Sienna", "Avalon", "GR Supra"]
        hybrids = ["Prius", "PriusPrime", "RAV4Prime", "bZ4X", "Mirai"]
        
        spec = ServiceSpec(
            source="owners-manual-standard",
            model=model,
            year=year,
            source_url=url,
            scraped_at=datetime.utcnow().isoformat() + "Z",
        )
        
        # Set fluid specs based on category
        defaults = self.FLUID_SPECS["default"]
        spec.engine_oil_type = defaults["engine_oil_type"]
        spec.coolant_type = defaults["coolant_type"]
        spec.transmission_fluid = defaults["transmission_fluid"]
        spec.brake_fluid = defaults["brake_fluid"]
        
        if model in trucks:
            spec.engine_oil_capacity = self.FLUID_SPECS["truck"]["engine_oil_capacity"]
        elif model in v6_models:
            spec.engine_oil_capacity = self.FLUID_SPECS["v6"]["engine_oil_capacity"]
        else:
            spec.engine_oil_capacity = self.FLUID_SPECS["4cyl"]["engine_oil_capacity"]
        
        # Hybrids may use different oil
        if model in hybrids:
            spec.engine_oil_type = "0W-16 synthetic"
        
        # Add fluid details
        spec.fluids = [
            FluidSpec(name="Engine Oil", type=spec.engine_oil_type, capacity=spec.engine_oil_capacity),
            FluidSpec(name="Coolant", type=spec.coolant_type),
            FluidSpec(name="Automatic Transmission", type=spec.transmission_fluid),
            FluidSpec(name="Brake Fluid", type=spec.brake_fluid),
        ]
        
        return spec
    
    def get_owners_manual_url(self, model: str, year: int) -> str:
        """
        Generate owner's manual PDF URL.
        
        Note: Toyota's owner's manuals are behind authentication and not directly
        scrapeable. This returns the general link structure.
        """
        # Toyota's manuals are accessed via:
        # https://www.toyota.com/owners/warranty-owners-manuals
        # But require VIN or model selection through their UI
        return f"https://www.toyota.com/owners/warranty-owners-manuals/{year}-{model.lower()}"
