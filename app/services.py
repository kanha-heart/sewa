"""Shared helpers: hour maths and the JSON shape sent to the app."""
from datetime import datetime, timezone

from sqlmodel import Session, select

from .models import Department, Signup, Volunteer, WorkRequest


def as_utc(dt: datetime) -> datetime:
    """Always return a timezone-aware UTC datetime, whichever way the database gave it back."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def hm(t: str) -> int:
    """'07:30' -> 450 minutes since midnight."""
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def start_min(req: WorkRequest) -> int:
    return hm(req.start_time)


def end_min(req: WorkRequest) -> int:
    return hm(req.start_time) + round(req.duration_hours * 60)


def target_hours(req: WorkRequest) -> float:
    return req.people_needed * req.duration_hours


def covered_hours(signups) -> float:
    return sum((s.to_min - s.from_min) / 60 for s in signups)


def is_full(req: WorkRequest, signups) -> bool:
    return covered_hours(signups) >= target_hours(req) - 1e-9


def signups_of(session: Session, request_id: int):
    return session.exec(select(Signup).where(Signup.request_id == request_id)).all()


def can_manage(v: Volunteer, dept_id: int) -> bool:
    return bool(v.is_admin and (v.admin_dept_id is None or v.admin_dept_id == dept_id))


def me_out(v: Volunteer) -> dict:
    return {
        "id": v.id,
        "name": v.name,
        "phone": v.phone,
        "group": v.group,
        "availability": [a for a in v.availability.split(",") if a],
        "profile_done": v.profile_done,
        "is_admin": v.is_admin,
        "admin_dept_id": v.admin_dept_id,
        "is_super": v.is_admin and v.admin_dept_id is None,
    }


def req_out(session: Session, req: WorkRequest, me: Volunteer) -> dict:
    signups = signups_of(session, req.id)
    dept = session.get(Department, req.dept_id)
    mine = next((s for s in signups if s.volunteer_id == me.id), None)
    return {
        "id": req.id,
        "dept_id": req.dept_id,
        "dept_name": dept.name if dept else "",
        "work": req.work,
        "day": req.day.isoformat(),
        "start_time": req.start_time,
        "duration_hours": req.duration_hours,
        "people_needed": req.people_needed,
        "group": req.group,
        "active": req.active,
        "place": req.place,
        "lat": req.lat,
        "lng": req.lng,
        "covered_hours": covered_hours(signups),
        "target_hours": target_hours(req),
        "signups_count": len(signups),
        "full": is_full(req, signups),
        "my_slot": {"from_min": mine.from_min, "to_min": mine.to_min} if mine else None,
        "can_manage": can_manage(me, req.dept_id),
    }
