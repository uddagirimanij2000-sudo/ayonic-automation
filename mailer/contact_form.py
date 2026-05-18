from __future__ import annotations
"""
mailer/contact_form.py
When a company has no email address, automatically find and submit
their website contact form using Playwright browser automation.

Flow:
  1. Visit company website
  2. Find the contact page (/contact, /about, etc.)
  3. Detect form fields (name, email, message, phone, subject)
  4. Fill with personalized message (same templates as email)
  5. Submit the form
  6. Update Google Sheets: status = "form_sent"

Requires: playwright (pip install playwright && playwright install chromium)
"""

import time
import asyncio
from colorama import Fore, Style
import config
from mailer.templates import render_email

# Pages to try for contact forms
CONTACT_PATHS = [
    "/contact",
    "/contact-us",
    "/contacto",
    "/kontakt",
    "/get-in-touch",
    "/reach-us",
    "/about",
    "/about-us",
    "",  # homepage last
]

# Common field name patterns
FIELD_PATTERNS = {
    "name": ["name", "your-name", "full-name", "fullname", "nome", "nombre",
              "contact_name", "sender_name", "first_name", "firstname"],
    "email": ["email", "e-mail", "your-email", "email_address", "emailaddress",
               "correo", "mail"],
    "phone": ["phone", "telephone", "tel", "mobile", "phone_number", "phonenumber",
               "telefone", "telefon"],
    "subject": ["subject", "assunto", "asunto", "topic", "re", "regarding"],
    "message": ["message", "msg", "comment", "comments", "body", "content",
                 "mensagem", "mensaje", "enquiry", "inquiry", "text"],
    "company": ["company", "company_name", "organization", "organisation", "empresa"],
}


async def _fill_and_submit_form(page, company: dict, message: str, subject: str) -> bool:
    """Try to fill and submit a contact form on the current page."""
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError

    # Look for form elements
    try:
        await page.wait_for_selector("form", timeout=5000)
    except PlaywrightTimeoutError:
        return False

    forms = await page.query_selector_all("form")
    if not forms:
        return False

    filled = False

    for form in forms:
        # Get all input/textarea fields within this form
        fields = await form.query_selector_all("input, textarea, select")
        if len(fields) < 2:
            continue  # Likely a search bar, not a contact form

        form_filled = False

        for field in fields:
            field_type  = (await field.get_attribute("type") or "text").lower()
            field_name  = (await field.get_attribute("name") or "").lower()
            field_id    = (await field.get_attribute("id") or "").lower()
            field_placeholder = (await field.get_attribute("placeholder") or "").lower()
            field_label = field_name or field_id or field_placeholder

            # Skip hidden, submit, checkbox, radio fields
            if field_type in ("hidden", "submit", "button", "checkbox", "radio", "file"):
                continue

            value = _match_field_value(
                field_label,
                company,
                message,
                subject,
                config.GMAIL_USER,
                config.SENDER_NAME,
            )

            if value:
                try:
                    await field.click()
                    await field.fill(value)
                    form_filled = True
                except Exception:
                    continue

        if form_filled:
            # Try to submit the form
            try:
                submit = await form.query_selector(
                    "button[type=submit], input[type=submit], button:has-text('Send'), "
                    "button:has-text('Submit'), button:has-text('Contact'), "
                    "button:has-text('Enviar'), button:has-text('Senden')"
                )
                if submit:
                    await submit.click()
                    await page.wait_for_timeout(3000)
                    filled = True
                    break
            except Exception:
                pass

    return filled


def _match_field_value(label: str, company: dict, message: str,
                        subject: str, sender_email: str, sender_name: str) -> str:
    """Match a form field label to the right value to fill in."""
    label = label.lower()

    for pattern in FIELD_PATTERNS["name"]:
        if pattern in label:
            return sender_name

    for pattern in FIELD_PATTERNS["email"]:
        if pattern in label:
            return sender_email

    for pattern in FIELD_PATTERNS["phone"]:
        if pattern in label:
            return getattr(config, "SENDER_PHONE", "")

    for pattern in FIELD_PATTERNS["subject"]:
        if pattern in label:
            return subject

    for pattern in FIELD_PATTERNS["message"]:
        if pattern in label:
            return message

    for pattern in FIELD_PATTERNS["company"]:
        if pattern in label:
            return getattr(config, "SENDER_COMPANY", sender_name)

    return ""


