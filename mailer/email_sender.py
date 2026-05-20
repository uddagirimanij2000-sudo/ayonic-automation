"""
mailer/email_sender.py
Send personalized outreach emails to leads that:
  - Have status = 'pending'
  - Have an email address
  - Were found >= EMAIL_DELAY_DAYS ago (default: 5 days)

Each company category gets its own tailored email template.
Edit templates in: mailer/templates.py
"""

import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from colorama import Fore, Style

import config
from mailer.templates import render_email, get_template


def _translate_with_groq(description: str) -> tuple[str, str]:
    """
    Use Groq AI (free) to translate description to both German and English.
    Returns (de_text, en_text). Falls back to original if Groq unavailable.
    """
    if not config.GROQ_API_KEY or not description or len(description.strip()) < 10:
        return description, description
    try:
        from groq import Groq
        client = Groq(api_key=config.GROQ_API_KEY)
        prompt = f"""You are a professional German-English translator.

Text to translate:
\"\"\"{description[:400]}\"\"\"

Reply with EXACTLY 2 lines, nothing else:
Line 1: German version (translate to German if English, keep if already German)
Line 2: English version (translate to English if German, keep if already English)"""
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.1,
        )
        lines = [l.strip() for l in response.choices[0].message.content.strip().split("\n") if l.strip()]
        if len(lines) >= 2:
            return lines[0], lines[1]
    except Exception:
        pass
    return description, description
from sheets.sheets_client import (
    get_leads_ready_to_email,
    update_lead_status,
    log_email_sent,
)


def build_email(company_name: str, category: str,
                city: str = "", description: str = "",
                contact_name: str = "") -> tuple:
    """Build a personalized MIME email using the category-specific template."""
    from email.utils import formatdate, make_msgid

    # Groq: translate description to both DE and EN for bilingual email
    de_description, en_description = _translate_with_groq(description)

    subject, body = render_email(
        company_name=company_name,
        category=category,
        sender_name=config.SENDER_NAME,
        sender_email=config.GMAIL_USER,
        city=city,
        description=de_description,
        contact_name=contact_name,
        ai_detail_de=de_description,
        ai_detail_en=en_description,
    )

    # Anti-spam: ensure unsubscribe footer
    if "unsubscribe" not in body.lower():
        body += "\n\n--\nIf you do not wish to receive further emails, simply reply with \"unsubscribe\".\n"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"Ayonic Team <{config.GMAIL_USER}>"
    # To header is set in send_email() — do NOT set it here
    msg["Reply-To"] = "info@ayonic.com"
    msg["Date"]    = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="ayonic.com")

    msg.attach(MIMEText(body, "plain", "utf-8"))
    return msg, subject


def send_email(to_email: str, msg: MIMEMultipart) -> bool:
    """Send a single email via Gmail SMTP. Returns True on success."""
    if not config.GMAIL_USER or not config.GMAIL_APP_PASSWORD:
        print(f"{Fore.RED}✘ Gmail credentials not set in .env{Style.RESET_ALL}")
        return False

    # Safely set To — remove any existing To header first to avoid duplicates
    if "To" in msg:
        del msg["To"]
    msg["To"] = to_email
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(config.GMAIL_USER, config.GMAIL_APP_PASSWORD)
            server.sendmail(config.GMAIL_USER, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"{Fore.RED}✘ Failed to send to {to_email}: {e}{Style.RESET_ALL}")
        return False


def preview_email(company_name: str, category: str):
    """Print a preview of what email would be sent to a company."""
    subject, body = render_email(
        company_name=company_name,
        category=category,
        sender_name=config.SENDER_NAME,
        sender_email=config.GMAIL_USER,
    )
    print(f"\n{Fore.CYAN}{'─'*55}")
    print(f"  📧 EMAIL PREVIEW — {company_name} [{category}]")
    print(f"{'─'*55}")
    print(f"  To      : {company_name} <email@example.com>")
    print(f"  Subject : {subject}")
    print(f"{'─'*55}")
    print(body)
    print(f"{'─'*55}{Style.RESET_ALL}")


def run_email_sender(dry_run: bool = False):
    """
    Main function: find eligible leads and send them outreach emails.
    Each company gets a template matched to its category.

    Args:
        dry_run: If True, prints what would be sent without actually sending.
    """
    print(f"\n{Fore.CYAN}{'─'*55}")
    print(f"📧 Email check — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"   Sending to leads >= {config.EMAIL_DELAY_DAYS} days old...")
    if dry_run:
        print(f"   {Fore.YELLOW}[DRY RUN MODE — no emails will be sent]{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'─'*55}{Style.RESET_ALL}\n")

    leads = get_leads_ready_to_email()

    if not leads:
        print(f"{Fore.YELLOW}  No leads ready to email yet.{Style.RESET_ALL}\n")
        return

    print(f"{Fore.CYAN}  Found {len(leads)} lead(s) ready to email.{Style.RESET_ALL}\n")
    sent_count   = 0
    failed_count = 0

    for lead in leads:
        company_name = lead.get("Company Name", "")
        to_email     = lead.get("Email", "")
        category     = lead.get("Category", "")
        city         = lead.get("Location", "")
        description  = lead.get("Description", "")
        row_index    = lead.get("row_index")
        days_old     = lead.get("days_old", 0)

        # Identify which template will be used
        from mailer.templates import TEMPLATES, _is_cleaning
        if _is_cleaning(category):
            template_used = f"ayonic_cleaning_{getattr(config, 'EMAIL_LANGUAGE', 'en')}"
        else:
            tmpl_key = category.strip().lower()
            template_used = tmpl_key if tmpl_key in TEMPLATES else "default"

        print(f"  → {Fore.WHITE}{company_name}{Style.RESET_ALL} <{to_email}>")
        print(f"     Category : {category}")
        print(f"     City     : {city or 'N/A'}")
        print(f"     Template : {template_used}")
        print(f"     Age      : {days_old} days old")

        if dry_run:
            preview_email(company_name, category, city=city, description=description)
            continue

        msg, subject = build_email(company_name, category,
                                   city=city, description=description)
        success = send_email(to_email, msg)

        today_str = datetime.now().strftime("%Y-%m-%d")

        if success:
            update_lead_status(row_index, "emailed", today_str)
            log_email_sent(company_name, to_email, category, template=template_used)
            print(f"     {Fore.GREEN}✔ Sent! Subject: \"{subject}\"{Style.RESET_ALL}")
            sent_count += 1
        else:
            failed_count += 1
            print(f"     {Fore.RED}✘ Failed{Style.RESET_ALL}")

        print()
        time.sleep(3)  # Small delay between emails to avoid spam flags

    if dry_run:
        print(f"\n{Fore.YELLOW}[DRY RUN] Would have sent {len(leads)} email(s){Style.RESET_ALL}\n")
    else:
        print(f"\n{Fore.GREEN}✔ Done — {sent_count} sent, {failed_count} failed{Style.RESET_ALL}\n")
