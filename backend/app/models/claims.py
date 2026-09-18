"""
CMS-1500 Claim Form & Electronic ANSI ASC X12N 837P Claims Models.
Defines standard Pydantic schemas for medical cross-coding administrative decision support.
"""

from typing import List, Optional, Union, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator, model_validator


class DiagnosisCode(BaseModel):
    """
    CMS-1500 Box 21 Diagnosis Item with ICD-10-CM code and standard pointer indicator (A-D).
    """
    pointer: str = Field(..., description="Diagnosis indicator pointer (A, B, C, or D)")
    code: str = Field(..., description="ICD-10-CM diagnosis code (e.g., E11.9, M26.61)")
    description: Optional[str] = Field(None, description="Clinical description of the medical diagnosis")


class ClaimServiceLine(BaseModel):
    """
    CMS-1500 Box 24A-24J Line Item Service Details.
    """
    date_of_service: str = Field(..., description="Box 24A: Date of Service (YYYY-MM-DD)")
    place_of_service: str = Field("11", description="Box 24B: Place of Service (11 = Office / Dental Operatory)")
    cpt_code: str = Field(..., description="Box 24D: CPT/HCPCS Procedure Code")
    modifiers: List[str] = Field(default_factory=list, description="Box 24D: CPT Modifiers (e.g. 22, 59)")
    diagnosis_pointer: str = Field("A", description="Box 24E: Diagnosis Pointer referencing Box 21 indicators (A, B, C, D)")
    charges: float = Field(..., description="Box 24F: Charge amount for this line item in USD")
    days_or_units: int = Field(1, description="Box 24G: Days or Units")
    rendering_provider_npi: Optional[str] = Field(None, description="Box 24J: Rendering Provider NPI")


class BillingProvider(BaseModel):
    """
    CMS-1500 Box 33 Billing Provider Info & Phrasing.
    """
    provider_npi: str = Field("1928374650", description="Box 33a: 10-digit National Provider Identifier (NPI)")
    clinic_name: str = Field("CareStack Center for Advanced Dentistry", description="Box 33: Clinic or Billing Organization Name")
    address: str = Field("100 Healthcare Boulevard, Suite 400, Boston, MA 02115", description="Box 33: Clinic Physical Address")
    taxonomy_code: str = Field("1223S0112X", description="Box 33a: Healthcare Provider Taxonomy Code (1223S0112X = Oral and Maxillofacial Surgery)")
    phone: Optional[str] = Field("(555) 019-2830", description="Box 33: Clinic Phone Number")


