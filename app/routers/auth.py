"""Login with email + one-time code (OTP).
The code is emailed (see app/emailer.py). In DEV_MODE the code is also returned to the browser,
so you can test on your own computer without email. Never use DEV_MODE on the internet."""
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from ..config import DEV_MODE, SUPERADMIN_EMAIL
from ..db import get_session
from ..deps import normalize_email
from ..emailer import EmailError, send_login_code
from ..models import GROUPS, LoginSession, Otp, Volunteer, utcnow
from ..services import as_utc, me_out

router = APIRouter(prefix="/api/auth", tags=["auth"])

MAX_CODES_PER_HOUR = 5   # per email address
MAX_WRONG_TRIES = 5      # then that code stops working


class OtpIn(BaseModel):
    email: str


class VerifyIn(BaseModel):
    email: str
    code: str
    name: str = ""
    group: str = ""


@router.post("/request-otp")
def request_otp(body: OtpIn, session: Session = Depends(get_session)):
    email = normalize_email(body.email)
    if not email:
        raise HTTPException(400, "Enter a valid email address")

    recent = session.exec(select(Otp).where(Otp.email == email).order_by(Otp.id.desc()).limit(20)).all()
    cutoff = utcnow() - timedelta(hours=1)
    if len([o for o in recent if as_utc(o.created_at) > cutoff]) >= MAX_CODES_PER_HOUR:
        raise HTTPException(429, "Too many codes requested. Please try again in an hour.")

    code = f"{secrets.randbelow(10**6):06d}"
    session.add(Otp(email=email, code=code, expires_at=utcnow() + timedelta(minutes=10)))
    session.commit()
    try:
        send_login_code(email, code)
    except EmailError as e:
        print(f"[SEWA email problem] {e}")
        raise HTTPException(502, "We could not send the email. Please try again in a minute.")
    out = {"ok": True}
    if DEV_MODE:
        out["dev_code"] = code
    return out


@router.post("/verify")
def verify(body: VerifyIn, session: Session = Depends(get_session)):
    email = normalize_email(body.email)
    otp = session.exec(
        select(Otp).where(Otp.email == email, Otp.used == False).order_by(Otp.id.desc())  # noqa: E712
    ).first()
    if not otp or as_utc(otp.expires_at) < utcnow():
        raise HTTPException(400, "That code is wrong or has expired")
    if not secrets.compare_digest(otp.code.encode(), body.code.strip().encode()):
        otp.attempts += 1
        if otp.attempts >= MAX_WRONG_TRIES:
            otp.used = True
        session.add(otp)
        session.commit()
        raise HTTPException(400, "That code is wrong or has expired")
    otp.used = True

    v = session.exec(select(Volunteer).where(Volunteer.email == email)).first()
    if not v:
        v = Volunteer(email=email)
        session.add(v)
    if not v.profile_done:
        if not body.name.strip() or body.group not in GROUPS:
            raise HTTPException(400, "First time here: add your name and choose Brothers or Sisters")
        v.name = body.name.strip()[:60]
        v.group = body.group
        v.profile_done = True
    if SUPERADMIN_EMAIL and email == SUPERADMIN_EMAIL:
        v.is_admin = True
        v.admin_dept_id = None
    session.add(v)
    session.commit()
    session.refresh(v)

    token = secrets.token_urlsafe(32)
    session.add(LoginSession(token=token, volunteer_id=v.id))
    session.commit()
    return {"token": token, "me": me_out(v)}
