# Pitch deck content: CareStack MAO

Slide text, ready to paste. Keep each slide to what is written here: the detail belongs in your voice, not on the slide.
Every number has a source at the bottom. Anything marked **[team]** is something only your team can fill in truthfully.

---

## Slide 1. Title

**CareStack MAO**
The medical-dental co-pilot that catches what the dental chart cannot see.

Team Aether · DSOLVE 2026 · [team: names]

---

## Slide 2. Introduction

**A dentist treats the mouth. The risk lives in the rest of the body.**

- A patient's heart stent, blood thinner or bone drug sits in a hospital record the dental office never sees.
- The dental chart and the medical record are two separate worlds, joined today by phone calls and fax.
- MAO connects them inside CareStack: it reads the medical history, checks the planned procedure against it, gets the
  physician's clearance, and answers the insurance question honestly.

*Say:* "One patient, one tooth, one missing piece of information. That is the whole problem."

---

## Slide 3. What the project does

- **Brings the medical history into the dental visit.** Add a patient by typing, talking, or uploading an old record
  as a PDF. The system reads it and files conditions, medications and allergies with standard codes.
- **Warns before the procedure, not after.** Type the planned treatment in plain words; it flags what a busy dentist
  could miss (bleeding risk, jaw-bone risk, the wrong antibiotic for an allergic patient) and backs it with published research.
- **Handles the physician clearance.** It finds the patient's doctor, sends the request, and turns the doctor's
  free-text reply into clear restrictions on the chart.
- **Answers "who pays?" truthfully.** If dental benefits cannot pay, it checks the insurer's own published policy for
  a genuine medical route and shows the exact wording. It also says "no" when the answer is no.
- **For CareStack:** turns a system that records care into one that actively protects patients and practices, in one
  guided workflow or entirely by chat and voice.

---

## Slide 4. The problem today

- **Two record systems that do not talk.** Most dental software stores teeth, x-rays and procedure codes; it was never
  built to read a medical record. Few integrated medical-dental records exist outside large health systems.
- **Dentists want the data and cannot get it.** In one study of clinics sharing a building with medical providers,
  100% of dental providers wanted to see patients' medical information; fewer than half could even use the shared system.
- **The risk is common, not rare.** About 8 million Americans take blood thinners. In published dental clinic studies,
  16% to 46% of patients had a relevant medical condition.
- **Patients forget or do not know.** Medical history comes from a paper form filled in a waiting room.
- **Clearance is slow.** A physician's sign-off means phone tag and fax, often days, while the chair sits empty.
- **Dental benefits run out fast.** The typical annual maximum is $1,000 to $1,500 and has barely moved in decades;
  about 12% of insured adults hit it (14% over age 55).
- **Nobody checks the medical route properly.** Some oral surgery genuinely belongs to medical insurance (jaw
  fractures, tumors, some impacted teeth, TMJ, sleep apnea). Front desks either never check, or guess.

**How we researched it**
- Read the insurers' own published policies end to end: Aetna, Cigna, UnitedHealthcare, two Blue Cross plans, Medicare.
- Read the clinical literature on dental treatment for patients on blood thinners, antiplatelets and bone drugs.
- Studied the standards the industry already uses: HL7 FHIR, CDS Hooks, CDT / CPT / ICD-10 coding.
- [team: add anything you actually did, e.g. dentists or front-desk staff you spoke to, CareStack material you reviewed]

---

## Slide 5. Why it needs our project

- **Interoperability, not another silo.** Built on HL7 FHIR R4, the standard hospitals already expose, so medical data
  arrives as coded facts (ICD-10, RxNorm, SNOMED, LOINC), not as a scanned letter.
- **Decision support at the moment of decision.** Risk rules run when the procedure is planned, the point where a
  warning can still change what happens.
- **Deterministic where it matters.** Clinical risk comes from fixed rules, not a language model, so the same patient
  always gets the same warning and every warning can be traced to a rule.
- **AI that cannot invent facts.** Every item read from a document must quote the sentence it came from, and the server
  checks that quote exists. Codes come from a rule dictionary, never from the model.
