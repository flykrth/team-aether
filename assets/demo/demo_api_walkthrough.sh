#!/usr/bin/env bash
# ==============================================================================
# MDIN: Medical-Dental Interoperability Node for CareStack
# DSOLVE 2026 — Live API & Clinical Decision Support Demo
# ==============================================================================

set -e

# Terminal colors
BOLD='\033[1m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

API_BASE="${MDIN_API_BASE:-http://localhost:8000}"

echo -e "${BOLD}${CYAN}===================================================================${NC}"
echo -e "${BOLD}${CYAN}  MDIN: Medical-Dental Interoperability Node for CareStack         ${NC}"
echo -e "${BOLD}${CYAN}  DSOLVE 2026 Live API & Clinical Decision Support Demo           ${NC}"
echo -e "${BOLD}${CYAN}===================================================================${NC}"
echo -e "Target API Base: ${GREEN}${API_BASE}${NC}\n"

# 1. Health check
echo -e "${BOLD}${YELLOW}[1/7] Checking System Health & Interoperability Status...${NC}"
HEALTH_RESP=$(curl -s "${API_BASE}/health" || true)
if [ -z "$HEALTH_RESP" ]; then
  echo -e "${RED}ERROR: Unable to connect to MDIN backend at ${API_BASE}.${NC}"
  echo -e "Please ensure the backend is running via: ${BOLD}python backend/run.py${NC}"
  exit 1
fi
echo "$HEALTH_RESP" | python3 -m json.tool || echo "$HEALTH_RESP"
echo ""

# 2. CareStack Patients
echo -e "${BOLD}${YELLOW}[2/7] Fetching Registered CareStack Dental Patients...${NC}"
curl -s "${API_BASE}/api/carestack/patients" | python3 -c '
import sys, json
data = json.load(sys.stdin)
print("Retrieved " + str(len(data)) + " dental patients from CareStack PMS:")
for p in data:
    name = p.get("first_name", "") + " " + p.get("last_name", "")
    pid = p.get("id", "")
    mrn = p.get("mrn", "")
    procs = [pr.get("code", "") + ": " + pr.get("description", "")[:28] + "..." for pr in p.get("active_treatment_plan", [])]
    print("  • [" + pid + "] " + name + " (MRN: " + mrn + ") | Planned: " + str(procs))
'
echo ""

# 3. Webhook Check-In Simulation: John Doe
echo -e "${BOLD}${YELLOW}[3/7] Simulating CareStack Webhook Check-In for John Doe (CS-2001)...${NC}"
CHECKIN_RESP=$(curl -s -X POST "${API_BASE}/api/carestack/webhook" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "patient.checkin",
    "patient": {
      "id": "CS-2001",
      "first_name": "John",
      "last_name": "Doe",
      "birth_date": "1968-04-12",
      "gender": "male",
      "mrn": "MRN-10001"
    }
  }')
echo "$CHECKIN_RESP" | python3 -c '
import sys, json
res = json.load(sys.stdin)
conf = res.get("match_confidence", 0.0) * 100
print("Status: " + str(res.get("status")) + " | Matched EHR: " + str(res.get("matched_ehr_patient_id")) + " (" + f"{conf:.0f}" + "% confidence)")
print("Generated " + str(res.get("alerts_generated", 0)) + " high-priority chart alerts:")
for a in res.get("alerts", []):
    print("  - [" + str(a.get("alert_type", "")).upper() + "] " + str(a.get("title", "")))
'
echo ""

# 4. FHIR ConceptMap Semantic Translation ($translate)
echo -e "${BOLD}${YELLOW}[4/7] FHIR ConceptMap: Translating RxNorm Warfarin (855332) to Dental Alert...${NC}"
curl -s -X POST "${API_BASE}/api/fhir/ConceptMap/\$translate" \
  -H "Content-Type: application/json" \
  -d '{
    "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
    "code": "855332"
  }' | python3 -m json.tool
