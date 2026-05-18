"""
tools/email_verifier.py

Verify email addresses BEFORE sending to prevent bounces and Gmail blocks.

3-step verification:
  1. Format check (regex)
  2. MX record lookup (DNS)
  3. SMTP handshake (connect + RCPT TO without sending)

Usage:
    from tools.email_verifier import verify_email, verify_batch

    result = verify_email("info@example.com")
    # → {"email": "info@example.com", "valid": True, "reason": "SMTP OK"}

    results = verify_batch(["a@b.com", "bad@fake.xyz"])
    # → [{"email": ..., "valid": ..., "reason": ...}, ...]
"""

from __future__ import annotations
import re
import dns.resolver
import smtplib
import socket
from datetime import datetime
from colorama import Fore, Style


# ── Regex for basic email format ──────────────────────────────────────────────
EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)

# Known disposable/temporary email domains (block these)
DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "tempmail.com", "throwaway.email",
    "yopmail.com", "10minutemail.com", "trashmail.com", "fakeinbox.com",
    "sharklasers.com", "guerrillamailblock.com", "grr.la", "dispostable.com",
    "maildrop.cc", "temp-mail.org", "mailnesia.com", "tempail.com",
}

# Known catch-all providers (always say "yes" — can't verify individual mailbox)
CATCH_ALL_PROVIDERS = {
    "gmail.com", "googlemail.com", "outlook.com", "hotmail.com",
    "yahoo.com", "icloud.com", "me.com", "mac.com",
}

# Cache MX lookups to avoid repeated DNS queries
_mx_cache: dict[str, list[str]] = {}


def verify_email(email: str, timeout: int = 10) -> dict:
    """
    Verify a single email address.

    Returns:
        {
            "email": str,
            "valid": bool,
            "reason": str,       # Human-readable explanation
            "step_failed": str,  # "format" | "mx" | "smtp" | None
        }
    """
    email = email.strip().lower()

    # Step 1: Format check
    if not EMAIL_REGEX.match(email):
        return _result(email, False, "Invalid email format", "format")

    domain = email.split("@")[1]

    # Step 1b: Disposable domain check
    if domain in DISPOSABLE_DOMAINS:
        return _result(email, False, f"Disposable email domain: {domain}", "format")

    # Step 2: MX record lookup
    mx_hosts = _get_mx_records(domain)
    if not mx_hosts:
        return _result(email, False, f"No MX records for domain: {domain}", "mx")

    # Step 3: SMTP handshake
    # For known catch-all providers, skip SMTP check (they always accept)
    if domain in CATCH_ALL_PROVIDERS:
        return _result(email, True, f"Valid format + MX OK (catch-all: {domain})", None)

    # Try SMTP verification against each MX host
    for mx_host in mx_hosts[:3]:  # Try top 3 MX servers
        smtp_result = _smtp_verify(email, mx_host, timeout)
        if smtp_result is not None:
            if smtp_result:
                return _result(email, True, "SMTP verified — mailbox exists", None)
            else:
                return _result(email, False, f"SMTP rejected — mailbox does not exist ({mx_host})", "smtp")

    # If all SMTP checks were inconclusive, trust MX records
    return _result(email, True, "MX records valid (SMTP inconclusive)", None)


def verify_batch(emails: list[str], timeout: int = 10) -> list[dict]:
    """Verify a list of email addresses."""
    results = []
    for email in emails:
        results.append(verify_email(email, timeout))
    return results


def _result(email: str, valid: bool, reason: str, step_failed: str | None) -> dict:
    return {
        "email": email,
        "valid": valid,
        "reason": reason,
        "step_failed": step_failed,
    }


def _get_mx_records(domain: str) -> list[str]:
    """Look up MX records for a domain. Returns sorted list of mail servers."""
    if domain in _mx_cache:
        return _mx_cache[domain]

    try:
        answers = dns.resolver.resolve(domain, "MX")
        mx_hosts = sorted(
            [(r.preference, str(r.exchange).rstrip(".")) for r in answers],
            key=lambda x: x[0]
        )
        result = [host for _, host in mx_hosts]
        _mx_cache[domain] = result
        return result
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN,
            dns.resolver.NoNameservers, dns.exception.Timeout):
        _mx_cache[domain] = []
        return []
    except Exception:
        return []


