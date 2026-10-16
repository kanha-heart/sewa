"""Admin endpoints. A department admin manages only their own department.
The top admin (SUPERADMIN_EMAIL) manages everything and creates departments."""
from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..config import SUPERADMIN_EMAIL
from ..db import get_session
from ..deps import normalize_email, require_admin, require_super
from ..models import Department, Signup, Volunteer, WorkRequest
from ..notify import alert_subscribers
from ..services import (
    can_manage, covered_hours, end_min, hm, is_full, req_out, signups_of, start_min, target_hours,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])

TIME = r"^([01]\d|2[0-3]):[0-5]\d$"


class RequestIn(BaseModel):
    dept_id: int
    work: str = Field(min_length=1, max_length=120)
    day: date
    start_time: str = Field(pattern=TIME)
    duration_hours: float = Field(gt=0, le=12)
    people_needed: int = Field(ge=1, le=500)
    group: Literal["Brothers", "Sisters"]
    place: Optional[str] = None
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)


class RequestPatch(BaseModel):
    dept_id: Optional[int] = None
    work: Optional[str] = Field(default=None, min_length=1, max_length=120)
    day: Optional[date] = None
    start_time: Optional[str] = Field(default=None, pattern=TIME)
    duration_hours: Optional[float] = Field(default=None, gt=0, le=12)
    people_needed: Optional[int] = Field(default=None, ge=1, le=500)
    group: Optional[Literal["Brothers", "Sisters"]] = None
    active: Optional[bool] = None
    place: Optional[str] = None
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)


class CopyIn(BaseModel):
    day: date
    start_time: Optional[str] = Field(default=None, pattern=TIME)
    people_needed: Optional[int] = Field(default=None, ge=1, le=500)


class DeptIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    incharge_name: str = Field(min_length=1, max_length=60)
    incharge_email: str
    place: str = ""
    lat: float = Field(default=0.0, ge=-90, le=90)
    lng: float = Field(default=0.0, ge=-180, le=180)


class AdminIn(BaseModel):
    email: str
    name: str = ""
    dept_id: Optional[int] = None


def _get_managed_request(session: Session, me: Volunteer, request_id: int) -> WorkRequest:
    req = session.get(WorkRequest, request_id)
    if not req:
        raise HTTPException(404, "Request not found")
    if not can_manage(me, req.dept_id):
        raise HTTPException(403, "You are not an admin of this department")
    return req


@router.post("/requests")
def create_request(body: RequestIn, me: Volunteer = Depends(require_admin), session: Session = Depends(get_session)):
    dept = session.get(Department, body.dept_id)
    if not dept:
        raise HTTPException(404, "Department not found")
    if not can_manage(me, dept.id):
        raise HTTPException(403, "You are not an admin of this department")
    req = WorkRequest(
        dept_id=dept.id, work=body.work.strip(), day=body.day, start_time=body.start_time,
        duration_hours=body.duration_hours, people_needed=body.people_needed, group=body.group,
        place=body.place if body.place is not None else dept.place,
        lat=body.lat if body.lat is not None else dept.lat,
        lng=body.lng if body.lng is not None else dept.lng,
        created_by=me.id,
    )
    session.add(req)
    session.commit()
    session.refresh(req)
    alerted = alert_subscribers(session, req, "New seva")
    return {**req_out(session, req, me), "alerted": alerted}


@router.patch("/requests/{request_id}")
def update_request(
    request_id: int, body: RequestPatch, me: Volunteer = Depends(require_admin), session: Session = Depends(get_session)
):
    req = _get_managed_request(session, me, request_id)
    data = body.model_dump(exclude_unset=True)
    if "dept_id" in data and data["dept_id"] is not None:
        if not session.get(Department, data["dept_id"]) or not can_manage(me, data["dept_id"]):
            raise HTTPException(403, "You cannot move this request to that department")

    old_start, old_people, old_active = start_min(req), req.people_needed, req.active
    old_day = req.day
    for key, value in data.items():
        if value is not None:
            setattr(req, key, value.strip() if isinstance(value, str) else value)
    session.add(req)

    # If the time moved or got shorter, move volunteers' hours with it and trim what no longer fits.
    shifted = start_min(req) != old_start or "duration_hours" in data
    if shifted:
        new_start, new_end = start_min(req), end_min(req)
        for s in signups_of(session, req.id):
            s.from_min = max(new_start, s.from_min - old_start + new_start)
            s.to_min = min(new_end, s.to_min - old_start + new_start)
            if s.to_min <= s.from_min:
                session.delete(s)
            else:
                session.add(s)
    session.commit()
    session.refresh(req)

    signups = signups_of(session, req.id)
    alerted = 0
    if req.active:
        if not old_active:
            alerted = alert_subscribers(session, req, "Open again")
        elif req.day != old_day or shifted:
            alerted = alert_subscribers(session, req, "Request updated")
        elif req.people_needed > old_people and not is_full(req, signups):
            alerted = alert_subscribers(session, req, "More hands needed")
    return {**req_out(session, req, me), "alerted": alerted}


@router.post("/requests/{request_id}/copy")
def copy_request(
    request_id: int, body: CopyIn, me: Volunteer = Depends(require_admin), session: Session = Depends(get_session)
):
    src = _get_managed_request(session, me, request_id)
    new = WorkRequest(
        dept_id=src.dept_id, work=src.work, day=body.day, start_time=body.start_time or src.start_time,
        duration_hours=src.duration_hours, people_needed=body.people_needed or src.people_needed,
        group=src.group, place=src.place, lat=src.lat, lng=src.lng, created_by=me.id,
    )
    session.add(new)
    session.commit()
    session.refresh(new)
    alerted = alert_subscribers(session, new, "New seva")
    return {**req_out(session, new, me), "alerted": alerted}


