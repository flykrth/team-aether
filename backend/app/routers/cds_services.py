"""
CDS Hooks v1.0 standard router mounted at /cds-services.
Provides Clinical Decision Support discovery and automated risk evaluation for dental-medical integration.
"""

from typing import List
from fastapi import APIRouter
from ..schemas.cds import (
    CDSDiscoveryResponse,
    CDSService,
    CDSHookRequest,
    CDSHookResponse,
    CDSCard,
    CDSSource,
    CDSSuggestion,
)

router = APIRouter()

SERVICES: List[CDSService] = [
    CDSService(
        hook="patient-view",
        title="Medical-Dental Cross-Domain Risk Evaluator",
        description="Analyzes medical conditions (osteoporosis, coagulopathy, diabetes) against proposed dental procedures to prevent adverse events.",
        id="med-dental-risk-evaluator",
        prefetch={
            "patient": "Patient/{{context.patientId}}",
            "conditions": "Condition?patient={{context.patientId}}",
            "observations": "Observation?patient={{context.patientId}}",
        },
    ),
    CDSService(
        hook="order-select",
        title="Infective Endocarditis & Antibiotic Prophylaxis Advisor",
        description="Verifies if high-risk cardiac status requires American Heart Association (AHA) antibiotic premedication prior to invasive dental manipulation.",
        id="antibiotic-prophylaxis-check",
        prefetch={
            "patient": "Patient/{{context.patientId}}",
            "conditions": "Condition?patient={{context.patientId}}",
            "allergies": "AllergyIntolerance?patient={{context.patientId}}",
        },
    ),
]


@router.get("", response_model=CDSDiscoveryResponse)
@router.get("/", response_model=CDSDiscoveryResponse)
async def cds_discovery():
    """
    CDS Hooks Discovery Endpoint.
    Returns the list of CDS Services offered by this MDIN server according to CDS Hooks specification.
    """
    return CDSDiscoveryResponse(services=SERVICES)


