from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from app.core.config import SENDGRID_API_KEY, FROM_EMAIL
from datetime import datetime

def send_email_otp(to_email: str, otp: str):
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
            If you didn't request this OTP, you can safely ignore this email.
          </p>
        </div>
        <div style="padding:16px 24px;background:#f9fafb;color:#6b7280;font-size:12px;">
          © {datetime.utcnow().year} Abhyaas • All rights reserved
        </div>
      </div>
    </body>
    </html>
    """
    
    message = Mail(
        from_email=f'Abhyaas <{FROM_EMAIL}>',
        to_emails=to_email,
        subject='Your Abhyaas OTP Code',
        html_content=html_body
    )
    
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        print(f"✅ Email sent: {response.status_code}")
        return True
    except Exception as e:
        print(f"❌ SendGrid error: {e}")
        return False
```
