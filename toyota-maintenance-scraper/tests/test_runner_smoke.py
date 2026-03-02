import unittest

from config import ScraperConfig
from runner import run_scraper


class RunnerSmokeTests(unittest.TestCase):
    def test_offline_smoke(self):
        cfg = ScraperConfig.smoke_test()
        cfg.output_dir = "output_test"
        stats = run_scraper(cfg, sources=["toyota-pdf", "owners-manual"], resume=False, offline=True)
        self.assertIn("toyota-pdf", stats["results"])


if __name__ == "__main__":
    unittest.main()
