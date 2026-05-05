"""SQLAlchemy ORM models — barrel import.

Importing this module guarantees that ``Base.metadata`` sees every table,
which is required for Alembic autogenerate to work correctly.
"""

from aloha.db.models.alert import Alert
from aloha.db.models.base import Base, TimestampMixin
from aloha.db.models.county_url import CountyUrl
from aloha.db.models.crawl_log import CrawlLog
from aloha.db.models.document_chunk import DocumentChunk
from aloha.db.models.outreach import DoNotContact, OutreachLog, OutreachTemplate
from aloha.db.models.owner import Entity, Owner, OwnerEntity
from aloha.db.models.parcel import Parcel
from aloha.db.models.property_image import PropertyImage
from aloha.db.models.queue_item import QueueItem
from aloha.db.models.score import Score
from aloha.db.models.source_screenshot import SourceScreenshot
from aloha.db.models.tax_lien import TaxLien
from aloha.db.models.user import User

__all__ = [
    "Base",
    "TimestampMixin",
    # Core entities
    "User",
    "Parcel",
    "TaxLien",
    "Owner",
    "Entity",
    "OwnerEntity",
    "Score",
    # Pipeline
    "QueueItem",
    "CrawlLog",
    # Evidence & media
    "PropertyImage",
    "SourceScreenshot",
    "DocumentChunk",
    # Outreach
    "OutreachLog",
    "DoNotContact",
    "OutreachTemplate",
    # Alerts
    "Alert",
    # URL resolution cache
    "CountyUrl",
]
