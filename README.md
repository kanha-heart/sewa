# Sewa

Volunteer requests for a community. Admins (heads of departments) post work. Volunteers join for the whole shift or only some hours, and get alerts. It runs in the phone browser for volunteers **and** admins, and can be installed on the home screen like an app.

- Server: Python (FastAPI + SQLModel). Database: Supabase Postgres online, a small file on your computer for testing.
- Screens: plain HTML, CSS, JavaScript in the `static` folder. No build step.
- Login: **email + one-time code**. WhatsApp number is optional, only for WhatsApp alerts.

**How to use this README:** do the parts in order, A to H. Copy and paste the commands exactly. Every command is run in the Terminal, inside the `sewa` folder, with `(.venv)` showing at the start of the line. If something fails, go to **Part I (Problems)**

---

## Part A. Run it on your computer


**A1. Put files in place.**
1. Unzip the `sewa.zip`

**A2. Install the new packages.**
```bash
python -m pip install -r requirements.txt
```

**A3. Update settings file.** Open `.env` in VS Code. Copy below content with this and put **your own email** on the first line:
```
SUPERADMIN_EMAIL=your-email@gmail.com
DEV_MODE=1
DATABASE_URL=sqlite:///sewa.db
COUNTRY_CODE=91
EMAIL_PROVIDER=console
EMAIL_FROM_NAME=Sewa
EMAIL_FROM=
BREVO_API_KEY=
WHATSAPP_TOKEN=
WHATSAPP_PHONE_ID=
```
(If you have no `.env` yet, run `cp .env.example .env` and edit it.)

**A4. Run the automatic tests.** They must say `2 passed`.
```bash
python -m pytest -q
```
If it shows `F` or an error, do not continue. 

**A5. Start the server.**
```bash
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000 in your browser.

**A6. Log in.**
1. Type your email (the same one as `SUPERADMIN_EMAIL`) and press **Send code**.
2. The code is shown on the screen (test mode) and also printed in the Terminal. Type your name, choose **Brothers** or **Sisters**, press **Sign in**.
3. You see an **Admin** tab at the bottom. If you do not, the email does not match `.env`. Fix `.env`, stop the server (`Ctrl+C`), start it again, tap **Me, Sign out**, and log in again.

**A7. Save your work in git.**
```bash
git add .
git commit -m "Email login, install support"
```

---

## Part B. Put the code on GitHub

1. Go to https://github.com and sign in (make a free account if you have none).
2. In VS Code, click the **Source Control** icon on the left (the branching icon).
3. If it shows **Publish Branch** or **Publish to GitHub**, click it. Choose **Private repository** and name it `sewa`. Tick all files. VS Code may ask you to sign in to GitHub in the browser: allow it.
4. Open https://github.com/YOUR-USERNAME/sewa in the browser and check that you see your files. You should see `app`, `static`, `requirements.txt`, but **no** `.env` file. That is correct: it is private and must stay on your computer.

If you prefer the Terminal, create an empty private repo on github.com, then run (change the address):
```bash
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/sewa.git
git push -u origin main
```
GitHub may ask for a password. Use a **Personal Access Token** (GitHub, Settings, Developer settings, Personal access tokens), not your normal password.

From now on, every time you change code: `git add .`, `git commit -m "what I changed"`, `git push`. Render will update the website by itself.

---

## Part C. Create the database on Supabase

1. Go to https://supabase.com, sign up, click **New project**.
2. Name: `sewa`. **Database password:** make one with **only letters and numbers** (for example `Sewa2026Blue99X`). Write it down. Special characters cause trouble. Region: the closest to India (for example **Mumbai**). Create the project and wait a minute or two.
3. Click **Connect** (top of the page). Find the **Session pooler** connection string. It looks like this:
   `postgresql://postgres.abcdefgh:[YOUR-PASSWORD]@aws-0-ap-south-1.pooler.supabase.com:5432/postgres`
4. Copy it into a note and replace `[YOUR-PASSWORD]` with your password (remove the square brackets too).

Use the **Session pooler** string, not the "Direct connection". The direct one does not work from Render's free plan. Do not use the "Transaction pooler" (port 6543) either.

You do not need to create any tables. The app creates them on its first start.

