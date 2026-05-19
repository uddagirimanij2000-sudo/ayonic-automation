"""
tools/phone_notify.py

Push notifications to your phone when important events happen:
  - Reply received from a lead
  - Daily email summary
  - Email verification warnings

Setup (choose one or both):

  Option A — ntfy.sh (recommended, free, no account):
    1. Install "ntfy" app on your phone (Android/iOS)
    2. Subscribe to topic: "ayonic-leads" (or custom)
    3. Add NTFY_TOPIC=ayonic-leads to .env

  Option B — WhatsApp via CallMeBot (free):
    1. Send "I allow callmebot to send me messages" to +34 644 71 87 08 on WhatsApp
    2. You'll get an API key
    3. Add to .env:
       WHATSAPP_PHONE=your_number_with_country_code
       WHATSAPP_APIKEY=your_api_key
"""

import os
import urllib.request
import urllib.parse
from datetime import datetime
from colorama import Fore, Style


def notify_reply_received(company: str, email: str, subject: str = ""):
    """🔔 HIGH PRIORITY — A lead replied to your email!"""
    now = datetime.now().strftime("%H:%M")
    title = f"💬 Reply Received! — {company}"
    body = f"From: {email}\nTime: {now}"
    if subject:
        body += f"\nSubject: {subject[:80]}"
    _send_notification(title, body, priority="high")


def notify_email_sent(company: str, email: str, remaining: int):
    """Notify when a personalized email is sent."""
    now = datetime.now().strftime("%H:%M")
    title = f"✉️ Email Sent"
    body = f"To: {company}\nEmail: {email}\nTime: {now}\nRemaining today: {remaining}"
    _send_notification(title, body)


def notify_daily_summary(sent: int, failed: int, replies: int, bounced: int = 0):
    """End-of-day summary notification."""
    title = f"📊 Daily Summary — {sent} emails sent"
    body = (
        f"Sent: {sent}\n"
        f"Failed: {failed}\n"
        f"Replies: {replies}\n"
    )
    if bounced:
        body += f"Bounced: {bounced}\n"
    body += f"Date: {datetime.now().strftime('%Y-%m-%d')}"
    _send_notification(title, body)


def notify_verification_warning(invalid_count: int, total: int):
    """Alert if many emails failed verification."""
    title = f"⚠️ Email Verification — {invalid_count} invalid"
    body = (
        f"Checked: {total}\n"
        f"Invalid: {invalid_count}\n"
        f"These leads will be skipped.\n"
        f"Check Google Sheet for details."
    )
    _send_notification(title, body, priority="high" if invalid_count > 10 else "default")


def notify_contact_form_filled(company: str, website: str):
    """Notify when a contact form is successfully filled."""
    now = datetime.now().strftime("%H:%M")
    title = f"📝 Contact Form Filled"
    body = f"Company: {company}\nWebsite: {website}\nTime: {now}"
    _send_notification(title, body)


def notify_error(module: str, error: str):
    """Alert on critical errors."""
    title = f"🚨 Error in {module}"
    body = f"Error: {error[:200]}\nTime: {datetime.now().strftime('%H:%M')}"
    _send_notification(title, body, priority="high")


def notify_unsubscribe(company: str, email: str):
    """Alert when a lead unsubscribes."""
    title = f"🚫 Unsubscribed: {company}"
    body = f"Email: {email}\nTime: {datetime.now().strftime('%H:%M')}\nRemoved from list."
    _send_notification(title, body, priority="default")


def notify_daily_report():
    """
    Send a daily morning summary to ntfy.
    Shows: emails sent today, total replies, new leads scraped, unsubscribes.
    Called by scheduler every morning.
    """
    try:
        from sheets.sheets_client import get_all_leads
        from datetime import date

        leads       = get_all_leads()
        today_str   = date.today().strftime("%Y-%m-%d")

        total       = len(leads)
        pending     = sum(1 for l in leads if str(l.get("Status","")).lower() == "pending")
        emailed     = sum(1 for l in leads if str(l.get("Status","")).lower() == "emailed")
        replied     = sum(1 for l in leads if str(l.get("Status","")).lower() == "replied")
        unsubs      = sum(1 for l in leads if str(l.get("Status","")).lower() == "unsubscribed")
        no_email    = sum(1 for l in leads if not str(l.get("Email","")).strip())

        title = f"📊 Daily Report — {today_str}"
        body = (
            f"Total leads   : {total}\n"
            f"Pending       : {pending}\n"
            f"Emailed       : {emailed}\n"
            f"Replied       : {replied}\n"
            f"Unsubscribed  : {unsubs}\n"
            f"No email yet  : {no_email}\n"
            f"\nNext email run: {date.today().strftime('%d %b')} at 13:00"
        )
        _send_notification(title, body, priority="default")
        print(f"  📊 Daily report sent to ntfy")
    except Exception as e:
        print(f"  ⚠ Daily report failed: {e}")


