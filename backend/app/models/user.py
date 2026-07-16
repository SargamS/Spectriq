"""
Minimal User model. Real auth (JWT/OAuth/session) is out of scope for this
backend skeleton - see app/auth.py for a stub `get_current_user` dependency
that should be replaced with real auth before shipping.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
