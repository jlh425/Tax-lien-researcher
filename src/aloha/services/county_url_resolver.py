"""County URL Resolver — 4-layer pipeline for finding assessor/tax portal URLs.

Resolution order:
1. DB cache (county_urls table)
2. Static registry (known URLs from existing scraper registries)
3. Web search (SearXNG API)
4. LLM validation (Ollama confirms the page is a tax portal)

Results are persisted to DB so each county is only searched once.
"""

from __future__ import annotations

import re
from typing import Any

import httpx
import structlog

from aloha.config import settings
from aloha.db.engine import async_session_factory
from aloha.db.repositories.county_url import CountyUrlRepository

log = structlog.get_logger().bind(component="county_url_resolver")

# ── Static registry of known county URLs ──────────────────────────────────────
# Consolidated from scraper registries (Socrata, qPublic, EagleWeb, ArcGIS, etc.)
_STATIC_REGISTRY: dict[tuple[str, str, str], str] = {
    # Wyoming
    ("WY", "natrona", "assessor"): "https://assessorsearch.natronacounty-wy.gov",
    ("WY", "natrona", "tax_collector"): "https://treasurersearch.natronacounty-wy.gov",
    ("WY", "natrona", "delinquent_list"): (
        "https://www.natronacounty-wy.gov/DocumentCenter/View/12592/Delinquent-List-2025"
    ),
    ("WY", "laramie", "assessor"): "https://www.laramiecounty.com/assessor",
    # Florida
    ("FL", "orange", "assessor"): "https://www.ocpafl.org",
    ("FL", "orange", "tax_collector"): "https://www.octaxcol.com",
    ("FL", "duval", "assessor"): "https://www.coj.net/departments/property-appraiser",
    ("FL", "duval", "tax_collector"): "https://www.coj.net/departments/finance/tax-collector",
    ("FL", "hillsborough", "assessor"): "https://www.hcpafl.org",
    ("FL", "hillsborough", "tax_collector"): "https://hillsboroughcounty.org/residents/property-owners-and-renters/pay-property-taxes",
    ("FL", "miami-dade", "assessor"): "https://www.miamidadepa.gov",
    ("FL", "miami-dade", "tax_collector"): "https://www.miamidade.gov/taxcollector",
    ("FL", "broward", "assessor"): "https://web.bcpa.net",
    ("FL", "pinellas", "assessor"): "https://www.pcpao.org",
    ("FL", "lee", "assessor"): "https://www.leepa.org",
    ("FL", "palm beach", "assessor"): "https://www.pbcgov.org/papa",
    # Texas
    ("TX", "harris", "assessor"): "https://hcad.org",
    ("TX", "dallas", "assessor"): "https://www.dallascad.org",
    ("TX", "tarrant", "assessor"): "https://www.tad.org",
    ("TX", "bexar", "assessor"): "https://www.bcad.org",
    ("TX", "travis", "assessor"): "https://www.traviscad.org",
    # Georgia
    ("GA", "fulton", "assessor"): "https://www.qpublic.net/ga/fulton",
    ("GA", "dekalb", "assessor"): "https://www.qpublic.net/ga/dekalb",
    ("GA", "gwinnett", "assessor"): "https://www.qpublic.net/ga/gwinnett",
    ("GA", "cobb", "assessor"): "https://www.qpublic.net/ga/cobb",
    # Arizona
    ("AZ", "maricopa", "assessor"): "https://mcassessor.maricopa.gov",
    ("AZ", "pima", "assessor"): "https://www.asr.pima.gov",
    # Illinois
    ("IL", "cook", "assessor"): "https://www.cookcountyassessor.com",
    # New Jersey
    ("NJ", "essex", "tax_collector"): "https://tax.essexcountynj.org",
    ("NJ", "hudson", "tax_collector"): "https://www.hudsoncountynj.org/tax",
    # Indiana
    ("IN", "marion", "assessor"): "https://www.indy.gov/agency/assessor",
    # Michigan
    ("MI", "wayne", "assessor"): "https://www.waynecounty.com/departments/treasurer",
}


