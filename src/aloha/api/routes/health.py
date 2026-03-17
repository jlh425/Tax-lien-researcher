"""Health-check endpoint."""

from fastapi import APIRouter

import aloha

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Return basic liveness information.

    Returns:
        JSON with ``status`` and ``version`` fields.
    """
    return {
        "status": "ok",
        "version": aloha.__version__,
    }
