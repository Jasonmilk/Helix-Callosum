#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────
# Helix-Callosum — One-Click Environment Setup & Test
# ─────────────────────────────────────────────────────────
# This script handles EVERYTHING:
#   1. Virtual environment creation & dependency installation
#   2. Pre-flight checks (Tuck connectivity & LLM backend liveness)
#   3. Unit tests (pytest)
#   4. Gateway smoke test (start server → health/compile/stats)
#   5. Cellrix manifest validation (cellrix check)
#   6. Teardown (stop server)
# ─────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/.venv"
LOG_FILE="$PROJECT_DIR/setup_$(date +%Y%m%d_%H%M%S).log"
PASS=0
FAIL=0

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

log()   { echo -e "$(date '+%H:%M:%S')  $*" | tee -a "$LOG_FILE"; }
pass()  { log "${GREEN}[PASS]${NC} $*"; PASS=$((PASS + 1)); }
fail()  { log "${RED}[FAIL]${NC} $*"; FAIL=$((FAIL + 1)); }
warn()  { log "${YELLOW}[WARN]${NC} $*"; }
step()  { log "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; log "  STEP: $*"; log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; }

# ─────────────────────────────────────────────────────────
# STEP 1: Environment Provisioning
# ─────────────────────────────────────────────────────────
step "1. Environment Provisioning"

if [ ! -d "$VENV_DIR" ]; then
    log "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    pass "Virtual environment created"
else
    warn "Virtual environment already exists, skipping creation"
fi

log "Installing dependencies (editable + dev)..."
source "$VENV_DIR/bin/activate"
pip install -e ".[dev]" 2>&1 | tail -3 | tee -a "$LOG_FILE"
pass "Dependencies installed"

# ─────────────────────────────────────────────────────────
# STEP 2: Pre-Flight Checks (Tuck & LLM Backend)
# ─────────────────────────────────────────────────────────
step "2. Pre-Flight Checks — Tuck Gateway & LLM Backends"

TUCK_PORTS=("8015" "8016" "8014")
TUCK_ALIVE=false
LLM_ALIVE=false

for port in "${TUCK_PORTS[@]}"; do
    if curl -s --max-time 2 "http://localhost:$port/v1/models" > /dev/null 2>&1; then
        TUCK_ALIVE=true
        log "Tuck backend alive on port $port"
        # Check if any model is loaded
        if curl -s --max-time 2 "http://localhost:$port/v1/models" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('data',[]))" 2>/dev/null | grep -q .; then
            LLM_ALIVE=true
            log "LLM model loaded on port $port"
        fi
    fi
done

if [ "$TUCK_ALIVE" = true ]; then
    pass "Tuck gateway reachable — local LLM matrix is online"
else
    warn "Tuck gateway unreachable on ports 8014-8016"
    warn "Callosum will start but adapters may report unhealthy"
    warn "Start Tuck with: tuck (in Tuck project directory)"
fi

if [ "$LLM_ALIVE" = true ]; then
    pass "LLM backend ready — full inference pipeline active"
else
    warn "No LLM model detected — inference will fail, but compilation/stats work"
fi

# ─────────────────────────────────────────────────────────
# STEP 3: Unit Tests (pytest)
# ─────────────────────────────────────────────────────────
step "3. Unit Tests (pytest)"

if pytest -v 2>&1 | tee -a "$LOG_FILE" | tail -5; then
    pass "All unit tests passed"
else
    fail "Some unit tests failed — check log: $LOG_FILE"
    exit 1
fi

# ─────────────────────────────────────────────────────────
# STEP 4: Gateway Startup & Smoke Test
# ─────────────────────────────────────────────────────────
step "4. Gateway Smoke Test (start → health → compile → stats)"

log "Starting Callosum gateway..."
callosum server start &
SERVER_PID=$!
sleep 3

cleanup() {
    log "Stopping Callosum gateway (PID: $SERVER_PID)..."
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
}

