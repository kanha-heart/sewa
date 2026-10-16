"""Endpoints for every signed-in person: profile, alerts, browsing requests, joining."""
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..db import get_session
from ..deps import current_volunteer, normalize_phone
from ..models import Department, Notification, Signup, Subscription, Volunteer, WorkRequest
from ..services import as_utc, end_min, is_full, me_out, req_out, signups_of, start_min

router = APIRouter(prefix="/api", tags=["volunteer"])


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    group: Literal["Brothers", "Sisters"]
    availability: list[Literal["Morning", "Afternoon", "Evening"]] = []
    whatsapp_phone: str = Field(default="", max_length=20)


class SubsIn(BaseModel):
    dept_ids: list[int]


class JoinIn(BaseModel):
    from_min: int
    to_min: int


@router.get("/me")
def get_me(me: Volunteer = Depends(current_volunteer)):
    return me_out(me)


@router.put("/me")
def update_me(body: ProfileIn, me: Volunteer = Depends(current_volunteer), session: Session = Depends(get_session)):
    phone = ""
    if body.whatsapp_phone.strip():
        phone = normalize_phone(body.whatsapp_phone)
        if not phone:
            raise HTTPException(400, "The WhatsApp number needs 10 digits, or leave it empty")
    me.whatsapp_phone = phone
    me.name = body.name.strip()
    me.group = body.group
    me.availability = ",".join(body.availability)
    me.profile_done = True
    session.add(me)
    session.commit()
    session.refresh(me)
    return me_out(me)


@router.get("/departments")
def departments(_: Volunteer = Depends(current_volunteer), session: Session = Depends(get_session)):
    return session.exec(select(Department).order_by(Department.name)).all()


@router.get("/me/subscriptions")
def get_subscriptions(me: Volunteer = Depends(current_volunteer), session: Session = Depends(get_session)):
    subs = session.exec(select(Subscription).where(Subscription.volunteer_id == me.id)).all()
    return {"dept_ids": [s.dept_id for s in subs]}


@router.put("/me/subscriptions")
def set_subscriptions(body: SubsIn, me: Volunteer = Depends(current_volunteer), session: Session = Depends(get_session)):
    for s in session.exec(select(Subscription).where(Subscription.volunteer_id == me.id)).all():
        session.delete(s)
    valid = {d.id for d in session.exec(select(Department)).all()}
    for dept_id in sorted(set(body.dept_ids) & valid):
        session.add(Subscription(volunteer_id=me.id, dept_id=dept_id))
    session.commit()
    return {"dept_ids": sorted(set(body.dept_ids) & valid)}


@router.get("/me/notifications")
def my_notifications(me: Volunteer = Depends(current_volunteer), session: Session = Depends(get_session)):
    rows = session.exec(
        select(Notification).where(Notification.volunteer_id == me.id).order_by(Notification.id.desc()).limit(30)
    ).all()
    return [{"id": n.id, "text": n.text, "created_at": as_utc(n.created_at).isoformat(), "status": n.status} for n in rows]


@router.get("/requests")
def list_requests(
    include_inactive: bool = False,
    include_past: bool = False,
    me: Volunteer = Depends(current_volunteer),
    session: Session = Depends(get_session),
):
    q = select(WorkRequest)
    if not include_past:
        q = q.where(WorkRequest.day >= date.today())
    if not (include_inactive and me.is_admin):
        q = q.where(WorkRequest.active == True)  # noqa: E712
    if not me.is_admin:
        q = q.where(WorkRequest.group == me.group)  # volunteers only see requests for their group
    reqs = session.exec(q.order_by(WorkRequest.day, WorkRequest.start_time)).all()
    return [req_out(session, r, me) for r in reqs]


@router.post("/requests/{request_id}/join")
def join(request_id: int, body: JoinIn, me: Volunteer = Depends(current_volunteer), session: Session = Depends(get_session)):
    req = session.get(WorkRequest, request_id)
    if not req or not req.active:
        raise HTTPException(404, "This request is not open")
    if req.group != me.group:
        raise HTTPException(403, f"This request is for {req.group}")
    if not (start_min(req) <= body.from_min < body.to_min <= end_min(req)):
        raise HTTPException(400, "Choose hours inside the time of the request")
    signups = signups_of(session, req.id)
    mine = next((s for s in signups if s.volunteer_id == me.id), None)
    others = [s for s in signups if s is not mine]
    if is_full(req, others):
        raise HTTPException(409, "Sorry, this request just filled up")
    if mine:
        mine.from_min, mine.to_min = body.from_min, body.to_min
        session.add(mine)
    else:
        session.add(Signup(request_id=req.id, volunteer_id=me.id, from_min=body.from_min, to_min=body.to_min))
    session.commit()
    return req_out(session, req, me)


@router.delete("/requests/{request_id}/join")
def leave(request_id: int, me: Volunteer = Depends(current_volunteer), session: Session = Depends(get_session)):
    req = session.get(WorkRequest, request_id)
    if not req:
        raise HTTPException(404, "Request not found")
    mine = session.exec(
        select(Signup).where(Signup.request_id == request_id, Signup.volunteer_id == me.id)
    ).first()
    if mine:
        session.delete(mine)
        session.commit()
    return req_out(session, req, me)
