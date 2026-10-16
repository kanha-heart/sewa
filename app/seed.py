"""Sample departments so the app is not empty on first run. Coordinates are sample values: replace them."""
from sqlmodel import Session, select

from .models import Department

SAMPLE = [
    ("Bookstore", "Anita Rao", "Bookstore, Main Block", 17.1822, 78.2291),
    ("Heartyculture", "Suresh Kumar", "Herb Garden", 17.1809, 78.2274),
    ("Nursery", "Lakshmi Devi", "Nursery Shed", 17.1814, 78.2268),
    ("Pottery", "Ramesh Babu", "Pottery Studio", 17.1827, 78.2283),
    ("Meditation Hall", "Kavitha Reddy", "Meditation Hall", 17.1831, 78.2299),
    ("Kitchen", "Venkat Rao", "Central Kitchen", 17.1818, 78.2302),
    ("Dining", "Padma Latha", "Dining Hall", 17.1820, 78.2306),
    ("Dish Washing", "Mohan Das", "Dining Hall, back yard", 17.1817, 78.2308),
    ("Bedding", "Sunitha Rani", "Linen Store", 17.1836, 78.2287),
    ("Comfort Dorms", "Harish Goud", "Comfort Dorm Block", 17.1840, 78.2279),
]


def seed_if_empty(session: Session) -> None:
    if session.exec(select(Department)).first():
        return
    for name, incharge, place, lat, lng in SAMPLE:
        session.add(Department(name=name, incharge_name=incharge, place=place, lat=lat, lng=lng))
    session.commit()
