# Sewa

Volunteer requests for an ashram or centre. Admins (heads of departments) post work. Volunteers join for the whole shift or only some hours, and get alerts. It works in a phone browser, for volunteers and for admins, and can be added to the home screen.

Stack: Python (FastAPI + SQLModel + SQLite) for the server. Plain HTML, CSS and JavaScript for the screens. No build step.

## Start in 10 minutes

You need Python 3.10 or newer and git.

```bash
# 1. get into the folder
cd sewa

# 2. make a private Python environment and install the packages
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. settings: copy the example and put YOUR phone number in SUPERADMIN_PHONE
cp .env.example .env               # Windows: copy .env.example .env

# 4. run the tests first (the server code was not run by the person who wrote it, so this matters)
pytest -q

# 5. start the server
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 .

1. Enter your phone number (the one in `.env`). In test mode (`DEV_MODE=1`) the one-time code appears on the screen and in the terminal.
2. First time only: type your name and choose Brothers or Sisters.
3. You are the top admin, so an **Admin** tab appears at the bottom. Try Post, Manage (the − and + buttons, Edit, Copy, Deactivate), Numbers, and People.
4. Open a private window and log in with another phone number as a volunteer. Turn on alerts for a department under **Alerts**, then post a request for it as admin. The alert shows in the volunteer's **Alerts** tab and is printed in the terminal.

If `pytest` or the server shows an error, copy the whole message and ask for help. Do not skip it.

## Open it on your phone

Same Wi-Fi: start the server with `uvicorn app.main:app --host 0.0.0.0 --reload`, find your computer's IP address (for example 192.168.1.20), and open `http://192.168.1.20:8000` on the phone.

The "Use my current location" button needs https, so it will not work on a plain `http://` address. It works once you deploy (below). On the phone, use the browser menu and choose "Add to Home Screen".

## What is where

```
app/
  main.py          starts the server, mounts the screens
  models.py        the database tables
  routers/auth.py  login with phone number + one-time code
  routers/public.py  profile, alerts, list requests, join, cancel slot
  routers/admin.py   post, edit, copy, resize, pause; analytics; departments; admins
  notify.py        alerts (saved in the app, and WhatsApp when configured)
  services.py      hour calculations
static/            index.html, style.css, app.js, manifest.json, icon.svg
tests/test_flow.py the main story as an automatic test
```

## How the rules work

- A request needs `people_needed` people for `duration_hours`. It is full when the hours covered reach people × hours. Two people giving one hour each count as one person for a 2 hour shift.
- Volunteers see only requests for their own group (Brothers or Sisters). Admins see all.
- Joining is limited to the request's time window. A volunteer can change or cancel their slot any time.
- Full requests stay visible to admins. They can Deactivate (hides it) and Activate later (volunteers who follow the department get an "Open again" alert).
- If an admin moves the start time, volunteers' hours move with it.
- A department admin manages only their own department and can make helpers admin of that department. Only the top admin (SUPERADMIN_PHONE) creates departments.

## Use git from day one

```bash
git init
git add .
git commit -m "Start Sewa"
```

Make a commit after each small thing that works. Make a branch for anything risky: `git switch -c whatsapp-alerts`.

## Put it online (so phones and https work)

1. Push the project to GitHub.
2. Create a Web Service on Render (or Railway). Build command: `pip install -r requirements.txt`. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
3. Free hosts wipe SQLite files when they restart. Create a free Postgres database (Render, Neon or Supabase), run `pip install psycopg2-binary` and add it to `requirements.txt`, and set the `DATABASE_URL` setting to its address.
4. Set the environment variables from `.env.example` on the host. Set `SUPERADMIN_PHONE` to your number and `DEV_MODE=0`.
5. With `DEV_MODE=0` the login code is no longer shown on screen. Before real users arrive you must send the code by SMS or WhatsApp. Replace the `print` in `app/routers/auth.py` (`request_otp`) with a call to an SMS provider such as Twilio or MSG91.

## Real WhatsApp alerts (do this last)

1. Create a Meta developer account and a WhatsApp Business app (WhatsApp Cloud API). Meta gives a test number for development. An adult should own the business account.
2. Put the token and phone number ID in `WHATSAPP_TOKEN` and `WHATSAPP_PHONE_ID`.
3. Meta only allows free text to people who messaged you in the last 24 hours. For alerts to everyone you must create a message template and get it approved, then change `send_whatsapp` in `app/notify.py` to send that template. Check Meta's current pricing and rules before you commit.
4. Sending happens inside the request right now. When there are many volunteers, move it to a background task or a queue.

## Before real users

- Add a limit on login code requests, and send the code by SMS.
- Ask volunteers for consent before sending WhatsApp messages, and let them switch alerts off (they can, under Alerts).
- Server dates use the server's clock. Set the server timezone to your local timezone.

## Ideas for later

Attendance check-in, reminders the day before, an export of hours per volunteer to Excel, a map of today's work, push notifications, and a Hindi or Telugu language switch.
