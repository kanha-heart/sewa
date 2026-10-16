"""Login with phone number + one-time code (OTP).
In DEV_MODE the code is printed in the server console AND returned to the browser, so you can test without SMS.
For real users, send the code by SMS or WhatsApp and set DEV_MODE=0."""
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from ..config import DEV_MODE, SUPERADMIN_PHONE
from ..db import get_session
from ..deps import normalize_phone
from ..models import GROUPS, LoginSession, Otp, Volunteer, utcnow
from ..services import as_utc, me_out

router = APIRouter(prefix="/api/auth", tags=["auth"])


class OtpIn(BaseModel):
    phone: str


class VerifyIn(BaseModel):
    phone: str
    code: str
    name: str = ""
    group: str = ""


@router.post("/request-otp")
def request_otp(body: OtpIn, session: Session = Depends(get_session)):
    phone = normalize_phone(body.phone)
    if not phone:
        raise HTTPException(400, "Enter a 10 digit phone number")
    code = f"{secrets.randbelow(10**6):06d}"
    session.add(Otp(phone=phone, code=code, expires_at=utcnow() + timedelta(minutes=10)))
    session.commit()
    print(f"[SEWA login code] {phone}: {code}")
    out = {"ok": True}
    if DEV_MODE:
        out["dev_code"] = code
    return out


@router.post("/verify")
def verify(body: VerifyIn, session: Session = Depends(get_session)):
    phone = normalize_phone(body.phone)
    otp = session.exec(
        select(Otp)
        .where(Otp.phone == phone, Otp.code == body.code.strip(), Otp.used == False)  # noqa: E712
        .order_by(Otp.id.desc())
    ).first()
    if not otp or as_utc(otp.expires_at) < utcnow():
        raise HTTPException(400, "That code is wrong or has expired")
    otp.used = True

    v = session.exec(select(Volunteer).where(Volunteer.phone == phone)).first()
    if not v:
        v = Volunteer(phone=phone)
        session.add(v)
    if not v.profile_done:
        if not body.name.strip() or body.group not in GROUPS:
            raise HTTPException(400, "First time here: add your name and choose Brothers or Sisters")
        v.name = body.name.strip()[:60]
        v.group = body.group
        v.profile_done = True
    if phone == SUPERADMIN_PHONE:
        v.is_admin = True
        v.admin_dept_id = None
    session.add(v)
    session.commit()
    session.refresh(v)

    token = secrets.token_urlsafe(32)
    session.add(LoginSession(token=token, volunteer_id=v.id))
    session.commit()
    return {"token": token, "me": me_out(v)}
