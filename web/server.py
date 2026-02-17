#!/usr/bin/env python3
"""
Toyota Maintenance Dashboard - Development Server

Simple HTTP server that serves the web dashboard and provides JSON API
endpoints for the scraped data.

Usage:
    python server.py              # Starts on port 8080
    python server.py --port 3000  # Custom port

API Endpoints:
    GET /                          - Dashboard (index.html)
    GET /api/models                - List all available model/year combos
    GET /api/maintenance           - All maintenance data (JSON array)
    GET /api/maintenance/<model>/<year> - Single vehicle maintenance
    GET /api/specs                 - All vehicle specs (JSON array)
    GET /api/specs/<model>/<year>  - Specs for a model/year
    GET /api/service-specs         - All service specs (JSON array)
    GET /api/service-specs/<model>/<year> - Service specs for a model/year
"""

import argparse
import json
import logging
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

WEB_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = WEB_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
SAMPLE_DIR = WEB_DIR / "sample_data"


def _find_jsonl(filename: str) -> Path | None:
    """Find a JSONL file in output/ or sample_data/."""
    output_path = OUTPUT_DIR / filename
    if output_path.exists():
        return output_path
    sample_path = SAMPLE_DIR / filename
    if sample_path.exists():
        return sample_path
    return None


def _load_jsonl(filename: str) -> list[dict]:
    """Load and parse a JSONL file."""
    path = _find_jsonl(filename)
    if not path:
        return []
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


# ---------------------------------------------------------------------------
# Preload data
# ---------------------------------------------------------------------------

maintenance_data: list[dict] = []
vehicle_specs_data: list[dict] = []
service_specs_data: list[dict] = []


def load_all_data():
    """Load all data files into memory."""
    global maintenance_data, vehicle_specs_data, service_specs_data
    maintenance_data = _load_jsonl("maintenance.jsonl")
    vehicle_specs_data = _load_jsonl("vehicle_specs.jsonl")
    service_specs_data = _load_jsonl("service_specs.jsonl")
    logger.info(
        f"Loaded: {len(maintenance_data)} maintenance, "
        f"{len(vehicle_specs_data)} vehicle specs, "
        f"{len(service_specs_data)} service specs"
    )


# ---------------------------------------------------------------------------
# Request Handler
# ---------------------------------------------------------------------------

class DashboardHandler(SimpleHTTPRequestHandler):
    """Serves static files from web/ and API endpoints."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def do_GET(self):
        path = unquote(self.path).split("?")[0]

        # API routing
        if path.startswith("/api/"):
            self._handle_api(path)
            return

        # Static files
        super().do_GET()

    def _handle_api(self, path: str):
        """Route API requests."""
        parts = path.strip("/").split("/")
        # parts[0] == "api"

        if len(parts) == 2 and parts[1] == "models":
            self._respond_json(self._get_models())
            return

        if len(parts) == 2 and parts[1] == "maintenance":
            self._respond_json(maintenance_data)
            return

        if len(parts) == 4 and parts[1] == "maintenance":
            model = unquote(parts[2])
            year = int(parts[3])
            result = self._filter_maintenance(model, year)
            self._respond_json(result)
            return

        if len(parts) == 2 and parts[1] == "specs":
            self._respond_json(vehicle_specs_data)
            return

        if len(parts) == 4 and parts[1] == "specs":
            model = unquote(parts[2])
            year = int(parts[3])
            result = self._filter_specs(model, year)
            self._respond_json(result)
            return

        if len(parts) == 2 and parts[1] == "service-specs":
            self._respond_json(service_specs_data)
            return

        if len(parts) == 4 and parts[1] == "service-specs":
            model = unquote(parts[2])
            year = int(parts[3])
            result = self._filter_service_specs(model, year)
            self._respond_json(result)
            return

        self._respond_json({"error": "Not found"}, status=404)

    def _get_models(self) -> list[dict]:
        """Return available model/year combinations."""
        seen = set()
        models = []
        for record in maintenance_data:
            key = (record.get("model"), record.get("year"))
            if key not in seen:
                seen.add(key)
                models.append({"model": key[0], "year": key[1]})
        return sorted(models, key=lambda x: (x["model"], x["year"]))

    def _filter_maintenance(self, model: str, year: int) -> list[dict]:
        return [
            r for r in maintenance_data
            if r.get("model") == model and r.get("year") == year
        ]

    def _filter_specs(self, model: str, year: int) -> list[dict]:
        return [
            r for r in vehicle_specs_data
            if r.get("model") == model and r.get("year") == year
        ]

    def _filter_service_specs(self, model: str, year: int) -> list[dict]:
        return [
            r for r in service_specs_data
            if r.get("model") == model and r.get("year") == year
        ]

    def _respond_json(self, data, status: int = 200):
        """Send a JSON response with CORS headers."""
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, fmt, *args):
        """Suppress static file logs, keep API logs."""
        path = args[0].split()[1] if args else ""
        if path.startswith("/api/"):
            logger.info(fmt % args)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Toyota Maintenance Dashboard Server")
    parser.add_argument("--port", type=int, default=8080, help="Port (default: 8080)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host (default: 127.0.0.1)")
    args = parser.parse_args()

    load_all_data()

    server = HTTPServer((args.host, args.port), DashboardHandler)
    logger.info(f"Dashboard: http://{args.host}:{args.port}")
    logger.info(f"Serving files from: {WEB_DIR}")
    logger.info(f"Data sources: {OUTPUT_DIR} (primary), {SAMPLE_DIR} (fallback)")
    logger.info("Press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down")
        server.server_close()


if __name__ == "__main__":
    main()