class CountyUrlResolver:
    """Resolves assessor/tax-collector URLs for any county via 4-layer pipeline."""

    async def resolve(
        self, state: str, county: str, url_type: str = "assessor"
    ) -> str | None:
        """Return the best URL for a county's assessor/tax portal.

        Tries each layer in order; persists successful results to DB.
        Returns None if all layers fail.
        """
        state = state.upper()
        county = county.lower()

        # Layer 1: DB cache
        url = await self._check_database(state, county, url_type)
        if url:
            log.debug("resolved_from_db", state=state, county=county, url=url)
            return url

        # Layer 2: Static registry
        url = self._check_static_registry(state, county, url_type)
        if url:
            log.info("resolved_from_registry", state=state, county=county, url=url)
            await self._persist_url(state, county, url_type, url, confidence=1.0, source="seed")
            return url

        # Layer 3: Web search
        candidates = await self._search_web(state, county, url_type)
        if candidates:
            # Layer 4: LLM validation
            validated = await self._validate_candidates(candidates, state, county, url_type)
            if validated:
                log.info(
                    "resolved_via_search_and_validation",
                    state=state, county=county, url=validated,
                )
                await self._persist_url(
                    state, county, url_type, validated, confidence=0.9, source="llm_validated"
                )
                return validated

            # Use best unvalidated candidate if LLM unavailable
            best = candidates[0]
            log.info(
                "resolved_via_search_unvalidated",
                state=state, county=county, url=best,
            )
            await self._persist_url(
                state, county, url_type, best, confidence=0.5, source="searxng"
            )
            return best

        log.warning("resolution_failed", state=state, county=county, url_type=url_type)
        return None

    # ── Layer 1: Database cache ───────────────────────────────────────────

    async def _check_database(
        self, state: str, county: str, url_type: str
    ) -> str | None:
        try:
            async with async_session_factory() as session:
                repo = CountyUrlRepository(session)
                record = await repo.get_url(state, county, url_type)
                return record.url if record else None
        except Exception as exc:
            log.debug("db_check_failed", error=str(exc))
            return None

    # ── Layer 2: Static registry ──────────────────────────────────────────

    def _check_static_registry(
        self, state: str, county: str, url_type: str
    ) -> str | None:
        return _STATIC_REGISTRY.get((state, county, url_type))

    # ── Layer 3: Web search via SearXNG ───────────────────────────────────

    async def _search_web(
        self, state: str, county: str, url_type: str
    ) -> list[str]:
        """Search SearXNG for county assessor/tax URLs. Returns candidate URLs."""
        query = f"{county} county {state} {url_type.replace('_', ' ')} property tax site:.gov"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{settings.searxng_url}/search",
                    params={"q": query, "format": "json", "engines": "google,bing,duckduckgo"},
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            log.debug("searxng_search_failed", error=str(exc))
            return []

        results: list[dict[str, Any]] = data.get("results", [])
        candidates: list[str] = []

        for r in results[:10]:
            url = r.get("url", "")
            if not url:
                continue
            # Prefer .gov domains and tax/assessor keywords
            if self._is_likely_tax_url(url, county):
                candidates.append(url)

        return candidates

    def _is_likely_tax_url(self, url: str, county: str) -> bool:
        """Heuristic filter: is this URL likely a county tax/assessor portal?"""
        url_lower = url.lower()
        # Prefer .gov domains
        has_gov = ".gov" in url_lower
        # Check for tax-related keywords
        tax_keywords = re.compile(
            r"(tax|assessor|treasurer|property|appraiser|parcel|lien)", re.IGNORECASE
        )
        has_keyword = bool(tax_keywords.search(url_lower))
        # Check county name appears
        county_clean = county.replace(" ", "").replace("-", "")
        has_county = county_clean in url_lower.replace("-", "").replace(" ", "")

        # Accept if .gov + (keyword or county name)
        if has_gov and (has_keyword or has_county):
            return True
        # Accept if both keyword and county match even without .gov
        if has_keyword and has_county:
            return True
        return False

    # ── Layer 4: LLM validation via Ollama ────────────────────────────────

    async def _validate_candidates(
        self, candidates: list[str], state: str, county: str, url_type: str
    ) -> str | None:
        """Fetch each candidate page and ask Ollama if it's a tax portal."""
        for url in candidates[:3]:
            try:
                async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        continue
                    page_text = resp.text[:3000]  # First 3KB of HTML

                validated = await self._ask_llm_is_tax_portal(
                    page_text, county, state, url_type
                )
                if validated:
                    return url
            except Exception:
                continue

        return None

    async def _ask_llm_is_tax_portal(
        self, page_html: str, county: str, state: str, url_type: str
    ) -> bool:
        """Ask Ollama (via OpenAI-compat API) if the page is a tax portal."""
        prompt = (
            f"Is this HTML page a {url_type.replace('_', ' ')} portal for "
            f"{county} county, {state}? Answer only YES or NO.\n\n"
            f"HTML snippet:\n{page_html[:2000]}"
        )
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{settings.ollama_base_url}/v1/chat/completions",
                    json={
                        "model": "llama3.1:8b",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.0,
                        "max_tokens": 10,
                    },
                )
                if resp.status_code != 200:
                    return False
                data = resp.json()
                answer = data["choices"][0]["message"]["content"].strip().upper()
                return answer.startswith("YES")
        except Exception as exc:
            log.debug("llm_validation_failed", error=str(exc))
            return False

    # ── Persistence ───────────────────────────────────────────────────────

    async def _persist_url(
        self,
        state: str,
        county: str,
        url_type: str,
        url: str,
        confidence: float,
        source: str,
    ) -> None:
        """Save a resolved URL to the database."""
        try:
            async with async_session_factory() as session:
                repo = CountyUrlRepository(session)
                await repo.upsert(
                    state=state,
                    county=county,
                    url_type=url_type,
                    url=url,
                    confidence=confidence,
                    source=source,
                )
                await session.commit()
        except Exception as exc:
            log.warning("persist_url_failed", error=str(exc))
