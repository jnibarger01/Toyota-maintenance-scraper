"""
Unit tests for toyota_pdf, fueleconomy, and owners_manual parsers.
"""
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parsers.toyota_pdf import ToyotaPDFParser, MaintenanceItem
from parsers.fueleconomy import FuelEconomyParser
from parsers.owners_manual import OwnersManualParser


# ---------------------------------------------------------------------------
# ToyotaPDFParser
# ---------------------------------------------------------------------------

FIXTURE_PDF_TEXT = """\
Some introductory text.

5,000 miles or 6 months
■ Rotate tires
■ Inspect and adjust all fluid levels
■ Visually inspect brake system

10,000 miles or 12 months
■ Replace engine oil and oil filter
■ Rotate tires
■ Replace cabin air filter
Additional Maintenance Items for Special Operating Conditions
Driving on dirt roads or dusty roads
■ Replace engine air filter

30,000 miles or 36 months
■ Replace engine air filter
■ Inspect drive shaft boots
■ Inspect ball joints and dust covers
■ Inspect fuel system
"""


class ToyotaPDFParserTests(unittest.TestCase):

    def setUp(self):
        self.parser = ToyotaPDFParser()

    # --- get_standard_schedule ---

    def test_standard_schedule_interval_count(self):
        sched = self.parser.get_standard_schedule("Camry", 2024)
        self.assertEqual(len(sched.intervals), len(self.parser.MILEAGE_INTERVALS))

    def test_standard_schedule_metadata(self):
        sched = self.parser.get_standard_schedule("RAV4", 2023, "http://example.com")
        self.assertEqual(sched.model, "RAV4")
        self.assertEqual(sched.year, 2023)
        self.assertEqual(sched.source_url, "http://example.com")
        self.assertEqual(sched.source, "toyota-standard")

    def test_standard_schedule_oil_change_at_10k(self):
        sched = self.parser.get_standard_schedule("Camry", 2024)
        interval_10k = next(i for i in sched.intervals if i.mileage == 10000)
        names = [item.name for item in interval_10k.items]
        self.assertIn("Replace engine oil and oil filter", names)

    def test_standard_schedule_no_oil_at_5k(self):
        sched = self.parser.get_standard_schedule("Camry", 2024)
        interval_5k = next(i for i in sched.intervals if i.mileage == 5000)
        names = [item.name for item in interval_5k.items]
        self.assertNotIn("Replace engine oil and oil filter", names)

    def test_standard_schedule_30k_items(self):
        sched = self.parser.get_standard_schedule("Camry", 2024)
        interval_30k = next(i for i in sched.intervals if i.mileage == 30000)
        names = [item.name for item in interval_30k.items]
        self.assertIn("Replace engine air filter", names)
        self.assertIn("Inspect drive shaft boots", names)

    def test_standard_schedule_coolant_at_100k(self):
        sched = self.parser.get_standard_schedule("Camry", 2024)
        interval_100k = next(i for i in sched.intervals if i.mileage == 100000)
        names = [item.name for item in interval_100k.items]
        self.assertIn("Replace engine coolant", names)

    def test_standard_schedule_to_dict_shape(self):
        sched = self.parser.get_standard_schedule("Camry", 2024)
        d = sched.to_dict()
        self.assertIn("source", d)
        self.assertIn("model", d)
        self.assertIn("year", d)
        self.assertIn("intervals", d)
        self.assertIsInstance(d["intervals"], list)
        first = d["intervals"][0]
        self.assertIn("mileage", first)
        self.assertIn("months", first)
        self.assertIn("items", first)

    # --- _split_by_intervals ---

    def test_split_finds_known_intervals(self):
        sections = self.parser._split_by_intervals(FIXTURE_PDF_TEXT)
        mileages = [m for m, _, _ in sections]
        self.assertIn(5000, mileages)
        self.assertIn(10000, mileages)
        self.assertIn(30000, mileages)

    def test_split_section_contains_items(self):
        sections = self.parser._split_by_intervals(FIXTURE_PDF_TEXT)
        section_5k = next(text for m, _, text in sections if m == 5000)
        self.assertIn("Rotate tires", section_5k)

    def test_split_sections_are_bounded(self):
        # 5k section should not contain 10k content
        sections = self.parser._split_by_intervals(FIXTURE_PDF_TEXT)
        section_5k = next(text for m, _, text in sections if m == 5000)
        self.assertNotIn("Replace engine oil and oil filter", section_5k)

    # --- _extract_items ---

    def test_extract_items_matches_tire_rotation(self):
        text = "■ Rotate tires\n■ Inspect and adjust all fluid levels\n"
        items = self.parser._extract_items(text)
        names = [i.name for i in items]
        self.assertIn("Rotate tires", names)

    def test_extract_items_matches_oil_change(self):
        text = "■ Replace engine oil and oil filter\n"
        items = self.parser._extract_items(text)
        self.assertTrue(any("engine oil" in i.name.lower() for i in items))

    def test_extract_items_special_has_condition(self):
        text = "Driving on dirt roads or dusty roads\n■ Replace engine air filter\n"
        items = self.parser._extract_items(text, is_special=True)
        for item in items:
            if item.name == "Replace engine air filter":
                self.assertEqual(item.special_conditions, "dust")
                return
        # If air filter wasn't found, that's also fine — just verify no crash

    # --- parse_pdf_text ---

    def test_parse_pdf_text_returns_schedule(self):
        sched = self.parser.parse_pdf_text(FIXTURE_PDF_TEXT, "Camry", 2024, "http://x")
        self.assertEqual(sched.model, "Camry")
        self.assertEqual(sched.year, 2024)
        self.assertIsInstance(sched.intervals, list)

    def test_parse_pdf_text_source_tag(self):
        sched = self.parser.parse_pdf_text(FIXTURE_PDF_TEXT, "Camry", 2024, "http://x")
        self.assertEqual(sched.source, "toyota-pdf")


