#!/usr/bin/env python3
"""
Repository root entrypoint.

Delegates execution to the maintained scraper app at:
    toyota-maintenance-scraper/runner.py
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parent
    app_dir = repo_root / "toyota-maintenance-scraper"
    runner_path = app_dir / "runner.py"

    if not runner_path.exists():
        print(f"Runner not found: {runner_path}", file=sys.stderr)
        return 1

    # Ensure local imports (config, fetcher, parsers, storage) resolve.
    sys.path.insert(0, str(app_dir))
    runpy.run_path(str(runner_path), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
