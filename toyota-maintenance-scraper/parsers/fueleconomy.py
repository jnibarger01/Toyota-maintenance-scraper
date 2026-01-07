"""
Parser for FuelEconomy.gov API.

Uses the official EPA REST API to fetch vehicle specifications and fuel economy data.
API docs: https://www.fueleconomy.gov/feg/ws/
"""
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

from fetcher import Fetcher, FetchResult
from config import FUELECONOMY_API_BASE

logger = logging.getLogger(__name__)


@dataclass
class VehicleSpec:
    """Vehicle specification from FuelEconomy.gov."""
    source: str
    make: str
    model: str
    year: int
    vehicle_id: int
    
    # Engine/drivetrain
    engine_displacement: Optional[float] = None
    cylinders: Optional[int] = None
    transmission: Optional[str] = None
    drive: Optional[str] = None
    fuel_type: Optional[str] = None
    
    # Fuel economy
    mpg_city: Optional[int] = None
    mpg_highway: Optional[int] = None
    mpg_combined: Optional[int] = None
    
    # Additional specs
    vehicle_class: Optional[str] = None
    annual_fuel_cost: Optional[int] = None
    co2_tailpipe: Optional[float] = None
    
    # Metadata
    scraped_at: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class FuelEconomyParser:
    """
    Parser for FuelEconomy.gov REST API.
    
    API endpoints used:
    - /ws/rest/vehicle/menu/year - List years
    - /ws/rest/vehicle/menu/make?year=YYYY - List makes for year
    - /ws/rest/vehicle/menu/model?year=YYYY&make=MMM - List models
    - /ws/rest/vehicle/menu/options?year=YYYY&make=MMM&model=NNN - List options/IDs
    - /ws/rest/vehicle/{id} - Get vehicle details
    """
    
    def __init__(self, fetcher: Fetcher):
        self.fetcher = fetcher
        self.source = "fueleconomy"
        self.base_url = FUELECONOMY_API_BASE
    
    def get_years(self) -> List[int]:
        """Get available years from API."""
        url = f"{self.base_url}/vehicle/menu/year"
        result = self.fetcher.fetch_json(url)
        
        if not result.success or not result.json_data:
            logger.error("Failed to fetch years")
            return []
        
        menu_items = result.json_data.get("menuItem", [])
        if isinstance(menu_items, dict):
            menu_items = [menu_items]
        
        return [int(item["value"]) for item in menu_items if "value" in item]
    
    def get_models_for_year(self, year: int, make: str = "Toyota") -> List[str]:
        """Get available models for a year and make."""
        url = f"{self.base_url}/vehicle/menu/model"
        result = self.fetcher.fetch_json(url, params={"year": year, "make": make})
        
        if not result.success or not result.json_data:
            logger.warning(f"Failed to fetch models for {year} {make}")
            return []
        
        menu_items = result.json_data.get("menuItem", [])
        if isinstance(menu_items, dict):
            menu_items = [menu_items]
        
        return [item["value"] for item in menu_items if "value" in item]
    
    def get_vehicle_options(self, year: int, make: str, model: str) -> List[Dict[str, Any]]:
        """Get vehicle options (trims) and their IDs."""
        url = f"{self.base_url}/vehicle/menu/options"
        result = self.fetcher.fetch_json(url, params={
            "year": year,
            "make": make,
            "model": model,
        })
        
        if not result.success or not result.json_data:
            logger.warning(f"Failed to fetch options for {year} {make} {model}")
            return []
        
        menu_items = result.json_data.get("menuItem", [])
        if isinstance(menu_items, dict):
            menu_items = [menu_items]
        
        return [
            {"text": item.get("text", ""), "value": int(item["value"])}
            for item in menu_items
            if "value" in item
        ]
    
    def get_vehicle_by_id(self, vehicle_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed vehicle info by ID."""
        url = f"{self.base_url}/vehicle/{vehicle_id}"
        result = self.fetcher.fetch_json(url)
        
        if not result.success or not result.json_data:
            logger.warning(f"Failed to fetch vehicle {vehicle_id}")
            return None
        
        return result.json_data
    
    def parse_vehicle(self, data: Dict[str, Any]) -> VehicleSpec:
        """Parse API response into VehicleSpec."""
        return VehicleSpec(
            source=self.source,
            make=data.get("make", "Toyota"),
            model=data.get("model", ""),
            year=int(data.get("year", 0)),
            vehicle_id=int(data.get("id", 0)),
            
            engine_displacement=self._safe_float(data.get("displ")),
            cylinders=self._safe_int(data.get("cylinders")),
            transmission=data.get("trany"),
            drive=data.get("drive"),
            fuel_type=data.get("fuelType1"),
            
            mpg_city=self._safe_int(data.get("city08")),
            mpg_highway=self._safe_int(data.get("highway08")),
            mpg_combined=self._safe_int(data.get("comb08")),
            
            vehicle_class=data.get("VClass"),
            annual_fuel_cost=self._safe_int(data.get("fuelCost08")),
            co2_tailpipe=self._safe_float(data.get("co2TailpipeGpm")),
            
            scraped_at=datetime.utcnow().isoformat() + "Z",
        )
    
    def fetch_all_toyota_vehicles(
        self,
        years: List[int],
        models: Optional[List[str]] = None,
    ) -> List[VehicleSpec]:
        """
        Fetch all Toyota vehicles for specified years.
        
        Args:
            years: List of years to fetch
            models: Optional list of specific models (None = all models)
            
        Returns:
            List of VehicleSpec objects
        """
        vehicles = []
        
        for year in years:
            logger.info(f"Fetching FuelEconomy data for {year}...")
            
            # Get models for this year
            available_models = self.get_models_for_year(year)
            
            # Filter to requested models if specified
            if models:
                available_models = [m for m in available_models if any(
                    req.lower() in m.lower() for req in models
                )]
            
            for model in available_models:
                logger.debug(f"  Fetching {year} Toyota {model}")
                
                # Get all options/trims for this model
                options = self.get_vehicle_options(year, "Toyota", model)
                
                for option in options:
                    vehicle_id = option["value"]
                    vehicle_data = self.get_vehicle_by_id(vehicle_id)
                    
                    if vehicle_data:
                        spec = self.parse_vehicle(vehicle_data)
                        vehicles.append(spec)
                        logger.debug(f"    Got: {spec.model} ({spec.transmission})")
        
        logger.info(f"Fetched {len(vehicles)} vehicle specs from FuelEconomy.gov")
        return vehicles
    
    @staticmethod
    def _safe_int(value: Any) -> Optional[int]:
        """Safely convert to int."""
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        """Safely convert to float."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
