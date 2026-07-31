"""
User model, keyed by Clerk's user ID.

Auth is handled by Clerk (see app/auth.py): the frontend authenticates the
user via Clerk and sends a session JWT, which the backend verifies against
Clerk's JWKS and reads the `sub` (Clerk user ID) claim from. `clerk_id` is
the real identity key here - `email` is best-effort (only present if Clerk's
JWT template includes it) and is kept purely as a display/debug field, never
used for authentication or lookup.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clerk_id = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
