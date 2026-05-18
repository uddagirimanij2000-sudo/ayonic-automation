"""
mailer/followup_sender.py

Automatic follow-up emails for leads that haven't replied.

Flow:
  Day 0:  First email sent (status = "emailed")
  Day 3:  Follow-up #1 sent (status = "follow-up-1")
  Day 7:  Follow-up #2 sent (status = "follow-up-2")

After follow-up #2, lead is marked "no-reply" and skipped.
If a lead replies, manually set status to "replied" to stop follow-ups.
"""

from __future__ import annotations
import smtplib
import time
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from colorama import Fore, Style

import config

SENDER_NAME  = "Manoj"
SENDER_TITLE = "Founder, Ayonic"
SENDER_EMAIL = "info@ayonic.com"
SENDER_PHONE = "+49 30 28619101"
AYONIC_URL   = "https://ayonic.com"

AYONIC_DESC = (
    "an on-demand service booking platform that connects customers directly "
    "with trusted local cleaning professionals."
)

# ── Follow-up schedule ────────────────────────────────────────────────────────
FOLLOWUP_RULES = [
    {"from_status": "emailed",     "days_after": 3, "new_status": "follow-up-1"},
    {"from_status": "follow-up-1", "days_after": 4, "new_status": "follow-up-2"},  # 7 days total
]


def _generate_followup_ai(company_name: str, followup_num: int, website: str) -> tuple:
    """Use Groq AI to write a unique follow-up email."""
    try:
        from groq import Groq
        client = Groq(api_key=config.GROQ_API_KEY)

        if followup_num == 1:
            context = "This is a FIRST follow-up (3 days after initial email). Be friendly and brief."
        else:
            context = "This is the FINAL follow-up (7 days after initial email). Be very brief, last chance."

        prompt = f"""You are Manoj Uddagiri, founder of Ayonic (ayonic.com).
{context}

Write a SHORT follow-up email to {company_name} who didn't reply to your first email.
The first email was about partnering with Ayonic - {AYONIC_DESC}

RULES:
1. Write in BOTH English and German (English first, then "---", then German)
2. MAX 60 words per language — very short
3. Sound human and casual, not pushy
4. Reference the previous email naturally
5. Do NOT repeat all the benefits — just nudge
6. End with a simple question
7. Do NOT use emojis
8. Sign off as:
   Manoj Uddagiri
   Founder, Ayonic
   Web: {AYONIC_URL}
   Tel: {SENDER_PHONE}
   Email: {SENDER_EMAIL}
9. Add unsubscribe line at end

Generate a subject line too (max 6 words, include "Re:" to look like a reply).
Format:
SUBJECT: [subject]
BODY:
[email]
"""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.7,
        )

        text = response.choices[0].message.content.strip()
        if "SUBJECT:" in text and "BODY:" in text:
            subject = text.split("SUBJECT:")[1].split("BODY:")[0].strip()
            body = text.split("BODY:")[1].strip()
        else:
            subject = f"Re: Quick question for {company_name}"
            body = text

        print(f"{Fore.GREEN}  AI follow-up generated{Style.RESET_ALL}")
        return subject, body

    except Exception as e:
        print(f"{Fore.YELLOW}  AI fallback: {e}{Style.RESET_ALL}")
        return None, None


