"""Tier 3 — AI-adaptive browser scraper for unknown county assessor portals.

Uses Playwright to load the target page, captures a simplified DOM snapshot,
asks an LLM (via Pydantic AI) to identify the search form and result structure,
then executes a programmatic search and extracts records.

This is a best-effort scraper. Low-confidence LLM responses are skipped
gracefully and the caller receives an empty list.
"""

from __future__ import annotations

from typing import Any

import structlog
from pydantic import BaseModel, ValidationError

from aloha.scrapers.stealth.helper import StealthHelper

log = structlog.get_logger().bind(scraper="adaptive_tier3")

# ── APN / address alias tuples (mirrors arcgis.py pattern) ────────────────────
_APN_ALIASES = ("parcel_id", "apn", "account", "accountno", "parcel", "pin", "tax_id", "folio")
_ADDRESS_ALIASES = ("address", "situs_address", "property_address", "location", "site_addr")
_OWNER_ALIASES = ("owner", "owner_name", "taxpayer", "owner1")
_VALUE_ALIASES = ("assessed_value", "assessed_total", "market_value", "total_value", "appraised")

_SYSTEM_PROMPT = """You are analyzing the structure of a county property assessor website.

Your goal is to identify:
1. The CSS selector for the search input field (APN / parcel number / account number).
2. The CSS selector for the submit button.
3. The CSS selector for the results container (table, list, or div).
4. Which result columns correspond to parcel ID, owner name, address, and assessed value.

Return a JSON object matching this schema exactly:
{
  "search_input_selector": "<CSS selector string>",
  "submit_selector": "<CSS selector string>",
  "result_table_selector": "<CSS selector string>",
  "field_map": {
    "parcel_id": "<column header text or index hint>",
    "address": "<column header text or index hint>",
    "owner": "<column header text or index hint>",
    "assessed_total": "<column header text or index hint>"
  },
  "confidence": <float 0.0-1.0>,
  "notes": "<optional string>"
}

Be conservative: set confidence=0.0 if you cannot reliably identify the form or results.
Do NOT invent selectors that are not visible in the provided DOM snapshot.
"""

_CONFIDENCE_THRESHOLD = 0.3


class PagePlan(BaseModel):
    """LLM-produced plan for interacting with a county assessor page."""

    search_input_selector: str
    submit_selector: str
    result_table_selector: str
    field_map: dict[str, str]
    confidence: float
    notes: str = ""