def _smtp_verify(email: str, mx_host: str, timeout: int = 10) -> bool | None:
    """
    Attempt SMTP handshake to verify mailbox exists.

    Returns:
        True  — mailbox exists (250 response)
        False — mailbox rejected (550 response)
        None  — inconclusive (timeout, connection refused, etc.)
    """
    try:
        smtp = smtplib.SMTP(timeout=timeout)
        smtp.connect(mx_host, 25)
        smtp.helo("ayonic.com")

        # Use a neutral sender for verification
        smtp.mail("verify@ayonic.com")
        code, _ = smtp.rcpt(email)
        smtp.quit()

        if code == 250:
            return True   # Mailbox exists
        elif code in (550, 551, 552, 553, 554):
            return False  # Mailbox rejected
        else:
            return None   # Inconclusive
    except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected,
            socket.timeout, ConnectionRefusedError, OSError):
        return None  # Can't connect — inconclusive
    except Exception:
        return None


# ── Integration with Google Sheets ────────────────────────────────────────────

def verify_leads_from_sheet(dry_run: bool = False) -> dict:
    """
    Verify all pending leads in Google Sheets that have email addresses.
    Updates Sheet with verification results.

    Returns summary dict.
    """
    from sheets.sheets_client import get_all_leads, update_lead_field

    leads = get_all_leads()
    pending = [
        (i + 2, lead) for i, lead in enumerate(leads)
        if str(lead.get("Status", "")).strip() == "pending"
        and str(lead.get("Email", "")).strip()
    ]

    print(f"\n{Fore.CYAN}▶ Email Verification{' (DRY RUN)' if dry_run else ''}{Style.RESET_ALL}")
    print(f"  {len(pending)} pending leads with email addresses")

    if not pending:
        print(f"\n{Fore.GREEN}✔ No leads to verify{Style.RESET_ALL}\n")
        return {"total": 0, "valid": 0, "invalid": 0, "error": 0}

    valid_count = 0
    invalid_count = 0
    error_count = 0

    for idx, (row_idx, lead) in enumerate(pending):
        email = str(lead.get("Email", "")).strip()
        company = str(lead.get("Company Name", ""))
        progress = f"[{idx+1}/{len(pending)}]"

        result = verify_email(email)

        if result["valid"]:
            icon = f"{Fore.GREEN}✔{Style.RESET_ALL}"
            valid_count += 1
        else:
            icon = f"{Fore.RED}✘{Style.RESET_ALL}"
            invalid_count += 1
            # Mark invalid emails in Sheet
            if not dry_run:
                update_lead_field(row_idx, "Status", "invalid-email")
                update_lead_field(row_idx, "Notes",
                    f"Email invalid: {result['reason']} ({datetime.now().strftime('%Y-%m-%d')})")

        print(f"  {progress} {icon} {email:40s} → {result['reason']}")

    print(f"\n{Fore.CYAN}{'─'*50}{Style.RESET_ALL}")
    print(f"  ✅ Valid:   {valid_count}")
    print(f"  ❌ Invalid: {invalid_count}")
    print(f"  Total:     {len(pending)}")
    print(f"{Fore.CYAN}{'─'*50}{Style.RESET_ALL}\n")

    return {
        "total": len(pending),
        "valid": valid_count,
        "invalid": invalid_count,
    }


if __name__ == "__main__":
    # Quick test
    test_emails = [
        "test@gmail.com",
        "info@berliner-reinigung.de",
        "fake@thisdoesnotexist12345.com",
        "not-an-email",
    ]
    print(f"\n{Fore.CYAN}🔍 Email Verification Test{Style.RESET_ALL}\n")
    for email in test_emails:
        r = verify_email(email, timeout=5)
        icon = "✅" if r["valid"] else "❌"
        print(f"  {icon} {r['email']:40s} → {r['reason']}")
    print()
