import requests
from fastapi import HTTPException
from app.core.config import SENDGRID_API_KEY, SENDGRID_FROM_EMAIL


def send_email_otp(to_email: str, otp: str):

    if not SENDGRID_API_KEY or not SENDGRID_FROM_EMAIL:
        raise HTTPException(status_code=500, detail="SendGrid env missing")

    url = "https://api.sendgrid.com/v3/mail/send"

    payload = {
        "personalizations": [
            {
                "to": [{"email": to_email}],
                "subject": "Your Abhyaas OTP Code"
            }
        ],
        "from": {"email": SENDGRID_FROM_EMAIL, "name": "Abhyaas"},
        "content": [
            {
                "type": "text/plain",
                "value": f"Your Abhyaas OTP is: {otp}\nThis OTP expires in 5 minutes."
            },
            {
                "type": "text/html",
                "value": f"""
                <div style="font-family:Arial,sans-serif;padding:16px">
                  <h2>Abhyaas OTP Verification</h2>
                  <p>Your OTP is:</p>
                  <div style="font-size:28px;font-weight:800;letter-spacing:4px">
                    {otp}
                  </div>
                  <p>This OTP expires in <b>5 minutes</b>.</p>
                </div>
                """
            }
        ]
    }

    headers = {
        "Authorization": f"Bearer {SENDGRID_API_KEY}",
        "Content-Type": "application/json"
    }

    r = requests.post(url, headers=headers, json=payload)

    if r.status_code not in [200, 202]:
        raise HTTPException(status_code=500, detail=f"SendGrid failed: {r.text}")
