#!/usr/bin/env bash
# End-to-end smoke test of a running API.  Usage: scripts/smoke_test.sh [BASE_URL]
# Exits non-zero (with a clear message) on the first failed check.
set -euo pipefail
BASE_URL="${1:-http://localhost:8000}"
WAIT_SECONDS="${WAIT_SECONDS:-90}"

pass() { echo "  [PASS] $*"; }
fail() { echo "  [FAIL] $*" >&2; exit 1; }

echo "Smoke test against ${BASE_URL}"

for ((i = 0; i < WAIT_SECONDS; i += 2)); do
  if curl -fsS "${BASE_URL}/health" >/dev/null 2>&1; then break; fi
  sleep 2
done
curl -fsS "${BASE_URL}/health" | grep -q '"status":"healthy"' || fail "/health not healthy after ${WAIT_SECONDS}s"
pass "/health"

curl -fsS "${BASE_URL}/model-info" | grep -q 'model_name' || fail "/model-info"
pass "/model-info"

PAYLOAD='{"age":63,"sex":1,"cp":1,"trestbps":145,"chol":233,"fbs":1,"restecg":2,"thalach":150,"exang":0,"oldpeak":2.3,"slope":3,"ca":0,"thal":6}'
RESP="$(curl -fsS -X POST "${BASE_URL}/predict" -H 'Content-Type: application/json' -d "${PAYLOAD}")"
echo "  response: ${RESP}"
python3 - "$RESP" <<'PY' || fail "/predict response invalid"
import json, sys
r = json.loads(sys.argv[1])
assert r["prediction"] in (0, 1)
assert 0.5 <= r["confidence"] <= 1 and 0 <= r["probability_disease"] <= 1
PY
pass "/predict returns prediction + confidence"

CODE="$(curl -s -o /dev/null -w '%{http_code}' -X POST "${BASE_URL}/predict" -H 'Content-Type: application/json' -d '{"age": 63}')"
[ "${CODE}" = "422" ] || fail "invalid payload should return 422, got ${CODE}"
pass "invalid input rejected (422)"

curl -fsS "${BASE_URL}/metrics" | grep -q 'heart_predictions_total' || fail "/metrics missing heart_predictions_total"
pass "/metrics exposes prediction counters"

echo "All smoke tests passed."
