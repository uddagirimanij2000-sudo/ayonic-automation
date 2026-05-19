"""
mailer/unsubscribe_handler.py

Auto-detect unsubscribe requests from leads.

How it works:
  1. Scans Gmail inbox (IMAP) for replies containing "unsubscribe"
  2. Updates Google Sheet status → "unsubscribed"
  3. Never emails that lead again (email_sender checks status)
  4. Sends ntfy push notification when someone unsubscribes
  5. Sends a polite confirmation email back to the lead

Trigger words detected (any language):
  EN: unsubscribe, remove me, stop emailing, opt out, do not contact
  DE: abmelden, kein interesse, bitte keine, abbestellen, nicht mehr
"""

from __future__ import annotations
import imaplib
import email
import smtplib
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate, make_msgid
from datetime import datetime, timedelta
from colorama import Fore, Style

import config

# ── Unsubscribe keywords (EN + DE) ───────────────────────────────────────────

UNSUB_KEYWORDS = [
    # English
    "unsubscribe", "remove me", "stop emailing", "stop email",
    "opt out", "opt-out", "do not contact", "don't contact",
    "no thanks", "not interested", "please remove",
    "take me off", "remove from list",
    # German
    "abmelden", "abbestellen", "kein interesse", "nicht mehr",
    "bitte keine", "keine emails", "keine mails",
    "von der liste", "aus der liste", "nicht kontaktieren",
    "stopp", "aufhören",
]


def _decode_header_value(value: str) -> str:
    """Decode email header (handles encoded subjects)."""
    if not value:
        return ""
    decoded_parts = decode_header(value)
    result = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(part)
    return " ".join(result)


def _extract_email_address(from_header: str) -> str:
    """Extract just the email from 'Name <email@example.com>'."""
    if "<" in from_header and ">" in from_header:
        return from_header.split("<")[1].split(">")[0].strip().lower()
    return from_header.strip().lower()


def _get_email_body(msg) -> str:
    """Extract plain text body from email message."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                try:
                    body += part.get_payload(decode=True).decode("utf-8", errors="replace")
                except Exception:
                    pass
    else:
        try:
            body = msg.get_payload(decode=True).decode("utf-8", errors="replace")
        except Exception:
            pass
    return body.lower()


def _is_unsubscribe(subject: str, body: str) -> bool:
    """Check if the email contains an unsubscribe request."""
    text = (subject + " " + body).lower()
    return any(keyword in text for keyword in UNSUB_KEYWORDS)


def _send_confirmation(to_email: str, company: str):
    """Send a polite confirmation email to the unsubscribed lead."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "You have been removed — Ayonic"
        msg["From"]    = f"Ayonic Team <{config.GMAIL_USER}>"
        msg["To"]      = to_email
        msg["Reply-To"] = "info@ayonic.com"
        msg["Date"]    = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain="ayonic.com")

        body = f"""\
Hello,

We have received your request and you have been removed from our outreach list.

You will not receive any further emails from Ayonic.

We wish {company} all the best!

Best regards,
Team Ayonic
info@ayonic.com
https://ayonic.com
"""
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as s:
            s.ehlo()
            s.starttls()
            s.login(config.GMAIL_USER, config.GMAIL_APP_PASSWORD)
            s.sendmail(config.GMAIL_USER, to_email, msg.as_string())

        print(f"     {Fore.GREEN}✔ Confirmation sent to {to_email}{Style.RESET_ALL}")
    except Exception as e:
        print(f"     {Fore.YELLOW}⚠ Could not send confirmation: {e}{Style.RESET_ALL}")


def _notify_unsubscribe(company: str, sender_email: str):
    """Send ntfy push notification about unsubscribe."""
    try:
        from tools.phone_notify import send_notification
        send_notification(
            title="🚫 Unsubscribe Request",
            message=f"{company} ({sender_email}) has unsubscribed.",
            tags="no_entry,email"
        )
    except Exception:
        pass


