#!/usr/bin/env bash
set -euo pipefail

# Toyota Scraper Go/No-Go Script
# Exit codes: 0=GO, 2=CONDITIONAL GO, 1=NO-GO

# ---- Config (override via env) ----
TIMER_NAME="${TIMER_NAME:-toyota-scraper.timer}"
SERVICE_NAME="${SERVICE_NAME:-toyota-scraper.service}"
OUT_DIR="${OUT_DIR:-output}"
CI_DIR="${CI_DIR:-output_ci}"
SUMMARY_JSON="${SUMMARY_JSON:-${OUT_DIR}/scrape_summary.json}"
MS_JSONL="${MS_JSONL:-${OUT_DIR}/maintenance_schedules.jsonl}"
SS_JSONL="${SS_JSONL:-${OUT_DIR}/service_specs.jsonl}"
YEAR_MIN="${YEAR_MIN:-2000}"
YEAR_MAX="${YEAR_MAX:-$(( $(date +%Y) + 1 ))}"
SAMPLE_N="${SAMPLE_N:-20}"
ERROR_RATE_MAX="${ERROR_RATE_MAX:-0.10}"

# Optional: set this to a file you update each run (seconds)
RUNTIME_FILE="${RUNTIME_FILE:-}"
RUNTIME_MAX_SEC="${RUNTIME_MAX_SEC:-1200}"

# Optional Telegram check
TELEGRAM_CHECK_MODE="${TELEGRAM_CHECK_MODE:-none}" # none|unit|command
TELEGRAM_ONFAILURE_UNIT="${TELEGRAM_ONFAILURE_UNIT:-}"
TELEGRAM_TEST_COMMAND="${TELEGRAM_TEST_COMMAND:-}"

# ---- State ----
HARD_FAIL=0
SOFT_FAIL=0
NOTES=()

have_cmd() { command -v "$1" >/dev/null 2>&1; }
ok() { printf "✅ %s\n" "$*"; }
warn() { printf "⚠️ %s\n" "$*"; SOFT_FAIL=1; NOTES+=("$*"); }
fail() { printf "❌ %s\n" "$*"; HARD_FAIL=1; NOTES+=("$*"); }
section() { printf "\n=== %s ===\n" "$*"; }

run_make() {
  local target="$1"
  if make "$target"; then
    ok "make ${target}"
    return 0
  else
    fail "make ${target} failed"
    return 1
  fi
}

file_nonempty() {
  local f="$1"
  [[ -f "$f" ]] && [[ -s "$f" ]]
}

sample_lines() {
  local f="$1"
  local n="$2"
  if have_cmd shuf; then
    shuf -n "$n" "$f" 2>/dev/null || head -n "$n" "$f"
  else
    head -n "$n" "$f"
  fi
}

section "1) Build Integrity"
run_make install
run_make lint
run_make test
run_make smoke

if [[ -d "$CI_DIR" ]] && find "$CI_DIR" -maxdepth 2 -type f | grep -q .; then
  ok "output_ci/ artifacts exist"
else
  warn "output_ci/ artifacts not found (make smoke may not emit files as expected)"
fi

section "2) Live Run Validation"
run_make run || true
file_nonempty "$MS_JSONL" && ok "${MS_JSONL} exists and non-empty" || fail "${MS_JSONL} missing/empty"
file_nonempty "$SS_JSONL" && ok "${SS_JSONL} exists and non-empty" || fail "${SS_JSONL} missing/empty"
file_nonempty "$SUMMARY_JSON" && ok "${SUMMARY_JSON} exists and non-empty" || fail "${SUMMARY_JSON} missing/empty"

section "3) Data Quality Gate"
if ! have_cmd jq; then
  fail "jq not installed (needed for JSON sanity checks)"
else
  if file_nonempty "$SUMMARY_JSON"; then
    if jq -e . "$SUMMARY_JSON" >/dev/null 2>&1; then
      ok "scrape_summary.json is valid JSON"
    else
      fail "scrape_summary.json is not valid JSON"
    fi

    ERR="$(jq -r '(.errors // .error_count // .counts.errors // empty) | tonumber? // empty' "$SUMMARY_JSON" 2>/dev/null || true)"
    TOT="$(jq -r '(.total // .total_count // .counts.total // empty) | tonumber? // empty' "$SUMMARY_JSON" 2>/dev/null || true)"
    SUC="$(jq -r '(.success // .success_count // .counts.success // empty) | tonumber? // empty' "$SUMMARY_JSON" 2>/dev/null || true)"

    RATE=""
    if [[ -n "${ERR:-}" ]]; then
      if [[ -n "${TOT:-}" && "$TOT" != "0" ]]; then
        RATE="$(python3 - <<PY
