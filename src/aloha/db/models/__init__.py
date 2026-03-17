"""SQLAlchemy ORM models — barrel import file.

Import all models here so that ``Base.metadata`` sees every table when
Alembic runs ``target_metadata = Base.metadata``.

Models will be added as they are implemented:

    from aloha.db.models.user import User              # noqa: F401
    from aloha.db.models.research import Research      # noqa: F401
    from aloha.db.models.parcel import Parcel          # noqa: F401
    from aloha.db.models.owner import Owner            # noqa: F401
    from aloha.db.models.queue_item import QueueItem   # noqa: F401
    from aloha.db.models.document import Document      # noqa: F401
"""