---

## Part D. Email for login codes (Brevo, free)

1. Sign up at https://www.brevo.com with your email and complete their questions.
2. **Add a sender:** in Brevo go to **Senders, Domains & Dedicated IPs**, then **Senders**, **Add a sender**. Use an email address you own (a Gmail address is fine). Brevo emails you a link: click it to verify. This address will be your `EMAIL_FROM`.
3. **Create an API key:** go to **SMTP & API**, then the **API Keys** tab, **Generate a new API key**. Name it `sewa`. Copy the key now and keep it secret.
4. Brevo may take some time to approve a new account for sending. If your codes do not arrive, use the **Plan B** in Part F.

Gmail users: login emails may land in **Spam** the first time. Tell your testers to look there.

---

## Part E. Put the app online on Render

1. Go to https://render.com and sign up with GitHub.
2. Click **New**, then **Web Service**. Connect your `sewa` repository (Render asks permission to see it: allow).
3. Fill in:
   - **Name:** sewa
   - **Region:** Singapore (closest to India)
   - **Branch:** main
   - **Runtime / Language:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type:** Free
4. Open **Environment Variables** and add these (name on the left, value on the right):

| Name | Value |
|---|---|
| `DATABASE_URL` | the Supabase Session pooler string from Part C, with your password in it |
| `SUPERADMIN_EMAIL` | your own email |
| `DEV_MODE` | `0` |
| `EMAIL_PROVIDER` | `brevo` |
| `BREVO_API_KEY` | the key from Part D |
| `EMAIL_FROM` | the sender address you verified in Part D |
| `EMAIL_FROM_NAME` | `Sewa` |
| `COUNTRY_CODE` | `91` |

5. Click **Create Web Service**. Wait for the build (a few minutes). When the log says the service is live, Render shows an address like `https://sewa-xxxx.onrender.com`.
6. Open that address. The first visit can take about a minute to wake up. That is normal on the free plan: it sleeps after 15 minutes without visitors.

**Why `DEV_MODE` must be `0` online:** with `1`, the login code is shown on the screen, so anyone typing your email could log in as top admin.

**Python version:** the file `.python-version` in the project tells Render to use Python 3.13.

---

## Part F. First use online

1. Open your Render address. Enter your email and press **Send code**.
2. Check your inbox (and Spam). Type the code, your name, choose Brothers or Sisters, **Sign in**.
3. You are the top admin: the **Admin** tab appears.

**Plan B if no email arrives:** in Render open your service, click **Environment**, change `EMAIL_PROVIDER` to `console`, save (it redeploys). Now codes are not emailed: they appear in the **Logs** tab, as a line `[SEWA login code] name@email: 123456`. Read the code there and type it in. For 5 testers you can send each of them their code yourself.

4. **Add your real departments:** Admin, **People**, **Add a department**. Fill the name, the in-charge name, the in-charge's **email**, the location name, and latitude and longitude (see the tip below). The in-charge becomes admin of that department when they log in with that email.
   - Tip for coordinates: on your phone, open Google Maps, press and hold on the place, and the numbers appear at the top. Or in the Post form press **Use my current location** when you are standing there.
5. **Post a request:** Admin, **Post**. Then look at **Manage**: use − and + to change how many people are needed, **Edit** to change anything, **Copy** to repeat it on another day, **Deactivate** to close it and **Activate** to open it again.

---

## Part G. Install it on a phone like an app

**Android (Chrome):** open your Render address, tap the **three dots** menu, then **Install app** (or **Add to Home screen**). Open it from the new Sewa icon.

**iPhone (Safari only):** open the address in Safari, tap the **Share** button, then **Add to Home Screen**.

Volunteers do the same. Then they log in with their email, open **Me** and set their name, Brothers or Sisters, and when they are free. They switch on department alerts under **Alerts**.

---

## Part H. WhatsApp alerts for up to 5 testers

Everyone already gets alerts **inside Sewa** (Alerts tab). WhatsApp is an extra. You use Meta's free test number: it can send to up to 5 phone numbers you verify, and test messages are free. Do **not** automate your personal WhatsApp: that breaks WhatsApp's rules and the number can be banned.

