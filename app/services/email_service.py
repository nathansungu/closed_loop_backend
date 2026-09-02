import logging
import os
import secrets
import smtplib
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
from dotenv import load_dotenv

# Load .env file
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path)
else:
    load_dotenv()

logger = logging.getLogger("closed_loop.email")


def generate_verification_code() -> str:
    """Generate a secure 6-digit numeric verification code."""
    return f"{secrets.randbelow(900000) + 100000}"


def get_smtp_config():
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = (
        os.getenv("SMTP_USER")
        or os.getenv("EMAIL_USER")
        or os.getenv("MAIL_USERNAME")
        or os.getenv("VITE_EMAIL")
        or os.getenv("EMAIL")
    )
    password = (
        os.getenv("SMTP_PASSWORD")
        or os.getenv("EMAIL_PASSWORD")
        or os.getenv("APP_PASSWORD")
        or os.getenv("VITE_PASSWORD")
        or os.getenv("MAIL_PASSWORD")
    )

    if user:
        user = user.strip()
    if password:
        password = password.replace(" ", "").strip()

    from_email = os.getenv("SMTP_FROM_EMAIL") or user or "no-reply@closedloop.co.ke"
    from_name = os.getenv("SMTP_FROM_NAME", "Closed Loop Protocol")
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes")
    use_ssl = os.getenv("SMTP_USE_SSL", "false").lower() in ("true", "1", "yes")

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "from_email": from_email,
        "from_name": from_name,
        "use_tls": use_tls,
        "use_ssl": use_ssl,
    }


def send_verification_email(to_email: str, recipient_name: str, code: str) -> bool:
    """
    Sends a 6-digit email verification code to the recipient.
    If SMTP credentials are not yet configured in .env, logs the code to console
    so local development and automated workflows continue seamlessly.
    """
    config = get_smtp_config()
    subject = f"Your Verification Code: {code} - Closed Loop Protocol"

    # Always log code for development visibility
    print(f"\n=======================================================")
    print(f"[EMAIL VERIFICATION] To: {to_email} ({recipient_name})")
    print(f"[CODE] Verification Code: {code} (Expires in 15 minutes)")
    print(f"=======================================================\n")

    # If credentials not set, treat as mock/dev mode
    if not config["user"] or not config["password"]:
        logger.info(
            "SMTP credentials not configured in environment. Verification code logged to console: %s",
            code,
        )
        return True

    # Build Email Message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{config['from_name']} <{config['from_email']}>"
    msg["To"] = to_email

    # Plain text version
    text_content = f"""Hello {recipient_name},

Thank you for registering on the Closed Loop Payment Network Protocol.

Your 6-digit email verification code is:
{code}

This code will expire in 15 minutes.
If you did not request this code, please ignore this email.

Need help? Contact our support team at support@closedloop.co.ke

Best regards,
Closed Loop Security Team
"""

    # Rich HTML version
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      background-color: #080c14;
      color: #e2e8f0;
      margin: 0;
      padding: 30px 15px;
    }}
    .container {{
      max-width: 520px;
      margin: 0 auto;
      background: #0f172a;
      border: 1px solid #1e293b;
      border-radius: 16px;
      padding: 32px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    }}
    .logo {{
      text-align: center;
      margin-bottom: 24px;
    }}
    .logo-text {{
      font-size: 20px;
      font-weight: 800;
      color: #ffffff;
      letter-spacing: 1px;
    }}
    .logo-highlight {{
      color: #e11d48;
    }}
    .greeting {{
      font-size: 16px;
      font-weight: 600;
      color: #f8fafc;
      margin-bottom: 12px;
    }}
    .instructions {{
      font-size: 14px;
      color: #94a3b8;
      line-height: 1.6;
      margin-bottom: 24px;
    }}
    .code-box {{
      background: #1e1b2e;
      border: 1px solid #e11d48;
      border-radius: 12px;
      padding: 18px;
      text-align: center;
      margin-bottom: 24px;
    }}
    .code {{
      font-family: 'Courier New', Courier, monospace;
      font-size: 32px;
      font-weight: 800;
      letter-spacing: 8px;
      color: #fb7185;
    }}
    .expire-notice {{
      font-size: 12px;
      color: #cbd5e1;
      text-align: center;
      margin-top: 8px;
    }}
    .footer {{
      font-size: 12px;
      color: #64748b;
      text-align: center;
      border-top: 1px solid #1e293b;
      padding-top: 20px;
      margin-top: 24px;
    }}
    .support-link {{
      color: #fb7185;
      text-decoration: none;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="logo">
      <div class="logo-text">CLOSED<span class="logo-highlight">LOOP</span></div>
      <div style="font-size: 10px; color: #64748b; text-transform: uppercase; letter-spacing: 2px;">Payment Network Protocol</div>
    </div>
    
    <div class="greeting">Hello {recipient_name},</div>
    <div class="instructions">
      Please verify your email address to activate your organization workspace on Closed Loop. Enter the 6-digit confirmation code below:
    </div>

    <div class="code-box">
      <div class="code">{code}</div>
      <div class="expire-notice">This code expires in <strong>15 minutes</strong>.</div>
    </div>

    <div class="instructions" style="font-size: 12px; color: #64748b;">
      Need help? Contact our support desk at <a href="mailto:support@closedloop.co.ke" class="support-link">support@closedloop.co.ke</a>
    </div>

    <div class="footer">
      &copy; Closed Loop Payment Network Protocol • Backed by Hamiltonian Graph Traversal
    </div>
  </div>
</body>
</html>
"""

    msg.attach(MIMEText(text_content, "plain"))
    msg.attach(MIMEText(html_content, "html"))

    try:
        if config["use_ssl"] or config["port"] == 465:
            server = smtplib.SMTP_SSL(config["host"], config["port"], timeout=10)
        else:
            server = smtplib.SMTP(config["host"], config["port"], timeout=10)
            if config["use_tls"]:
                server.starttls()

        server.login(config["user"], config["password"])
        server.send_message(msg)
        server.quit()
        logger.info("Verification email successfully sent to %s", to_email)
        return True
    except Exception as e:
        logger.error("Failed to send verification email to %s: %s", to_email, str(e))
        print(f"[SMTP ERROR]: {e}")
        return False
