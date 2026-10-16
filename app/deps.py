"""Login checks used by the endpoints."""
import re

from fastapi import Depends, Header, HTTPException
from sqlmodel import Session

from .db import get_session
from .models import LoginSession, Volunteer


def normalize_phone(raw: str) -> str:
    """Keep the last 10 digits. Returns '' if there are fewer than 10."""
    digits = re.sub(r"\D", "", raw or "")
    return digits[-10:] if len(digits) >= 10 else ""


def current_volunteer(
    authorization: str = Header(default=""), session: Session = Depends(get_session)
) -> Volunteer:
    token = authorization.removeprefix("Bearer ").strip()
    login = session.get(LoginSession, token) if token else None
    volunteer = session.get(Volunteer, login.volunteer_id) if login else None
    if not volunteer:
        raise HTTPException(401, "Please sign in")
    return volunteer


def require_admin(me: Volunteer = Depends(current_volunteer)) -> Volunteer:
    if not me.is_admin:
        raise HTTPException(403, "Admins only")
    return me


def require_super(me: Volunteer = Depends(require_admin)) -> Volunteer:
    if me.admin_dept_id is not None:
        raise HTTPException(403, "Only the top admin can do this")
    return me
