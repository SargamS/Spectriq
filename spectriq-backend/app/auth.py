"""
Authentication via Clerk (https://clerk.com).

The frontend signs the user in with Clerk (Google OAuth or email) and sends
the resulting session JWT on every request as `Authorization: Bearer <token>`.
This module verifies that JWT against Clerk's public JWKS - it never trusts
a client-supplied identity header. (Previous version of this file identified
users purely from an `X-User-Id`/`X-User-Email` header with no verification
at all - that's gone now.)

Setup required:
  1. Create a free Clerk application at https://clerk.com
  2. Set CLERK_JWKS_URL in your environment (see app/config.py for the
     exact value - it's your Clerk Frontend API URL + /.well-known/jwks.json)
  3. The frontend needs matching NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY /
     CLERK_SECRET_KEY env vars (see spectriq-landing-page's Clerk setup)
"""
from functools import lru_cache

import jwt
from fastapi import Depends, Header, HTTPException
from jwt import PyJWKClient
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models.user import User


@lru_cache
def _jwk_client() -> PyJWKClient:
    # PyJWKClient caches the JWKS itself and re-fetches on an unrecognized
    # key id, so a single long-lived client is fine to reuse across requests.
    if not settings.CLERK_JWKS_URL:
        raise HTTPException(
            status_code=500,
            detail="Server misconfigured: CLERK_JWKS_URL is not set.",
        )
    return PyJWKClient(settings.CLERK_JWKS_URL)


def _verify_session_token(token: str) -> dict:
    try:
        signing_key = _jwk_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            # Clerk session tokens don't set a fixed `aud`; we're already
            # verifying the signature against Clerk's own JWKS and that the
            # token isn't expired, which is what actually matters here.
            options={"verify_aud": False},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid or expired session: {exc}") from exc
    return claims


def get_current_user(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or malformed Authorization header. Expected 'Bearer <clerk session token>'.",
        )
    token = authorization.removeprefix("Bearer ").strip()

    claims = _verify_session_token(token)
    clerk_id = claims.get("sub")
    if not clerk_id:
        raise HTTPException(status_code=401, detail="Session token missing 'sub' claim")

    # Email is only present if your Clerk JWT template includes it - treated
    # as a best-effort display field, never as the identity key.
    email = claims.get("email")

    user = db.query(User).filter(User.clerk_id == clerk_id).first()
    if not user:
        user = User(clerk_id=clerk_id, email=email)
        db.add(user)
        db.commit()
        db.refresh(user)
    elif email and user.email != email:
        # Keep the display email in sync if it changed on Clerk's side.
        user.email = email
        db.commit()

    return user
