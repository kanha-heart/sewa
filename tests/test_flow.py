"""Run with:  pytest -q
Walks through the main story: admin posts, volunteers join (full and partial hours), cancel,
the number changes, alerts arrive, and permissions are enforced."""
import os
import sys
from datetime import date, timedelta
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///test_sewa.db"
os.environ["SUPERADMIN_PHONE"] = "9000000001"
os.environ["DEV_MODE"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if Path("test_sewa.db").exists():
    Path("test_sewa.db").unlink()

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def login(client, phone, name="", group=""):
    code = client.post("/api/auth/request-otp", json={"phone": phone}).json()["dev_code"]
    r = client.post("/api/auth/verify", json={"phone": phone, "code": code, "name": name, "group": group})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


def test_story():
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    with TestClient(app) as c:
        assert c.get("/api/ping").json() == {"ok": True}
        assert c.get("/api/requests").status_code == 401

        # top admin creates a department; its in-charge becomes an admin of that department only
        boss = login(c, "9000000001", "Boss", "Brothers")
        assert c.get("/api/me", headers=boss).json()["is_super"] is True
        r = c.post("/api/admin/departments", headers=boss, json={
            "name": "Library", "incharge_name": "Lata", "incharge_phone": "9000000002",
            "place": "Library hall", "lat": 17.18, "lng": 78.22})
        assert r.status_code == 200, r.text
        lib = r.json()["id"]
        kitchen = next(d["id"] for d in c.get("/api/departments", headers=boss).json() if d["name"] == "Kitchen")

        lata = login(c, "9000000002", "Lata", "Sisters")
        me = c.get("/api/me", headers=lata).json()
        assert me["is_admin"] and me["admin_dept_id"] == lib and not me["is_super"]

        # dept admin cannot touch another department or create departments
        bad = {"dept_id": kitchen, "work": "x", "day": tomorrow, "start_time": "07:00",
               "duration_hours": 2, "people_needed": 2, "group": "Brothers"}
        assert c.post("/api/admin/requests", headers=lata, json=bad).status_code == 403
        assert c.post("/api/admin/departments", headers=lata, json={
            "name": "Z", "incharge_name": "Z", "incharge_phone": "9000000009"}).status_code == 403

        # volunteers
        ravi = login(c, "9000000003", "Ravi", "Brothers")
        sita = login(c, "9000000004", "Sita", "Sisters")
        assert c.put("/api/me/subscriptions", headers=ravi, json={"dept_ids": [lib]}).status_code == 200

        # admin posts a request for Brothers: 2 people x 2 hours = 4 person-hours
        r = c.post("/api/admin/requests", headers=boss, json={
            "dept_id": lib, "work": "Shelve books", "day": tomorrow, "start_time": "09:00",
            "duration_hours": 2, "people_needed": 2, "group": "Brothers"})
        assert r.status_code == 200, r.text
        req = r.json()
        assert req["alerted"] == 1 and req["place"] == "Library hall"  # location copied from department
        rid = req["id"]

        # Ravi got an alert; Sita (Sisters) does not see the Brothers request
        notes = c.get("/api/me/notifications", headers=ravi).json()
        assert len(notes) == 1 and "Shelve books" in notes[0]["text"]
        assert all(x["id"] != rid for x in c.get("/api/requests", headers=sita).json())

        # partial hours: Ravi gives 9:00-10:00 (540 to 600)
        r = c.post(f"/api/requests/{rid}/join", headers=ravi, json={"from_min": 540, "to_min": 600})
        assert r.status_code == 200 and r.json()["covered_hours"] == 1.0
        # outside the window is rejected
        assert c.post(f"/api/requests/{rid}/join", headers=ravi, json={"from_min": 500, "to_min": 600}).status_code == 400
        # a Sister cannot join a Brothers request
        assert c.post(f"/api/requests/{rid}/join", headers=sita, json={"from_min": 540, "to_min": 600}).status_code == 403

        # Amit gives 2 hours and Kiran 1 hour: 1 + 2 + 1 = 4 person-hours, so the request is full
        amit = login(c, "9000000005", "Amit", "Brothers")
        kiran = login(c, "9000000006", "Kiran", "Brothers")
        assert c.post(f"/api/requests/{rid}/join", headers=amit, json={"from_min": 540, "to_min": 660}).status_code == 200
        r = c.post(f"/api/requests/{rid}/join", headers=kiran, json={"from_min": 540, "to_min": 600})
        assert r.status_code == 200 and r.json()["full"] is True
        # now full: a new volunteer is turned away
        john = login(c, "9000000007", "John", "Brothers")
        assert c.post(f"/api/requests/{rid}/join", headers=john, json={"from_min": 540, "to_min": 660}).status_code == 409

        # Ravi cancels his slot, so John can take the freed hour
        assert c.delete(f"/api/requests/{rid}/join", headers=ravi).json()["my_slot"] is None
        assert c.post(f"/api/requests/{rid}/join", headers=john, json={"from_min": 540, "to_min": 600}).status_code == 200

        # admin raises the number: alert goes out to followers (Ravi)
        r = c.patch(f"/api/admin/requests/{rid}", headers=lata, json={"people_needed": 3})
        assert r.status_code == 200 and r.json()["alerted"] == 1 and r.json()["full"] is False
        assert "More hands needed" in c.get("/api/me/notifications", headers=ravi).json()[0]["text"]

        # pause hides it from volunteers; activating brings it back
        c.patch(f"/api/admin/requests/{rid}", headers=lata, json={"active": False})
        assert all(x["id"] != rid for x in c.get("/api/requests", headers=ravi).json())
        c.patch(f"/api/admin/requests/{rid}", headers=lata, json={"active": True})
        assert any(x["id"] == rid for x in c.get("/api/requests", headers=ravi).json())

        # moving the start time shifts sign-ups with it
        c.patch(f"/api/admin/requests/{rid}", headers=lata, json={"start_time": "10:00"})
        mine = next(x for x in c.get("/api/requests", headers=john).json() if x["id"] == rid)["my_slot"]
        assert mine == {"from_min": 600, "to_min": 660}

        # copy to another day, changing only date and number
        r = c.post(f"/api/admin/requests/{rid}/copy", headers=lata, json={
            "day": (date.today() + timedelta(days=2)).isoformat(), "people_needed": 5})
        assert r.status_code == 200 and r.json()["people_needed"] == 5 and r.json()["signups_count"] == 0

        # analytics
        a = c.get("/api/admin/analytics", headers=lata).json()
        assert a["total_requests"] == 2 and a["person_hours_requested"] > 0
        assert any(d["name"] == "Library" for d in a["by_dept"])

        # dept admin adds a helper for their own department only
        assert c.post("/api/admin/admins", headers=lata, json={"phone": "9000000008", "name": "Helper", "dept_id": kitchen}).status_code == 200
        admins = c.get("/api/admin/admins", headers=boss).json()
        helper = next(x for x in admins if x["phone"] == "9000000008")
        assert helper["dept_id"] == lib  # forced to Lata's department

        # volunteers cannot use admin endpoints
        assert c.get("/api/admin/analytics", headers=ravi).status_code == 403
