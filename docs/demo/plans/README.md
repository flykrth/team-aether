# Sample member plan documents

Upload these in **Manual → Coverage recovery → Insurance → "Upload the member's plan document (SBC or Certificate of
Coverage)"**. PDF or text, up to 10 MB. The document stays on this machine.

All six are **fictional**, written to read like a real Summary of Benefits and Coverage (SBC), Certificate of Coverage or
Medicare Evidence of Coverage. Every page is marked SAMPLE. They are not copies of any insurer's document.

**Not tested:** files 03 to 06 were generated on request without being run through the app, so the "what it should
show" column below is what the wording is written to produce, not an observed result. Files 01 and 02 were checked
earlier (three runs each) with the impacted-third-molar case.

| File | Plan type to select | What the wording says | Use it with | What it should show |
| :--- | :--- | :--- | :--- | :--- |
| `01_PPO_oral_surgery_covered.pdf` | PPO | Covers jaw fractures, tumors and cysts, and surgical removal of bone impacted teeth; excludes routine dental | Impacted third molar (case 1) | Potential pathway, no longer "plan not verified" |
| `02_HMO_impacted_teeth_excluded.pdf` | HMO | "Removal of impacted teeth is not covered under this plan"; also excludes TMJ | Impacted third molar (case 1) | No pathway: the member's own plan excludes it |
| `03_PPO_TMJ_and_sleep_apnea_covered.pdf` | PPO | Covers TMJ treatment (surgery only after three months of failed conservative care), oral appliances for sleep apnea with a sleep study, prior authorization required | TMJ arthrocentesis (case 5), or a sleep apnea oral appliance | A plan-level condition the chart can answer: the case 5 note says six months of splint and physical therapy failed |
| `04_EPO_TMJ_excluded.pdf` | EPO | Excludes TMJ, sleep apnea appliances, impacted teeth and all extractions; covers only trauma fractures and tumors | TMJ (case 5) or impacted tooth (case 1); then jaw fracture (case 4) | No pathway for TMJ and impacted teeth; the jaw fracture still has one |
| `05_Medicare_Advantage_integral_dental.pdf` | HMO | Dental care integral to covered medical treatment: before transplant, before cardiac valve replacement, during head and neck cancer treatment. States plainly that heart disease, diabetes or a risky medication is not enough | An extraction before valve replacement (tick "needed before or as part of a covered medical treatment"), then the stent extraction (case 3) | The valve case has a route; the stent case does not, in the plan's own words |
| `06_HDHP_silent_on_oral_surgery.pdf` | PPO | A thin SBC that only says "dental care (adult)" is not covered and refers to the full certificate | Any case | A plan document that does not answer the question. Worth showing: uploading something is not the same as verifying |

## What a real one looks like

- **SBC (Summary of Benefits and Coverage):** the standard 4 to 8 page summary every US health plan must provide. Look
  for "Excluded Services & Other Covered Services". Often too thin to settle an oral surgery question (see file 06).
- **Certificate / Evidence of Coverage:** the full contract, often 80 to 200 pages. The sections that matter are covered
  services (oral surgery, TMJ, accidental injury to teeth), exclusions, and prior authorization.
- Members can download both from their insurer's portal, or the employer's HR team has them.

Large documents are fine: only the passages relevant to the case are read, and the file is limited to 10 MB.
A scanned PDF (no selectable text) is read through OCR if an AI key is set; a PDF with real text is read locally.
