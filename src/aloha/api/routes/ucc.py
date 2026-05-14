"""UCC filing API routes — search and detail lookups."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from aloha.api.deps import get_current_user
from aloha.api.schemas.ucc import UCCDetailResponse, UCCSearchResponse
from aloha.mcp_servers.ucc.server import UCCMCPServer, create_ucc_server

router = APIRouter(prefix="/ucc", tags=["ucc"])

# ── Dependency ────────────────────────────────────────────────────────────────

# Module-level singleton; safe because FastAPI runs in a single process with an
# async event loop — no concurrent threads mutate this reference.
_server: UCCMCPServer | None = None


def _get_server() -> UCCMCPServer:
    global _server
    if _server is None:
        _server = create_ucc_server()
    return _server


# ── Routes ────────────────────────────────────────────────────────────────────


@router.get("/filings", response_model=UCCSearchResponse)
async def search_ucc_filings(
    debtor_name: str = Query(
        ...,
        min_length=1,
        max_length=200,
        description="Name of the debtor (person or entity)",
    ),
    state: str = Query(
        ...,
        min_length=2,
        max_length=2,
        pattern=r"^[A-Z]{2}$",
        description="Two-letter US state abbreviation (uppercase)",
    ),
    filing_type: str | None = Query(
        None,
        max_length=50,
        description="Filter: initial, amendment, continuation",
    ),
    limit: int = Query(
        100,
        ge=1,
        le=1000,
        description="Maximum number of results to return",
    ),
    _user: Annotated[None, Depends(get_current_user)] = None,
) -> UCCSearchResponse:
    """Search UCC filings by debtor name and state."""
    server = _get_server()
    result = await server.search_ucc_filings(
        debtor_name=debtor_name,
        state=state,
        filing_type=filing_type,
    )
    # Apply client-side result limit
    filings = result.get("filings", [])[:limit]
    return UCCSearchResponse(filings=filings, error=result.get("error"))


@router.get("/filings/{filing_number}", response_model=UCCDetailResponse)
async def get_filing_details(
    filing_number: str = Path(
        ...,
        min_length=1,
        max_length=50,
        description="UCC filing number",
    ),
    state: str = Query(
        ...,
        min_length=2,
        max_length=2,
        pattern=r"^[A-Z]{2}$",
        description="State where the filing was recorded (uppercase)",
    ),
    _user: Annotated[None, Depends(get_current_user)] = None,
) -> dict:
    """Fetch full UCC filing details by filing number and state."""
    server = _get_server()
    result = await server.get_filing_details(
        filing_number=filing_number,
        state=state,
    )
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