1. Ask a parent or other adult to own the Meta account. Go to https://developers.facebook.com, log in, **Create app**, choose the business type, then add the **WhatsApp** product.
2. Open **WhatsApp, API Setup**. You see a **Phone number ID** and a temporary **access token**. Copy both.
3. Under **To**, add each tester's WhatsApp number (up to 5). WhatsApp sends each tester a confirmation code to enter.
4. In Render, add environment variables `WHATSAPP_PHONE_ID` and `WHATSAPP_TOKEN` with those values, and save.
5. Each tester must open **Me** in Sewa, type their **WhatsApp number** (10 digits), and **Save**.
6. Each tester sends the message **Hi** from their WhatsApp to the test number shown on the API Setup page. This opens a 24-hour window in which WhatsApp delivers our messages. They must repeat it each day during the test.
7. The temporary token stops working after about a day. For a longer test, create a permanent token with a System User in Meta Business settings.

If a WhatsApp message does not arrive, the alert is still in the Sewa Alerts tab. Meta's rules and limits can change: check their documentation.

---

## Part I. Problems

| What you see | What to do |
|---|---|
| `zsh: command not found: pytest` | Use `python -m pytest -q`, with `(.venv)` showing. Run `source .venv/bin/activate` first. |
| No **Admin** tab | The email you logged in with must equal `SUPERADMIN_EMAIL` exactly. Fix it, restart the server (or redeploy on Render), **Me, Sign out**, log in again. |
| Local server error about a missing column | Delete the old database file: `rm -f sewa.db`, then start again. |
| Render build fails | Open the **Logs**, copy the red lines, and paste them to Claude. |
| Render says the database cannot connect | Check `DATABASE_URL`: it must start with `postgresql://`, come from **Session pooler**, and contain your real password with no brackets. |
| "We could not send the email" | Check `EMAIL_FROM` is the verified Brevo sender and `BREVO_API_KEY` is correct. Look at the Render **Logs** for a line starting `[SEWA email problem]`. Or use Plan B in Part F. |
| First page load is very slow online | Free Render wakes up in about a minute. Wait. |
| Supabase project paused | Free projects pause after a week of no use. Open supabase.com, click **Restore**. |
| "Too many codes requested" | One email can ask for 5 codes an hour. Wait an hour. |
| Location button does nothing | It needs `https` and permission. Use the Render address and allow location. |

---

## What is where

```
app/main.py            starts the server
app/models.py          the database tables
app/emailer.py         sends the login code (console, Brevo, SMTP)
app/notify.py          alerts: saved in the app, and WhatsApp if a number is set
app/routers/auth.py    login with email code (limits on tries and requests)
app/routers/public.py  profile, alerts, requests, join, cancel slot
app/routers/admin.py   post, edit, copy, resize, pause; numbers; departments; admins
static/                the screens, icons, manifest.json, sw.js (install support)
tests/test_flow.py     automatic test of the main story
```

## How the rules work

- A request needs `people_needed` people for `duration_hours`. It is full when the hours covered reach people times hours. Two people giving one hour each count as one person for a 2 hour shift.
- Volunteers see only requests for their own group (Brothers or Sisters). Admins see all.
- Joining is limited to the request's time. A volunteer can change or cancel their slot any time.
- A full request stays visible to admins. Deactivate hides it. Activate opens it again, and followers get an "Open again" alert.
- If an admin moves the start time, volunteers' hours move with it.
- A department admin manages only their department and can make helpers admins of that department. Only the top admin (`SUPERADMIN_EMAIL`) creates departments.

---

## Later

**Play Store.** The app is a PWA, so it can be wrapped into an Android app (a Trusted Web Activity, with Bubblewrap or PWABuilder). You need a Google Play developer account (a one-time fee, check the current amount). A new personal account must run a closed test with at least 12 testers for 14 days before publishing publicly. Before that, an Android file can be sent directly to early testers. 

**Growing.** Everything is standard Postgres and a plain Python server, so you can move hosts by changing `DATABASE_URL` and the Render service. Supabase Pro  does not pause and has backups. Render has an always-on paid plan. WhatsApp costs money at scale (Meta bills per message, using approved templates), so in-app alerts and push notifications keep cost down.