def _scan_folder(mail, folder: str, since_date: str,
                 email_to_lead: dict, processed: set,
                 dry_run: bool) -> list:
    """Scan a single IMAP folder for unsubscribe requests."""
    from sheets.sheets_client import update_lead_field

    unsubscribed = []

    try:
        mail.select(folder)
        status, messages = mail.search(None, f"(SINCE {since_date})")
        if status != "OK":
            return []

        msg_ids = messages[0].split()
        for msg_id in msg_ids:
            try:
                status, msg_data = mail.fetch(msg_id, "(RFC822)")
                if status != "OK":
                    continue

                raw   = msg_data[0][1]
                msg   = email.message_from_bytes(raw)

                from_h  = _decode_header_value(msg.get("From", ""))
                sender  = _extract_email_address(from_h)
                subject = _decode_header_value(msg.get("Subject", ""))
                body    = _get_email_body(msg)

                # Only process known leads not yet processed
                if sender not in email_to_lead or sender in processed:
                    continue

                if not _is_unsubscribe(subject, body):
                    continue

                lead_info = email_to_lead[sender]
                company   = lead_info["company"]
                processed.add(sender)

                print(f"\n  {Fore.RED}🚫 UNSUBSCRIBE DETECTED!{Style.RESET_ALL}")
                print(f"     Company : {company}")
                print(f"     Email   : {sender}")
                print(f"     Subject : {subject[:60]}")
                print(f"     Folder  : {folder}")

                if not dry_run:
                    # Mark in Google Sheet
                    update_lead_field(lead_info["row_idx"], "Status", "unsubscribed")
                    update_lead_field(
                        lead_info["row_idx"], "Notes",
                        f"Unsubscribed {datetime.now().strftime('%Y-%m-%d %H:%M')}: {subject[:50]}"
                    )
                    print(f"     {Fore.GREEN}✔ Sheet updated → 'unsubscribed'{Style.RESET_ALL}")

                    # Send confirmation back
                    _send_confirmation(sender, company)

                    # Push notification
                    _notify_unsubscribe(company, sender)

                    unsubscribed.append({
                        "email":   sender,
                        "company": company,
                        "subject": subject,
                        "folder":  folder,
                    })
                else:
                    print(f"     {Fore.YELLOW}(dry run — no changes made){Style.RESET_ALL}")
                    unsubscribed.append({
                        "email":   sender,
                        "company": company,
                        "subject": subject,
                        "folder":  folder,
                    })

            except Exception:
                continue

    except Exception as e:
        print(f"  {Fore.YELLOW}⚠ Could not scan folder '{folder}': {e}{Style.RESET_ALL}")

    return unsubscribed


def check_unsubscribes(days_back: int = 30, dry_run: bool = False) -> list:
    """
    Scan Gmail inbox + spam for unsubscribe requests.

    Returns list of leads that unsubscribed.
    """
    from sheets.sheets_client import get_all_leads

    print(f"\n{Fore.CYAN}▶ Unsubscribe Handler{' (DRY RUN)' if dry_run else ''}{Style.RESET_ALL}")

    # Load all emailed leads
    leads = get_all_leads()
    emailed_statuses = {"emailed", "follow-up-1", "follow-up-2", "replied"}

    email_to_lead = {}
    for i, lead in enumerate(leads):
        status     = str(lead.get("Status", "")).strip().lower()
        lead_email = str(lead.get("Email", "")).strip().lower()
        if status in emailed_statuses and lead_email:
            email_to_lead[lead_email] = {
                "row_idx": i + 2,
                "company": str(lead.get("Company Name", "")),
                "status":  status,
            }

    if not email_to_lead:
        print("  No emailed leads to check")
        return []

    print(f"  Scanning {len(email_to_lead)} emailed leads for unsubscribe requests...")
    print(f"  Looking back {days_back} days")

    # Connect via IMAP
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(config.GMAIL_USER, config.GMAIL_APP_PASSWORD)
    except Exception as e:
        print(f"  {Fore.RED}✘ IMAP error: {e}{Style.RESET_ALL}")
        return []

    since_date = (datetime.now() - timedelta(days=days_back)).strftime("%d-%b-%Y")
    processed  = set()
    all_unsubs = []

    # Scan: Inbox
    results = _scan_folder(mail, "INBOX", since_date, email_to_lead, processed, dry_run)
    all_unsubs.extend(results)

    # Scan: Spam/Junk
    for spam_folder in ["[Gmail]/Spam", "Junk", "Spam"]:
        try:
            results = _scan_folder(mail, spam_folder, since_date,
                                   email_to_lead, processed, dry_run)
            all_unsubs.extend(results)
            break
        except Exception:
            continue

    mail.logout()

    # Summary
    print(f"\n{'─'*50}")
    if all_unsubs:
        print(f"  {Fore.RED}🚫 {len(all_unsubs)} unsubscribe(s) processed{Style.RESET_ALL}")
        for u in all_unsubs:
            print(f"    • {u['company']} — {u['email']}")
    else:
        print(f"  {Fore.GREEN}✔ No unsubscribe requests found{Style.RESET_ALL}")
    print(f"{'─'*50}\n")

    return all_unsubs


def run_unsubscribe_handler(dry_run: bool = False):
    """Main entry point called by scheduler."""
    return check_unsubscribes(days_back=30, dry_run=dry_run)
