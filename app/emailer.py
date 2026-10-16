"""Sends the login code by email.

EMAIL_PROVIDER=console  prints the code in the server log (good for your own computer).
EMAIL_PROVIDER=brevo    sends through Brevo's web API. Use this on Render's free plan,
                        which blocks the normal email (SMTP) ports.
EMAIL_PROVIDER=smtp     sends through any SMTP server (works on your own computer)."""
import smtplib
from email.message import EmailMessage

import httpx

from .config import (
    BREVO_API_KEY, EMAIL_FROM, EMAIL_FROM_NAME, EMAIL_PROVIDER,
    SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USER,
)


class EmailError(Exception):
    pass


def send_login_code(to_email: str, code: str) -> str:
    subject = "Your Sewa login code"
    text = (
        f"Hari Om!\n\nYour Sewa login code is {code}\n\n"
        "It works for 10 minutes. If you did not ask for it, you can ignore this email."
    )
    html = (
        "<p>Hari Om!</p>"
        f"<p>Your Sewa login code is <b style=\"font-size:20px;letter-spacing:2px\">{code}</b></p>"
        "<p>It works for 10 minutes. If you did not ask for it, you can ignore this email.</p>"
    )

    if EMAIL_PROVIDER == "brevo":
        if not (BREVO_API_KEY and EMAIL_FROM):
            raise EmailError("BREVO_API_KEY and EMAIL_FROM must be set")
        try:
            r = httpx.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={"api-key": BREVO_API_KEY, "accept": "application/json", "content-type": "application/json"},
                json={
                    "sender": {"name": EMAIL_FROM_NAME, "email": EMAIL_FROM},
                    "to": [{"email": to_email}],
                    "subject": subject,
                    "htmlContent": html,
                    "textContent": text,
                },
                timeout=15,
            )
        except httpx.HTTPError as e:
            raise EmailError(f"Brevo not reachable: {e}") from e
        if r.status_code >= 300:
            raise EmailError(f"Brevo refused the email ({r.status_code}): {r.text[:300]}")
        return "sent"

    if EMAIL_PROVIDER == "smtp":
        if not (SMTP_HOST and EMAIL_FROM):
            raise EmailError("SMTP_HOST and EMAIL_FROM must be set")
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"{EMAIL_FROM_NAME} <{EMAIL_FROM}>"
        msg["To"] = to_email
        msg.set_content(text)
        msg.add_alternative(html, subtype="html")
        try:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as s:
                s.starttls()
                if SMTP_USER:
                    s.login(SMTP_USER, SMTP_PASSWORD)
                s.send_message(msg)
        except (OSError, smtplib.SMTPException) as e:
            raise EmailError(f"SMTP failed: {e}") from e
        return "sent"

    # console
    print(f"[SEWA login code] {to_email}: {code}")
    return "console"
