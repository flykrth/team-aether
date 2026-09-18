# Coverage recovery: check it, then demo it

Run against the real published payer policies and a real model. Patients and plan documents are fictional.

**What was verified, honestly:** cases 2 to 8 and "dental benefit active" gave the documented result on the live server
with John Doe. Case 1 gave the documented result on a patient with no medical history, and cases 7 and 8 were each
repeated three times with the same outcome. After the last rule change (policy sections treated as alternative routes)
case 1 was **not** re-run on John Doe before this was written. A language model picks the sentences, so rehearse the
list once yourself; if a result differs, open **Passages that were read** to see why, and tell me rather than trusting
this table.

## 1. Start and check (2 minutes)

```bash
# terminal 1
cd backend && source ../.venv/bin/activate && python run.py          # this machine serves on :8080
# terminal 2
cd frontend && npm run dev                                          # http://localhost:5173
# terminal 3: one command that checks everything, read-only
./docs/demo/preflight.sh
```

`preflight.sh` checks: backend and frontend up, AI key present, 12 of 12 payer policies downloaded, the search index,
the seeded patients, and the sample files. It prints `Ready.` or tells you exactly what to fix.
(If your backend is on port 8000: `API=http://localhost:8000 ./docs/demo/preflight.sh`.)

**First run on a new machine:** the policy library is not in git (payer documents are copyrighted). Open
*Manual → Coverage recovery* and press **Refresh sources**. Downloading takes seconds; the semantic index then builds in
the background at the free tier's 100 passages per minute (about 6 minutes). Search works while it builds.

### Check it without the UI

```bash
API=http://localhost:8080
curl -s "$API/api/coverage/sources?region=US" | python3 -m json.tool | head -40     # library, ages, index
curl -s -X PUT "$API/api/coverage/patients/CS-2001/insurance" -H 'Content-Type: application/json' \
  -d '{"dental":{"status":"exhausted"},"medical":{"insurer":"Aetna","plan_type":"PPO","plan_name":"Open Access PPO"}}'
curl -s -X POST "$API/api/coverage/analyze" -H 'Content-Type: application/json' -d '{
  "patient_id":"CS-2001","region":"US","procedure":"porcelain crown on tooth 30",
  "clinical_note":"Fractured cusp, needs a full coverage crown."}' \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); print(r["determination"]["headline"]); [print(" -",c["kind"],"|",c["quote"][:110],"|",c["source"]["insurer"]) for c in r["criteria"]]'
# expected: "No medical pathway" with Aetna exclusion quote(s)
cd backend && python -m pytest tests/test_coverage_recovery.py -q                  # no network needed
```

## 2. Set up the patient (30 seconds)

*Manual → Coverage recovery*, pick **John Doe** (or add a fresh patient in *Patients* if you want a chart with no
medical history), then in **Insurance**:
Dental benefit **Annual maximum used up** · Medical insurer **Aetna** · Plan type **PPO**.

## 3. The cases, in demo order

Paste the text exactly. Column 4 is what you should see; if you see something else, that is a bug worth telling me about.

| # | Procedure | Clinical note | Expected result | The point to make |
| :- | :--- | :--- | :--- | :--- |
| 1 | `D7240 removal of completely bony impacted third molar` (diagnosis: `impacted mandibular third molar K01.1`) | `Completely bony impacted lower right third molar on panoramic radiograph. Recurrent pericoronitis with facial swelling, three episodes this year. No trauma.` | **Potential medical pathway · plan not verified** | A genuine indication. It quotes Aetna, links the policy and shows its review date. It will not say "covered" and says the plan is unchecked. |
| 2 | `porcelain crown on tooth 30` | `Fractured cusp, needs a full coverage crown.` | **No medical pathway** | Routine care gets a clear no, in Aetna's own words ("root canals, fillings, crowns, bridges"). |
| 3 | `surgical extraction of tooth 19` | `Non-restorable tooth 19. Patient had a coronary stent placed 8 months ago and takes clopidogrel and aspirin.` | **No medical pathway** | The trap. A risky medical history is not a medical indication. An earlier version of this project got this wrong; it was deleted. |
| 4 | `open reduction of mandibular fracture` (diagnosis: `fracture of mandible`) | `Patient was assaulted two days ago. CT shows a displaced fracture of the mandibular body.` | **Potential medical pathway · plan not verified** | "Reduction of any facial bone fractures is covered under all Aetna medical plans." |
| 5 | `TMJ arthrocentesis` (diagnosis: `temporomandibular joint disorder, internal derangement`) | `Painful TMJ with internal derangement on MRI. Six months of splint therapy and physical therapy have failed.` | **Needs human review** | The policy has conditions the note does not answer. It lists exactly what the chart must say instead of guessing. |
| 6 | `D7240 removal of impacted third molar` | `Impacted third molar.` | **Needs human review** | Same tooth as case 1 with a lazy note: it refuses to assume the missing facts. Good documentation is what creates the pathway. |