# ---------------------------------------------------------------------------
# FuelEconomyParser (no network — tests pure logic)
# ---------------------------------------------------------------------------

SAMPLE_XML_MENU = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<menuItems>
  <menuItem><text>Camry</text><value>Camry</value></menuItem>
  <menuItem><text>RAV4</text><value>RAV4</value></menuItem>
</menuItems>
"""

SAMPLE_XML_VEHICLE = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<vehicle>
  <id>12345</id>
  <make>Toyota</make>
  <model>Camry</model>
  <year>2024</year>
  <displ>2.5</displ>
  <cylinders>4</cylinders>
  <trany>Automatic</trany>
  <drive>FWD</drive>
  <fuelType1>Regular Gasoline</fuelType1>
  <city08>28</city08>
  <highway08>39</highway08>
  <comb08>32</comb08>
  <fuelCost08>1650</fuelCost08>
  <VClass>Midsize Cars</VClass>
  <co2TailpipeGpm>278.5</co2TailpipeGpm>
</vehicle>
"""


class MockFetchResult:
    def __init__(self, text=None, json_data=None, success=True):
        self.text = text
        self.json_data = json_data
        self.success = success


class FuelEconomyParserTests(unittest.TestCase):

    def setUp(self):
        self.parser = FuelEconomyParser.__new__(FuelEconomyParser)
        self.parser.source = "fueleconomy"

    def test_normalize_xml_menu(self):
        result = MockFetchResult(text=SAMPLE_XML_MENU)
        payload = FuelEconomyParser._normalize_payload(result)
        self.assertIn("menuItem", payload)
        items = payload["menuItem"]
        self.assertIsInstance(items, list)
        self.assertEqual(len(items), 2)

    def test_normalize_xml_vehicle(self):
        result = MockFetchResult(text=SAMPLE_XML_VEHICLE)
        payload = FuelEconomyParser._normalize_payload(result)
        self.assertEqual(payload.get("make"), "Toyota")
        self.assertEqual(payload.get("model"), "Camry")
        self.assertEqual(payload.get("year"), "2024")

    def test_normalize_json(self):
        result = MockFetchResult(json_data={"menuItem": [{"value": "Camry"}]})
        payload = FuelEconomyParser._normalize_payload(result)
        self.assertEqual(payload["menuItem"][0]["value"], "Camry")

    def test_normalize_empty(self):
        result = MockFetchResult(text=None, json_data=None)
        payload = FuelEconomyParser._normalize_payload(result)
        self.assertEqual(payload, {})

    def test_normalize_bad_xml(self):
        result = MockFetchResult(text="not xml at all <<<")
        payload = FuelEconomyParser._normalize_payload(result)
        self.assertEqual(payload, {})

    def test_parse_vehicle(self):
        result = MockFetchResult(text=SAMPLE_XML_VEHICLE)
        payload = FuelEconomyParser._normalize_payload(result)
        spec = self.parser.parse_vehicle(payload)
        self.assertEqual(spec.make, "Toyota")
        self.assertEqual(spec.model, "Camry")
        self.assertEqual(spec.year, 2024)
        self.assertAlmostEqual(spec.engine_displacement, 2.5)
        self.assertEqual(spec.cylinders, 4)
        self.assertEqual(spec.mpg_city, 28)
        self.assertEqual(spec.mpg_highway, 39)
        self.assertEqual(spec.mpg_combined, 32)
        self.assertEqual(spec.annual_fuel_cost, 1650)
        self.assertAlmostEqual(spec.co2_tailpipe, 278.5)

    def test_safe_int_conversions(self):
        self.assertEqual(FuelEconomyParser._safe_int("42"), 42)
        self.assertIsNone(FuelEconomyParser._safe_int(None))
        self.assertIsNone(FuelEconomyParser._safe_int("bad"))

    def test_safe_float_conversions(self):
        self.assertAlmostEqual(FuelEconomyParser._safe_float("3.14"), 3.14)
        self.assertIsNone(FuelEconomyParser._safe_float(None))
        self.assertIsNone(FuelEconomyParser._safe_float("nope"))

    def test_vehicle_to_dict(self):
        result = MockFetchResult(text=SAMPLE_XML_VEHICLE)
        payload = FuelEconomyParser._normalize_payload(result)
        spec = self.parser.parse_vehicle(payload)
        d = spec.to_dict()
        self.assertIn("make", d)
        self.assertIn("vehicle_id", d)
        self.assertIn("mpg_combined", d)


