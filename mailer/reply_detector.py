"""
mailer/reply_detector.py

Auto-detect replies from leads in Gmail inbox.
When a lead replies → updates Google Sheet status to "replied".
Stops all follow-ups for that lead automatically.

Uses IMAP to read Gmail inbox — same app password, no extra setup.
"""

from __future__ import annotations
import imaplib
import email
from email.header import decode_header
from datetime import datetime, timedelta
from colorama import Fore, Style

import config


def _decode_header_value(value):
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
    """Extract just the email address from 'Name <email@example.com>'."""
    if "<" in from_header and ">" in from_header:
        return from_header.split("<")[1].split(">")[0].strip().lower()
    return from_header.strip().lower()


def check_replies(days_back: int = 14, dry_run: bool = False) -> list:
    """
    Check Gmail inbox for replies from leads.
    
    Returns list of matched leads that replied.
    """
    from sheets.sheets_client import get_all_leads, update_lead_field

    print(f"\n{Fore.CYAN}▶ Reply Detector{' (DRY RUN)' if dry_run else ''}{Style.RESET_ALL}")

    # Get all leads that were emailed (could get a reply)
    leads = get_all_leads()
    emailed_statuses = {"emailed", "follow-up-1", "follow-up-2"}
    
    # Build email → lead mapping
    email_to_lead = {}
    for i, lead in enumerate(leads):
        status = str(lead.get("Status", "")).strip()
        lead_email = str(lead.get("Email", "")).strip().lower()
        
        if status in emailed_statuses and lead_email:
            email_to_lead[lead_email] = {
                "row_idx": i + 2,
                "company": str(lead.get("Company Name", "")),
                "status": status,
            }

    if not email_to_lead:
        print(f"  No emailed leads to check for replies")
        print(f"\n{Fore.GREEN}✔ Done{Style.RESET_ALL}\n")
        return []

    print(f"  Checking replies from {len(email_to_lead)} emailed leads...")
    print(f"  Looking back {days_back} days")

    # Connect to info@ayonic.com via IMAP — replies go here (Reply-To: info@ayonic.com)
    imap_user = config.INFO_EMAIL or config.GMAIL_USER
    imap_pass = config.INFO_APP_PASSWORD or config.GMAIL_APP_PASSWORD
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(imap_user, imap_pass)
        mail.select("INBOX")
        print(f"  📬 Monitoring inbox: {imap_user}")
    except Exception as e:
        print(f"  {Fore.RED}✘ IMAP error for {imap_user}: {e}{Style.RESET_ALL}")
        print(f"  Make sure IMAP is enabled and INFO_APP_PASSWORD is set")
        return []

    # Search for emails from the last N days
    since_date = (datetime.now() - timedelta(days=days_back)).strftime("%d-%b-%Y")
    
    try:
        status, messages = mail.search(None, f'(SINCE {since_date})')
        if status != "OK":
            print(f"  {Fore.RED}✘ Search failed{Style.RESET_ALL}")
            mail.logout()
            return []
        
        message_ids = messages[0].split()
        print(f"  Found {len(message_ids)} emails in last {days_back} days")
    except Exception as e:
        print(f"  {Fore.RED}✘ Search error: {e}{Style.RESET_ALL}")
        mail.logout()
        return []

    # Check each email
    matched_replies = []
    
    for msg_id in message_ids:
        try:
            status, msg_data = mail.fetch(msg_id, "(RFC822)")
            if status != "OK":
                continue
            
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            
            from_header = _decode_header_value(msg.get("From", ""))
            sender_email = _extract_email_address(from_header)
            subject = _decode_header_value(msg.get("Subject", ""))
            date_str = msg.get("Date", "")
            
            # Check if sender matches any emailed lead
            if sender_email in email_to_lead:
                lead_info = email_to_lead[sender_email]
                company = lead_info["company"]
                
                # Check if we already processed this reply
                if sender_email not in [r["email"] for r in matched_replies]:
                    matched_replies.append({
                        "email": sender_email,
                        "company": company,
                        "subject": subject,
                        "date": date_str,
                        "row_idx": lead_info["row_idx"],
                    })
                    
                    print(f"\n  {Fore.GREEN}📬 REPLY DETECTED!{Style.RESET_ALL}")
                    print(f"     Company : {company}")
                    print(f"     From    : {sender_email}")
                    print(f"     Subject : {subject[:60]}")
                    print(f"     Date    : {date_str}")
                    
                    if not dry_run:
                        # Update Google Sheet
                        update_lead_field(lead_info["row_idx"], "Status", "replied")
                        update_lead_field(
                            lead_info["row_idx"], "Notes",
                            f"Replied on {datetime.now().strftime('%Y-%m-%d %H:%M')}: {subject[:50]}"
                        )
                        print(f"     {Fore.GREEN}✔ Sheet updated → 'replied'{Style.RESET_ALL}")

                        # 📱 Phone notification — REPLY RECEIVED!
                        try:
                            from tools.phone_notify import notify_reply_received
                            notify_reply_received(company, sender_email, subject)
                        except Exception:
                            pass
                    else:
                        print(f"     {Fore.YELLOW}(dry run — sheet not updated){Style.RESET_ALL}")
        
        except Exception as e:
            continue  # Skip problematic emails silently

    mail.logout()

    # Also check Spam/Junk folder
    try:
        mail2 = imaplib.IMAP4_SSL("imap.gmail.com")
        mail2.login(imap_user, imap_pass)
        mail2.select("[Gmail]/Spam")
        
        status, messages = mail2.search(None, f'(SINCE {since_date})')
        if status == "OK":
            spam_ids = messages[0].split()
            for msg_id in spam_ids:
                try:
                    status, msg_data = mail2.fetch(msg_id, "(RFC822)")
                    if status != "OK":
                        continue
                    
                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)
                    sender_email = _extract_email_address(
                        _decode_header_value(msg.get("From", ""))
                    )
                    
                    if sender_email in email_to_lead:
                        subject = _decode_header_value(msg.get("Subject", ""))
                        lead_info = email_to_lead[sender_email]
                        
                        if sender_email not in [r["email"] for r in matched_replies]:
                            print(f"\n  {Fore.YELLOW}📬 Reply found in SPAM!{Style.RESET_ALL}")
                            print(f"     Company : {lead_info['company']}")
                            print(f"     From    : {sender_email}")
                            matched_replies.append({
                                "email": sender_email,
                                "company": lead_info["company"],
                                "subject": subject,
                                "date": msg.get("Date", ""),
                                "row_idx": lead_info["row_idx"],
                                "in_spam": True,
                            })
                            
                            if not dry_run:
                                update_lead_field(lead_info["row_idx"], "Status", "replied")
                                update_lead_field(
                                    lead_info["row_idx"], "Notes",
                                    f"Replied (found in spam) {datetime.now().strftime('%Y-%m-%d')}: {subject[:50]}"
                                )
                except Exception:
                    continue
        
        mail2.logout()
    except Exception:
        pass  # Spam folder might not exist or be accessible

    # Summary
    print(f"\n{'─'*50}")
    if matched_replies:
        print(f"  {Fore.GREEN}✔ {len(matched_replies)} replies detected!{Style.RESET_ALL}")
        for r in matched_replies:
            spam_tag = " (SPAM)" if r.get("in_spam") else ""
            print(f"    • {r['company']} — {r['email']}{spam_tag}")
    else:
        print(f"  No replies found in last {days_back} days")
    
    print(f"{'─'*50}\n")
    return matched_replies


def run_reply_detector(dry_run: bool = False):
    """Main entry point for reply detection."""
    return check_replies(days_back=14, dry_run=dry_run)
