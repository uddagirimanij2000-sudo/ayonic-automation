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


def _translate_with_groq(description: str) -> tuple[str, str]:
    """
    Use Groq AI to translate description between German and English.
    Returns (de_text, en_text) — both versions of the actual description.
    """
    if not config.GROQ_API_KEY or not description or len(description.strip()) < 10:
        return description, description

    try:
        from groq import Groq
        client = Groq(api_key=config.GROQ_API_KEY)

        desc = description.strip()[:500]

        # Step 1: Translate to English
        r_en = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{
                "role": "user",
                "content": f"Translate this text to English. Return ONLY the translated text, nothing else:\n\n{desc}"
            }],
            max_tokens=300,
            temperature=0.1,
        )
        en_text = r_en.choices[0].message.content.strip()

        # Step 2: Translate to German
        r_de = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{
                "role": "user",
                "content": f"Translate this text to German. Return ONLY the translated text, nothing else:\n\n{desc}"
            }],
            max_tokens=300,
            temperature=0.1,
        )
        de_text = r_de.choices[0].message.content.strip()

        print(f"  🌐 DE: {de_text[:70]}...")
        print(f"  🌐 EN: {en_text[:70]}...")
        return de_text, en_text

    except Exception as e:
        print(f"  ⚠ Groq translation failed ({e}) — using original")
        return description, description




def _send_one(name: str, email: str, description: str) -> bool:
    """Send a single test email using DeepL bilingual translation."""

    # Groq: auto-detect German/English and produce both versions
    de_description, en_description = _translate_with_groq(description)

    subject, body = render_email(
        company_name=name,
        category="service business",
        sender_name="Team Ayonic",
        sender_email=config.GMAIL_USER,
        city="Berlin",
        description=de_description,   # German version for DE part of email
        contact_name="",
        ai_detail_de=de_description,
        ai_detail_en=en_description,
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
    """
    Test mode — uses the 'test' sheet directly:
    - Each row's name + description is used as the email template data
    - Sends to each recipient's own email address
    - Same bilingual template as the real outreach emails
    """
    print(f"\n{Fore.CYAN}{'='*55}")
    print(f"  TEST EMAIL SENDER — Sheet: '{TEST_SHEET_NAME}'")
    print(f"  Limit: {TEST_DAILY_LIMIT} per run | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*55}{Style.RESET_ALL}\n")

    # Get all test sheet recipients
    test_leads = _get_test_leads()
    if not test_leads:
        print(f"{Fore.YELLOW}⚠ No recipients in 'test' sheet.")
        print(f"  Add rows with columns: name | email | description{Style.RESET_ALL}")
        return

    print(f"Found {len(test_leads)} recipients in test sheet:")
    for l in test_leads:
        print(f"  • {l['name']:20} → {l['email']}")

    print(f"\n📧 Sending (max {TEST_DAILY_LIMIT})...\n")
    sent = 0

    for lead in test_leads[:TEST_DAILY_LIMIT]:
        # Use each row's own name + description from the test sheet
        success = _send_one(
            name=lead["name"],
            email=lead["email"],
            description=lead["description"],
        )
        if success:
            sent += 1
        time.sleep(SMTP_DELAY_SEC)

    print(f"\n{Fore.GREEN}✅ Done — {sent}/{len(test_leads)} test emails sent.{Style.RESET_ALL}\n")