# Health check
if curl -s --max-time 3 http://localhost:8687/health | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['status']=='healthy'" 2>/dev/null; then
    pass "Health check: Gateway is healthy"
else
    fail "Health check: Gateway returned error"
    cleanup
    exit 1
fi

# Compile endpoint
COMPILE_RESULT=$(curl -s -X POST http://localhost:8687/v1/compile \
  -H "Content-Type: application/json" \
  -H "X-Trace-Id: setup-test-001" \
  -d '{"blocks":[{"content":"System prompt","volatility":{"score":0,"reason":"system_prompt"},"role":"system"},{"content":"User query","volatility":{"score":10,"reason":"dynamic_query"},"role":"user"}],"trace_id":"setup-test-001"}')

if echo "$COMPILE_RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'blocks' in d and 'prefix_hash' in d" 2>/dev/null; then
    HASH=$(echo "$COMPILE_RESULT" | python3 -c "import json,sys; print(json.load(sys.stdin)['prefix_hash'][:16])")
    pass "Compile endpoint: Valid CompiledRequest returned (prefix=$HASH...)"
else
    fail "Compile endpoint: Invalid response"
    cleanup
    exit 1
fi

# Stats endpoint
if curl -s --max-time 3 http://localhost:8687/v1/usage-stats | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'total_requests' in d" 2>/dev/null; then
    pass "Stats endpoint: Valid UsageStatsResponse returned"
else
    fail "Stats endpoint: Invalid response"
fi

cleanup
sleep 1

# ─────────────────────────────────────────────────────────
# STEP 5: Cellrix Manifest Validation
# ─────────────────────────────────────────────────────────
step "5. Cellrix Manifest Validation (CIS v0.3.0)"

# Cellrix is an optional visualization tool. Its absence or failure does NOT affect Callosum.
# We temporarily activate Cellrix's own virtualenv to run 'cellrix check'.
CELLRIX_VENV="/opt/Cellrix/.venv"
if [ -f "$CELLRIX_VENV/bin/activate" ]; then
    log "Temporarily activating Cellrix environment for validation..."
    (
        source "$CELLRIX_VENV/bin/activate"
        if command -v cellrix &> /dev/null; then
            log "Running cellrix check..."
            if cellrix check 2>&1 | tee -a "$LOG_FILE"; then
                pass "Cellrix manifest validation passed (cellrix check)"
            else
                warn "Cellrix manifest validation FAILED — review errors above. (Callosum is unaffected)"
            fi
        else
            warn "cellrix command not found even in Cellrix venv — skipping"
        fi
    )
else
    warn "Cellrix virtualenv not found at $CELLRIX_VENV — skipping Cellrix validation"
    warn "To enable: cd /opt/Cellrix && python3 -m venv .venv && source .venv/bin/activate && pip install -e ."
fi
# ─────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────
step "Summary"
log "Passed: $PASS | Failed: $FAIL | Warnings: See above"
log "Full log: $LOG_FILE"
echo ""
echo "  ██╗  ██╗███████╗██╗     ██╗██╗  ██╗"
echo "  ██║  ██║██╔════╝██║     ██║╚██╗██╔╝"
echo "  ███████║█████╗  ██║     ██║ ╚███╔╝ "
echo "  ██╔══██║██╔══╝  ██║     ██║ ██╔██╗ "
echo "  ██║  ██║███████╗███████╗██║██╔╝ ██╗"
echo "  ╚═╝  ╚═╝╚══════╝╚══════╝╚═╝╚═╝  ╚═╝"
echo "  Helix-Callosum Setup Complete!"
echo ""

if [ "$FAIL" -gt 0 ]; then
    log "${RED}Some tests failed. Please review the log above.${NC}"
    exit 1
else
    log "${GREEN}All checks passed. Your Helix-Callosum is ready.${NC}"
fi

