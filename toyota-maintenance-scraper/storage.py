"""
Storage module for JSON and CSV output.

Handles writing scraped data to files with:
- JSONL format for streaming/resumable writes
- CSV export for spreadsheet use
- Deduplication by key
"""
import json
import csv
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from datetime import datetime

logger = logging.getLogger(__name__)


class Storage:
    """
    Storage handler for scraped data.
    
    Features:
    - JSONL streaming writes (one record per line)
    - CSV export with flattening
    - Deduplication by configurable key
    """
    
    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._seen_keys: Dict[str, Set[str]] = {}
    
    def _get_file_path(self, filename: str) -> Path:
        """Get full path for output file."""
        return self.output_dir / filename
    
    def _make_key(self, record: Dict[str, Any], key_fields: List[str]) -> str:
        """Generate deduplication key from record."""
        return "|".join(str(record.get(f, "")) for f in key_fields)
    
    def write_jsonl(
        self,
        filename: str,
        records: List[Dict[str, Any]],
        key_fields: Optional[List[str]] = None,
        append: bool = True,
    ) -> int:
        """
        Write records to JSONL file.
        
        Args:
            filename: Output filename
            records: List of dictionaries to write
            key_fields: Fields to use for deduplication (None = no dedup)
            append: Append to existing file vs overwrite
            
        Returns:
            Number of records written
        """
        filepath = self._get_file_path(filename)
        mode = "a" if append else "w"
        
        # Initialize seen keys for this file
        if filename not in self._seen_keys:
            self._seen_keys[filename] = set()
            
            # Load existing keys if appending
            if append and filepath.exists():
                with open(filepath, "r") as f:
                    for line in f:
                        try:
                            existing = json.loads(line.strip())
                            if key_fields:
                                key = self._make_key(existing, key_fields)
                                self._seen_keys[filename].add(key)
                        except json.JSONDecodeError:
                            continue
        
        written = 0
        with open(filepath, mode) as f:
            for record in records:
                # Deduplication check
                if key_fields:
                    key = self._make_key(record, key_fields)
                    if key in self._seen_keys[filename]:
                        logger.debug(f"Skipping duplicate: {key}")
                        continue
                    self._seen_keys[filename].add(key)
                
                f.write(json.dumps(record, default=str) + "\n")
                written += 1
        
        logger.info(f"Wrote {written} records to {filepath}")
        return written
    
    def write_json(self, filename: str, data: Any) -> None:
        """Write data as formatted JSON."""
        filepath = self._get_file_path(filename)
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)
        logger.info(f"Wrote JSON to {filepath}")
    
    def read_jsonl(self, filename: str) -> List[Dict[str, Any]]:
        """Read all records from JSONL file."""
        filepath = self._get_file_path(filename)
        if not filepath.exists():
            return []
        
        records = []
        with open(filepath, "r") as f:
            for line in f:
                try:
                    records.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
        return records
    
    def export_to_csv(
        self,
        jsonl_filename: str,
        csv_filename: Optional[str] = None,
        flatten: bool = True,
    ) -> None:
        """
        Export JSONL file to CSV.
        
        Args:
            jsonl_filename: Source JSONL file
            csv_filename: Output CSV file (default: same name with .csv)
            flatten: Flatten nested dictionaries
        """
        if csv_filename is None:
            csv_filename = jsonl_filename.rsplit(".", 1)[0] + ".csv"
        
        records = self.read_jsonl(jsonl_filename)
        if not records:
            logger.warning(f"No records to export from {jsonl_filename}")
            return
        
        # Flatten records if needed
        if flatten:
            records = [self._flatten_dict(r) for r in records]
        
        # Collect all unique keys
        all_keys = set()
        for record in records:
            all_keys.update(record.keys())
        fieldnames = sorted(all_keys)
        
        filepath = self._get_file_path(csv_filename)
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(records)
        
        logger.info(f"Exported {len(records)} records to {filepath}")
    
    def _flatten_dict(
        self,
        d: Dict[str, Any],
        parent_key: str = "",
        sep: str = "_",
    ) -> Dict[str, Any]:
        """Flatten nested dictionary."""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep).items())
            elif isinstance(v, list):
                # For lists, join as comma-separated string or expand
                if v and isinstance(v[0], dict):
                    # List of dicts - take first or summarize
                    items.append((new_key, json.dumps(v)))
                else:
                    items.append((new_key, ", ".join(str(x) for x in v)))
            else:
                items.append((new_key, v))
        
        return dict(items)
    
    def get_stats(self, filename: str) -> Dict[str, Any]:
        """Get statistics for a JSONL file."""
        records = self.read_jsonl(filename)
        
        if not records:
            return {"count": 0}
        
        stats = {
            "count": len(records),
            "fields": list(records[0].keys()) if records else [],
        }
        
        # Count by source if available
        if "source" in records[0]:
            by_source = {}
            for r in records:
                src = r.get("source", "unknown")
                by_source[src] = by_source.get(src, 0) + 1
            stats["by_source"] = by_source
        
        # Count by year if available
        if "year" in records[0]:
            by_year = {}
            for r in records:
                yr = r.get("year", "unknown")
                by_year[yr] = by_year.get(yr, 0) + 1
            stats["by_year"] = by_year
        
        return stats


class Checkpoint:
    """
    Checkpoint manager for resumable scraping.
    
    Tracks progress to allow resuming after interruption.
    """
    
    def __init__(self, output_dir: str = "output"):
        self.checkpoint_file = Path(output_dir) / ".checkpoint.json"
        self._state = self._load()
    
    def _load(self) -> Dict[str, Any]:
        """Load checkpoint state."""
        if self.checkpoint_file.exists():
            with open(self.checkpoint_file, "r") as f:
                return json.load(f)
        return {"completed": {}, "started_at": None}
    
    def _save(self) -> None:
        """Save checkpoint state."""
        with open(self.checkpoint_file, "w") as f:
            json.dump(self._state, f, indent=2)
    
    def mark_completed(self, source: str, model: str, year: int) -> None:
        """Mark a model/year as completed."""
        key = f"{source}:{model}:{year}"
        self._state["completed"][key] = datetime.utcnow().isoformat()
        self._save()
    
    def is_completed(self, source: str, model: str, year: int) -> bool:
        """Check if model/year is already completed."""
        key = f"{source}:{model}:{year}"
        return key in self._state["completed"]
    
    def start_session(self) -> None:
        """Mark session start."""
        self._state["started_at"] = datetime.utcnow().isoformat()
        self._save()
    
    def get_progress(self) -> Dict[str, Any]:
        """Get current progress."""
        return {
            "completed_count": len(self._state["completed"]),
            "started_at": self._state["started_at"],
        }
    
    def clear(self) -> None:
        """Clear checkpoint (start fresh)."""
        self._state = {"completed": {}, "started_at": None}
        self._save()
