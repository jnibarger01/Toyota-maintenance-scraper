"""
Parser for Toyota Warranty & Maintenance Guide PDFs.

Extracts structured maintenance schedule data from Toyota's official PDFs.
"""
import re
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class MaintenanceItem:
    """Single maintenance item."""
    name: str
    required: bool = True
    special_conditions: Optional[str] = None


@dataclass
class MaintenanceInterval:
    """Maintenance schedule at a specific mileage interval."""
    mileage: int
    months: int
    items: List[MaintenanceItem]
    special_operating_items: List[MaintenanceItem]


@dataclass
class MaintenanceSchedule:
    """Complete maintenance schedule for a vehicle."""
    source: str
    model: str
    year: int
    intervals: List[MaintenanceInterval]
    source_url: str
    scraped_at: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "source": self.source,
            "model": self.model,
            "year": self.year,
            "intervals": [
                {
                    "mileage": interval.mileage,
                    "months": interval.months,
                    "items": [asdict(item) for item in interval.items],
                    "special_operating_items": [asdict(item) for item in interval.special_operating_items],
                }
                for interval in self.intervals
            ],
            "source_url": self.source_url,
            "scraped_at": self.scraped_at,
        }


class ToyotaPDFParser:
    """
    Parser for Toyota Warranty & Maintenance Guide PDFs.
    
    Toyota PDFs follow a consistent structure:
    - Maintenance intervals at 5,000 mile increments
    - Standard items and special operating condition items
    - Items marked with ■ (checkbox) indicators
    """
    
    # Standard mileage intervals
    MILEAGE_INTERVALS = [
        (5000, 6), (10000, 12), (15000, 18), (20000, 24), (25000, 30),
        (30000, 36), (35000, 42), (40000, 48), (45000, 54), (50000, 60),
        (55000, 66), (60000, 72), (65000, 78), (70000, 84), (75000, 90),
        (80000, 96), (85000, 102), (90000, 108), (95000, 114), (100000, 120),
        (105000, 126), (110000, 132), (115000, 138), (120000, 144),
    ]
    
    # Regex patterns for parsing
    INTERVAL_PATTERN = re.compile(
        r"(\d{1,3},?\d{3})\s*miles\s*(?:or\s*)?(\d+)\s*months",
        re.IGNORECASE
    )
    
    MAINTENANCE_ITEM_PATTERN = re.compile(
        r"[■□]\s*(.+?)(?=\n[■□]|\nAdditional|\nDealer|\Z)",
        re.DOTALL
    )
    
    SPECIAL_CONDITIONS_HEADER = re.compile(
        r"Additional Maintenance Items for\s*Special Operating Conditions",
        re.IGNORECASE
    )
    
    CONDITION_PATTERNS = {
        "dust": re.compile(r"Driving on dirt roads or dusty roads", re.IGNORECASE),
        "towing": re.compile(r"Driving while towing", re.IGNORECASE),
        "cold": re.compile(r"Repeated trips.*below 32°F", re.IGNORECASE),
        "idling": re.compile(r"Extensive idling", re.IGNORECASE),
    }
    
    def __init__(self):
        self.source = "toyota-pdf"
    
    def parse_pdf_text(self, text: str, model: str, year: int, url: str) -> MaintenanceSchedule:
        """
        Parse extracted PDF text into structured maintenance schedule.
        
        Args:
            text: Raw text extracted from PDF
            model: Vehicle model name
            year: Model year
            url: Source URL
            
        Returns:
            MaintenanceSchedule object
        """
        intervals = []
        
        # Split by mileage intervals
        sections = self._split_by_intervals(text)
        
        for mileage, months, section_text in sections:
            items, special_items = self._parse_section(section_text)
            
            interval = MaintenanceInterval(
                mileage=mileage,
                months=months,
                items=items,
                special_operating_items=special_items,
            )
            intervals.append(interval)
        
        return MaintenanceSchedule(
            source=self.source,
            model=model,
            year=year,
            intervals=intervals,
            source_url=url,
            scraped_at=datetime.utcnow().isoformat() + "Z",
        )
    
    def _split_by_intervals(self, text: str) -> List[tuple]:
        """Split text into sections by mileage interval."""
        sections = []
        
        # Find all interval headers
        for mileage, months in self.MILEAGE_INTERVALS:
            # Look for patterns like "5,000 miles or 6 months"
            pattern = re.compile(
                rf"{mileage:,}".replace(",", ",?") + r"\s*miles\s*(?:or\s*)?(\d+)\s*months",
                re.IGNORECASE
            )
            
            match = pattern.search(text)
            if match:
                # Find the section text (until next interval or end)
                start = match.end()
                
                # Find next interval
                next_interval = None
                for next_mileage, _ in self.MILEAGE_INTERVALS:
                    if next_mileage > mileage:
                        next_pattern = re.compile(
                            rf"{next_mileage:,}".replace(",", ",?") + r"\s*miles",
                            re.IGNORECASE
                        )
                        next_match = next_pattern.search(text, start)
                        if next_match:
                            next_interval = next_match.start()
                            break
                
                end = next_interval if next_interval else len(text)
                section_text = text[start:end]
                sections.append((mileage, months, section_text))
        
        return sections
    
    def _parse_section(self, text: str) -> tuple:
        """Parse a maintenance interval section."""
        items = []
        special_items = []
        
        # Split into standard and special operating conditions
        special_match = self.SPECIAL_CONDITIONS_HEADER.search(text)
        
        if special_match:
            standard_text = text[:special_match.start()]
            special_text = text[special_match.end():]
        else:
            standard_text = text
            special_text = ""
        
        # Parse standard items
        items = self._extract_items(standard_text)
        
        # Parse special condition items
        if special_text:
            special_items = self._extract_items(special_text, is_special=True)
        
        return items, special_items
    
    def _extract_items(self, text: str, is_special: bool = False) -> List[MaintenanceItem]:
        """Extract maintenance items from text."""
        items = []
        
        # Common maintenance items to look for
        item_patterns = [
            (r"Replace engine oil and oil filter", "Replace engine oil and oil filter"),
            (r"Replace cabin air filter", "Replace cabin air filter"),
            (r"Replace engine air filter", "Replace engine air filter"),
            (r"Rotate tires", "Rotate tires"),
            (r"Inspect.*brake.*(?:lining|pad|disc)", "Inspect brake system"),
            (r"Inspect.*fluid levels", "Inspect and adjust all fluid levels"),
            (r"Inspect.*wiper blades", "Inspect wiper blades"),
            (r"Inspect.*drive shaft boots", "Inspect drive shaft boots"),
            (r"Inspect.*ball joints", "Inspect ball joints and dust covers"),
            (r"Inspect.*steering linkage", "Inspect steering linkage and boots"),
            (r"Replace spark plugs", "Replace spark plugs"),
            (r"Replace engine coolant", "Replace engine coolant"),
            (r"Inspect.*exhaust", "Inspect exhaust pipes and mountings"),
            (r"Inspect.*fuel.*(?:lines|tank)", "Inspect fuel system"),
            (r"Replace.*(?:differential|transfer case) oil", "Replace differential/transfer case oil"),
            (r"Re-?torque propeller shaft", "Re-torque propeller shaft bolt"),
            (r"Tighten nuts and bolts", "Tighten nuts and bolts on chassis and body"),
            (r"Add.*EFI Tank Additive", "Add Toyota EFI Tank Additive"),
            (r"Check.*driver.*floor mat", "Check installation of driver's floor mat"),
        ]
        
        for pattern, name in item_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                condition = None
                if is_special:
                    # Try to identify the condition
                    for cond_name, cond_pattern in self.CONDITION_PATTERNS.items():
                        if cond_pattern.search(text):
                            condition = cond_name
                            break
                
                items.append(MaintenanceItem(
                    name=name,
                    required=True,
                    special_conditions=condition,
                ))
        
        return items
    
    def get_standard_schedule(self, model: str, year: int, url: str = "") -> MaintenanceSchedule:
        """
        Generate standard Toyota maintenance schedule.
        
        Used when PDF parsing fails - returns Toyota's standard 5k/10k schedule.
        """
        intervals = []
        
        for mileage, months in self.MILEAGE_INTERVALS:
            # Standard items at every interval
            items = [
                MaintenanceItem(name="Rotate tires"),
                MaintenanceItem(name="Inspect wiper blades"),
                MaintenanceItem(name="Inspect and adjust all fluid levels"),
                MaintenanceItem(name="Visually inspect brake system"),
                MaintenanceItem(name="Check installation of driver's floor mat"),
            ]
            
            # 10k intervals: oil change + cabin filter
            if mileage % 10000 == 0:
                items.insert(0, MaintenanceItem(name="Replace engine oil and oil filter"))
                items.append(MaintenanceItem(name="Replace cabin air filter"))
            
            # 30k intervals: additional inspections
            if mileage % 30000 == 0:
                items.extend([
                    MaintenanceItem(name="Replace engine air filter"),
                    MaintenanceItem(name="Inspect drive shaft boots"),
                    MaintenanceItem(name="Inspect ball joints and dust covers"),
                    MaintenanceItem(name="Inspect fuel system"),
                ])
            
            # 60k intervals: major service
            if mileage % 60000 == 0:
                items.extend([
                    MaintenanceItem(name="Inspect drive belts"),
                    MaintenanceItem(name="Replace spark plugs (V6 only)"),
                ])
            
            # 100k: coolant
            if mileage == 100000:
                items.append(MaintenanceItem(name="Replace engine coolant"))
            
            # 120k: spark plugs for 4-cyl
            if mileage == 120000:
                items.append(MaintenanceItem(name="Replace spark plugs"))
            
            intervals.append(MaintenanceInterval(
                mileage=mileage,
                months=months,
                items=items,
                special_operating_items=[],
            ))
        
        return MaintenanceSchedule(
            source="toyota-standard",
            model=model,
            year=year,
            intervals=intervals,
            source_url=url,
            scraped_at=datetime.utcnow().isoformat() + "Z",
        )
