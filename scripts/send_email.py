"""
send_email.py
-------------
Sends the daily story email via Gmail SMTP (SSL, port 465).

Requires a Gmail App Password — NOT your regular Gmail password.
See README for how to generate one (2-step verification must be on).

Debug tip: Call test_smtp_connection() first to verify credentials
before running the full pipeline.
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465  # SSL


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

def test_smtp_connection(gmail_user: str, gmail_app_password: str) -> bool:
    """
    Verify Gmail SMTP credentials without sending any mail.
    Returns True on success, False on failure (logs the reason).
    """
    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.login(gmail_user, gmail_app_password)
        logger.info("SMTP connection test: SUCCESS")
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error(
            "SMTP authentication failed. Make sure you're using a Gmail App Password, "
            "not your regular password. See: https://support.google.com/accounts/answer/185833"
        )
        return False
    except Exception as e:
        logger.error(f"SMTP connection test failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Email builder
# ---------------------------------------------------------------------------

def _build_html_email(story_data: dict, story_url: str) -> str:
    """Build the HTML email body."""
    preview = story_data["story_pt"][:130].rsplit(" ", 1)[0] + "…"

    return f"""<!DOCTYPE html>
<html lang="pt-PT">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#f0ede6;font-family:Georgia,serif;">

  <table width="100%" cellpadding="0" cellspacing="0" style="padding:24px 16px;">
    <tr><td align="center">
      <table width="100%" style="max-width:480px;background:#fff;border-radius:14px;
                                  overflow:hidden;box-shadow:0 2px 16px rgba(0,0,0,0.10);">

        <!-- Header -->
        <tr>
          <td style="background:#2c5f2e;padding:24px 28px 22px;">
            <p style="margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                      font-size:11px;font-weight:700;letter-spacing:0.6px;
                      text-transform:uppercase;color:rgba(255,255,255,0.72);">
              {story_data['date_formatted']}
            </p>
            <p style="margin:10px 0 0;font-size:22px;font-weight:700;
                      color:#ffffff;line-height:1.3;">
              {story_data['title_pt']}
            </p>
            <p style="margin:8px 0 0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                      font-size:13px;color:rgba(255,255,255,0.80);">
              {story_data['topic_en']}
            </p>
          </td>
        </tr>

        <!-- Preview -->
        <tr>
          <td style="padding:22px 28px 8px;">
            <p style="margin:0;font-size:16px;line-height:1.75;color:#3a3a3a;">
              {preview}
            </p>
          </td>
        </tr>

        <!-- CTA -->
        <tr>
          <td style="padding:16px 28px 30px;text-align:center;">
            <a href="{story_url}"
               style="display:inline-block;background:#2c5f2e;color:#ffffff;
                      text-decoration:none;padding:13px 30px;border-radius:8px;
                      font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                      font-size:15px;font-weight:600;letter-spacing:0.2px;">
              Ler o conto →
            </a>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="border-top:1px solid #eeebe4;padding:14px 28px;text-align:center;">
            <p style="margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                      font-size:12px;color:#a0a0a0;">
              O teu conto diário em português continental &nbsp;🇵🇹
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>

</body>
</html>"""


def _build_text_email(story_data: dict, story_url: str) -> str:
    """Plain-text fallback."""
    preview = story_data["story_pt"][:200].rsplit(" ", 1)[0] + "…"
    return (
        f"Conto do dia: {story_data['title_pt']}\n"
        f"{story_data['date_formatted']} — {story_data['topic_en']}\n\n"
        f"{preview}\n\n"
        f"Lê o conto completo aqui:\n{story_url}"
    )


# ---------------------------------------------------------------------------
# Send
# ---------------------------------------------------------------------------

def send_story_email(
    gmail_user: str,
    gmail_app_password: str,
    recipient: str,
    story_url: str,
    story_data: dict,
) -> bool:
    """Send the daily story email. Returns True on success, raises on failure."""
    subject = f"🇵🇹 Conto do dia: {story_data['title_pt']}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = recipient

    msg.attach(MIMEText(_build_text_email(story_data, story_url), "plain", "utf-8"))
    msg.attach(MIMEText(_build_html_email(story_data, story_url), "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.login(gmail_user, gmail_app_password)
            server.sendmail(gmail_user, recipient, msg.as_string())

        logger.info(f"Email sent to {recipient}: \"{subject}\"")
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error("Email send failed: Gmail authentication error (check App Password)")
        raise
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        raise
