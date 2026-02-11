import os
import requests

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL")  # must be verified sender in SendGrid

def send_email_otp(to_email: str, otp: str):

    if not SENDGRID_API_KEY:
        raise Exception("SENDGRID_API_KEY missing in env")

    if not FROM_EMAIL:
        raise Exception("FROM_EMAIL missing in env")

    subject = "Your Abhyaas OTP Code"

    html_content = f"""
    <div style="font-family:Arial; padding:16px;">
      <h2>Abhyaas OTP Verification</h2>
      <p>Your OTP is:</p>
      <h1 style="letter-spacing:6px;">{otp}</h1>
      <p>This OTP will expire in 5 minutes.</p>
    </div>
    """

    url = "https://api.sendgrid.com/v3/mail/send"

    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": FROM_EMAIL, "name": "Abhyaas"},
        "subject": subject,
        "content": [{"type": "text/html", "value": html_content}]
    }

    headers = {
        "Authorization": f"Bearer {SENDGRID_API_KEY}",
        "Content-Type": "application/json"
    }

    r = requests.post(url, json=payload, headers=headers)

    if r.status_code not in [200, 202]:
        raise Exception(f"SendGrid failed: {r.status_code} - {r.text}")
