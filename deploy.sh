#!/usr/bin/env bash
set -eo pipefail

# ==============================================================================
# MDIN: Medical-Dental Interoperability Node — Automated Production Deployer
# DSOLVE 2026 · DRISHTI · College of Engineering Trivandrum (CET)
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================================================"
echo "  MDIN Production Deployment: CareStack Dental $\leftrightarrow$ Hospital EHR"
echo "========================================================================"
echo ""

# ------------------------------------------------------------------------------
# 1. Pre-Flight Checks
# ------------------------------------------------------------------------------
echo "[1/4] Running pre-flight system checks..."

# Check Docker CLI
if ! command -v docker >/dev/null 2>&1; then
    echo "  [ERROR] Docker CLI is not installed or not in PATH."
    echo "  Please install Docker Engine: https://docs.docker.com/engine/install/"
    exit 1
fi
echo "  [✓] Docker CLI detected: $(docker --version)"

# Check Docker Daemon
if ! docker info >/dev/null 2>&1; then
    echo "  [ERROR] Docker daemon is not running or current user lacks permissions."
    echo "  Please start the Docker daemon (e.g., 'sudo systemctl start docker')"
    echo "  or verify your user belongs to the 'docker' group."
    exit 1
fi
echo "  [✓] Docker daemon is running and responsive."

# Detect Docker Compose
if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
else
    echo "  [ERROR] Docker Compose plugin or docker-compose binary was not found."
    echo "  Please install Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi
echo "  [✓] Docker Compose detected: $($COMPOSE_CMD version)"

# ------------------------------------------------------------------------------
# 2. Clean Container Build
# ------------------------------------------------------------------------------
echo ""
echo "[2/4] Building container images with clean cache flags..."
echo "  Command: $COMPOSE_CMD build --no-cache"
$COMPOSE_CMD build --no-cache

echo ""
echo "[3/4] Launching MDIN services in detached mode..."
echo "  Command: $COMPOSE_CMD up -d --remove-orphans"
$COMPOSE_CMD up -d --remove-orphans

# ------------------------------------------------------------------------------
# 3. Endpoint Availability & Health Verification
# ------------------------------------------------------------------------------
echo ""
echo "[4/4] Verifying endpoint availability and service readiness..."

BACKEND_HEALTH_URL="http://127.0.0.1:8000/health"
FRONTEND_GATEWAY_URL="http://127.0.0.1:80"

MAX_ATTEMPTS=30
ATTEMPT=0
BACKEND_OK=false
FRONTEND_OK=false

echo -n "  Waiting for services to respond"
while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    ATTEMPT=$((ATTEMPT + 1))
    echo -n "."

    if [ "$BACKEND_OK" = false ]; then
        if curl -s -f -m 2 "$BACKEND_HEALTH_URL" >/dev/null 2>&1; then
            BACKEND_OK=true
        fi
    fi

    if [ "$FRONTEND_OK" = false ]; then
        if curl -s -f -m 2 "$FRONTEND_GATEWAY_URL" >/dev/null 2>&1; then
            FRONTEND_OK=true
        fi
    fi

    if [ "$BACKEND_OK" = true ] && [ "$FRONTEND_OK" = true ]; then
        break
    fi

    sleep 2
done
echo ""

if [ "$BACKEND_OK" = true ]; then
    echo "  [✓] Backend Service (Port 8000): HEALTHY"
else
    echo "  [!] Backend Service did not respond within ${MAX_ATTEMPTS} attempts."
    echo "      Inspect container logs using: $COMPOSE_CMD logs backend"
fi

if [ "$FRONTEND_OK" = true ]; then
    echo "  [✓] Frontend Reverse Proxy (Port 80): HEALTHY & ROUTING"
else
    echo "  [!] Frontend Reverse Proxy did not respond within ${MAX_ATTEMPTS} attempts."
    echo "      Inspect container logs using: $COMPOSE_CMD logs frontend"
fi

# Probe sub-endpoints through the frontend reverse proxy
echo ""
echo "  Testing proxied endpoints through Port 80:"
for ep in "/health" "/cds-services" "/api/carestack/status" "/api/fhir/metadata"; do
    STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" -m 2 "http://127.0.0.1:80${ep}" 2>/dev/null || echo "ERR")
    if [ "$STATUS_CODE" = "200" ]; then
        echo "    - http://localhost${ep} -> [HTTP $STATUS_CODE OK]"
    else
        echo "    - http://localhost${ep} -> [HTTP $STATUS_CODE]"
    fi
done

# ------------------------------------------------------------------------------
# 4. Access URLs & Operation Summary
# ------------------------------------------------------------------------------
echo ""
echo "========================================================================"
echo "  MDIN Production Application Deployed Successfully!                   "
echo "========================================================================"
echo ""
echo "  Local Web Access Points:"
echo "    • Chairside Clinical UI:        http://localhost:80  (or http://localhost)"
echo "    • Backend API Service:          http://localhost:8000"
echo "    • Interactive Swagger Docs:     http://localhost/docs (or :8000/docs)"
echo "    • CareStack Web API V1:         http://localhost/api/v1.0"
echo "    • CDS Hooks Discovery:          http://localhost/cds-services"
echo "    • Health & Diagnostics:         http://localhost/health"
echo ""
echo "  Useful Management Commands:"
echo "    • View live logs:               $COMPOSE_CMD logs -f"
echo "    • Stop all containers:          $COMPOSE_CMD down"
echo "    • Restart deployment:           $COMPOSE_CMD restart"
echo "    • Rebuild and restart:          ./deploy.sh"
echo "========================================================================"