def _build_followup_template(company_name: str, followup_num: int) -> tuple:
    """Fallback template for follow-ups."""
    if followup_num == 1:
        subject = f"Re: Quick question for {company_name}"
        body = f"""Hi,

I sent you a message a few days ago about a potential partnership between {company_name} and Ayonic. I understand things get busy, so I wanted to follow up briefly.

We help cleaning companies get more customers through our booking platform — at no upfront cost. Would you be open to a quick 5-minute chat?

---

Hallo,

ich hatte Ihnen vor einigen Tagen wegen einer moeglichen Partnerschaft zwischen {company_name} und Ayonic geschrieben. Ich verstehe, dass es manchmal hektisch zugeht, deshalb moechte ich kurz nachhaken.

Wir helfen Reinigungsunternehmen, ueber unsere Buchungsplattform mehr Kunden zu gewinnen — ohne Vorabkosten. Haetten Sie 5 Minuten fuer ein kurzes Gespraech?

Viele Gruesse,
Manoj Uddagiri
Founder, Ayonic
Web: {AYONIC_URL}
Tel: {SENDER_PHONE}
Email: {SENDER_EMAIL}

--
If you do not wish to receive further emails, simply reply with "unsubscribe".
"""
    else:
        subject = f"Re: Partnership with {company_name}?"
        body = f"""Hi,

Just a final note — I'd love to connect {company_name} with new customers through Ayonic. No cost to join, and you stay in full control.

If this isn't a fit, no worries at all. Otherwise, I'm happy to chat anytime.

---

Hallo,

nur eine letzte Nachricht — ich wuerde {company_name} gerne ueber Ayonic mit neuen Kunden verbinden. Kein Beitritt notwendig, und Sie behalten die volle Kontrolle.

Falls es nicht passt, kein Problem. Ansonsten freue ich mich ueber ein Gespraech.

Viele Gruesse,
Manoj Uddagiri
Founder, Ayonic
Web: {AYONIC_URL}
Tel: {SENDER_PHONE}
Email: {SENDER_EMAIL}

--
If you do not wish to receive further emails, simply reply with "unsubscribe".
"""

    return subject, body


def _build_followup_email(company_name: str, followup_num: int,
                           website: str = "") -> tuple:
    """Build follow-up email — AI first, template fallback."""
    if config.GROQ_API_KEY:
        subject, body = _generate_followup_ai(company_name, followup_num, website)
        if subject and body:
            return subject, body
    return _build_followup_template(company_name, followup_num)


def get_followup_candidates() -> list:
    """Get leads that are due for a follow-up."""
    from sheets.sheets_client import get_all_leads

    leads = get_all_leads()
    candidates = []

    for i, lead in enumerate(leads):
        row_idx = i + 2  # 1-indexed + header
        status = str(lead.get("Status", "")).strip()
        email = str(lead.get("Email", "")).strip()
        email_send_date = str(lead.get("Email Send Date", "")).strip()

        if not email or not email_send_date:
            continue

        # Parse the send date
        try:
            sent_date = datetime.strptime(email_send_date, "%Y-%m-%d").date()
        except ValueError:
            try:
                sent_date = datetime.strptime(email_send_date, "%Y-%m-%d %H:%M:%S").date()
            except ValueError:
                continue

        days_since = (datetime.now().date() - sent_date).days

        for rule in FOLLOWUP_RULES:
            if status == rule["from_status"] and days_since >= rule["days_after"]:
                followup_num = 1 if rule["new_status"] == "follow-up-1" else 2
                candidates.append({
                    "row_idx": row_idx,
                    "lead": lead,
                    "followup_num": followup_num,
                    "new_status": rule["new_status"],
                    "days_since": days_since,
                })
                break

    return candidates


