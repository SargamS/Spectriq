"""
STUB authentication.

This backend skeleton does not implement real auth (JWT/OAuth/session
cookies). Instead, `get_current_user` resolves a user from an
`X-User-Id` header (or the `X-User-Email` header, creating the user on
first sight) so the rest of the app has a concrete `current_user` to work
with. Replace this with real auth before deploying.
"""
import uuid

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.user import User

DEMO_USER_EMAIL = "demo@spectriq.local"


def get_current_user(
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
) -> User:
    if x_user_id:
        try:
            user_uuid = uuid.UUID(x_user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid X-User-Id header")
        user = db.query(User).filter(User.id == user_uuid).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user

    # Fallback: get-or-create a demo user by email, so the API is usable
    # without wiring up auth during local development.
    email = x_user_email or DEMO_USER_EMAIL
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user