def send_notification(title: str, message: str, tags: str = "briefcase"):
    """Public helper — send any custom notification to ntfy."""
    _send_notification(title, message)


# ── Internal dispatch ─────────────────────────────────────────────────────────

def _send_notification(title: str, body: str, priority: str = "default"):
    """Send notification via all configured channels."""
    sent = False

    # Option A: ntfy.sh (free push notifications)
    topic = os.getenv("NTFY_TOPIC", "")
    if topic:
        sent = _send_ntfy(topic, title, body, priority) or sent

    # Option B: WhatsApp via CallMeBot
    phone = os.getenv("WHATSAPP_PHONE", "")
    apikey = os.getenv("WHATSAPP_APIKEY", "")
    if phone and apikey:
        sent = _send_whatsapp(phone, apikey, title, body) or sent

    # Option C: macOS desktop notification (always)
    _send_macos(title, body)

    if not sent and not topic:
        # First run — remind user to set up notifications
        pass


def _send_ntfy(topic: str, title: str, body: str, priority: str = "default") -> bool:
    """Send push notification via ntfy.sh."""
    try:
        url  = f"https://ntfy.sh/{topic}"
        data = body.encode("utf-8")
        req  = urllib.request.Request(url, data=data, method="POST")
        # ntfy headers must be ASCII — encode title for emoji support
        req.add_header("Title",    title.encode("utf-8").decode("latin-1", errors="replace"))
        req.add_header("Priority", priority)
        req.add_header("Tags",     "briefcase,email")
        req.add_header("Content-Type", "text/plain; charset=utf-8")

        urllib.request.urlopen(req, timeout=10)
        print(f"  {Fore.CYAN}📱 Phone notification sent (ntfy){Style.RESET_ALL}")
        return True
    except Exception as e:
        # Fallback: try without special chars in title
        try:
            import re
            clean_title = re.sub(r'[^\x00-\x7F]', '', title).strip()
            url  = f"https://ntfy.sh/{topic}"
            data = (title + "\n\n" + body).encode("utf-8")
            req  = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Title",    clean_title or "Ayonic Alert")
            req.add_header("Priority", priority)
            req.add_header("Content-Type", "text/plain; charset=utf-8")
            urllib.request.urlopen(req, timeout=10)
            print(f"  {Fore.CYAN}📱 Phone notification sent (ntfy){Style.RESET_ALL}")
            return True
        except Exception as e2:
            print(f"  {Fore.YELLOW}⚠ ntfy failed: {e2}{Style.RESET_ALL}")
            return False


def _send_whatsapp(phone: str, apikey: str, title: str, body: str) -> bool:
    """Send WhatsApp message via CallMeBot."""
    try:
        message = f"*{title}*\n\n{body}"
        encoded_msg = urllib.parse.quote(message)
        url = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={encoded_msg}&apikey={apikey}"

        urllib.request.urlopen(url, timeout=15)
        print(f"  {Fore.CYAN}📱 WhatsApp notification sent{Style.RESET_ALL}")
        return True
    except Exception as e:
        print(f"  {Fore.YELLOW}⚠ WhatsApp failed: {e}{Style.RESET_ALL}")
        return False


def _send_macos(title: str, body: str):
    """Send macOS desktop notification."""
    import subprocess
    try:
        safe_body = body.replace('"', '\\"').replace('\n', '\\n')
        safe_title = title.replace('"', '\\"')
        subprocess.run([
            "osascript", "-e",
            f'display notification "{safe_body}" with title "{safe_title}"'
        ], capture_output=True, timeout=5)
    except Exception:
        pass


if __name__ == "__main__":
    print(f"\n{Fore.CYAN}📱 Testing Phone Notifications...{Style.RESET_ALL}\n")
    notify_reply_received("CleanWhale Berlin", "info@cleanwhale.de", "Re: Partnership")
    print(f"\n{Fore.GREEN}✔ Test complete{Style.RESET_ALL}\n")