def run_followup_sender(dry_run: bool = False):
    """Send follow-up emails to leads that haven't replied."""
    from sheets.sheets_client import update_lead_status, log_email_sent
    from mailer.personalized_sender import _get_today_count, _increment_daily_count

    daily_limit = getattr(config, "DAILY_EMAIL_LIMIT", 400)
    delay_secs  = getattr(config, "EMAIL_DELAY_SECONDS", 3)
    already_sent = _get_today_count()
    remaining = max(0, daily_limit - already_sent)

    candidates = get_followup_candidates()

    mode = "(DRY RUN)" if dry_run else ""
    print(f"\n{Fore.CYAN}▶ Follow-Up Email Sender {mode}{Style.RESET_ALL}")
    print(f"  {len(candidates)} leads due for follow-up")
    print(f"  📊 Daily limit: {daily_limit} | Sent today: {already_sent} | Remaining: {remaining}")

    if not candidates:
        print(f"\n{Fore.GREEN}✔ No follow-ups needed right now{Style.RESET_ALL}\n")
        return

    if remaining == 0 and not dry_run:
        print(f"\n{Fore.YELLOW}⚠ Daily limit reached! Try again tomorrow.{Style.RESET_ALL}\n")
        return

    # Cap to remaining
    if not dry_run and len(candidates) > remaining:
        print(f"  ⚡ Will send {remaining} of {len(candidates)} (daily limit)")
        candidates = candidates[:remaining]

    print()

    if not dry_run:
        server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT)
        server.starttls()
        server.login(config.GMAIL_USER, config.GMAIL_APP_PASSWORD)

    sent = failed = 0
    for idx, candidate in enumerate(candidates):
        lead = candidate["lead"]
        company = str(lead.get("Company Name", ""))
        email   = str(lead.get("Email", ""))
        website = str(lead.get("Website", ""))
        followup_num = candidate["followup_num"]
        new_status = candidate["new_status"]
        days = candidate["days_since"]

        tag = f"Follow-up #{followup_num}"
        progress = f"[{idx+1}/{len(candidates)}]"
        print(f"{Fore.MAGENTA}{progress} 📧 {tag} → {company[:35]:<35} ({days}d ago){Style.RESET_ALL}")

        try:
            subject, body = _build_followup_email(company, followup_num, website)

            if dry_run:
                print(f"  SUBJECT: {subject}")
                print(f"  PREVIEW: {body[:150]}...")
                print()
                continue

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = f"Manoj | Ayonic <{config.GMAIL_USER}>"
            msg["To"]      = email
            msg["Reply-To"] = SENDER_EMAIL
            msg.attach(MIMEText(body, "plain", "utf-8"))
            server.sendmail(config.GMAIL_USER, email, msg.as_string())

            # Update sheet
            update_lead_status(candidate["row_idx"], new_status, "")
            log_email_sent(company, email, f"[{tag}] {subject}")
            _increment_daily_count(1)

            remaining_now = daily_limit - _get_today_count()
            print(f"  {Fore.GREEN}✔ Sent → {email} | {remaining_now} left today{Style.RESET_ALL}")
            sent += 1
            time.sleep(delay_secs)

        except Exception as e:
            print(f"  {Fore.RED}✘ Failed — {e}{Style.RESET_ALL}")
            failed += 1

    if not dry_run:
        server.quit()

    # Mark leads past follow-up-2 as "no-reply"
    if not dry_run:
        _mark_no_reply_leads()

    total_today = _get_today_count()
    print(f"\n{Fore.GREEN}✔ Follow-ups done — {sent} sent, {failed} failed{Style.RESET_ALL}")
    print(f"{Fore.CYAN}📊 Total sent today: {total_today}/{daily_limit}{Style.RESET_ALL}\n")


def _mark_no_reply_leads():
    """Mark leads stuck in follow-up-2 for 4+ days as 'no-reply'."""
    from sheets.sheets_client import get_all_leads, update_lead_field

    leads = get_all_leads()
    for i, lead in enumerate(leads):
        status = str(lead.get("Status", "")).strip()
        email_send_date = str(lead.get("Email Send Date", "")).strip()

        if status != "follow-up-2" or not email_send_date:
            continue

        try:
            sent_date = datetime.strptime(email_send_date, "%Y-%m-%d").date()
            if (datetime.now().date() - sent_date).days >= 4:
                row_idx = i + 2
                update_lead_field(row_idx, "Status", "no-reply")
                company = str(lead.get("Company Name", ""))
                print(f"  {Fore.YELLOW}⏹ {company} → no-reply (14 days total){Style.RESET_ALL}")
        except ValueError:
            continue