err=float("$ERR"); tot=float("$TOT")
print(err/tot)
PY
)"
      elif [[ -n "${SUC:-}" ]]; then
        RATE="$(python3 - <<PY
err=float("$ERR"); suc=float("$SUC"); tot=err+suc
print(err/tot if tot>0 else 0.0)
PY
)"
      fi
    fi

    if [[ -n "${RATE:-}" ]]; then
      if python3 - <<PY
rate=float("$RATE"); maxr=float("$ERROR_RATE_MAX")
print(f"error_rate = {rate:.4f} (threshold {maxr:.4f})")
raise SystemExit(0 if rate < maxr else 1)
PY
      then
        ok "Error rate below threshold"
      else
        fail "Error rate >= threshold"
      fi
    else
      warn "Could not compute error rate from summary (unknown schema)"
    fi
  fi

  check_jsonl_sample() {
    local f="$1"
    local label="$2"

    if ! file_nonempty "$f"; then
      fail "${label}: jsonl missing/empty"
      return
    fi

    local total=0
    local bad=0
    local missing_any=0

    while IFS= read -r line; do
      [[ -z "$line" ]] && continue
      total=$((total+1))

      if ! echo "$line" | jq -e . >/dev/null 2>&1; then
        bad=$((bad+1))
        continue
      fi

      local year make model
      year="$(echo "$line" | jq -r '(.year // .model_year // .vehicle.year // .vehicleYear // empty) | tostring' 2>/dev/null || true)"
      make="$(echo "$line" | jq -r '(.make // .manufacturer // .vehicle.make // .vehicleMake // empty) | tostring' 2>/dev/null || true)"
      model="$(echo "$line" | jq -r '(.model // .vehicle.model // .vehicleModel // empty) | tostring' 2>/dev/null || true)"

      if [[ -z "$year" || "$year" == "null" || -z "$make" || "$make" == "null" || -z "$model" || "$model" == "null" ]]; then
        missing_any=$((missing_any+1))
      fi

      if [[ -n "$year" && "$year" != "null" ]]; then
        if [[ "$year" =~ ^[0-9]{4}$ ]]; then
          if (( year < YEAR_MIN || year > YEAR_MAX )); then
            bad=$((bad+1))
          fi
        else
          bad=$((bad+1))
        fi
      fi
    done < <(sample_lines "$f" "$SAMPLE_N")

    if (( total == 0 )); then
      fail "${label}: sample produced 0 records"
      return
    fi

    if (( bad > 0 )); then
      fail "${label}: malformed/implausible records detected (bad=${bad} of ${total})"
    else
      ok "${label}: JSON sanity OK (${total} checked)"
    fi

    if python3 - <<PY
missing=int("$missing_any"); total=int("$total")
threshold=total*0.2
print(f"missing_any = {missing} (threshold <= {threshold:.1f})")
raise SystemExit(0 if missing <= threshold else 1)
PY
    then
      ok "${label}: key fields present (record-level gate)"
    else
      fail "${label}: key fields missing too often"
    fi
  }

  check_jsonl_sample "$MS_JSONL" "maintenance_schedules"
  check_jsonl_sample "$SS_JSONL" "service_specs"
fi

section "4) Operational Readiness"
if have_cmd systemctl; then
  if systemctl --user list-unit-files | grep -q "^${TIMER_NAME}"; then
    ok "Timer unit exists: ${TIMER_NAME}"
    if systemctl --user is-enabled "${TIMER_NAME}" >/dev/null 2>&1; then
      ok "Timer is enabled"
    else
      fail "Timer exists but is NOT enabled"
    fi
  else
    fail "Timer unit not found: ${TIMER_NAME}"
  fi

  if systemctl --user status "${SERVICE_NAME}" >/dev/null 2>&1; then
    ok "Service unit exists: ${SERVICE_NAME}"
    if journalctl --user -u "${SERVICE_NAME}" -n 5 >/dev/null 2>&1; then
      ok "Service has journal logs"
    else
      warn "No journal logs found for service (observability weak)"
    fi
  else
    warn "Service unit not found: ${SERVICE_NAME} (timer may call a different unit)"
  fi
