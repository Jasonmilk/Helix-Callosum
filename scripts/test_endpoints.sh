#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# Helix-Callosum Automated Endpoint Test Suite
# ─────────────────────────────────────────────────────────
# Tests /health, /v1/compile, /v1/usage-stats against
# a running Callosum gateway.
#
# Tolerates "degraded" health status (e.g. when Tuck is
# unreachable) so that this suite is safe to run even
# without a live LLM backend.
# ─────────────────────────────────────────────────────────
set -euo pipefail

HOST="${1:-http://localhost:8687}"
PASS=0
FAIL=0

check() {
    local name="$1"
    local cmd="$2"
    echo -n "Testing $name... "
    if eval "$cmd" > /dev/null 2>&1; then
        echo "✅ PASS"
        PASS=$((PASS + 1))
    else
        echo "❌ FAIL"
        FAIL=$((FAIL + 1))
    fi
}

check "Health Endpoint (accepts healthy or degraded)" \
    'curl -s --max-time 3 '"$HOST"'/health | python3 -c "import json,sys; d=json.load(sys.stdin); assert d[\"status\"] in (\"healthy\",\"degraded\")"'

check "Compile Endpoint (Valid)" \
    'curl -s -X POST '"$HOST"'/v1/compile -H "Content-Type: application/json" -H "X-Trace-Id: test-001" -d '\''{"blocks":[{"content":"System","volatility":{"score":0,"reason":"system_prompt"},"role":"system"}],"trace_id":"test-001"}'\'' | python3 -c "import json,sys; d=json.load(sys.stdin); assert \"prefix_hash\" in d"'

check "Compile Endpoint (With Barrier)" \
    'curl -s -X POST '"$HOST"'/v1/compile -H "Content-Type: application/json" -H "X-Trace-Id: test-002" -d '\''{"blocks":[{"content":"Tool","volatility":{"score":1,"reason":"tool"},"role":"tool"},{"content":"<callosum-barrier>","volatility":{"score":0,"reason":"barrier"},"role":"system","contains_barrier":true},{"content":"User","volatility":{"score":10,"reason":"user"},"role":"user"}],"trace_id":"test-002"}'\'' | python3 -c "import json,sys; d=json.load(sys.stdin); assert d[\"estimated_savings\"] > 0"'

check "Stats Endpoint" \
    'curl -s --max-time 3 '"$HOST"'/v1/usage-stats | python3 -c "import json,sys; d=json.load(sys.stdin); assert \"total_requests\" in d"'

check "Stats By Namespace" \
    'curl -s --max-time 3 "'"$HOST"'/v1/usage-stats?namespace=test" | python3 -c "import json,sys; d=json.load(sys.stdin); assert \"by_namespace\" in d"'

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
