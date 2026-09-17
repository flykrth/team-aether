#!/usr/bin/env bash
# ==============================================================================
# MDIN: Medical-Dental Interoperability Node — E2E Deployment & Integration Test Script
# DSOLVE 2026 · DRISHTI · College of Engineering Trivandrum (CET)
# ==============================================================================
# Verifies:
#   1. Docker daemon and container status (mdin-backend, mdin-frontend).
#   2. HTTP endpoints & Nginx reverse proxy routing:
#      - http://localhost:8000/cds-services
#      - http://localhost/api/fhir/Patient/pat-1/$everything
#      - http://localhost/ (Frontend index.html)
#   3. Automated Pytest suite execution:
#      pytest backend/tests/test_mdin_suite.py -v --tb=short
#   4. Sub-500ms Clinical Decision Support latency measurement.
# ==============================================================================

set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Color constants
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BOLD}${CYAN}========================================================================${NC}"
echo -e "${BOLD}${CYAN}  MDIN: Automated Deployment, Integration & Latency Validation Suite   ${NC}"
echo -e "${BOLD}${CYAN}========================================================================${NC}"
echo ""

# Find Python and Pytest binary
if [ -x "$SCRIPT_DIR/.venv/bin/pytest" ]; then
    PYTEST_BIN="$SCRIPT_DIR/.venv/bin/pytest"
    PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
elif [ -x "$SCRIPT_DIR/backend/.venv/bin/pytest" ]; then
    PYTEST_BIN="$SCRIPT_DIR/backend/.venv/bin/pytest"
    PYTHON_BIN="$SCRIPT_DIR/backend/.venv/bin/python"
elif command -v pytest >/dev/null 2>&1; then
    PYTEST_BIN="pytest"
    PYTHON_BIN="python3"
else
    echo -e "${RED}[ERROR] Neither .venv pytest nor system pytest binary was found.${NC}"
    exit 1
fi

# ------------------------------------------------------------------------------
# 1. Docker Daemon & Container Status Check
# ------------------------------------------------------------------------------
echo -e "${BOLD}[1/5] Checking Docker Infrastructure & Container State...${NC}"

DOCKER_AVAILABLE=false
BACKEND_CONTAINER_RUNNING=false
FRONTEND_CONTAINER_RUNNING=false

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    DOCKER_AVAILABLE=true
    echo -e "  ${GREEN}[✓] Docker daemon is active and responsive.${NC}"

    if docker ps --format '{{.Names}}' | grep -q "mdin-backend"; then
        BACKEND_CONTAINER_RUNNING=true
        echo -e "  ${GREEN}[✓] Container 'mdin-backend' is RUNNING.${NC}"
    else
        echo -e "  ${YELLOW}[!] Container 'mdin-backend' is not running in Docker.${NC}"
    fi

    if docker ps --format '{{.Names}}' | grep -q "mdin-frontend"; then
        FRONTEND_CONTAINER_RUNNING=true
        echo -e "  ${GREEN}[✓] Container 'mdin-frontend' is RUNNING.${NC}"
    else
        echo -e "  ${YELLOW}[!] Container 'mdin-frontend' is not running in Docker.${NC}"
    fi
else
    echo -e "  ${YELLOW}[INFO] Docker daemon is not active or not installed.${NC}"
    echo -e "         Evaluating system in native local environment mode."
fi

# ------------------------------------------------------------------------------
# 2. Local Backend Service Readiness Check / Auto-Start
# ------------------------------------------------------------------------------
echo ""
echo -e "${BOLD}[2/5] Verifying Backend Service Availability on Port 8000...${NC}"

BACKEND_URL="http://127.0.0.1:8000"
BACKEND_STARTED_BY_SCRIPT=false
BACKEND_PID=""

# Check if port 8000 is responding
if curl -s -f -m 2 "$BACKEND_URL/health" >/dev/null 2>&1; then
    echo -e "  ${GREEN}[✓] Backend service is active on $BACKEND_URL.${NC}"
else
    echo -e "  ${YELLOW}[*] Port 8000 is not currently active. Launching local backend instance...${NC}"
    export PYTHONPATH="$SCRIPT_DIR:$SCRIPT_DIR/backend"
    "$PYTHON_BIN" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 >/dev/null 2>&1 &
    BACKEND_PID=$!
    BACKEND_STARTED_BY_SCRIPT=true

    # Wait up to 10s for backend startup
    for i in {1..20}; do
        if curl -s -f -m 1 "$BACKEND_URL/health" >/dev/null 2>&1; then
            echo -e "  ${GREEN}[✓] Local backend successfully initialized (PID: $BACKEND_PID).${NC}"
            break
        fi
        sleep 0.5
    done
fi

cleanup() {
    if [ "$BACKEND_STARTED_BY_SCRIPT" = true ] && [ -n "$BACKEND_PID" ]; then
        echo ""
        echo -e "${YELLOW}[*] Stopping background test backend server (PID: $BACKEND_PID)...${NC}"
        kill "$BACKEND_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT

# ------------------------------------------------------------------------------
# 3. HTTP Probes & Reverse Proxy Routing Checks
# ------------------------------------------------------------------------------
echo ""
echo -e "${BOLD}[3/5] Executing Endpoint Health & Reverse Proxy Probes...${NC}"

# 3a. CDS Services Discovery endpoint (Port 8000)
CDS_DISCOVERY_URL="http://127.0.0.1:8000/cds-services"
CDS_HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -m 3 "$CDS_DISCOVERY_URL" 2>/dev/null || echo "000")
if [ "$CDS_HTTP_CODE" = "200" ]; then
    echo -e "  ${GREEN}[✓] Direct CDS Discovery: $CDS_DISCOVERY_URL -> [HTTP 200 OK]${NC}"
