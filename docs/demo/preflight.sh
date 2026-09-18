#!/usr/bin/env bash
# Pre-flight check before a demo. Read-only: it changes nothing.
#   ./docs/demo/preflight.sh              (backend on :8080, frontend on :5173)
#   API=http://localhost:8000 ./docs/demo/preflight.sh
API="${API:-http://localhost:8080}"
WEB="${WEB:-http://localhost:5173}"
PY="$(command -v python3)"
ok()   { printf "  \033[32mOK\033[0m    %s\n" "$1"; }
warn() { printf "  \033[33mWARN\033[0m  %s\n" "$1"; }
fail() { printf "  \033[31mFAIL\033[0m  %s\n" "$1"; FAILED=1; }
get()  { curl -s -m 8 "$API$1"; }

echo "Backend  $API"
[ "$(curl -s -m 5 -o /dev/null -w '%{http_code}' "$API/health")" = "200" ] && ok "backend is up" || { fail "backend not reachable: cd backend && python run.py"; exit 1; }

echo "Frontend $WEB"
[ "$(curl -s -m 5 -o /dev/null -w '%{http_code}' "$WEB/")" = "200" ] && ok "frontend is up" || fail "frontend not reachable: cd frontend && npm run dev"

echo "AI assistant"
get /api/assistant/status | "$PY" -c '
import json,sys
d=json.load(sys.stdin)
print("  OK    master model configured (%s)" % d.get("provider") if d.get("configured") else "  FAIL  no AI key: add GEMINI_API_KEY to backend/.env and restart")
for name,p in (d.get("providers") or {}).items():
    print("  %s  provider %-7s %s" % ("OK  " if p["configured"] else "--  ", name, "configured" if p["configured"] else "no key (optional)"))
s=d.get("speech") or {}
print("  OK    server speech-to-text configured" if s.get("configured") else "  WARN  no speech key: the mic falls back to browser dictation (works in Chrome)")
print("  OK    %d assistant tools" % len(d.get("tools",[])))'

echo "Coverage recovery"
get "/api/coverage/sources?region=US" | "$PY" -c '
import json,sys
d=json.load(sys.stdin); src=d["sources"]; cached=[s for s in src if s["cached"]]; bad=[s for s in src if s.get("error")]
print("  %s  %d of %d published policies downloaded" % ("OK  " if len(cached)==len(src) else "FAIL", len(cached), len(src)) + ("" if len(cached)==len(src) else "  -> press Refresh sources on the Coverage recovery page"))
for s in bad: print("  WARN  %s: %s" % (s["id"], s["error"]))
old=[s for s in cached if (s.get("age_days") or 0) > 30]
if old: print("  WARN  %d sources are older than 30 days: consider Refresh sources" % len(old))
i=d["index"]
if i["mode"]=="semantic" and i["state"]=="done": print("  OK    semantic index complete (%d passages, %s)" % (i["indexed"], i.get("embedding_model")))
elif i["mode"]=="semantic": print("  WARN  semantic index %d of %d: still usable, finishes in the background after Refresh sources" % (i["indexed"], i["total"]))
else: print("  WARN  keyword search only (no embedding key): works, slightly less precise")
print("  OK    insurers in the library: " + ", ".join(d["insurers"]))'

echo "Demo patients"
get /api/records/patients | "$PY" -c '
import json,sys
ids={p["patient_id"]:p["name"] for p in json.load(sys.stdin)}
for need in ("CS-9921","CS-2001","CS-2002"):
    print("  %s  %s %s" % ("OK  " if need in ids else "FAIL", need, ids.get(need, "missing: delete backend/app/data/runtime_registry.json and restart")))
extra=[n for i,n in ids.items() if i.startswith("CS-3")]
if extra: print("  --    patients added at runtime: " + ", ".join(extra) + " (keep them, or remove any rehearsal leftovers in Manual > Patients)")'

echo "Sample files"
for f in margaret_ellis_discharge_summary.pdf daniel_okafor_cardiology_letter.pdf plans/01_PPO_oral_surgery_covered.pdf plans/02_HMO_impacted_teeth_excluded.pdf; do
  [ -f "$(dirname "$0")/$f" ] && ok "$f" || fail "$f is missing"
done
[ -z "$FAILED" ] && echo && echo "Ready." || { echo; echo "Fix the FAIL lines above first."; exit 1; }
