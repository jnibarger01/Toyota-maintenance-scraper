import json
import tempfile
import unittest
from pathlib import Path

from config import ScraperConfig


class ConfigTests(unittest.TestCase):
    def test_from_json_file(self):
        payload = {
            "years": [2024],
            "models": ["Camry"],
            "rate_limit": 1.5,
            "timeout": 20,
            "max_retries": 2,
        }
        with tempfile.TemporaryDirectory() as td:
            fp = Path(td) / "cfg.json"
            fp.write_text(json.dumps(payload))
            cfg = ScraperConfig.from_file(str(fp))
            self.assertEqual(cfg.years, [2024])
            self.assertEqual(cfg.models, ["Camry"])
            self.assertEqual(cfg.timeout, 20)

    def test_invalid_model_validation(self):
        cfg = ScraperConfig(years=[2024], models=["NotAModel"])
        with self.assertRaises(ValueError):
            cfg.validate()


if __name__ == "__main__":
    unittest.main()
