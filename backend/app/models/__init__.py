"""SQLAlchemy declarative base and model re-exports.

All models inherit from ``Base`` and are re-exported here for
convenience imports and metadata.create_all() registration.
"""

from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Import all models to register them on Base.metadata
# and make them available via from app.models import *
from app.models.customer import Customer  # noqa: E402, F401
from app.models.product import Product  # noqa: E402, F401
from app.models.credit import Credit  # noqa: E402, F401
from app.models.insurance import Insurance  # noqa: E402, F401
from app.models.policy import Policy  # noqa: E402, F401
from app.models.claim import Claim  # noqa: E402, F401
from app.models.application import Application  # noqa: E402, F401
from app.models.document import Document  # noqa: E402, F401
from app.models.conversation import Conversation  # noqa: E402, F401
from app.models.session import Session  # noqa: E402, F401
from app.models.opportunity import Opportunity  # noqa: E402, F401
from app.models.notification import Notification  # noqa: E402, F401
from app.models.interest_rate import InterestRate  # noqa: E402, F401
from app.models.multichannel import LedgerConflict, insert_message, redact_message  # noqa: E402, F401

__all__ = [
    "Base",
    "Customer",
    "Product",
    "Credit",
    "Insurance",
    "Policy",
    "Claim",
    "Application",
    "Document",
    "Conversation",
    "Session",
    "Opportunity",
    "Notification",
    "InterestRate",
    "LedgerConflict",
    "insert_message",
    "redact_message",
]