### The plan-level check (the part most tools skip)

Still on case 1's text:

| # | Do this | Expected result | The point to make |
| :- | :--- | :--- | :--- |
| 7 | Upload `plans/01_PPO_oral_surgery_covered.pdf` as the plan document, run case 1 again | **Potential medical pathway** (no "plan not verified"), with quotes tagged *Member's own plan* | Now it has read this patient's actual plan. |
| 8 | Remove it, set Plan type **HMO**, upload `plans/02_HMO_impacted_teeth_excluded.pdf`, run case 1 again | **No medical pathway**: "The member's own plan document excludes this" | Same patient, same tooth, same insurer, different plan, opposite answer. The plan outranks the insurer's general policy. |
| 9 | Set Region to **United Kingdom**, run again | "UK is not supported yet", nothing guessed | It says what it cannot do. Set Region back to United States afterwards. |
| 10 | Set Dental benefit to **Active**, run again | **Use the dental benefit**, two steps only | It never goes looking for a medical route when the dental benefit can pay. (This check runs first, before region or anything else.) |

More plan documents (TMJ covered, TMJ excluded, Medicare Advantage "integral to medical treatment", and a thin SBC that
does not answer the question) are in [`plans/`](plans/README.md). Those four were generated without being run through the app.

### Finish: the document
Back on case 7 (potential pathway): type a reviewer name, press **Create and file to chart**. Show the first lines:
"This is a request for a determination before treatment, **not a claim**", the payer quote with its link, and
"procedure coding to be confirmed by a certified coder". Clear the name: the button disables. No sign-off, no document.

Then scroll to **Policy library**: each source, its review date, how old our copy is.

## 4. What to say if pushed

- **"Is any coverage rule hardcoded?"** No. `backend/app/data/coverage_sources.json` holds URLs only. Open it on screen.
- **"What if the AI makes something up?"** The server checks every quote against the downloaded document, word for
  word (an ellipsis is allowed only if every piece is verbatim and in order). Anything else is discarded and the screen
  says how many were discarded. `backend/tests/test_coverage_recovery.py` has a test where the model invents
  "All oral surgery is always covered": it is dropped and cannot create a pathway.
- **"Why not just say covered?"** Because only the payer decides. Aetna's own policy tells members to get a
  pre-treatment estimate for oral surgery; that is the document this produces.
- **"What is simulated?"** Dental benefit status is typed in by staff (a real office would get it from an X12 270/271
  eligibility check). The plan PDFs here are fictional samples. The insurer policies are the real published documents.
- **"Does it work outside the US?"** Not yet, and it says so. The UK (NHS / private dental / private medical) and
  Australia (Medicare / hospital / extras) are different decision trees, not different data.

## 5. If something goes wrong live

| Symptom | Cause | Fix |
| :--- | :--- | :--- |
| Every case says "Needs human review" and no quotes appear | No AI key, or the provider is down | Check `preflight.sh`. The **Passages that were read** section still shows the right policy text, which is itself a fair demo of "no model, no verdict". |
| "0 of 12 published policies" | Fresh machine, or the cache folder was deleted | Press **Refresh sources** |
| A source shows a red warning | The insurer moved or blocked the URL | The last good copy keeps working. Fix the URL in `coverage_sources.json`. |
| Results differ slightly between runs | The model picks different sentences to quote | The outcome is computed by fixed rules from verified quotes; the plan-document cases were checked three times each with the same outcome. |
| A result surprises you | | Open **Passages that were read**: you can see exactly what text it had to work with. |
| Left-over test patients | Earlier rehearsals | Manual → Patients → trash icon, or delete `backend/app/data/runtime_registry.json` and restart |
