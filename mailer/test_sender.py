"""
Test email sender — reads from the 'test' sheet.
No age delay. Sends up to TEST_DAILY_LIMIT emails per run.
"""

import smtplib, time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from colorama import Fore, Style

import config
from mailer.templates import render_email

TEST_SHEET_NAME  = "test"
TEST_DAILY_LIMIT = 20        # Max emails per run
SMTP_DELAY_SEC   = 3         # Seconds between emails


def _get_test_leads() -> list[dict]:
    """Read all rows from the 'test' sheet."""
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds  = Credentials.from_service_account_file("credentials.json", scopes=scopes)
    gc     = gspread.authorize(creds)
    sh     = gc.open_by_key(config.GOOGLE_SHEET_ID)

    try:
        ws = sh.worksheet(TEST_SHEET_NAME)
    except Exception:
        print(f"{Fore.RED}❌ 'test' sheet not found in Google Sheet!{Style.RESET_ALL}")
        return []

    rows = ws.get_all_records()
    leads = []
    for i, row in enumerate(rows, start=2):
        name  = str(row.get("name", "") or row.get("Name", "")).strip()
        email = str(row.get("email", "") or row.get("Email", "")).strip()
        desc  = str(row.get("description", "") or row.get("Description", "")).strip()
        if name and email:
            leads.append({"row": i, "name": name, "email": email, "description": desc})
    return leads


def _send_one(name: str, email: str, description: str) -> bool:
    """Send a single test email. Returns True on success."""
    subject, body = render_email(
        company_name=name,
        category="service business",
        sender_name="Team Ayonic",
        sender_email=config.GMAIL_USER,
        city="Berlin",
        description=description,
        contact_name="",
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"]    = subject
    msg["From"]       = f"Ayonic Team <{config.GMAIL_USER}>"
    msg["To"]         = email
    msg["Reply-To"]   = "info@ayonic.com"
    msg["Date"]       = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="ayonic.com")
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as s:
            s.ehlo(); s.starttls()
            s.login(config.GMAIL_USER, config.GMAIL_APP_PASSWORD)
            s.sendmail(config.GMAIL_USER, email, msg.as_string())
        print(f"  {Fore.GREEN}✅ Sent → {email} ({name}){Style.RESET_ALL}")
        return True
    except Exception as e:
        print(f"  {Fore.RED}❌ Failed → {email}: {e}{Style.RESET_ALL}")
        return False


def run_test_sender():
    """Main function — send test emails from 'test' sheet."""
    print(f"\n{Fore.CYAN}{'='*55}")
    print(f"  TEST EMAIL SENDER — Sheet: '{TEST_SHEET_NAME}'")
    print(f"  Limit: {TEST_DAILY_LIMIT} per run | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*55}{Style.RESET_ALL}\n")

    leads = _get_test_leads()
    if not leads:
        print(f"{Fore.YELLOW}⚠ No leads found in 'test' sheet. Add rows with: name, email, description{Style.RESET_ALL}")
        return

    print(f"Found {len(leads)} test leads:")
    for l in leads:
        print(f"  • {l['name']} → {l['email']}")

    print(f"\nSending (max {TEST_DAILY_LIMIT})...\n")
    sent = 0
    for lead in leads[:TEST_DAILY_LIMIT]:
        success = _send_one(lead["name"], lead["email"], lead["description"])
        if success:
            sent += 1
        time.sleep(SMTP_DELAY_SEC)

    print(f"\n{Fore.GREEN}✅ Done — {sent}/{len(leads)} test emails sent.{Style.RESET_ALL}\n")
