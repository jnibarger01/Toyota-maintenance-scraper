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
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class SQLiteStore:
    """Lightweight SQLite persistence for exported scraper records."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dataset TEXT NOT NULL,
                    dedupe_key TEXT NOT NULL,
                    source TEXT,
                    model TEXT,
                    year INTEGER,
                    payload_json TEXT NOT NULL,
                    inserted_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(dataset, dedupe_key)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    written_at TEXT NOT NULL
                )
                """
            )

    def upsert_records(self, dataset: str, rows: List[Tuple[str, Dict[str, Any]]]) -> int:
        if not rows:
            return 0

        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO records (dataset, dedupe_key, source, model, year, payload_json, inserted_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(dataset, dedupe_key)
                DO UPDATE SET
                    source=excluded.source,
                    model=excluded.model,
                    year=excluded.year,
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at
                """,
                [
                    (
                        dataset,
                        dedupe_key,
                        record.get("source"),
                        record.get("model"),
                        int(record["year"]) if record.get("year") is not None else None,
                        json.dumps(record, default=str),
                        now,
                        now,
                    )
                    for dedupe_key, record in rows
                ],
            )
        return len(rows)

    def insert_summary(self, filename: str, data: Any) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO summaries (filename, payload_json, written_at) VALUES (?, ?, ?)",
                (filename, json.dumps(data, default=str), datetime.now(timezone.utc).isoformat()),
            )

    def reset(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM records")
            conn.execute("DELETE FROM summaries")


class Storage:
    """
    Storage handler for scraped data.
    
    Features:
    - JSONL streaming writes (one record per line)
    - CSV export with flattening
    - Deduplication by configurable key
    """
    
    def __init__(self, output_dir: str = "output", sqlite_path: Optional[str] = "scraper.db"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._seen_keys: Dict[str, Set[str]] = {}

        resolved_sqlite: Optional[Path] = None
        if sqlite_path:
            sqlite_candidate = Path(sqlite_path)
            resolved_sqlite = sqlite_candidate if sqlite_candidate.is_absolute() else self.output_dir / sqlite_candidate

        self.sqlite = SQLiteStore(resolved_sqlite) if resolved_sqlite else None
    
    def _get_file_path(self, filename: str) -> Path:
        """Get full path for output file."""
        return self.output_dir / filename

    def reset_files(self, filenames: Optional[List[str]] = None) -> None:
        """
        Remove output files to force a clean run.

        Args:
            filenames: Specific filenames to remove. If None, clear all files in output dir.
        """
        targets: List[Path]
        if filenames is None:
            targets = [p for p in self.output_dir.iterdir() if p.is_file()]
        else:
            targets = [self._get_file_path(name) for name in filenames]

        for path in targets:
            if path.exists() and path.is_file():
                path.unlink()

        self._seen_keys.clear()
        if self.sqlite:
            self.sqlite.reset()
    
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
        skipped = 0
        sqlite_rows: List[Tuple[str, Dict[str, Any]]] = []
        with open(filepath, mode) as f:
            for record in records:
                # Deduplication check
                if key_fields:
                    key = self._make_key(record, key_fields)
                    if key in self._seen_keys[filename]:
                        skipped += 1
                        logger.debug(f"Skipping duplicate: {key}")
                        continue
                    self._seen_keys[filename].add(key)
                else:
                    key = f"{filename}:{written}:{record.get('model', '')}:{record.get('year', '')}"

                f.write(json.dumps(record, default=str) + "\n")
                sqlite_rows.append((key, record))
                written += 1

        if skipped:
            logger.info(f"Skipped {skipped} duplicate record(s) in {filepath}")

        if self.sqlite and sqlite_rows:
            self.sqlite.upsert_records(filename, sqlite_rows)

        logger.info(f"Wrote {written} records to {filepath}")
        return written
    
    def write_json(self, filename: str, data: Any) -> None:
        """Write data as formatted JSON."""
        filepath = self._get_file_path(filename)
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)
        if self.sqlite:
            self.sqlite.insert_summary(filename, data)
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
                items.append((new_key, json.dumps(v)))
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
        self._state["completed"][key] = datetime.now(timezone.utc).isoformat()
        self._save()
    
    def is_completed(self, source: str, model: str, year: int) -> bool:
        """Check if model/year is already completed."""
        key = f"{source}:{model}:{year}"
        return key in self._state["completed"]
    
    def start_session(self) -> None:
        """Mark session start."""
        self._state["started_at"] = datetime.now(timezone.utc).isoformat()
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
