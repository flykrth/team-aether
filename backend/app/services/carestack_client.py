"""
CareStack Web API HTTP Client Service.
Executes JSON HTTP requests authenticated with VendorKey, AccountKey, and AccountId
headers, and maps standard HTTP status codes (2xx, 4xx, 5xx) onto typed exceptions.

Scope note: the endpoint paths and payload shapes below are modeled on CareStack's
publicly described Web API V1 conventions. They have NOT been validated against a
live CareStack account or against the published specification at
developer.carestack.com (which is gated behind a partner login). Treat them as a
best-effort integration surface that will need reconciliation against the real
specification before any production use.
"""

from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timezone
import httpx
from ..config import settings
from ..schemas.carestack import (
    PatientViewModel,
    SearchRequest,
    PatientSearchResponseModel,
    ProcedureCodeBasicApiResponseModel,
    PeriodontalChart,
    AppointmentDetailModel,
    TreatmentProcedureSyncModel,
)


class CareStackAPIError(Exception):
    """Base exception for CareStack API failures."""
    def __init__(self, status_code: int, message: str, details: Optional[str] = None):
        self.status_code = status_code
        self.message = message
        self.details = details
        super().__init__(f"CareStack API Error [{status_code}]: {message} - {details or ''}")


class CareStackAuthenticationError(CareStackAPIError):
    """Raised when VendorKey, AccountKey, or AccountId is invalid or missing (HTTP 401)."""
    pass


class CareStackNotFoundError(CareStackAPIError):
    """Raised when a patient, appointment, or resource is not found (HTTP 404)."""
    pass


class CareStackValidationError(CareStackAPIError):
    """Raised on invalid request body or query parameters (HTTP 400)."""
    pass


class CareStackServerError(CareStackAPIError):
    """Raised on internal CareStack PMS server errors (HTTP 5xx)."""
    pass


