"""
Parser for Toyota Warranty & Maintenance Guide PDFs.

Extracts structured maintenance schedule data from PDF text.
"""
import re
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict

import pdfplumber

logger = logging.getLogger(__name__)


@dataclass
class MaintenanceItem:
    """Single maintenance item."""
    service: str
    category: str = "standard"  # standard, special_condition, inspection
    condition: Optional[str] = None  # e.g., "dusty_roads", "towing"


@dataclass 
class MaintenanceInterval:
    """Maintenance schedule for a specific mileage interval."""
    interval_miles: int
    interval_months: int
    items: list[MaintenanceItem] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "interval_miles": self.interval_miles,
            "interval_months": self.interval_months,
            "items": [asdict(item) for item in self.items],
        }


@dataclass
class MaintenanceSchedule:
    """Complete maintenance schedule for a vehicle."""
    make: str
    model: str
    year: int
    intervals: list[MaintenanceInterval] = field(default_factory=list)
    source_pdf: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "make": self.make,
            "model": self.model,
            "year": self.year,
            "maintenance_schedule": [i.to_dict() for i in self.intervals],
            "source_pdf": self.source_pdf,
        }


class MaintenancePDFParser:
    """
    Parser for Toyota Warranty & Maintenance Guide PDFs.
    
    These PDFs follow a consistent structure:
    - Maintenance schedules start around page 38-40
    - Each interval has a header like "5,000 miles or 6 months"
    - Items are listed with checkboxes (■)
    - Special operating conditions are in subsections
    """
    
    # Common mileage intervals (miles, months)
    INTERVALS = [
        (5000, 6), (10000, 12), (15000, 18), (20000, 24), (25000, 30),
        (30000, 36), (35000, 42), (40000, 48), (45000, 54), (50000, 60),
        (55000, 66), (60000, 72), (65000, 78), (70000, 84), (75000, 90),
        (80000, 96), (85000, 102), (90000, 108), (95000, 114), (100000, 120),
        (105000, 126), (110000, 132), (115000, 138), (120000, 144),
    ]
    
    # Patterns for identifying sections
    INTERVAL_PATTERN = re.compile(
        r'(\d{1,3},?\d{3})\s*miles?\s*(?:or)?\s*(\d+)\s*months?',
        re.IGNORECASE
    )
    
    # Item patterns
    ITEM_PATTERNS = [
        # Checkbox items
        (re.compile(r'■\s*(.+?)(?:\n|$)'), "standard"),
        # Inspection items
        (re.compile(r'_\s*(.+?)(?:\n|$)'), "inspection"),
    ]
    
    # Special operating condition keywords
    SPECIAL_CONDITIONS = {
        "dusty": "dusty_roads",
        "dirt road": "dusty_roads", 
        "towing": "towing",
        "car-top carrier": "towing",
        "heavy vehicle loading": "heavy_loading",
        "trips of less than five miles": "short_trips_cold",
        "temperatures below 32": "short_trips_cold",
        "extensive idling": "extensive_idling",
        "low speed driving": "extensive_idling",
        "police": "fleet_use",
        "taxi": "fleet_use",
        "door-to-door delivery": "fleet_use",
    }
    
    def __init__(self):
        self.current_condition: Optional[str] = None
    
    def parse(self, pdf_path: Path, model: str, year: int) -> MaintenanceSchedule:
        """
        Parse a maintenance PDF and extract schedule data.
        
        Args:
            pdf_path: Path to the PDF file
            model: Vehicle model name
            year: Model year
            
        Returns:
            MaintenanceSchedule with extracted data
        """
        schedule = MaintenanceSchedule(
            make="Toyota",
            model=model,
            year=year,
            source_pdf=str(pdf_path),
        )
        
        try:
            text = self._extract_text(pdf_path)
            schedule.intervals = self._parse_intervals(text)
        except Exception as e:
            logger.error(f"Failed to parse {pdf_path}: {e}")
        
        return schedule
    
    def _extract_text(self, pdf_path: Path) -> str:
        """Extract all text from PDF."""
        text_parts = []
        
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        
        return "\n".join(text_parts)
    
    def _parse_intervals(self, text: str) -> list[MaintenanceInterval]:
        """Parse maintenance intervals from PDF text."""
        intervals = []
        
        # Split text by interval headers
        sections = self._split_by_intervals(text)
        
        for (miles, months), section_text in sections.items():
            interval = MaintenanceInterval(
                interval_miles=miles,
                interval_months=months,
            )
            
            # Parse items from section
            interval.items = self._parse_items(section_text)
            
            if interval.items:
                intervals.append(interval)
        
        return sorted(intervals, key=lambda x: x.interval_miles)
    
    def _split_by_intervals(self, text: str) -> dict[tuple[int, int], str]:
        """Split text into sections by mileage interval."""
        sections = {}
        
        # Find all interval headers and their positions
        matches = list(self.INTERVAL_PATTERN.finditer(text))
        
        for i, match in enumerate(matches):
            miles_str = match.group(1).replace(",", "")
            months_str = match.group(2)
            
            try:
                miles = int(miles_str)
                months = int(months_str)
            except ValueError:
                continue
            
            # Get text until next interval or end
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            
            section_text = text[start:end]
            sections[(miles, months)] = section_text
        
        return sections
    
    def _parse_items(self, section_text: str) -> list[MaintenanceItem]:
        """Parse maintenance items from a section."""
        items = []
        self.current_condition = None
        
        # Check for special operating conditions section
        if "Special Operating Conditions" in section_text:
            parts = section_text.split("Special Operating Conditions", 1)
            
            # Parse standard items first
            items.extend(self._extract_items(parts[0], "standard"))
            
            # Parse special condition items
            if len(parts) > 1:
                items.extend(self._parse_special_conditions(parts[1]))
        else:
            items.extend(self._extract_items(section_text, "standard"))
        
        return items
    
    def _extract_items(
        self, 
        text: str, 
        default_category: str,
        condition: Optional[str] = None,
    ) -> list[MaintenanceItem]:
        """Extract maintenance items from text."""
        items = []
        
        # Match checkbox items
        checkbox_pattern = re.compile(r'■\s*([^\n■]+)')
        for match in checkbox_pattern.finditer(text):
            service = self._clean_service_text(match.group(1))
            if service and len(service) > 3:  # Skip noise
                items.append(MaintenanceItem(
                    service=service,
                    category=default_category if not condition else "special_condition",
                    condition=condition,
                ))
        
        # Match inspection items (underscored)
        inspection_pattern = re.compile(r'_\s*([^\n_]+?)(?=\s*_|\n|$)')
        for match in inspection_pattern.finditer(text):
            service = self._clean_service_text(match.group(1))
            if service and len(service) > 3:
                items.append(MaintenanceItem(
                    service=service,
                    category="inspection",
                    condition=condition,
                ))
        
        return items
    
    def _parse_special_conditions(self, text: str) -> list[MaintenanceItem]:
        """Parse special operating condition items."""
        items = []
        
        # Split by condition headers
        lines = text.split('\n')
        current_condition = None
        current_block = []
        
        for line in lines:
            # Check if this line indicates a condition
            line_lower = line.lower()
            new_condition = None
            
            for keyword, condition in self.SPECIAL_CONDITIONS.items():
                if keyword in line_lower:
                    new_condition = condition
                    break
            
            if new_condition and new_condition != current_condition:
                # Process previous block
                if current_block and current_condition:
                    block_text = '\n'.join(current_block)
                    items.extend(self._extract_items(
                        block_text, 
                        "special_condition", 
                        current_condition
                    ))
                
                current_condition = new_condition
                current_block = [line]
            else:
                current_block.append(line)
        
        # Process final block
        if current_block and current_condition:
            block_text = '\n'.join(current_block)
            items.extend(self._extract_items(
                block_text, 
                "special_condition", 
                current_condition
            ))
        
        return items
    
    def _clean_service_text(self, text: str) -> str:
        """Clean up service item text."""
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # Remove common noise
        noise_patterns = [
            r'^\d+\s*',  # Leading numbers
            r'\(.*?\)',  # Parenthetical notes (keep for now, might be useful)
            r'Dealer Service Verification.*',  # Footer noise
            r'Date:.*',
            r'Mileage:.*',
        ]
        
        for pattern in noise_patterns[:-3]:  # Keep first few
            text = re.sub(pattern, '', text)
        
        return text.strip()


def parse_maintenance_pdf(pdf_path: Path, model: str, year: int) -> MaintenanceSchedule:
    """
    Convenience function to parse a maintenance PDF.
    
    Args:
        pdf_path: Path to PDF file
        model: Vehicle model
        year: Model year
        
    Returns:
        Parsed MaintenanceSchedule
    """
    parser = MaintenancePDFParser()
    return parser.parse(pdf_path, model, year)
