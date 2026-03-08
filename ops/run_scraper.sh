#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/jace/Toyota-maintenance-scraper"
APP="$ROOT/toyota-maintenance-scraper"
OUT_DIR="$ROOT/output"
TELEGRAM_TARGET="${TELEGRAM_TARGET:-8593378188}"

mkdir -p "$OUT_DIR"
cd "$APP"

python3 runner.py --offline --no-resume --output-dir "$OUT_DIR" > "$ROOT/ops/last_run.log" 2>&1 || {
  if command -v openclaw >/dev/null 2>&1; then
    openclaw message send --channel telegram --target "$TELEGRAM_TARGET" --message "🚨 Toyota scraper failed on $(hostname). Check $ROOT/ops/last_run.log"
  fi
  exit 1
}

if command -v openclaw >/dev/null 2>&1; then
  openclaw message send --channel telegram --target "$TELEGRAM_TARGET" --message "✅ Toyota scraper completed. Output: $OUT_DIR"
fi