class AdaptiveBrowserScraper:
    """LLM-guided Playwright scraper for unknown county assessor portals.

    Used as Tier 3 fallback when no Tier 1 or Tier 2 entry exists for a county.
    The scraper launches a headless browser, captures the page DOM, asks an LLM
    to produce a ``PagePlan``, then executes a delinquent-tax search and parses
    whatever results appear.

    Low-confidence plans (< 0.3) are silently skipped and return ``[]``.
    """

    def __init__(self) -> None:
        self._stealth = StealthHelper(min_delay=0.8, max_delay=2.0)
        self._model: Any = None

    def _get_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from aloha.core.llm import get_agent_model
            self._model = get_agent_model("discovery")
        except Exception as exc:
            log.debug("adaptive_llm_unavailable", error=str(exc))
            self._model = None
        return self._model

    async def discover(
        self,
        base_url: str,
        *,
        state: str,
        county: str,
        max_records: int = 500,
    ) -> list[dict[str, Any]]:
        """Navigate *base_url*, identify the search form via LLM, and extract records.

        Args:
            base_url: Landing URL of the county assessor portal.
            state: Two-letter state abbreviation.
            county: County name (lowercase).
            max_records: Advisory cap on returned records.

        Returns:
            List of normalised record dicts (may be empty).
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            log.error("playwright_not_installed")
            return []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            ctx = await self._stealth.new_context(browser)
            page = await ctx.new_page()
            try:
                await page.goto(base_url, wait_until="networkidle", timeout=30_000)
                plan = await self._analyse_page(page, state, county)

                if plan.confidence < _CONFIDENCE_THRESHOLD:
                    log.info(
                        "adaptive_low_confidence",
                        state=state,
                        county=county,
                        confidence=plan.confidence,
                        url=base_url,
                    )
                    return []

                await self._execute_search(page, plan)
                raw_records = await self._extract_records(page, plan)
                results = []
                for raw in raw_records[:max_records]:
                    normalised = self._normalise_adaptive(raw, state, county)
                    if normalised:
                        results.append(normalised)
                log.info(
                    "adaptive_extracted",
                    state=state,
                    county=county,
                    raw=len(raw_records),
                    normalised=len(results),
                )
                return results

            except Exception as exc:
                log.warning("adaptive_scrape_error", state=state, county=county, error=str(exc))
                return []
            finally:
                await browser.close()

    # ── LLM analysis ─────────────────────────────────────────────────────────

    async def _analyse_page(self, page: Any, state: str, county: str) -> PagePlan:
        """Ask the LLM to identify the search form and result structure."""
        # Capture simplified DOM text (first 8 000 chars)
        try:
            dom_text: str = await page.evaluate(
                "() => document.body.innerText.slice(0, 8000)"
            )
        except Exception:
            dom_text = ""

        # Capture form field metadata
        try:
            form_fields: list[dict[str, str]] = await page.evaluate(
                """() => [...document.querySelectorAll('form input, form select, form button, input, select, button')]
                    .map(e => ({
                        tag: e.tagName,
                        type: e.type || '',
                        name: e.name || '',
                        id: e.id || '',
                        placeholder: e.placeholder || '',
                    }))
                    .slice(0, 40)
                """
            )
        except Exception:
            form_fields = []

        model = self._get_model()
        if model is None:
            return PagePlan(
                search_input_selector="input",
                submit_selector='button[type="submit"]',
                result_table_selector="table",
                field_map={},
                confidence=0.0,
                notes="LLM unavailable",
            )

        prompt = (
            f"State: {state}, County: {county}\n\n"
            f"Page text (truncated):\n{dom_text}\n\n"
            f"Form fields found: {form_fields}\n\n"
            "Identify the parcel search form and result structure. "
            "Return JSON matching the PagePlan schema."
        )

        try:
            from pydantic_ai import Agent
            agent: Agent[None, PagePlan] = Agent(
                model,
                result_type=PagePlan,
                system_prompt=_SYSTEM_PROMPT,
            )
            result = await agent.run(prompt)
            return result.output
        except (ValidationError, Exception) as exc:
            log.warning("adaptive_llm_failed", error=str(exc))
            return PagePlan(
                search_input_selector="input",
                submit_selector='button[type="submit"]',
                result_table_selector="table",
                field_map={},
                confidence=0.0,
                notes=f"LLM error: {exc}",
            )

    # ── Search execution ──────────────────────────────────────────────────────

    async def _execute_search(self, page: Any, plan: PagePlan) -> None:
        """Fill and submit the search form using the LLM-identified selectors."""
        try:
            await page.fill(plan.search_input_selector, "delinquent", timeout=5_000)
            await self._stealth.human_delay()
        except Exception as e:
            # Try a blank search — some sites list all delinquent by default
            log.debug("search_fill_failed", error=str(e))

        try:
            await page.click(plan.submit_selector, timeout=5_000)
            await self._stealth.human_delay()
            await page.wait_for_load_state("networkidle", timeout=20_000)
        except Exception:
            try:
                await page.keyboard.press("Enter")
                await page.wait_for_load_state("networkidle", timeout=20_000)
            except Exception as e:
                log.warning("search_submit_fallback_failed", error=str(e))

    # ── Result extraction ─────────────────────────────────────────────────────

    async def _extract_records(self, page: Any, plan: PagePlan) -> list[dict[str, str]]:
        """Extract raw row dicts from the results container."""
        try:
            rows: list[dict[str, str]] = await page.evaluate(
                f"""() => {{
                    const container = document.querySelector({plan.result_table_selector!r});
                    if (!container) return [];
                    const rows = container.querySelectorAll('tr, li, [class*="row"], [class*="result"]');
                    return [...rows].slice(0, 200).map(row => {{
                        const cells = row.querySelectorAll('td, th, span, div');
                        const obj = {{}};
                        [...cells].forEach((cell, i) => {{
                            obj['col_' + i] = cell.innerText.trim();
                        }});
                        return obj;
                    }}).filter(r => Object.keys(r).length > 0);
                }}"""
            )
            return rows
        except Exception as exc:
            log.debug("extract_records_failed", error=str(exc))
            return []

    # ── Normalisation ─────────────────────────────────────────────────────────

    def _normalise_adaptive(
        self,
        raw: dict[str, str],
        state: str,
        county: str,
    ) -> dict[str, Any] | None:
        """Map raw column dict to canonical scraper output fields."""
        values = list(raw.values())
        all_text = " ".join(values).lower()

        # Attempt to find a parcel ID — look for common patterns
        parcel_id = self._pick_alias(raw, _APN_ALIASES)
        if not parcel_id:
            # Try to find a value that looks like an APN (digits/dashes, 8-20 chars)
            import re
            for v in values:
                v = v.strip()
                if re.match(r"^[\dA-Z\-\.\/]{6,20}$", v, re.IGNORECASE):
                    parcel_id = v
                    break

        if not parcel_id:
            return None

        # Normalise parcel_id: uppercase, strip whitespace/punctuation noise
        parcel_id = parcel_id.upper().strip()

        address = self._pick_alias(raw, _ADDRESS_ALIASES)
        owner = self._pick_alias(raw, _OWNER_ALIASES)
        assessed_total = self._pick_alias(raw, _VALUE_ALIASES)

        return {
            "parcel_id": parcel_id,
            "state": state.upper(),
            "county": county.lower(),
            "address": address,
            "owner": owner,
            "assessed_total": self._to_float(assessed_total),
            "source_url": "",
            "instrument_type": None,   # discovery agent will infer from state
        }

    @staticmethod
    def _pick_alias(raw: dict[str, str], aliases: tuple[str, ...]) -> str | None:
        """Case-insensitive key lookup against a tuple of alias names."""
        raw_lower = {k.lower().replace(" ", "_"): v for k, v in raw.items()}
        for alias in aliases:
            val = raw_lower.get(alias)
            if val:
                return val.strip()
        return None

    @staticmethod
    def _to_float(value: str | None) -> float | None:
        if not value:
            return None
        try:
            return float(value.replace("$", "").replace(",", "").strip())
        except (ValueError, AttributeError):
            return None
