"""
FuelEconomy.gov API client.

Uses the official public REST API to fetch vehicle specifications.
API docs: https://www.fueleconomy.gov/feg/ws/

Note: This API provides vehicle specs (engine, MPG, drivetrain) but NOT maintenance schedules.
"""
import logging
from typing import Optional
from xml.etree import ElementTree

from .base import BaseScraper
from config import settings, FUELECONOMY_MODEL_MAP

logger = logging.getLogger(__name__)


class FuelEconomyScraper(BaseScraper):
    """Client for FuelEconomy.gov REST API."""
    
    def __init__(self):
        super().__init__(rate_limit=settings.FUELECONOMY_RATE_LIMIT)
        self.base_url = settings.FUELECONOMY_BASE_URL
    
    def _parse_xml(self, xml_text: str) -> ElementTree.Element:
        """Parse XML response."""
        return ElementTree.fromstring(xml_text)
    
    def get_years(self) -> list[int]:
        """Get all available model years."""
        url = f"{self.base_url}/vehicle/menu/year"
        response = self._fetch(url)
        root = self._parse_xml(response.text)
        
        years = []
        for item in root.findall(".//menuItem"):
            value = item.find("value")
            if value is not None and value.text:
                years.append(int(value.text))
        
        return sorted(years, reverse=True)
    
    def get_makes(self, year: int) -> list[str]:
        """Get all makes for a given year."""
        url = f"{self.base_url}/vehicle/menu/make?year={year}"
        response = self._fetch(url)
        root = self._parse_xml(response.text)
        
        makes = []
        for item in root.findall(".//menuItem"):
            value = item.find("value")
            if value is not None and value.text:
                makes.append(value.text)
        
        return makes
    
    def get_models(self, year: int, make: str = "Toyota") -> list[str]:
        """Get all models for a given year and make."""
        url = f"{self.base_url}/vehicle/menu/model?year={year}&make={make}"
        response = self._fetch(url)
        root = self._parse_xml(response.text)
        
        models = []
        for item in root.findall(".//menuItem"):
            value = item.find("value")
            if value is not None and value.text:
                models.append(value.text)
        
        return models
    
    def get_options(self, year: int, make: str, model: str) -> list[dict]:
        """Get vehicle options/variants for a specific year/make/model."""
        url = f"{self.base_url}/vehicle/menu/options?year={year}&make={make}&model={model}"
        response = self._fetch(url)
        root = self._parse_xml(response.text)
        
        options = []
        for item in root.findall(".//menuItem"):
            text = item.find("text")
            value = item.find("value")
            if text is not None and value is not None:
                options.append({
                    "description": text.text,
                    "vehicle_id": value.text,
                })
        
        return options
    
    def get_vehicle(self, vehicle_id: str) -> dict:
        """Get detailed vehicle data by ID."""
        url = f"{self.base_url}/vehicle/{vehicle_id}"
        response = self._fetch(url)
        root = self._parse_xml(response.text)
        
        def get_text(element: ElementTree.Element, tag: str) -> Optional[str]:
            el = element.find(tag)
            return el.text if el is not None else None
        
        def get_float(element: ElementTree.Element, tag: str) -> Optional[float]:
            text = get_text(element, tag)
            if text:
                try:
                    return float(text)
                except ValueError:
                    return None
            return None
        
        def get_int(element: ElementTree.Element, tag: str) -> Optional[int]:
            text = get_text(element, tag)
            if text:
                try:
                    return int(text)
                except ValueError:
                    return None
            return None
        
        return {
            "vehicle_id": vehicle_id,
            "year": get_int(root, "year"),
            "make": get_text(root, "make"),
            "model": get_text(root, "model"),
            "engine_displacement": get_float(root, "displ"),
            "cylinders": get_int(root, "cylinders"),
            "transmission": get_text(root, "trany"),
            "drive": get_text(root, "drive"),
            "fuel_type": get_text(root, "fuelType"),
            "fuel_type_1": get_text(root, "fuelType1"),
            "mpg_city": get_int(root, "city08"),
            "mpg_highway": get_int(root, "highway08"),
            "mpg_combined": get_int(root, "comb08"),
            "annual_fuel_cost": get_int(root, "fuelCost08"),
            "vehicle_class": get_text(root, "VClass"),
            "atv_type": get_text(root, "atvType"),  # Alternative fuel type
            "ev_motor": get_text(root, "evMotor"),
            "phev_blended": get_text(root, "phevBlended") == "true",
            "range_city": get_float(root, "rangeCity"),
            "range_highway": get_float(root, "rangeHwy"),
        }
    
    def scrape(self, model: str, year: int, make: str = "Toyota") -> list[dict]:
        """
        Scrape all vehicle variants for a model/year.
        
        Returns list of vehicle specification dicts.
        """
        # Map our model name to FuelEconomy.gov's naming
        fe_model = FUELECONOMY_MODEL_MAP.get(model, model)
        
        logger.info(f"Fetching specs for {year} {make} {fe_model}")
        
        try:
            options = self.get_options(year, make, fe_model)
        except Exception as e:
            logger.warning(f"No options found for {year} {make} {fe_model}: {e}")
            return []
        
        vehicles = []
        for option in options:
            try:
                vehicle = self.get_vehicle(option["vehicle_id"])
                vehicle["option_description"] = option["description"]
                vehicles.append(vehicle)
            except Exception as e:
                logger.warning(f"Failed to get vehicle {option['vehicle_id']}: {e}")
        
        return vehicles
    
    def scrape_all_toyota(self, start_year: int = 2018, end_year: int = 2025) -> list[dict]:
        """Scrape all Toyota vehicles for a year range."""
        all_vehicles = []
        
        for year in range(start_year, end_year + 1):
            logger.info(f"Fetching Toyota models for {year}")
            
            try:
                models = self.get_models(year, "Toyota")
            except Exception as e:
                logger.warning(f"Failed to get models for {year}: {e}")
                continue
            
            for model in models:
                vehicles = self.scrape(model, year)
                all_vehicles.extend(vehicles)
        
        return all_vehicles
