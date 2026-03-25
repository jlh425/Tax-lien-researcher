"""Court records API routes — federal cases and state liens."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from aloha.api.deps import get_current_user
from aloha.api.schemas.court_records import (
    CaseDetailResponse,
    CaseSearchResponse,
    LienSearchResponse,
)
from aloha.mcp_servers.court_records.server import (
    CourtRecordsMCPServer,
    create_court_records_server,
)

router = APIRouter(prefix="/court-records", tags=["court-records"])

# ── Dependency ────────────────────────────────────────────────────────────────

_server: CourtRecordsMCPServer | None = None


def _get_server() -> CourtRecordsMCPServer:
    global _server
    if _server is None:
        _server = create_court_records_server()
    return _server


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/cases", response_model=CaseSearchResponse)
async def search_federal_cases(
    party_name: str = Query(..., description="Name of a party (plaintiff or defendant)"),
    state: str | None = Query(None, description="Two-letter US state abbreviation"),
    case_type: str | None = Query(None, description="Filter: civil, bankruptcy, criminal"),
    _user: Annotated[None, Depends(get_current_user)] = None,
) -> CaseSearchResponse:
    """Search federal court cases by party name via CourtListener."""
    server = _get_server()
    result = await server.search_federal_cases(
        party_name=party_name,
        state=state,
        case_type=case_type,
    )
    return CaseSearchResponse(**result)


@router.get("/cases/{case_id}", response_model=CaseDetailResponse)
async def get_case_details(
    case_id: str,
    _user: Annotated[None, Depends(get_current_user)] = None,
) -> dict:
    """Fetch full case details by CourtListener docket ID."""
    server = _get_server()
    result = await server.get_case_details(case_id=case_id)
    if "error" in result:
        error_msg = result["error"]
        if "not configured" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=error_msg,
            )
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=error_msg,
        )
    return result


@router.get("/liens", response_model=LienSearchResponse)
async def search_state_liens(
    debtor_name: str = Query(..., description="Name of the debtor"),
    state: str = Query(..., description="Two-letter US state abbreviation"),
    lien_type: str | None = Query(None, description="Filter: tax, judgment, mechanics"),
    _user: Annotated[None, Depends(get_current_user)] = None,
) -> LienSearchResponse:
    """Search state-level lien filings by debtor name and state."""
    server = _get_server()
    result = await server.search_state_liens(
        debtor_name=debtor_name,
        state=state,
        lien_type=lien_type,
    )
    return LienSearchResponse(**result)
