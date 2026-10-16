"""Database tables. Each class with table=True becomes one table."""
from datetime import date, datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel

GROUPS = ("Brothers", "Sisters")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Department(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    incharge_name: str = ""
    place: str = ""
    lat: float = 0.0
    lng: float = 0.0


class Volunteer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)  # used to log in
    whatsapp_phone: str = ""  # optional, 10 digits, used only for WhatsApp alerts
    name: str = ""
    group: str = "Brothers"  # "Brothers" or "Sisters"
    availability: str = ""  # comma list: Morning,Afternoon,Evening
    profile_done: bool = False
    is_admin: bool = False
    # None with is_admin=True means admin of every department (top admin).
    admin_dept_id: Optional[int] = Field(default=None, foreign_key="department.id")
    created_at: datetime = Field(default_factory=utcnow)


class LoginSession(SQLModel, table=True):
    token: str = Field(primary_key=True)
    volunteer_id: int = Field(foreign_key="volunteer.id", index=True)
    created_at: datetime = Field(default_factory=utcnow)


class Otp(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True)
    code: str
    expires_at: datetime
    used: bool = False
    attempts: int = 0
    created_at: datetime = Field(default_factory=utcnow)


class Subscription(SQLModel, table=True):
    """A volunteer wants alerts for a department."""
    id: Optional[int] = Field(default=None, primary_key=True)
    volunteer_id: int = Field(foreign_key="volunteer.id", index=True)
    dept_id: int = Field(foreign_key="department.id", index=True)


class WorkRequest(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    dept_id: int = Field(foreign_key="department.id", index=True)
    work: str
    day: date = Field(index=True)
    start_time: str  # "HH:MM"
    duration_hours: float
    people_needed: int
    group: str  # "Brothers" or "Sisters"
    active: bool = True
    place: str = ""
    lat: float = 0.0
    lng: float = 0.0
    created_by: Optional[int] = Field(default=None, foreign_key="volunteer.id")
    created_at: datetime = Field(default_factory=utcnow)


class Signup(SQLModel, table=True):
    """One volunteer's hours on one request. Minutes since midnight allow partial hours."""
    id: Optional[int] = Field(default=None, primary_key=True)
    request_id: int = Field(foreign_key="workrequest.id", index=True)
    volunteer_id: int = Field(foreign_key="volunteer.id", index=True)
    from_min: int
    to_min: int


class Notification(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    volunteer_id: int = Field(foreign_key="volunteer.id", index=True)
    text: str
    channel: str = "whatsapp"
    status: str = "logged"
    created_at: datetime = Field(default_factory=utcnow)
