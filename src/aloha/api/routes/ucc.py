"""UCC filing API routes — search and detail lookups."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from aloha.api.deps import get_current_user
from aloha.api.schemas.ucc import UCCDetailResponse, UCCSearchResponse
from aloha.mcp_servers.ucc.server import UCCMCPServer, create_ucc_server

router = APIRouter(prefix="/ucc", tags=["ucc"])

# ── Dependency ────────────────────────────────────────────────────────────────

_server: UCCMCPServer | None = None


def _get_server() -> UCCMCPServer:
    global _server
    if _server is None:
        _server = create_ucc_server()
    return _server


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/filings", response_model=UCCSearchResponse)
async def search_ucc_filings(
    debtor_name: str = Query(..., description="Name of the debtor (person or entity)"),
    state: str = Query(..., description="Two-letter US state abbreviation"),
    filing_type: str | None = Query(
        None, description="Filter: initial, amendment, continuation"
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
    return UCCSearchResponse(**result)


@router.get("/filings/{filing_number}", response_model=UCCDetailResponse)
async def get_filing_details(
    filing_number: str,
    state: str = Query(..., description="State where the filing was recorded"),
    _user: Annotated[None, Depends(get_current_user)] = None,
) -> dict:
    """Fetch full UCC filing details by filing number and state."""
    server = _get_server()
    return await server.get_filing_details(
        filing_number=filing_number,
        state=state,
    )