- **Evidence attached.** Each warning carries verbatim quotes from peer-reviewed reviews (Europe PMC) with a link.
- **Insurance answers you can defend.** No coverage rule is hardcoded. The system downloads the payers' published
  policies, searches them (code matching + AI embeddings), and quotes them. It never says "covered".
- **Unstructured in, structured out.** PDFs, dictated notes and physicians' free-text replies become coded, reviewable data.
- **Safe by design.** It never tells staff to stop a medication, never clears a patient on an ambiguous reply, and asks
  before any destructive action.
- **Resilient.** Works with one AI provider or three, fails over between them, and the core checks still run with none.

---

## Slide 6. Business case

**The market**
- US dental services: about $172 to $185 billion in 2025, heading to about $211 billion by 2030.
- US dental practice-management software: roughly $0.6 to $1.0 billion in 2025, growing about 9% to 11% a year.
- Dental support organizations (DSOs), CareStack's core customers, are the fastest growing segment (about 18% a year).
- CareStack already serves more than 2,500 dental practices.

**Where the value comes from**
- **Chair time recovered:** clearance in minutes instead of days means fewer cancelled and rescheduled surgeries.
- **Liability avoided:** one prevented bleed or jaw-bone complication outweighs years of software cost.
- **Revenue kept:** when benefits run out, patients often abandon treatment. A legitimate medical route keeps the case.
- **Scale without headcount:** a DSO adds locations without adding a clearance-and-insurance clerk to each one.

**How CareStack could sell it** [team: these are options to discuss, not validated prices]
- A premium module per location per month, or included in the enterprise tier to win DSO deals.
- A differentiator against Dentrix, Curve and Open Dental: none of them brings the medical record into the visit.

*Be careful:* do not quote a revenue figure per practice. We have not measured one, and judges will ask where it came from.

---

## Slide 7. How it works

**One visit, six steps**

1. **Patient.** Add by form, by chat, by voice, or by uploading a previous record.
2. **History.** Medical record linked; every item is coded and editable.
3. **Risk check.** Type the procedure and what you learned today. Get the hazards, the precautions and the evidence.
4. **Clearance.** If the risk is critical, the physician is asked and the reply becomes restrictions on the chart.
5. **Procedure.** Carried out, marked as done. Everything said so far is carried forward.
6. **Insurance.** Dental benefit active? Bill dental. If not, check for a genuine medical pathway, in the payer's own words.

*Visual:* use the flow diagram from `docs/MAO_PLATFORM.md` section 4.9b.
*Say:* "Nobody types anything twice. What the dentist said at step 3 is what the insurance step starts from."

---

## Slide 8. The agents

| Agent | Its job | What makes it trustworthy |
| :--- | :--- | :--- |
| **Intake** | Pulls the medical record, or reads what the patient says, into coded facts | A word dictionary, not a model: it cannot invent a diagnosis |
| **Clinical Risk** | Checks the procedure against the history: blood thinners, recent stents, bone drugs, heart valves, allergies | Fixed rules; every warning names its rule |
| **Medical Clearance** | Finds the physician, sends the request, chases after 48 hours, reads the reply | An unclear or negative reply never clears the patient |
| **Coverage Recovery** | When dental cannot pay: is there a real medical reason, and does this plan allow it? | Quotes the payer's published policy; never says "covered", never suggests a billing code |
| **MAO Assistant** | One chat (typed or spoken) that can run every step above | Can only state what a tool returned; asks before removing anything |

*Say:* "Language models listen, route and explain. Rules and published documents decide."

---

## Slide 9. Summary

- Medical and dental records live apart, and patients get hurt in the gap.
- MAO brings the medical history into the dental visit, warns before the procedure, gets the physician's clearance,
  and answers the insurance question from the insurer's own words.
- It is built on the standards healthcare already uses, and designed so the AI cannot make things up.
- It runs today: one guided workflow, or the whole thing by chat and voice, with 345 automated tests behind it.

---

## Slide 10. Conclusion

**From a chart that records care to a platform that protects it.**

- Safer patients: the risk is caught before the drill, not after.
- Faster practices: days of phone calls become minutes.
- Honest billing: a real medical pathway when there is one, a clear "no" when there is not.
- A reason for every DSO to choose CareStack.