else
  fail "systemctl not available (cannot validate timer/service)"
fi

case "$TELEGRAM_CHECK_MODE" in
  none)
    warn "Telegram alerting not verified (set TELEGRAM_CHECK_MODE=unit|command to enforce)"
    ;;
  unit)
    if [[ -z "$TELEGRAM_ONFAILURE_UNIT" ]]; then
      fail "TELEGRAM_CHECK_MODE=unit set but TELEGRAM_ONFAILURE_UNIT is empty"
    else
      if have_cmd systemctl && systemctl --user status "$TELEGRAM_ONFAILURE_UNIT" >/dev/null 2>&1; then
        ok "Telegram OnFailure unit exists: $TELEGRAM_ONFAILURE_UNIT"
      else
        fail "Telegram OnFailure unit not found: $TELEGRAM_ONFAILURE_UNIT"
      fi
    fi
    ;;
  command)
    if [[ -z "$TELEGRAM_TEST_COMMAND" ]]; then
      fail "TELEGRAM_CHECK_MODE=command set but TELEGRAM_TEST_COMMAND is empty"
    else
      if bash -lc "$TELEGRAM_TEST_COMMAND" >/dev/null 2>&1; then
        ok "Telegram test command executed successfully"
      else
        fail "Telegram test command failed"
      fi
    fi
    ;;
  *)
    fail "Invalid TELEGRAM_CHECK_MODE: $TELEGRAM_CHECK_MODE (use none|unit|command)"
    ;;
esac

if [[ -n "$RUNTIME_FILE" ]]; then
  if file_nonempty "$RUNTIME_FILE"; then
    runtime="$(tr -d ' \t\n\r' < "$RUNTIME_FILE" || true)"
    if [[ "$runtime" =~ ^[0-9]+$ ]]; then
      if (( runtime <= RUNTIME_MAX_SEC )); then
        ok "Runtime gate OK (${runtime}s <= ${RUNTIME_MAX_SEC}s)"
      else
        fail "Runtime gate FAIL (${runtime}s > ${RUNTIME_MAX_SEC}s)"
      fi
    else
      warn "RUNTIME_FILE present but not a plain integer seconds value: $RUNTIME_FILE"
    fi
  else
    warn "RUNTIME_FILE set but file missing/empty: $RUNTIME_FILE"
  fi
else
  warn "Runtime not verified (set RUNTIME_FILE to enforce)"
fi

section "5) Security / Compliance"
if have_cmd git && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  ok "Git repo detected"

  if git grep -nE '(AKIA[0-9A-Z]{16}|xox[baprs]-[0-9A-Za-z-]{10,}|-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY-----|api[_-]?key\s*=\s*["'"'"']?[A-Za-z0-9_\-]{16,}|token\s*=\s*["'"'"']?[A-Za-z0-9_\-]{16,}|secret\s*=\s*["'"'"']?[A-Za-z0-9_\-]{16,})' -- . >/dev/null 2>&1; then
    fail "Potential secret patterns found in tracked files (inspect with git grep -nE ...)"
  else
    ok "No obvious secret patterns found in tracked files"
  fi

  if git ls-files | grep -E '(^|/)\.env$|(^|/)\.env\.|cookies\.txt|cookie(s)?\.json' >/dev/null 2>&1; then
    fail "Secret-like files tracked (.env/cookies*)"
  else
    ok "No .env/cookies files tracked"
  fi
else
  warn "Not a git repo (cannot scan for committed secrets)"
fi

section "6) Rollback / Recovery"
if [[ -d "${OUT_DIR}_prev" ]] || [[ -d "backups" ]]; then
  ok "Backup/retention directory detected"
else
  warn "No obvious retention detected (consider output_prev/ or backups/)"
fi
ok "Disable command: systemctl --user disable --now ${TIMER_NAME}"

section "Promotion Decision"
if (( HARD_FAIL == 1 )); then
  printf "\nVERDICT: NO-GO\n"
  printf "Reasons:\n"
  for n in "${NOTES[@]}"; do
    printf " - %s\n" "$n"
  done
  exit 1
fi

if (( SOFT_FAIL == 1 )); then
  printf "\nVERDICT: CONDITIONAL GO\n"
  printf "Open items:\n"
  for n in "${NOTES[@]}"; do
    printf " - %s\n" "$n"
  done
  exit 2
fi

printf "\nVERDICT: GO\n"
exit 0
