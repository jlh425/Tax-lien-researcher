"""Agent registry."""

AGENT_REGISTRY: dict[str, str] = {
    "orchestrator": "aloha.agents.orchestrator.agent",
    "database": "aloha.agents.database.agent",
    "discovery": "aloha.agents.discovery.agent",
    "parcel_research": "aloha.agents.parcel_research.agent",
    "owner_research": "aloha.agents.owner_research.agent",
    "entity_research": "aloha.agents.entity_research.agent",
    "contact_research": "aloha.agents.contact_research.agent",
    "outreach": "aloha.agents.outreach.agent",
    "zoning": "aloha.agents.zoning.agent",
    "enrichment": "aloha.agents.enrichment.agent",
    "scoring": "aloha.agents.scoring.agent",
    "report": "aloha.agents.report.agent",
}
