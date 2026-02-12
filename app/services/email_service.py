import smtplib
from email.message import EmailMessage
from datetime import datetime
from app.core.config import SMTP_EMAIL, SMTP_APP_PASSWORD, SMTP_HOST, SMTP_PORT
from dotenv import load_dotenv
load_dotenv()

def send_email_otp(to_email: str, otp: str):
    if not SMTP_EMAIL or not SMTP_APP_PASSWORD:
        raise RuntimeError("SMTP_EMAIL or SMTP_APP_PASSWORD missing")

    msg = EmailMessage()

    # ✅ Subject
    msg["Subject"] = "Your Abhyaas OTP Code"

    # ✅ Sender name will show as "Abhyaas" instead of email
    msg["From"] = f"Abhyaas <{SMTP_EMAIL}>"

    msg["To"] = to_email

    # ✅ Plain text fallback (for safety)
    msg.set_content(
        f"Your Abhyaas OTP is: {otp}\n\n"
        f"This OTP will expire in 5 minutes.\n"
        f"If you did not request this, ignore this email.\n"
    )

    # ✅ Stylish HTML template
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8" />
    </head>
    <body style="margin:0;padding:0;background:#f6f7fb;font-family:Arial, sans-serif;">
      <div style="max-width:520px;margin:40px auto;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 8px 30px rgba(0,0,0,0.08);">

        <div style="background:linear-gradient(135deg,#6d28d9,#2563eb);padding:22px 24px;color:white;">
          <h2 style="margin:0;font-size:20px;font-weight:700;">Abhyaas • OTP Verification</h2>
          <p style="margin:6px 0 0;font-size:14px;opacity:0.9;">Secure email verification</p>
        </div>

        <div style="padding:26px 24px;color:#111827;">
          <p style="margin:0 0 14px;font-size:15px;">Hi 👋</p>

          <p style="margin:0 0 18px;font-size:15px;line-height:1.5;">
            Your OTP for Abhyaas verification is:
          </p>

          <div style="text-align:center;margin:20px 0;">
            <div style="display:inline-block;background:#111827;color:white;font-size:28px;font-weight:800;letter-spacing:6px;padding:14px 22px;border-radius:14px;">
              {otp}
            </div>
          </div>

          <p style="margin:0 0 12px;font-size:14px;color:#374151;">
            This OTP will expire in <b>5 minutes</b>.
          </p>

          <p style="margin:0;font-size:13px;color:#6b7280;">
            If you didn’t request this OTP, you can safely ignore this email.
          </p>
        </div>

        <div style="padding:16px 24px;background:#f9fafb;color:#6b7280;font-size:12px;">
          © {datetime.utcnow().year} Abhyaas • All rights reserved
        </div>

      </div>
    </body>
    </html>
    """

    # ✅ Attach HTML
    msg.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_APP_PASSWORD)
        server.send_message(msg)