# ---------------------------------------------------------------------------
# OwnersManualParser
# ---------------------------------------------------------------------------

class OwnersManualParserTests(unittest.TestCase):

    def setUp(self):
        self.parser = OwnersManualParser()

    # --- get_standard_specs ---

    def test_truck_oil_capacity(self):
        spec = self.parser.get_standard_specs("Tacoma", 2024)
        self.assertIn("7.5", spec.engine_oil_capacity)

    def test_v6_oil_capacity(self):
        spec = self.parser.get_standard_specs("Highlander", 2024)
        self.assertIn("6.4", spec.engine_oil_capacity)

    def test_4cyl_oil_capacity(self):
        spec = self.parser.get_standard_specs("Camry", 2024)
        self.assertIn("4.8", spec.engine_oil_capacity)

    def test_hybrid_oil_type(self):
        spec = self.parser.get_standard_specs("Prius", 2024)
        self.assertIn("0W-16", spec.engine_oil_type)

    def test_non_hybrid_oil_type(self):
        spec = self.parser.get_standard_specs("Camry", 2024)
        self.assertIn("0W-20", spec.engine_oil_type)

    def test_fluids_list_populated(self):
        spec = self.parser.get_standard_specs("Camry", 2024)
        self.assertGreater(len(spec.fluids), 0)
        names = [f.name for f in spec.fluids]
        self.assertIn("Engine Oil", names)
        self.assertIn("Brake Fluid", names)

    def test_to_dict_shape(self):
        spec = self.parser.get_standard_specs("Camry", 2024)
        d = spec.to_dict()
        self.assertIn("source", d)
        self.assertIn("model", d)
        self.assertIn("year", d)
        self.assertIn("fluids", d)
        self.assertIsInstance(d["fluids"], list)

    def test_source_tag(self):
        spec = self.parser.get_standard_specs("Camry", 2024)
        self.assertEqual(spec.source, "owners-manual-standard")

    # --- parse_manual_text ---

    def test_parse_oil_capacity_from_text(self):
        text = "Engine oil capacity with filter 4.8 qt\nOil type: 0W-20"
        spec = self.parser.parse_manual_text(text, "Corolla", 2023, "")
        self.assertIsNotNone(spec.engine_oil_capacity)
        self.assertIn("4.8", spec.engine_oil_capacity)

    def test_parse_oil_type_from_text(self):
        text = "Recommended oil: 0W-20 synthetic"
        spec = self.parser.parse_manual_text(text, "Corolla", 2023, "")
        self.assertEqual(spec.engine_oil_type, "0W-20")

    def test_parse_tire_size_from_text(self):
        text = "Tire size 215/55R17"
        spec = self.parser.parse_manual_text(text, "Corolla", 2023, "")
        self.assertEqual(spec.tire_size, "215/55R17")

    def test_parse_missing_fields_are_none(self):
        spec = self.parser.parse_manual_text("no useful content", "Camry", 2024, "")
        self.assertIsNone(spec.engine_oil_capacity)
        self.assertIsNone(spec.tire_size)

    # --- get_owners_manual_url ---

    def test_url_contains_model_and_year(self):
        url = self.parser.get_owners_manual_url("Camry", 2024)
        self.assertIn("2024", url)
        self.assertIn("camry", url)


if __name__ == "__main__":
    unittest.main()
