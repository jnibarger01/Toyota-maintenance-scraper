"""
Toyota Maintenance PDF scraper.

Downloads and caches Toyota Warranty & Maintenance Guide PDFs.
"""
import logging
from pathlib import Path
from typing import Optional

from .base import BaseScraper
from config import settings, get_pdf_url, TOYOTA_MODELS

logger = logging.getLogger(__name__)


class ToyotaPDFScraper(BaseScraper):
    """Downloads Toyota maintenance PDFs."""
    
    def __init__(self):
        super().__init__(rate_limit=settings.TOYOTA_PDF_RATE_LIMIT)
        self.pdf_dir = settings.PDF_DIR
    
    def _get_cache_path(self, model: str, year: int) -> Path:
        """Get local cache path for a PDF."""
        return self.pdf_dir / f"{year}_{model.replace(' ', '_')}.pdf"
    
    def _is_cached(self, model: str, year: int) -> bool:
        """Check if PDF is already downloaded."""
        cache_path = self._get_cache_path(model, year)
        return cache_path.exists() and cache_path.stat().st_size > 0
    
    def download_pdf(self, model: str, year: int, force: bool = False) -> Optional[Path]:
        """
        Download a maintenance PDF for a model/year.
        
        Returns path to downloaded PDF, or None if failed.
        """
        cache_path = self._get_cache_path(model, year)
        
        if not force and self._is_cached(model, year):
            logger.debug(f"Using cached PDF: {cache_path}")
            return cache_path
        
        # Try primary URL pattern
        try:
            url = get_pdf_url(model, year)
            logger.info(f"Downloading PDF: {year} {model}")
            
            content = self.fetch_binary(url)
            
            # Verify it's actually a PDF
            if not content.startswith(b'%PDF'):
                logger.warning(f"Invalid PDF content for {year} {model}")
                return None
            
            cache_path.write_bytes(content)
            logger.info(f"Saved: {cache_path}")
            return cache_path
            
        except Exception as e:
            logger.warning(f"Failed to download {year} {model}: {e}")
            
            # Try alternate URL pattern
            try:
                return self._try_alternate_url(model, year, cache_path)
            except Exception as e2:
                logger.error(f"All download attempts failed for {year} {model}: {e2}")
                return None
    
    def _try_alternate_url(self, model: str, year: int, cache_path: Path) -> Optional[Path]:
        """Try alternate PDF URL pattern."""
        if model not in TOYOTA_MODELS:
            return None
        
        yy = str(year)[2:]
        code = TOYOTA_MODELS[model]["code"]
        
        # Try assets.sia.toyota.com pattern
        alt_url = f"https://assets.sia.toyota.com/publications/en/omms-s/T-MMS-{yy}{code}/pdf/T-MMS-{yy}{code}.pdf"
        
        logger.debug(f"Trying alternate URL: {alt_url}")
        content = self.fetch_binary(alt_url)
        
        if not content.startswith(b'%PDF'):
            return None
        
        cache_path.write_bytes(content)
        logger.info(f"Saved from alternate URL: {cache_path}")
        return cache_path
    
    def scrape(self, model: str, year: int, force: bool = False) -> Optional[Path]:
        """
        Scrape (download) a single PDF.
        
        Alias for download_pdf to match BaseScraper interface.
        """
        return self.download_pdf(model, year, force)
    
    def scrape_all(
        self,
        start_year: int = 2018,
        end_year: int = 2025,
        force: bool = False,
    ) -> dict[tuple[str, int], Optional[Path]]:
        """
        Download all PDFs for the given year range.
        
        Returns dict mapping (model, year) -> Path or None.
        """
        results = {}
        
        for model, info in TOYOTA_MODELS.items():
            model_start = max(start_year, info["years"][0])
            model_end = min(end_year, info["years"][1])
            
            for year in range(model_start, model_end + 1):
                path = self.download_pdf(model, year, force)
                results[(model, year)] = path
        
        # Summary
        success = sum(1 for p in results.values() if p is not None)
        total = len(results)
        logger.info(f"Downloaded {success}/{total} PDFs")
        
        return results
    
    def get_cached_pdfs(self) -> list[Path]:
        """Get list of all cached PDFs."""
        return list(self.pdf_dir.glob("*.pdf"))