echo ""

# 5. CDS Hook: order-select on Extraction (D7140) for John Doe
echo -e "${BOLD}${YELLOW}[5/7] CDS Hook (order-select): Evaluating Extraction D7140 for John Doe...${NC}"
CDS_RESP_1=$(curl -s -X POST "${API_BASE}/cds-services/order-select-contraindication" \
  -H "Content-Type: application/json" \
  -d '{
    "hook": "order-select",
    "hookInstance": "demo-hook-001",
    "context": {
      "patientId": "patient-001",
      "procedureCode": "D7140",
      "selections": ["D7140"]
    }
  }')
echo "$CDS_RESP_1" | python3 -c '
import sys, json
cards = json.load(sys.stdin).get("cards", [])
for c in cards:
    ind = str(c.get("indicator", "")).upper()
    print("\n>>> [" + ind + "] " + str(c.get("summary", "")))
    src = c.get("source", {})
    print("Source: " + str(src.get("label", "")) + " (" + str(src.get("url", "")) + ")")
    print("Detail: " + str(c.get("detail", "")))
    for s in c.get("suggestions", []):
        print("Action Suggestion: " + str(s.get("label", "")))
'
echo ""

# 6. CDS Hook: order-select on Prophylaxis (D1110) for Jane Smith (Prosthetic Valve)
echo -e "${BOLD}${YELLOW}[6/7] CDS Hook (order-select): Evaluating Adult Prophylaxis D1110 for Jane Smith...${NC}"
CDS_RESP_2=$(curl -s -X POST "${API_BASE}/cds-services/order-select-contraindication" \
  -H "Content-Type: application/json" \
  -d '{
    "hook": "order-select",
    "hookInstance": "demo-hook-002",
    "context": {
      "patientId": "patient-002",
      "procedureCode": "D1110",
      "selections": ["D1110"]
    }
  }')
echo "$CDS_RESP_2" | python3 -c '
import sys, json
cards = json.load(sys.stdin).get("cards", [])
for c in cards:
    ind = str(c.get("indicator", "")).upper()
    print("\n>>> [" + ind + "] " + str(c.get("summary", "")))
    src = c.get("source", {})
    print("Source: " + str(src.get("label", "")) + " (" + str(src.get("url", "")) + ")")
    print("Detail: " + str(c.get("detail", "")))
    for s in c.get("suggestions", []):
        print("Action Suggestion: " + str(s.get("label", "")))
'
echo ""

# 7. CDS Hook: patient-view on Robert Taylor (Uncontrolled Diabetes HbA1c 9.2%)
echo -e "${BOLD}${YELLOW}[7/7] CDS Hook (patient-view): Evaluating Systemic Risk for Robert Taylor...${NC}"
CDS_RESP_3=$(curl -s -X POST "${API_BASE}/cds-services/patient-view-alert" \
  -H "Content-Type: application/json" \
  -d '{
    "hook": "patient-view",
    "hookInstance": "demo-hook-003",
    "context": {
      "patientId": "patient-003"
    }
  }')
echo "$CDS_RESP_3" | python3 -c '
import sys, json
cards = json.load(sys.stdin).get("cards", [])
for c in cards:
    ind = str(c.get("indicator", "")).upper()
    print("\n>>> [" + ind + "] " + str(c.get("summary", "")))
    src = c.get("source", {})
    print("Source: " + str(src.get("label", "")) + " (" + str(src.get("url", "")) + ")")
    print("Detail: " + str(c.get("detail", "")))
'
echo ""

echo -e "${BOLD}${GREEN}===================================================================${NC}"
echo -e "${BOLD}${GREEN}  All 7 Demonstration Flows Executed Successfully!                 ${NC}"
echo -e "${BOLD}${GREEN}  Open http://localhost:5173 to test in the Split-Screen Web UI.  ${NC}"
echo -e "${BOLD}${GREEN}===================================================================${NC}"
