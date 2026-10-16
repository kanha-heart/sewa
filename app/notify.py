"""Alerts. Every alert is saved in the Notification table (shown inside the app)
and also sent to WhatsApp when WHATSAPP_TOKEN and WHATSAPP_PHONE_ID are set."""
import httpx
from sqlmodel import Session, select

from .config import COUNTRY_CODE, WHATSAPP_PHONE_ID, WHATSAPP_TOKEN
from .models import Department, Notification, Subscription, Volunteer, WorkRequest
from .services import end_min


def fmt_min(m: int) -> str:
    h, mm = (m // 60) % 24, m % 60
    return f"{(h + 11) % 12 + 1}:{mm:02d} {'AM' if h < 12 else 'PM'}"


def message_text(req: WorkRequest, dept: Department, name: str, headline: str) -> str:
    hours = f"{req.duration_hours:g}"
    return (
        f"Hari Om {name}!\n"
        f"{headline} in {dept.name}:\n"
        f"{req.work}\n"
        f"{req.day.strftime('%a %d %b')}, {fmt_min(int(req.start_time[:2]) * 60 + int(req.start_time[3:]))} "
        f"to {fmt_min(end_min(req))} ({hours} h)\n"
        f"{req.people_needed} {req.group} needed\n"
        f"Location: {req.place} ({req.lat:.4f}, {req.lng:.4f})\n"
        f"Open Sewa to join, full or part of the time."
    )


def send_whatsapp(phone: str, text: str) -> str:
    """Returns 'logged', 'sent' or 'failed'.
    NOTE: Meta only allows free-text messages inside 24 hours of the user's last message.
    For alerts to everyone you must create and get approval for a message template."""
    if not (WHATSAPP_TOKEN and WHATSAPP_PHONE_ID):
        print(f"[WhatsApp not configured] to {phone}:\n{text}\n")
        return "logged"
    try:
        r = httpx.post(
            f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_ID}/messages",
            headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"},
            json={
                "messaging_product": "whatsapp",
                "to": COUNTRY_CODE + phone,
                "type": "text",
                "text": {"body": text},
            },
            timeout=10,
        )
        return "sent" if r.status_code < 300 else "failed"
    except Exception:
        return "failed"


def alert_subscribers(session: Session, req: WorkRequest, headline: str) -> int:
    """Alert volunteers who follow this department and belong to the group asked for."""
    dept = session.get(Department, req.dept_id)
    subs = session.exec(select(Subscription).where(Subscription.dept_id == req.dept_id)).all()
    sent = 0
    for sub in subs:
        v = session.get(Volunteer, sub.volunteer_id)
        if not v or v.group != req.group:
            continue
        text = message_text(req, dept, v.name or "friend", headline)
        # Everyone gets the alert inside the app. WhatsApp only if they added a number.
        status = send_whatsapp(v.whatsapp_phone, text) if v.whatsapp_phone else "in-app"
        session.add(Notification(volunteer_id=v.id, text=text, status=status))
        sent += 1
    session.commit()
    return sent