@router.get("/analytics")
def analytics(_: Volunteer = Depends(require_admin), session: Session = Depends(get_session)):
    reqs = session.exec(select(WorkRequest)).all()
    depts = {d.id: d.name for d in session.exec(select(Department)).all()}
    by_dept: dict[str, dict] = {name: {"name": name, "requested": 0.0, "covered": 0.0, "requests": 0} for name in depts.values()}
    by_day: dict[str, float] = {}
    total_req = total_cov = people = need = 0.0
    open_count = 0
    for r in reqs:
        signups = signups_of(session, r.id)
        tgt, cov = target_hours(r), min(covered_hours(signups), target_hours(r))
        total_req += tgt
        total_cov += cov
        people += len(signups)
        need += r.people_needed
        open_count += 1 if r.active else 0
        row = by_dept.setdefault(depts.get(r.dept_id, "?"), {"name": depts.get(r.dept_id, "?"), "requested": 0.0, "covered": 0.0, "requests": 0})
        row["requested"] += tgt
        row["covered"] += cov
        row["requests"] += 1
        by_day[r.day.isoformat()] = by_day.get(r.day.isoformat(), 0.0) + tgt
    return {
        "total_requests": len(reqs),
        "open_requests": open_count,
        "person_hours_requested": total_req,
        "person_hours_covered": total_cov,
        "fill_rate": round(total_cov / total_req * 100) if total_req else 0,
        "signups": int(people),
        "people_needed": int(need),
        "by_dept": list(by_dept.values()),
        "by_day": [{"day": d, "requested": h} for d, h in sorted(by_day.items())],
    }


@router.post("/departments")
def create_department(body: DeptIn, me: Volunteer = Depends(require_super), session: Session = Depends(get_session)):
    if session.exec(select(Department).where(Department.name == body.name.strip())).first():
        raise HTTPException(409, "A department with this name already exists")
    email = normalize_email(body.incharge_email)
    if not email:
        raise HTTPException(400, "Enter the in-charge's email address")
    dept = Department(
        name=body.name.strip(), incharge_name=body.incharge_name.strip(),
        place=body.place.strip(), lat=body.lat, lng=body.lng,
    )
    session.add(dept)
    session.commit()
    session.refresh(dept)
    # Copy the values now: the next commit makes the dept object stale.
    dept_id, dept_name, incharge_name = dept.id, dept.name, dept.incharge_name
    place, lat, lng = dept.place, dept.lat, dept.lng
    v = session.exec(select(Volunteer).where(Volunteer.email == email)).first()
    if not v:
        v = Volunteer(email=email, name=incharge_name)
    if not (v.is_admin and v.admin_dept_id is None):  # never reduce the top admin
        v.is_admin = True
        v.admin_dept_id = dept_id
    session.add(v)
    session.commit()
    return {
        "id": dept_id, "name": dept_name, "incharge_name": incharge_name,
        "place": place, "lat": lat, "lng": lng,
    }


@router.get("/admins")
def list_admins(me: Volunteer = Depends(require_admin), session: Session = Depends(get_session)):
    q = select(Volunteer).where(Volunteer.is_admin == True)  # noqa: E712
    if me.admin_dept_id is not None:
        q = q.where(Volunteer.admin_dept_id == me.admin_dept_id)
    depts = {d.id: d.name for d in session.exec(select(Department)).all()}
    return [
        {"id": v.id, "name": v.name, "email": v.email, "dept_id": v.admin_dept_id,
         "dept_name": depts.get(v.admin_dept_id, "All departments")}
        for v in session.exec(q).all()
    ]


@router.post("/admins")
def add_admin(body: AdminIn, me: Volunteer = Depends(require_admin), session: Session = Depends(get_session)):
    email = normalize_email(body.email)
    if not email:
        raise HTTPException(400, "Enter a valid email address")
    dept_id = body.dept_id
    if me.admin_dept_id is not None:
        dept_id = me.admin_dept_id  # department admins can only add helpers to their own department
    if dept_id is not None and not session.get(Department, dept_id):
        raise HTTPException(404, "Department not found")
    v = session.exec(select(Volunteer).where(Volunteer.email == email)).first()
    if not v:
        v = Volunteer(email=email, name=body.name.strip() or "Helper")
    if me.admin_dept_id is not None and v.is_admin and v.admin_dept_id != dept_id:
        raise HTTPException(403, "This person is an admin elsewhere")
    if SUPERADMIN_EMAIL and email == SUPERADMIN_EMAIL:
        raise HTTPException(400, "This is the top admin already")
    v.is_admin = True
    v.admin_dept_id = dept_id
    session.add(v)
    session.commit()
    return {"ok": True}


@router.delete("/admins/{volunteer_id}")
def remove_admin(volunteer_id: int, me: Volunteer = Depends(require_admin), session: Session = Depends(get_session)):
    v = session.get(Volunteer, volunteer_id)
    if not v or not v.is_admin:
        raise HTTPException(404, "Admin not found")
    if SUPERADMIN_EMAIL and v.email == SUPERADMIN_EMAIL:
        raise HTTPException(400, "The top admin cannot be removed")
    if me.admin_dept_id is not None and (v.admin_dept_id != me.admin_dept_id or v.id == me.id):
        raise HTTPException(403, "You can only remove other helpers in your department")
    v.is_admin = False
    v.admin_dept_id = None
    session.add(v)
    session.commit()
    return {"ok": True}