class CMS1500Claim(BaseModel):
    """
    Pydantic model representing the official CMS-1500 Health Insurance Claim Form
    and its electronic ANSI ASC X12N 837P equivalent.
    """
    # Header & Demographics (Boxes 1-7)
    insurance_type: str = Field("OTHER", description="Box 1: Insurance Type (MEDICARE, MEDICAID, TRICARE, CHAMPVA, GROUP_HEALTH_PLAN, FECA, OTHER)")
    insured_id: str = Field(..., description="Box 1a: Insured's ID Number")
    patient_name: str = Field(..., description="Box 2: Patient's Full Name (Last, First, Middle)")
    patient_dob: str = Field(..., description="Box 3: Patient's Date of Birth (YYYY-MM-DD)")
    patient_gender: str = Field(..., description="Box 3: Patient's Sex (male, female, other)")
    patient_address: str = Field(..., description="Box 5: Patient's Address (Street, City, State, ZIP)")
    insured_name: Optional[str] = Field(None, description="Box 4: Insured's Name (if different from patient)")
    patient_relationship: str = Field("18", description="Box 6: Patient Relationship to Insured (18 = Self, 01 = Spouse, 19 = Child)")

    # Clinical Justification (Box 21 - Diagnoses)
    diagnosis_codes: List[DiagnosisCode] = Field(
        default_factory=list,
        description="Box 21: List of up to 4 ICD-10 codes with pointer indicators A-D",
    )

    # Line Item Service Details (Box 24A-24J)
    service_lines: List[ClaimServiceLine] = Field(
        default_factory=list,
        description="Box 24A-24J: List of procedure lines",
    )

    # Billing Provider (Box 33)
    billing_provider: BillingProvider = Field(
        default_factory=BillingProvider,
        description="Box 33: Billing Provider Details",
    )

    # Financial Summary (Boxes 28-30)
    total_charge: float = Field(0.0, description="Box 28: Total Charge in USD")
    amount_paid: float = Field(0.0, description="Box 29: Amount Paid in USD")
    balance_due: float = Field(0.0, description="Box 30: Balance Due in USD")

    # Electronic 837P Preview
    edi_837p_preview: Optional[str] = Field(
        None,
        description="ANSI ASC X12N 837 Professional electronic claim transaction EDI string",
    )

    @field_validator("diagnosis_codes", mode="before")
    @classmethod
    def normalize_diagnosis_codes(cls, v: Any) -> List[DiagnosisCode]:
        """Allow passing a list of raw strings (e.g. ['E11.9', 'M26.61']) or dicts, mapping them to A-D pointers."""
        if not v:
            return []
        result: List[DiagnosisCode] = []
        pointers = ["A", "B", "C", "D"]
        for idx, item in enumerate(v[:4]):
            ptr = pointers[idx]
            if isinstance(item, str):
                result.append(DiagnosisCode(pointer=ptr, code=item.strip()))
            elif isinstance(item, dict):
                p = item.get("pointer") or ptr
                c = item.get("code") or ""
                desc = item.get("description")
                result.append(DiagnosisCode(pointer=p, code=c, description=desc))
            elif isinstance(item, DiagnosisCode):
                result.append(item)
        return result

    @model_validator(mode="after")
    def compute_totals_and_837p(self) -> "CMS1500Claim":
        """Compute financial totals and synthesize 837P EDI preview if not set."""
        if self.service_lines and self.total_charge == 0.0:
            self.total_charge = sum(line.charges for line in self.service_lines)
            self.balance_due = max(0.0, self.total_charge - self.amount_paid)

        if not self.edi_837p_preview:
            self.edi_837p_preview = self.generate_837p()
        return self

    def generate_837p(self) -> str:
        """
        Synthesizes an authentic ANSI ASC X12N 837 Professional (837P) EDI transaction string.
        """
        now_date = datetime.now(timezone.utc).strftime("%Y%m%d")
        now_time = datetime.now(timezone.utc).strftime("%H%M")
        pat_name_parts = [p.strip() for p in self.patient_name.replace(",", " ").split() if p.strip()]
        last_name = pat_name_parts[-1] if pat_name_parts else "PATIENT"
        first_name = pat_name_parts[0] if len(pat_name_parts) > 1 else ""

        # Primary diagnosis
        primary_dx = self.diagnosis_codes[0].code.replace(".", "") if self.diagnosis_codes else "Z0000"
        dx_segments = [f"HI*BK:{self.diagnosis_codes[0].code}"] if self.diagnosis_codes else []
        for dx in self.diagnosis_codes[1:4]:
            dx_segments.append(f"HI*BF:{dx.code}")
        dx_block = "~".join(dx_segments)

        # Service lines SV1
        sv1_segments = []
        for idx, line in enumerate(self.service_lines, 1):
            modifier_str = f":{':'.join(line.modifiers)}" if line.modifiers else ""
            sv1_segments.append(
                f"LX*{idx}~SV1*HC:{line.cpt_code}{modifier_str}*{line.charges:.2f}*UN*{line.days_or_units}***1~"
                f"DTP*472*D8*{line.date_of_service.replace('-', '')}"
            )
        sv1_block = "~".join(sv1_segments) if sv1_segments else f"LX*1~SV1*HC:41899*{self.total_charge:.2f}*UN*1***1"

        segments = [
            f"ISA*00*          *00*          *ZZ*MDIN-SENDER    *ZZ*PAYER-RECEIVER *{now_date[2:]}*{now_time}*^*00501*000000001*0*P*:~",
            f"GS*HC*MDIN-SENDER*PAYER-RECEIVER*{now_date}*{now_time}*1*X*005010X222A1~",
            f"ST*837*0001*005010X222A1~",
            f"BHT*0019*00*CLAIM-{self.insured_id}*{now_date}*{now_time}*CH~",
            f"NM1*41*2*{self.billing_provider.clinic_name.upper()}*****XX*{self.billing_provider.provider_npi}~",
            f"PER*IC*BILLING DEPT*TE*{self.billing_provider.phone or '5550192830'}~",
            f"NM1*40*2*PRIMARY MEDICAL PAYER*****46*PAYER01~",
            f"HL*1**20*1~",
            f"NM1*IL*1*{last_name.upper()}*{first_name.upper()}****MI*{self.insured_id}~",
            f"DMG*D8*{self.patient_dob.replace('-', '')}*{self.patient_gender[0].upper()}~",
            f"CLM*CLM-{self.insured_id}*{self.total_charge:.2f}***11:B:1*Y*A*Y*Y~",
            dx_block,
            sv1_block,
            f"SE*14*0001~",
            f"GE*1*1~",
            f"IEA*1*000000001~",
        ]
        return "\n".join(seg for seg in segments if seg)


class CrossCodingOpportunity(BaseModel):
    """
    Evaluated opportunity for cross-coding dental procedures (CDT) into medical insurance claims (CPT).
    """
    is_eligible: bool = Field(..., description="Whether procedural CDT qualifies for medical primary cross-coding")
    cdt_code: str = Field(..., description="Original dental procedure CDT code")
    suggested_cpt: Optional[str] = Field(None, description="Suggested medical cross-coded CPT code")
    justifying_icd10: List[str] = Field(default_factory=list, description="Qualifying ICD-10 diagnostic codes identified in patient history")
    estimated_coverage: float = Field(0.0, description="Estimated medical primary insurance reimbursement in USD")
    claim_preview: Optional[CMS1500Claim] = Field(None, description="Pre-populated CMS-1500 claim form schema instance")
    reimbursement_category: Optional[str] = Field(None, description="Coverage tier or policy uplift description")
    narrative_justification: Optional[str] = Field(None, description="Clinical decision support explanation justifying medical necessity")