async def submit_contact_form_async(company: dict, headless: bool = True) -> bool:
    """
    Main async function: find and submit a contact form for a company.
    Returns True if form was successfully submitted.
    """
    from playwright.async_api import async_playwright

    website = company.get("website", "")
    if not website:
        return False

    if not website.startswith("http"):
        website = "https://" + website

    company_name = company.get("name", "")
    category     = company.get("category", "")

    # Get personalized message using the category template
    subject, message = render_email(
        company_name=company_name,
        category=category,
        sender_name=config.SENDER_NAME,
        sender_email=config.GMAIL_USER,
    )

    print(f"{Fore.CYAN}  🌐 Trying contact form: {website}{Style.RESET_ALL}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        submitted = False

        for path in CONTACT_PATHS:
            url = website.rstrip("/") + path
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                await page.wait_for_timeout(1500)

                result = await _fill_and_submit_form(page, company, message, subject)
                if result:
                    print(f"{Fore.GREEN}  ✔ Contact form submitted at {url}{Style.RESET_ALL}")
                    submitted = True
                    break

            except Exception as e:
                continue

        await browser.close()

    return submitted


def submit_contact_form(company: dict, headless: bool = True) -> bool:
    """Synchronous wrapper around the async contact form submitter."""
    try:
        return asyncio.run(submit_contact_form_async(company, headless=headless))
    except Exception as e:
        print(f"{Fore.RED}  ✘ Contact form error: {e}{Style.RESET_ALL}")
        return False


def run_contact_form_outreach(dry_run: bool = False):
    """
    Find all leads with no email ('no email' status) that have a website,
    and try to submit their contact form instead.
    """
    from sheets.sheets_client import get_all_leads, update_lead_status, log_email_sent

    print(f"\n{Fore.CYAN}{'─'*55}")
    print(f"📋 Contact Form Outreach")
    print(f"   Finding leads with no email but a website...")
    print(f"{'─'*55}{Style.RESET_ALL}\n")

    all_leads = get_all_leads()

    # Only process leads with status = "no email" and a website
    targets = [
        (i + 2, lead) for i, lead in enumerate(all_leads)
        if str(lead.get("Status", "")).lower() == "no email"
        and lead.get("Website", "")
    ]

    if not targets:
        print(f"{Fore.YELLOW}  No leads found without email but with a website.{Style.RESET_ALL}\n")
        return

    print(f"{Fore.CYAN}  Found {len(targets)} lead(s) to try contact forms{Style.RESET_ALL}\n")

    sent = 0
    failed = 0

    for row_index, lead in targets:
        company_name = lead.get("Company Name", "")
        website      = lead.get("Website", "")
        category     = lead.get("Category", "")

        company = {
            "name":     company_name,
            "website":  website,
            "category": category,
            "source":   lead.get("Source", ""),
        }

        print(f"  → {Fore.WHITE}{company_name}{Style.RESET_ALL} | {website}")

        if dry_run:
            print(f"    {Fore.YELLOW}[DRY RUN] Would submit contact form{Style.RESET_ALL}")
            continue

        success = submit_contact_form(company)

        if success:
            update_lead_status(row_index, "form_sent", "")
            log_email_sent(company_name, "contact_form", category,
                           source=lead.get("Source", ""), template="contact_form")
            print(f"    {Fore.GREEN}✔ Form submitted!{Style.RESET_ALL}")
            sent += 1
        else:
            print(f"    {Fore.RED}✘ No contact form found or submit failed{Style.RESET_ALL}")
            failed += 1

        time.sleep(3)  # Be polite between submissions

    if dry_run:
        print(f"\n{Fore.YELLOW}[DRY RUN] Would have tried {len(targets)} contact forms{Style.RESET_ALL}\n")
    else:
        print(f"\n{Fore.GREEN}✔ Done — {sent} forms submitted, {failed} failed{Style.RESET_ALL}\n")