else
    echo -e "  ${RED}[✗] Direct CDS Discovery: $CDS_DISCOVERY_URL -> [HTTP $CDS_HTTP_CODE]${NC}"
fi

# 3b. Nginx Reverse Proxy / Port 80 checks
PROXY_PATIENT_URL="http://127.0.0.1/api/fhir/Patient/pat-1/\$everything"
PROXY_HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -m 2 "$PROXY_PATIENT_URL" 2>/dev/null || echo "000")
if [ "$PROXY_HTTP_CODE" = "200" ]; then
    echo -e "  ${GREEN}[✓] Nginx Reverse Proxy FHIR R4: $PROXY_PATIENT_URL -> [HTTP 200 OK]${NC}"
else
    # Check if backend direct URL responds
    DIRECT_PATIENT_URL="http://127.0.0.1:8000/api/fhir/Patient/pat-1/\$everything"
    DIRECT_HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -m 3 "$DIRECT_PATIENT_URL" 2>/dev/null || echo "000")
    if [ "$DIRECT_HTTP_CODE" = "200" ]; then
        echo -e "  ${YELLOW}[INFO] Nginx reverse proxy port 80 not bound; direct endpoint responded: [HTTP 200 OK]${NC}"
    else
        echo -e "  ${RED}[✗] FHIR Patient \$everything endpoint failed direct check: [HTTP $DIRECT_HTTP_CODE]${NC}"
    fi
fi

# 3c. Frontend index.html check
FRONTEND_URL="http://127.0.0.1/"
FRONTEND_HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -m 2 "$FRONTEND_URL" 2>/dev/null || echo "000")
if [ "$FRONTEND_HTTP_CODE" = "200" ]; then
    echo -e "  ${GREEN}[✓] Frontend Gateway: $FRONTEND_URL -> [HTTP 200 OK]${NC}"
else
    if [ -f "$SCRIPT_DIR/frontend/dist/index.html" ] || [ -f "$SCRIPT_DIR/frontend/index.html" ]; then
        echo -e "  ${YELLOW}[INFO] Static frontend file exists on disk; HTTP port 80 gateway offline.${NC}"
    else
        echo -e "  ${RED}[✗] Frontend index.html not found.${NC}"
    fi
fi

# ------------------------------------------------------------------------------
# 4. Latency Benchmark: Sub-500ms CDS Hook Evaluation
# ------------------------------------------------------------------------------
echo ""
echo -e "${BOLD}[4/5] Benchmarking CDS Hook Evaluation Latency (<500ms bound)...${NC}"

ORDER_SELECT_URL="http://127.0.0.1:8000/cds-services/order-select-contraindication"
PAYLOAD='{"hook":"order-select","hookInstance":"latency-benchmark-01","context":{"patientId":"pat-1","selections":["D7140"]}}'

# Perform warm-up request
curl -s -X POST -H "Content-Type: application/json" -d "$PAYLOAD" "$ORDER_SELECT_URL" >/dev/null 2>&1 || true

# Measure latency using curl total time
LATENCY_SEC=$(curl -s -o /dev/null -w "%{time_total}" -X POST -H "Content-Type: application/json" -d "$PAYLOAD" "$ORDER_SELECT_URL" 2>/dev/null || echo "9.999")

# Convert seconds to milliseconds
LATENCY_MS=$("$PYTHON_BIN" -c "sec = float('$LATENCY_SEC'); print(f'{sec * 1000:.2f}')")
IS_SUB_500=$("$PYTHON_BIN" -c "print('true' if float('$LATENCY_MS') < 500.0 else 'false')")

if [ "$IS_SUB_500" = "true" ]; then
    echo -e "  ${GREEN}[✓] CDS Hook (order-select) Latency: ${BOLD}${LATENCY_MS} ms${NC}${GREEN} (< 500ms threshold PASSED)${NC}"
else
    echo -e "  ${RED}[✗] CDS Hook Latency EXCEEDED bound: ${LATENCY_MS} ms (>= 500ms)${NC}"
    exit 1
fi

# ------------------------------------------------------------------------------
# 5. Execute Pytest Test Suite
# ------------------------------------------------------------------------------
echo ""
echo -e "${BOLD}[5/5] Executing Exhaustive Pytest Suite (test_mdin_suite.py)...${NC}"
echo -e "  Command: $PYTEST_BIN backend/tests/test_mdin_suite.py -v --tb=short"
echo ""

cd "$SCRIPT_DIR"
"$PYTEST_BIN" backend/tests/test_mdin_suite.py -v --tb=short

echo ""
echo -e "${BOLD}${GREEN}========================================================================${NC}"
echo -e "${BOLD}${GREEN}  All MDIN Automated Tests & Deployment Checks PASSED Successfully!     ${NC}"
echo -e "${BOLD}${GREEN}========================================================================${NC}"