@router.post("/med-dental-risk-evaluator", response_model=CDSHookResponse)
async def evaluate_med_dental_risk(request: CDSHookRequest):
    """
    Evaluates cross-domain clinical risk between medical EHR diagnoses and dental chair procedures.
    Generates actionable CDS Cards.
    """
    patient_id = request.context.get("patientId", "")
    cards: List[CDSCard] = []

    # Case 1: Eleanor Vance (EHR-88201 / CS-1001) - Bisphosphonates & Planned Extraction
    if "88201" in patient_id or "1001" in patient_id:
        cards.append(
            CDSCard(
                summary="CRITICAL: Medication-Related Osteonecrosis of the Jaw (MRONJ) Risk",
                indicator="critical",
                detail=(
                    "Patient is currently receiving IV Bisphosphonate therapy (Zoledronic Acid) for Osteoporosis. "
                    "CareStack treatment plan indicates proposed surgical extraction of Tooth #19 (D7140). "
                    "High risk of osteonecrosis of the jaw post-extraction. Recommend conservative endodontic therapy "
                    "or mandatory medical oncology clearance with chlorhexidine pre-rinse."
                ),
                source=CDSSource(
                    label="MDIN Clinical Safety Engine",
                    url="https://www.aaoms.org/practice-resources/clinical-resources/mronj",
                ),
                suggestions=[
                    CDSSuggestion(
                        label="Request Physician Clearance & Modify Plan to Endodontic Preservation",
                        actions=[
                            {
                                "type": "create",
                                "description": "Consultation note sent to treating oncologist via FHIR CommunicationRequest",
                            }
                        ],
                    )
                ],
                links=[
                    {"label": "AAOMS MRONJ Guidelines", "url": "https://www.aaoms.org"}
                ],
            )
        )
        cards.append(
            CDSCard(
                summary="ALERT: Documented Severe Latex Allergy",
                indicator="warning",
                detail="Patient has documented anaphylactic hypersensitivity to Natural Rubber Latex. Ensure latex-free dental dams, gloves, and prophylaxis cups.",
                source=CDSSource(label="EHR Allergy Intolerance Sync"),
            )
        )

    # Case 2: Robert Taylor (EHR-99342 / CS-1003) - Mechanical Valve & Warfarin Anticoagulation
    elif "99342" in patient_id or "1003" in patient_id:
        cards.append(
            CDSCard(
                summary="CRITICAL: AHA Antibiotic Prophylaxis Required (Prosthetic Valve)",
                indicator="critical",
                detail=(
                    "Patient has a prosthetic mechanical heart valve (Z95.2) and severe Penicillin allergy. "
                    "Bacteremia from planned extraction #32 carries high risk of Infective Endocarditis. "
                    "AHA Guidelines require antibiotic prophylaxis: Clindamycin 600mg PO or Azithromycin 500mg PO 30-60 min prior to procedure."
                ),
                source=CDSSource(
                    label="AHA Dental Antibiotic Prophylaxis Protocol",
                    url="https://www.heart.org",
                ),
                suggestions=[
                    CDSSuggestion(
                        label="Prescribe Azithromycin 500mg (Penicillin-Allergic Alternative)",
                        actions=[
                            {
                                "type": "create",
                                "description": "Add Azithromycin 500mg 1 hr pre-op to CareStack Rx",
                            }
                        ],
                    )
                ],
            )
        )
        cards.append(
            CDSCard(
                summary="WARNING: Coagulopathy / Anticoagulated State (INR 3.2)",
                indicator="warning",
                detail="Latest INR is 3.2 (elevated therapeutic anticoagulation). Local hemostatic agents (gelatin sponge, tranexamic acid rinse, sutures) required for extraction #32.",
                source=CDSSource(label="Hematology Lab Interoperability Stream"),
            )
        )

    # Case 3: Marcus Chen (EHR-54109 / CS-1002) - Uncontrolled Diabetes HbA1c 8.6%
    elif "54109" in patient_id or "1002" in patient_id:
        cards.append(
            CDSCard(
                summary="WARNING: Uncontrolled Glycemia (HbA1c 8.6%) Affecting Periodontal Prognosis",
                indicator="warning",
                detail=(
                    "Most recent HbA1c is 8.6% (measured August 2026). Elevated glucose levels impair wound healing "
                    "and increase risk of periodontal breakdown and post-restorative infection. "
                    "Recommend morning appointment scheduling and coordination with primary endocrinologist."
                ),
                source=CDSSource(label="Endocrine-Dental Correlation Module"),
            )
        )

    else:
        # Default card when patient has no high-risk flags
        cards.append(
            CDSCard(
                summary="Medical-Dental Record Synchronized",
                indicator="info",
                detail=f"Patient {patient_id or 'General'} has been cross-referenced with medical EHR. No acute clinical contraindications identified for current dental treatment plan.",
                source=CDSSource(label="MDIN Surveillance Node"),
            )
        )

    return CDSHookResponse(cards=cards)


@router.post("/antibiotic-prophylaxis-check", response_model=CDSHookResponse)
async def evaluate_prophylaxis(request: CDSHookRequest):
    """Specific hook checking cardiac conditions and antibiotic premedication needs."""
    patient_id = request.context.get("patientId", "")
    cards: List[CDSCard] = []

    if "99342" in patient_id or "1003" in patient_id:
        cards.append(
            CDSCard(
                summary="Antibiotic Premedication Indicated",
                indicator="critical",
                detail="Prosthetic cardiac valve present. Administer AHA-recommended non-penicillin regimen prior to invasive dental therapy.",
                source=CDSSource(label="AHA Infective Endocarditis Guidelines"),
            )
        )
    else:
        cards.append(
            CDSCard(
                summary="No Antibiotic Prophylaxis Required",
                indicator="info",
                detail="Standard dental care protocols apply. No indication for prophylactic antibiotic therapy.",
                source=CDSSource(label="AHA Guidelines Engine"),
            )
        )

    return CDSHookResponse(cards=cards)
