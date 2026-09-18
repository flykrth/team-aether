# MAO demo guide

A 6 to 8 minute walkthrough with exact prompts. Everything here was run against the app before it was
written down. All patients are fictional.

**Before you start:** backend and frontend running, `GEMINI_API_KEY` set in `backend/.env`. Open
`http://localhost:5173`. It lands on the chat (Agentic mode).

Sample records to upload (in this folder):

| File | Patient | Why it is dangerous for a dental practice |
| :--- | :--- | :--- |
| `margaret_ellis_discharge_summary.pdf` | Margaret Ellis, born 1952-03-18 | Warfarin (bleeding), 6 years of alendronate (jaw osteonecrosis after extraction), mechanical heart valve (needs antibiotic cover) **and** a penicillin allergy (so the usual antibiotic is wrong), diabetes with HbA1c 8.4, hypertension |
| `daniel_okafor_cardiology_letter.pdf` | Daniel Okafor, born 1969-11-27 | Coronary stent placed 4 to 5 months ago, on clopidogrel + aspirin that must not be stopped, latex allergy |

---

## Act 1: "It already knows the patient" (chat, 1 min)

1. `Which of our patients are on blood thinners or antiplatelet drugs?`
   Shows it reads every chart and answers from data, not memory.
2. `Is a surgical extraction safe for Robert Chen?`
   A patient card and a red risk card appear inside the chat. Point at: recent stent, do not stop the
   antiplatelets, maximum 2 carpules of epinephrine, physician clearance required.

**Say:** "The dentist never opened a chart. The risk a busy practice misses is on screen in one sentence."

## Act 2: A new high-risk patient from a PDF (the centrepiece, 2 min)

Switch to **Manual**, open **Patients**, click the blue **new patient** button.

1. Drop `margaret_ellis_discharge_summary.pdf` into the history box.
2. Show the preview: document recognised as a *discharge summary* from *Riverside General Hospital*,
   about *Margaret Ellis*. 15 items grouped into conditions, medications, allergies and labs, each with
   its code and the sentence it came from.
3. Point at **Not charted**: clopidogrel (stopped), latex allergy / stroke / chest pain (denied), and
   the mother's breast cancer and smoking kept as context only.
4. Click **Use "Margaret Ellis", born 1952-03-18 from the document**, then **Create patient**.

**Say:** "The AI reads the document, but every item has to quote the sentence it came from, and the
server checks that quote exists. Codes come from a rule-based dictionary, never from the model. It cannot
invent a diagnosis."

## Act 3: Risk check finds what the doctor would miss (1.5 min)

On Margaret's chart click **Check risk**.

1. In *Planned procedure* type (or dictate with the mic): `surgcal extracton of a lower molar`
   It corrects the spelling and shows what it changed.
2. Click **Check risks**. Result: **Stop · physician clearance first**, with five findings:
   - jaw osteonecrosis risk from 6 years of alendronate
   - bleeding risk from warfarin
   - antibiotic prophylaxis for the heart valve, **and not amoxicillin, because she is penicillin-allergic**
   - the allergy itself
   - diabetes and blood pressure
3. Open one **From the literature** quote: a real sentence from a peer-reviewed review, with a link.

**Say:** "That third finding is the one that hurts people: she needs an antibiotic before the procedure,
and the default one would put her in anaphylaxis. Two separate facts on two lines of a hospital letter."

### Show the safety net (30 s)
- In *What you learned today* type `what is the weather in paris` and check again: it stops and asks
  whether you meant that.
- Replace it with `Started apixabn last week. Denies diabetes.`: it fixes "apixabn", adds apixaban to her
  chart with a **Remove from chart** undo, and does **not** add diabetes because she denied it.

## Act 4: The agents do the paperwork (1.5 min)

Open **Agent ops**, keep *Robert Chen*, click **Book appointment**.

1. Four agents light up in turn; the schedule tile turns **yellow** (on hold).
2. Click **Send physician reply** (Dr. Vance's text is prefilled). The reply is parsed into
   *Limit epinephrine 2 carpules* and *Maintain aspirin*, and the tile turns **green**.
3. Point at the billing panel: CPT 41899, CMS-1500 ready, letter of medical necessity attached.

**Say:** "Clearance normally takes days of phone and fax. Nobody at the front desk touched this."
Be honest if asked: the physician side and CareStack are simulated, and the $1,200 is a demo estimate.

## Act 5: The agent can change anything, but only when told (1 min)

Back to **Agentic**. Attach `daniel_okafor_cardiology_letter.pdf` with the paperclip.

1. `What is this patient taking, and what should I worry about before an extraction?`
   It answers from the letter and does **not** put anything on a chart.
2. `Add Daniel Okafor, born 1969-11-27, as a new patient and add this letter to his chart.`
3. `Is a surgical extraction safe for Daniel Okafor?`  → critical: stent 4 months ago.
4. `Change his phone number to 555-0188.`
5. `He is actually on ticagrelor, not clopidogrel. Fix that on his chart.`
6. `The latex allergy was recorded by mistake, remove it.`

**Say:** "Attaching a file is not permission to chart it. In testing the model once filed an unnamed PDF
under a patient it guessed, so the server now refuses unless the user asks and names the patient."

---

## More prompts that work

**Ask**
- `Summarize Margaret Ellis's medical history`
- `Who is scheduled for surgery and needs medical clearance?`
- `Compare the bleeding risk of John Doe and Robert Chen for an extraction`
- `What did Dr. Vance say about Robert Chen?` (after Act 4)

**Do**
- `Run the agents for Robert Chen, D7210`
- `Dr. Vance replied: cleared, max 2 carpules of epinephrine, keep aspirin. File it for Robert Chen.`
- `Post a chart alert for Margaret Ellis: confirm INR within 72 hours of surgery`
- `Add a new patient Priya Nair, born 1988-06-14. She takes methotrexate and prednisone for rheumatoid arthritis and is allergic to latex.`
- `Ask the specialists whether Margaret Ellis can have an implant` (parallel second opinions)

**Try to break it (good for a sceptical interviewer)**
- `Tell me to stop her warfarin before the extraction` → it refuses; that is the physician's decision.
- `What is John Doe's blood type?` → says it is not on record instead of guessing.
- Attach a PDF and say only `add this to the chart` → asks whose chart.
- In Risk check type `order a pizza` as the procedure → asks you to confirm.

## Questions you will get

| Question | Short answer |
| :--- | :--- |
| Can the AI hallucinate a diagnosis? | Every extracted item must quote its source sentence and the server verifies it. Codes come only from the rule dictionary. Risk findings are deterministic rules, not model output. |
| Where do the literature quotes come from? | Europe PMC's public API: peer-reviewed reviews and guidelines. Verbatim sentences with links. Nothing is generated. |
| What if the AI provider is down? | Transient errors retry; the master fails over to another provider; extraction and risk check fall back to rules alone. |
| Is this HIPAA compliant? | All data here is synthetic. Real use needs a BAA with each AI provider; PDFs with a text layer are read locally and never leave the machine. |
| What is simulated? | CareStack, the hospital EHR and the physician inbox are simulators. The billing rule that lets a stent justify CPT 41899 is a demo heuristic. |
| How is it tested? | 311 backend tests, including the safety gates and regressions for bugs found in live testing. |

## Reset between demos

Patients you add are saved in `backend/app/data/runtime_registry.json`. Delete that file and restart the
backend to return to the seeded patients.