class CareStackClient:
    """
    Asynchronous client for CareStack Dental Practice Management System.
    Connects to CareStack Web API V1 using header-based authentication.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        vendor_key: Optional[str] = None,
        account_key: Optional[str] = None,
        account_id: Optional[str] = None,
        timeout: float = 15.0,
        app: Optional[Any] = None,
    ):
        # Falls back to a simulator placeholder so an unconfigured client still has a
        # resolvable origin; live mode always supplies a real base_url.
        self.base_url = (
            base_url or settings.CARESTACK_BASE_URL or "http://carestack-simulator.local"
        ).rstrip("/")
        self.vendor_key = vendor_key or settings.CARESTACK_VENDOR_KEY
        self.account_key = account_key or settings.CARESTACK_ACCOUNT_KEY
        self.account_id = account_id or settings.CARESTACK_ACCOUNT_ID
        self.timeout = timeout
        self.app = app  # Allows in-process ASGITransport for testing or local simulation

    def _get_headers(self, custom_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Constructs headers containing the required 3 CareStack authentication keys."""
        headers = {
            "VendorKey": self.vendor_key,
            "AccountKey": self.account_key,
            "AccountId": self.account_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if custom_headers:
            headers.update(custom_headers)
        return headers

    def _handle_response(self, response: httpx.Response) -> Any:
        """Evaluates standard HTTP status codes and extracts JSON payload."""
        status = response.status_code

        # 2xx Success
        if 200 <= status < 300:
            if status == 204 or not response.content:
                return {}
            try:
                return response.json()
            except Exception:
                return {"text": response.text}

        # Error response parsing
        error_msg = f"HTTP {status}"
        error_detail = response.text
        try:
            err_json = response.json()
            error_msg = err_json.get("message") or err_json.get("detail") or error_msg
            error_detail = str(err_json)
        except Exception:
            pass

        # 4xx Client Errors
        if status == 401:
            raise CareStackAuthenticationError(status, "Unauthorized: Invalid or missing CareStack API credentials (VendorKey, AccountKey, AccountId)", error_detail)
        elif status == 404:
            raise CareStackNotFoundError(status, error_msg, error_detail)
        elif status == 400:
            raise CareStackValidationError(status, error_msg, error_detail)
        elif 400 <= status < 500:
            raise CareStackAPIError(status, error_msg, error_detail)

        # 5xx Server Errors
        raise CareStackServerError(status, f"CareStack PMS Server Error: {error_msg}", error_detail)

    async def _request(
        self,
        method: str,
        path: str,
        json_data: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        """Executes an authenticated HTTP request against CareStack Web API."""
        all_headers = self._get_headers(headers)

        transport = None
        if self.app is not None:
            transport = httpx.ASGITransport(app=self.app)

        async with httpx.AsyncClient(
            timeout=self.timeout, transport=transport, base_url=self.base_url
        ) as client:
            resp = await client.request(
                method=method,
                url=path,
                json=json_data,
                params=params,
                headers=all_headers,
            )
            return self._handle_response(resp)

    # -----------------------------------------------------------------
    # Patient Endpoints (Official CareStack V1)
    # -----------------------------------------------------------------

    async def get_patient(self, patient_id: Union[int, str]) -> Dict[str, Any]:
        """GET /api/v1.0/patients/{id} - Retrieve detailed CareStack patient record."""
        return await self._request("GET", f"/api/v1.0/patients/{patient_id}")

    async def search_patients(
        self,
        search_term: Optional[str] = None,
        offset: int = 0,
        limit: int = 50,
        filter_fields: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """POST /api/v1.0/patients/search - Search CareStack dental patients."""
        payload = {
            "SearchTerm": search_term or "",
            "FilterByFields": filter_fields or [],
            "OrderByFields": [],
            "Offset": offset,
            "Limit": limit,
        }
        return await self._request("POST", "/api/v1.0/patients/search", json_data=payload)

    async def create_patient(self, patient_data: Union[PatientViewModel, Dict[str, Any]]) -> Dict[str, Any]:
        """POST /api/v1.0/patients - Create a new patient in CareStack."""
        payload = patient_data.model_dump() if isinstance(patient_data, PatientViewModel) else patient_data
        return await self._request("POST", "/api/v1.0/patients", json_data=payload)

    async def update_patient(self, patient_data: Union[PatientViewModel, Dict[str, Any]]) -> Dict[str, Any]:
        """PUT /api/v1.0/patients - Update an existing patient in CareStack."""
        payload = patient_data.model_dump() if isinstance(patient_data, PatientViewModel) else patient_data
        return await self._request("PUT", "/api/v1.0/patients", json_data=payload)

    async def get_periodontal_charting(self, patient_id: Union[int, str]) -> Dict[str, Any]:
        """GET /api/v1.0/patients/{patientId}/periodontal-charting - Retrieve perio exam & pocket depths."""
        return await self._request("GET", f"/api/v1.0/patients/{patient_id}/periodontal-charting")

    async def sync_patients(
        self,
        modified_since: Optional[str] = None,
        continue_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """GET /api/v1.0/sync/patients - Incremental patient synchronization."""
        params = {}
        if modified_since:
            params["modifiedSince"] = modified_since
        if continue_token:
            params["continueToken"] = continue_token
        return await self._request("GET", "/api/v1.0/sync/patients", params=params)

    # -----------------------------------------------------------------
    # Treatments & CDT Procedures (Official CareStack V1)
    # -----------------------------------------------------------------

    async def get_procedure_codes(self) -> List[Dict[str, Any]]:
        """GET /api/v1.0/procedure-codes - Retrieve all CDT procedure codes."""
        return await self._request("GET", "/api/v1.0/procedure-codes")

    async def get_appointment_procedures(self, appointment_id: int) -> List[int]:
        """GET /api/v1.0/treatments/appointment-procedures/{appointmentId} - Procedure codes for appointment."""
        return await self._request("GET", f"/api/v1.0/treatments/appointment-procedures/{appointment_id}")

    async def sync_treatment_procedures(
        self,
        modified_since: Optional[str] = None,
        continue_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """GET /api/v1.0/sync/treatment-procedures - Sync dental procedures modified after timestamp."""
        params = {}
        if modified_since:
            params["modifiedSince"] = modified_since
        if continue_token:
            params["continueToken"] = continue_token
        return await self._request("GET", "/api/v1.0/sync/treatment-procedures", params=params)

    # -----------------------------------------------------------------
    # Appointments (Official CareStack V1)
    # -----------------------------------------------------------------

    async def get_appointment(self, appointment_id: int) -> Dict[str, Any]:
        """GET /api/v1.0/appointments/{appointmentId} - Retrieve appointment details."""
        return await self._request("GET", f"/api/v1.0/appointments/{appointment_id}")

    async def create_appointment(self, appointment_data: Union[AppointmentDetailModel, Dict[str, Any]]) -> Dict[str, Any]:
        """POST /api/v1.0/appointments - Schedule new dental appointment."""
        payload = appointment_data.model_dump() if isinstance(appointment_data, AppointmentDetailModel) else appointment_data
        return await self._request("POST", "/api/v1.0/appointments", json_data=payload)

    async def modify_appointment_status(self, appointment_id: int, status_id: int) -> Dict[str, Any]:
        """PUT /api/v1.0/appointments/{appointmentId}/modify-status - Update appointment status."""
        return await self._request(
            "PUT",
            f"/api/v1.0/appointments/{appointment_id}/modify-status",
            json_data={"StatusId": status_id},
        )

    async def checkout_appointment(self, appointment_id: int) -> Dict[str, Any]:
        """PUT /api/v1.0/appointments/{appointmentId}/checkout - Mark appointment as checked out."""
        return await self._request("PUT", f"/api/v1.0/appointments/{appointment_id}/checkout")

    async def cancel_appointment(self, appointment_id: int, reason: Optional[str] = None) -> Dict[str, Any]:
        """PUT /api/v1.0/appointments/{appointmentId}/cancel - Cancel an appointment."""
        return await self._request(
            "PUT",
            f"/api/v1.0/appointments/{appointment_id}/cancel",
            json_data={"CancelReason": reason or "Patient request"},
        )

    async def get_appointment_statuses(self) -> List[Dict[str, Any]]:
        """GET /api/v1.0/appointment-status - List all available appointment statuses."""
        return await self._request("GET", "/api/v1.0/appointment-status")

    # -----------------------------------------------------------------
    # Practice Infrastructure (Locations & Operatories)
    # -----------------------------------------------------------------

    async def get_locations(self) -> List[Dict[str, Any]]:
        """GET /api/v1.0/locations - List dental clinic locations."""
        return await self._request("GET", "/api/v1.0/locations")

    async def get_operatories(self) -> List[Dict[str, Any]]:
        """GET /api/v1.0/operatories - List practice operatories / dental chairs."""
        return await self._request("GET", "/api/v1.0/operatories")

    # -----------------------------------------------------------------
    # Document Management & LOMN Ingestion (Step 9)
    # -----------------------------------------------------------------

    async def attach_patient_document(
        self,
        patient_id: Union[int, str],
        document_type: str = "Letter of Medical Necessity",
        title: str = "Clinical Document",
        file_content: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """POST /api/carestack/patients/{id}/documents - Attach clinical document to chart."""
        payload = {
            "document_type": document_type,
            "title": title,
            "file_content": file_content,
            "metadata": metadata or {},
        }
        return await self._request("POST", f"/api/carestack/patients/{patient_id}/documents", json_data=payload)

    async def get_patient_documents(self, patient_id: Union[int, str]) -> List[Dict[str, Any]]:
        """GET /api/carestack/patients/{id}/documents - Retrieve patient attached documents."""
        return await self._request("GET", f"/api/carestack/patients/{patient_id}/documents")

    # -----------------------------------------------------------------
    # Interoperability Node Health & Connectivity Check
    # -----------------------------------------------------------------

    async def check_connectivity(self) -> Dict[str, Any]:
        """Verify API credentials and connectivity."""
        try:
            status_data = await self._request("GET", "/api/v1.0/auth/verify")
            return {"connected": True, "details": status_data}
        except Exception as e:
            return {"connected": False, "error": str(e)}


def get_carestack_client() -> CareStackClient:
    """
    Build the CareStack client for the currently configured integration mode.

    Live mode (USE_LIVE_CARESTACK=true with all credentials supplied) targets the
    real account over the network. Otherwise the identical client is pointed at the
    bundled simulator in-process via ASGI transport, so the integration code path is
    exercised the same way in demos as it would be against a real account.
    """
    if settings.carestack_live_configured:
        return CareStackClient(
            base_url=settings.CARESTACK_BASE_URL,
            vendor_key=settings.CARESTACK_VENDOR_KEY,
            account_key=settings.CARESTACK_ACCOUNT_KEY,
            account_id=settings.CARESTACK_ACCOUNT_ID,
        )

    # Imported lazily: app imports routers, which import this module.
    from ..main import app

    return CareStackClient(
        base_url="http://carestack-simulator.local",
        vendor_key=settings.SIMULATOR_VENDOR_KEY,
        account_key=settings.SIMULATOR_ACCOUNT_KEY,
        account_id=settings.SIMULATOR_ACCOUNT_ID,
        app=app,
    )


def describe_integration_mode() -> Dict[str, Any]:
    """Report which CareStack backend is serving traffic, for status endpoints."""
    if settings.carestack_live_configured:
        return {
            "mode": "live",
            "target": settings.CARESTACK_BASE_URL,
            "description": "Configured to target a live CareStack account over the network.",
        }
    return {
        "mode": "simulator",
        "target": "in-process bundled simulator",
        "description": (
            "Serving the bundled CareStack simulator with synthetic patient data. "
            "Set USE_LIVE_CARESTACK=true and supply CARESTACK_BASE_URL, "
            "CARESTACK_VENDOR_KEY, CARESTACK_ACCOUNT_KEY and CARESTACK_ACCOUNT_ID "
            "to target a real account."
        ),
    }