*Ask:* [team: what you want from the judges: pilot access to the CareStack API, a design partner clinic, feedback]

---

# Slides worth adding

1. **A patient story (put it second, before the introduction).** "Margaret, 74. Blood thinner, six years on a bone drug,
   a mechanical heart valve, and a penicillin allergy. Booked for an extraction." Four facts, four ways it goes wrong.
   Judges remember a person, not an architecture.
2. **Live demo (the most important slide is no slide).** Two minutes: upload her PDF, run the risk check, show the
   insurance answer. Use `docs/demo/DEMO_GUIDE.md`. Have a 60-second screen recording ready in case the network fails.
3. **Safety and trust.** One slide, five guarantees: rules decide clinical risk; AI must quote its source; codes never
   come from a model; ambiguous replies never clear a patient; insurance answers quote the payer. This is your strongest
   differentiator against every "AI for healthcare" pitch.
4. **What is real and what is simulated.** Say it before they ask: CareStack, the hospital record and the physician inbox
   are simulators with synthetic patients; the payer policies, the research quotes, the AI and the standards are real.
   Owning this builds more credibility than any feature.
5. **Competition.** A small table: Dentrix, Curve, Open Dental, CareStack today, CareStack + MAO. Rows: reads medical
   record, risk check before procedure, physician clearance loop, evidence-backed insurance answer.
6. **Architecture (one diagram, for the technical judge).** FHIR in, rules and agents in the middle, CareStack out.
   Keep it in the appendix unless asked.
7. **Roadmap.** Next 90 days: real CareStack API, real eligibility feed (X12 270/271), a pilot clinic. Later: UK and
   Australia, prior-authorization submission (FHIR Da Vinci, required of US payers from 2027).
8. **Compliance.** HIPAA treatment-payment-operations basis, BAAs needed with AI providers, PDFs read locally where possible.
9. **Team.** Who built what. Judges fund people.

**Suggested order:** Title → Patient story → Problem → What it does → Demo → How it works → Agents → Why it needs this
(technical) → Safety → Business → Real vs simulated → Roadmap → Summary → Conclusion and ask.

---

# Sources for the numbers

- Annual maximum $1,000 to $1,500, unchanged for decades; about 12% of insured adults reach it, 14% over 55 (CareQuest):
  https://www.docseducation.com/blog/dental-benefit-caps-haven't-changed-40-years-your-patients-are-paying-price ·
  https://adanews.ada.org/ada-news/2025/december/dear-ada-annual-maximums/ · https://www.nadp.org/new-data-sheds-light-on-dental-benefits-and-the-cost-of-serving-enrollees/
- US dental services market $172 to $185B (2025) to $211B (2030); DSO growth about 17.9% a year:
  https://www.certifyhealth.com/market-study/dental-market-study-2025/
- US dental practice-management software market (estimates vary by firm, $583M to $1.0B in 2025, 9% to 11% growth):
  https://www.imarcgroup.com/united-states-dental-practice-management-software-market ·
  https://www.grandviewresearch.com/industry-analysis/us-dental-practice-management-software-market-report ·
  https://www.precedenceresearch.com/us-dental-practice-management-software-market
- CareStack serves more than 2,500 practices: https://carestack.com/
- 8 million Americans take blood thinners: https://www.aarp.org/health/drugs-supplements/blood-thinners/
- 16.3% of new dental patients medically compromised: https://pubmed.ncbi.nlm.nih.gov/27295833/ ·
  45.7% with pre-existing disease: https://pmc.ncbi.nlm.nih.gov/articles/PMC13353924/
- Dental providers' access to medical records (100% want it; 42% can use the shared system; 88% cannot revise shared plans):
  https://carequest.org/medical-and-dental-integration-a-need-for-improved-electronic-health-records/
- Few integrated medical-dental records exist: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12552933/

**A caution on the numbers:** market-size figures come from commercial research firms and differ from one firm to the
next, so say "roughly" and give the range. The two clinic studies are single-site studies (one outside the US), so say
"in published clinic studies", not "X% of all dental patients".
