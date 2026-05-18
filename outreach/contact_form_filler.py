"""
outreach/contact_form_filler.py

Automatically fills contact forms on company websites.
Used for leads that have no email address.

Flow:
  1. Finds leads with status "no email" or "pending" with no email
  2. Visits their website
  3. Finds contact/kontakt page
  4. Fills the form with AI-generated message (Groq)
  5. Submits the form
  6. Updates Sheet status → "contacted-form"

Usage:
    python main.py contact-forms            # Fill all 'no email' leads
    python main.py contact-forms --dry-run  # Preview without submitting
"""

from __future__ import annotations
import time
import re
from colorama import Fore, Style
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

import config

# ── Your outreach details ─────────────────────────────────────────────────────
SENDER = {
    "name":    "Manoj Uddagiri",
    "email":   "info@ayonic.com",
    "phone":   "+493028619101",
    "company": "Ayonic",
    "subject": "Zusammenarbeit anfragen – Ayonic",
}

AYONIC_DESC = (
    "an on-demand service booking platform that connects customers directly "
    "with trusted local cleaning professionals."
)


def _generate_form_message_ai(company_name: str) -> str:
    """Use Groq AI to write a contact form message."""
    try:
        from groq import Groq
        client = Groq(api_key=config.GROQ_API_KEY)

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": f"""Write a SHORT contact form message to {company_name}.
You are Manoj from Ayonic (ayonic.com) — {AYONIC_DESC}

RULES:
1. Write in German (they are a Berlin company)
2. MAX 80 words
3. Be friendly and direct
4. Mention: more customers, no costs to join, full control
5. Ask for a quick call or email reply
6. End with your contact: info@ayonic.com / +49 30 28619101
7. No emojis, no bullet points
8. Just the message, no subject line

Return ONLY the message text."""}],
            max_tokens=300,
            temperature=0.7,
        )
        msg = response.choices[0].message.content.strip()
        print(f"  {Fore.GREEN}AI message generated{Style.RESET_ALL}")
        return msg
    except Exception:
        pass

    # Fallback template
    return f"""Hallo {company_name},

mein Name ist Manoj von Ayonic. Wir verbinden Reinigungsunternehmen in Berlin mit neuen Kunden ueber unsere Buchungsplattform.

Fuer Sie: mehr Auftraege, keine Marketingkosten, volle Kontrolle ueber Preise und Termine. Der Beitritt ist kostenlos.

Ich wuerde mich ueber ein kurzes Gespraech freuen.

Kontakt: info@ayonic.com / +49 30 28619101

Viele Gruesse,
Manoj Uddagiri, Ayonic"""


# ── Contact page URL patterns ─────────────────────────────────────────────────
CONTACT_URL_PATTERNS = [
    "/contact", "/kontakt", "/kontaktieren", "/anfrage",
    "/contact-us", "/kontakt.html", "/kontakt.php",
    "/kontakt/", "/contact/", "/anfrage/",
    "/angebot", "/angebot-anfordern", "/anfrage-senden",
    "/impressum", "/anfragen", "/get-in-touch",
    "/about/contact", "/en/contact", "/de/kontakt",
    "/feedback", "/schreib-uns", "/write-us",
]

# Link text patterns (for finding contact links by visible text)
CONTACT_LINK_TEXT = [
    "Kontakt", "Contact", "Anfrage", "Angebot",
    "Schreiben Sie uns", "Write to us", "Get in touch",
    "Contact us", "Kontaktieren", "Nachricht",
]

# ── Common field selectors ────────────────────────────────────────────────────
# German forms use: Name, Firma, Vorname, Nachname, Ihr Name, etc.
NAME_SELECTORS = [
    'input[name*="name" i]', 'input[placeholder*="name" i]',
    'input[id*="name" i]',   'input[name*="vorname" i]',
    'input[placeholder*="Ihr Name" i]', 'input[aria-label*="Name" i]',
    'input[name*="your-name" i]', 'input[name*="full_name" i]',
    'input[placeholder*="Name*" i]', 'input[placeholder*="Ansprechpartner" i]',
]
# German: E-Mail, Mail, E-Mail-Adresse
EMAIL_SELECTORS = [
    'input[type="email"]', 'input[name*="email" i]',
    'input[id*="email" i]', 'input[placeholder*="email" i]',
    'input[placeholder*="E-Mail" i]', 'input[name*="your-email" i]',
    'input[aria-label*="mail" i]', 'input[name*="mail" i]',
    'input[placeholder*="Mail" i]',
]
# German: Telefon, Handy, Rufnummer, Mobilnummer
PHONE_SELECTORS = [
    'input[type="tel"]', 'input[name*="phone" i]',
    'input[name*="telefon" i]', 'input[name*="tel" i]',
    'input[id*="phone" i]',     'input[placeholder*="Telefon" i]',
    'input[name*="your-phone" i]', 'input[aria-label*="Telefon" i]',
    'input[placeholder*="Phone" i]', 'input[placeholder*="Handy" i]',
    'input[placeholder*="Rufnummer" i]',
]
# German: Betreff, Anliegen, Thema
SUBJECT_SELECTORS = [
    'input[name*="subject" i]', 'input[name*="betreff" i]',
    'input[id*="subject" i]',   'input[placeholder*="Betreff" i]',
    'input[name*="your-subject" i]', 'input[placeholder*="Anliegen" i]',
    'input[placeholder*="Thema" i]',
]
# German: Nachricht, Mitteilung, Notiz, Anmerkung, Kommentar, Anliegen
MESSAGE_SELECTORS = [
    'textarea[name*="message" i]', 'textarea[name*="nachricht" i]',
    'textarea[id*="message" i]',   'textarea[name*="text" i]',
    'textarea[placeholder*="Nachricht" i]', 'textarea[name*="your-message" i]',
    'textarea[aria-label*="Nachricht" i]', 'textarea[name*="comment" i]',
    'textarea[placeholder*="Mitteilung" i]', 'textarea[placeholder*="Notiz" i]',
    'textarea[placeholder*="Anmerkung" i]', 'textarea[placeholder*="Anliegen" i]',
    'textarea[placeholder*="help" i]', 'textarea[placeholder*="How can" i]',
    'textarea',
]
# German: Senden, Absenden, Abschicken, Anfrage senden, Nachricht senden
SUBMIT_SELECTORS = [
    'button[type="submit"]', 'input[type="submit"]',
    'button:has-text("Senden")', 'button:has-text("Absenden")',
    'button:has-text("Send")',   'button:has-text("Submit")',
    'button:has-text("Anfrage")', 'button:has-text("Nachricht senden")',
    'button:has-text("Abschicken")', 'button:has-text("Formular")',
    'button:has-text("Jetzt senden")', 'button:has-text("Anfrage senden")',
    '[class*="submit" i]', 'input[value*="Send" i]',
    'input[value*="Senden" i]', 'input[value*="Absenden" i]',
]


def _try_fill(page, selectors: list[str], value: str) -> bool:
    """Try each selector until one works. Returns True if filled."""
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                # Use fill() directly — click() can be blocked by cookie overlays
                el.fill(value)
                return True
        except Exception:
            continue
    return False


def _smart_fill_form(page, message: str) -> dict:
    """
    Smart form filler: tries selectors first, then falls back to
    type-based detection for forms with empty name fields.
    Returns dict of what was filled.
    """
    filled = {}

    # Standard selector-based filling
    filled["name"]    = _try_fill(page, NAME_SELECTORS, SENDER["name"])
    filled["email"]   = _try_fill(page, EMAIL_SELECTORS, SENDER["email"])
    filled["phone"]   = _try_fill(page, PHONE_SELECTORS, SENDER["phone"])
    filled["subject"] = _try_fill(page, SUBJECT_SELECTORS, SENDER["subject"])
    filled["message"] = _try_fill(page, MESSAGE_SELECTORS, message)

    # Fallback: if email not filled, try by input type OR placeholder
    if not filled["email"]:
        try:
            # Try type=email first
            el = page.query_selector('form input[type="email"]')
            if not (el and el.is_visible()):
                # German sites often use type=text with placeholder "E-Mail"
                inputs = page.query_selector_all('form input[type="text"]')
                for inp in inputs:
                    if inp.is_visible():
                        ph = (inp.get_attribute("placeholder") or "").lower()
                        if "mail" in ph or "e-mail" in ph:
                            el = inp
                            break
            if el and el.is_visible():
                el.fill(SENDER["email"])
                filled["email"] = True
        except Exception:
            pass

    # Fallback: if phone not filled, try by input type
    if not filled["phone"]:
        try:
            el = page.query_selector('form input[type="tel"]')
            if el and el.is_visible():
                el.fill(SENDER["phone"])
                filled["phone"] = True
        except Exception:
            pass

    # Fallback: if message not filled, try any visible textarea inside a form
    if not filled["message"]:
        try:
            textareas = page.query_selector_all('form textarea')
            for ta in textareas:
                if ta.is_visible():
                    ta_name = (ta.get_attribute("name") or "").lower()
                    # Skip reCAPTCHA hidden textarea
                    if "recaptcha" in ta_name:
                        continue
                    ta.fill(message)
                    filled["message"] = True
                    break
        except Exception:
            pass

    # Fallback: if name not filled, try first visible text input in form
    if not filled["name"]:
        try:
            inputs = page.query_selector_all('form input[type="text"]')
            for inp in inputs:
                if inp.is_visible():
                    ph = (inp.get_attribute("placeholder") or "").lower()
                    name_attr = (inp.get_attribute("name") or "").lower()
                    # Only fill if it looks like a name field
                    if any(k in ph or k in name_attr for k in ["name", "firma", "vorname"]):
                        inp.fill(SENDER["name"])
                        filled["name"] = True
                        break
        except Exception:
            pass

    # Auto-tick privacy/consent checkboxes
    filled["checkbox"] = _tick_checkboxes(page)

    return filled


def _tick_checkboxes(page) -> bool:
    """
    Auto-tick Datenschutz / privacy / consent checkboxes.
    German forms almost always require this before submitting.
    """
    ticked = False

    # Common German privacy checkbox patterns
    checkbox_selectors = [
        # By label text (most reliable)
        'label:has-text("Datenschutz") input[type="checkbox"]',
        'label:has-text("datenschutz") input[type="checkbox"]',
        'label:has-text("Privacy") input[type="checkbox"]',
        'label:has-text("Einwilligung") input[type="checkbox"]',
        'label:has-text("Zustimmung") input[type="checkbox"]',
        'label:has-text("akzeptiere") input[type="checkbox"]',
        'label:has-text("stimme zu") input[type="checkbox"]',
        'label:has-text("consent") input[type="checkbox"]',
        'label:has-text("agree") input[type="checkbox"]',
        'label:has-text("DSGVO") input[type="checkbox"]',
        # By name/id attribute
        'input[type="checkbox"][name*="datenschutz" i]',
        'input[type="checkbox"][name*="privacy" i]',
        'input[type="checkbox"][name*="consent" i]',
        'input[type="checkbox"][name*="dsgvo" i]',
        'input[type="checkbox"][name*="agree" i]',
        'input[type="checkbox"][name*="gdpr" i]',
        'input[type="checkbox"][name*="terms" i]',
        'input[type="checkbox"][id*="datenschutz" i]',
        'input[type="checkbox"][id*="privacy" i]',
        'input[type="checkbox"][id*="consent" i]',
    ]

    for sel in checkbox_selectors:
        try:
            boxes = page.query_selector_all(sel)
            for box in boxes:
                if box.is_visible() and not box.is_checked():
                    box.check()
                    ticked = True
        except Exception:
            continue

    # Fallback: if no specific checkbox found, look for any checkbox
    # near privacy-related text on the page
    if not ticked:
        try:
            all_boxes = page.query_selector_all('form input[type="checkbox"]')
            for box in all_boxes:
                if not box.is_visible() or box.is_checked():
                    continue
                # Check surrounding text for privacy keywords
                parent = box.evaluate("""el => {
                    let p = el.closest('label, div, p, span, li');
                    return p ? p.innerText.toLowerCase().substring(0, 120) : '';
                }""")
                privacy_keywords = [
                    "datenschutz", "privacy", "einwillig", "zustimm",
                    "akzeptier", "consent", "agree", "dsgvo", "gdpr",
                    "personenbezogen", "einverstand", "bestätig",
                ]
                if any(kw in parent for kw in privacy_keywords):
                    box.check()
                    ticked = True
        except Exception:
            pass

    return ticked


def _has_captcha(page) -> bool:
    """Check if the current page has a CAPTCHA."""
    try:
        return bool(
            page.query_selector('[class*="recaptcha"]')
            or page.query_selector('[class*="captcha"]')
            or page.query_selector('iframe[src*="recaptcha"]')
            or page.query_selector('iframe[src*="hcaptcha"]')
            or page.query_selector('[class*="g-recaptcha"]')
        )
    except Exception:
        return False


def _find_next_button(page):
    """
    Find a 'Next' / 'Continue' button for multi-step forms.
    Returns the element or None.
    """
    next_selectors = [
        # German
        'button:has-text("Weiter")',
        'button:has-text("Nächster Schritt")',
        'button:has-text("Fortfahren")',
        'button:has-text("Nächste")',
        'button:has-text("Schritt")',
        'a:has-text("Weiter")',
        'a:has-text("Nächster Schritt")',
        # English
        'button:has-text("Next")',
        'button:has-text("Continue")',
        'button:has-text("Next step")',
        'a:has-text("Next")',
        'a:has-text("Continue")',
        # Generic
        'button[class*="next" i]',
        'button[class*="weiter" i]',
        'input[value*="Weiter" i]',
        'input[value*="Next" i]',
    ]
    for sel in next_selectors:
        try:
            btn = page.query_selector(sel)
            if btn and btn.is_visible():
                # Make sure it's NOT a submit button
                btn_text = (btn.inner_text() or "").lower()
                btn_type = (btn.get_attribute("type") or "").lower()
                if btn_type == "submit":
                    continue  # Skip — this is the final submit
                if any(w in btn_text for w in ["senden", "absenden", "submit", "abschicken"]):
                    continue  # Skip — this is the final submit
                return btn
        except Exception:
            continue
    return None


def _detect_form_success(page) -> str:
    """
    Detect if a form was submitted successfully by checking for
    thank-you messages, URL changes, or confirmation elements.
    Returns a status string: 'confirmed', 'likely', or 'unknown'.
    """
    # Check 1: URL changed to a thank-you page
    current_url = page.url.lower()
    thank_you_urls = [
        "danke", "thank", "success", "bestätigung",
        "confirmation", "vielen-dank", "erfolgreich",
    ]
    if any(kw in current_url for kw in thank_you_urls):
        return "confirmed"

    # Check 2: Page body contains success text
    try:
        body_text = (page.inner_text("body") or "").lower()[:2000]
    except Exception:
        body_text = ""

    # Strong confirmation phrases (German + English)
    confirmed_phrases = [
        "vielen dank für ihre nachricht",
        "vielen dank für ihre anfrage",
        "ihre nachricht wurde gesendet",
        "ihre anfrage wurde gesendet",
        "nachricht erfolgreich",
        "formular erfolgreich",
        "wir haben ihre anfrage erhalten",
        "wir melden uns bei ihnen",
        "thank you for your message",
        "your message has been sent",
        "message sent successfully",
        "we will get back to you",
        "successfully submitted",
    ]
    if any(phrase in body_text for phrase in confirmed_phrases):
        return "confirmed"

    # Weaker signals — "Danke" or "Thank you" appearing
    # (but NOT from cookie banners or generic page text)
    likely_phrases = [
        "vielen dank", "herzlichen dank",
        "danke für ihre", "danke für ihr",
        "thank you", "thanks for", "erfolgreich gesendet",
    ]
    if any(phrase in body_text for phrase in likely_phrases):
        return "likely"

    # Check 3: Success toast / alert / notification appeared
    success_selectors = [
        '[class*="success"]', '[class*="alert-success"]',
        '[class*="notice-success"]', '[class*="message-success"]',
        '[class*="toast"]', '[class*="confirmation"]',
        '[role="alert"]',
    ]
    for sel in success_selectors:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                text = (el.inner_text() or "").lower()
                if any(w in text for w in ["dank", "thank", "success", "gesendet", "sent"]):
                    return "confirmed"
        except Exception:
            continue

    # Check 4: Original form is no longer visible (replaced by a message)
    try:
        forms = page.query_selector_all("form")
        visible_forms = [f for f in forms if f.is_visible()]
        if len(visible_forms) == 0:
            return "likely"  # Form disappeared = probably submitted
    except Exception:
        pass

    return "unknown"


def _dismiss_cookies(page):
    """Try to dismiss cookie banners (including cookiescript overlays)."""
    # First: try removing cookie overlay via JavaScript (works for cookiescript)
    try:
        page.evaluate("""
            document.querySelectorAll(
                '#cookiescript_injected_wrapper, .cookie-banner, .cookie-consent, ' +
                '[id*="cookie-banner"], [class*="cookie-overlay"], ' +
                '[id*="cookieconsent"], .cc-window'
            ).forEach(el => el.remove());
        """)
    except Exception:
        pass

    cookie_btns = [
        'button:has-text("Akzeptieren")', 'button:has-text("Accept")',
        'button:has-text("Alle akzeptieren")', 'button:has-text("Accept all")',
        'button:has-text("OK")', 'button:has-text("Verstanden")',
        'a:has-text("Akzeptieren")', '[id*="cookie"] button',
        '[class*="cookie"] button', '[id*="consent"] button',
        '#cookiescript_accept',
    ]
    for sel in cookie_btns:
        try:
            btn = page.query_selector(sel)
            if btn and btn.is_visible():
                btn.click()
                page.wait_for_timeout(500)
                return
        except Exception:
            continue


def _find_contact_url(page, base_url: str) -> str | None:
    """Look for a contact page link on the current page."""

    # Method 1: Check if current page already has a fillable form
    # (many German sites have contact form right on homepage!)
    try:
        forms = page.query_selector_all('form')
        for form in forms:
            email_input = form.query_selector('input[type="email"]')
            textarea = form.query_selector('textarea')
            if email_input or textarea:
                return page.url
    except Exception:
        pass

    # Method 2: Find by href pattern
    for pattern in CONTACT_URL_PATTERNS:
        try:
            link = page.query_selector(f'a[href*="{pattern}" i]')
            if link:
                href = link.get_attribute("href")
                if href:
                    if href.startswith("http"):
                        return href
                    elif href.startswith("/"):
                        return base_url.rstrip("/") + href
                    else:
                        return base_url.rstrip("/") + "/" + href
        except Exception:
            continue

    # Method 3: Find by link text (German: "Kontakt", "Anfrage", etc.)
    for text in CONTACT_LINK_TEXT:
        try:
            link = page.query_selector(f'a:has-text("{text}")')
            if link:
                href = link.get_attribute("href")
                if href and href != "#" and "javascript" not in href:
                    if href.startswith("http"):
                        return href
                    elif href.startswith("/"):
                        return base_url.rstrip("/") + href
                    else:
                        return base_url.rstrip("/") + "/" + href
        except Exception:
            continue

    # Method 4: Try directly navigating to common contact paths
    for pattern in ["/kontakt", "/contact", "/kontakt/", "/contact/", "/anfrage"]:
        url = base_url.rstrip("/") + pattern
        try:
            resp = page.goto(url, timeout=8000, wait_until="domcontentloaded")
            if resp and resp.status < 400:
                form = page.query_selector('form') or page.query_selector('textarea')
                if form:
                    return url
        except Exception:
            continue

    return None


def fill_contact_form(website: str, company_name: str = "",
                      dry_run: bool = False) -> dict:
    """
    Try to fill and submit a contact form on the given website.
    Returns dict with keys: success (bool), reason (str), url (str)
    """
    result = {"success": False, "reason": "", "url": website}

    if not website or not website.startswith("http"):
        result["reason"] = "invalid URL"
        return result

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="de-DE",
        )
        page = context.new_page()
        page.set_default_timeout(10000)

        try:
            # Step 1: Load homepage
            page.goto(website, timeout=12000, wait_until="domcontentloaded")
            page.wait_for_timeout(1000)
            m = re.match(r'https?://[^/]+', page.url)
            if not m:
                result["reason"] = "invalid URL after redirect"
                return result
            base_url = m.group(0)

            # Step 1b: Dismiss cookie banner (very common on German sites)
            _dismiss_cookies(page)

            # Step 2: Find contact page
            contact_url = _find_contact_url(page, base_url)
            if not contact_url:
                result["reason"] = "no contact page found"
                return result

            result["url"] = contact_url
            if contact_url != page.url:
                page.goto(contact_url, timeout=10000, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)

            # Dismiss cookies again (some sites show it on every page)
            _dismiss_cookies(page)

            # Step 3: Fill fields using smart filler
            message = _generate_form_message_ai(company_name or "Ihr Unternehmen")
            filled = _smart_fill_form(page, message)

            if not (filled.get("email") or filled.get("message")):
                result["reason"] = "could not fill any fields"
                return result

            # Check for reCAPTCHA (can't bypass, but form is filled)
            has_captcha = _has_captcha(page)

            # Step 4: Handle multi-page forms (up to 3 steps)
            pages_filled = 1
            for step in range(2):  # Try 2 more steps max
                next_btn = _find_next_button(page)
                if not next_btn:
                    break  # No next button = single page form

                if dry_run:
                    # In dry-run, note it's multi-page but don't click
                    filled[f"page{step+2}"] = True
                    pages_filled += 1
                    break

                # Click next/continue
                try:
                    next_btn.click()
                    page.wait_for_timeout(2000)
                except Exception:
                    break

                # Fill new fields on the next page
                extra = _smart_fill_form(page, message)
                for k, v in extra.items():
                    if v and not filled.get(k):
                        filled[k] = True

                pages_filled += 1
                has_captcha = has_captcha or _has_captcha(page)

            # Step 5: Submit (unless dry run)
            if not dry_run:
                if has_captcha:
                    result["success"] = False
                    result["reason"] = "form filled but has CAPTCHA - cannot auto-submit"
                    return result

                submitted = False
                for sel in SUBMIT_SELECTORS:
                    try:
                        btn = page.query_selector(sel)
                        if btn and btn.is_visible():
                            btn.click()
                            page.wait_for_timeout(3000)
                            submitted = True
                            break
                    except Exception:
                        continue

                if not submitted:
                    result["reason"] = "submit button not found"
                    return result

                # Step 6: Detect success
                confirmation = _detect_form_success(page)
            else:
                confirmation = "dry-run"

            filled_fields = [k for k, v in filled.items() if v]
            captcha_note = " (has CAPTCHA)" if has_captcha else ""
            multi_note = f" ({pages_filled} pages)" if pages_filled > 1 else ""
            confirm_note = f" ✓{confirmation}" if confirmation != "unknown" else ""
            result["success"] = True
            result["confirmation"] = confirmation
            result["reason"] = f"{'dry run' if dry_run else 'submitted'} [{', '.join(filled_fields)}]{captcha_note}{multi_note}{confirm_note}"
            return result

        except PlaywrightTimeout:
            result["reason"] = "timeout"
            return result
        except Exception as e:
            result["reason"] = str(e)[:80]
            return result
        finally:
            browser.close()


def _get_today_form_count() -> int:
    """Get how many forms were submitted today."""
    import json, os
    from datetime import date
    tracker = os.path.join(os.path.dirname(__file__), "..", ".form_count.json")
    try:
        with open(tracker) as f:
            data = json.load(f)
        if data.get("date") == str(date.today()):
            return data.get("count", 0)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return 0


def _increment_form_count():
    """Increment today's form submission count."""
    import json, os
    from datetime import date
    tracker = os.path.join(os.path.dirname(__file__), "..", ".form_count.json")
    count = _get_today_form_count() + 1
    with open(tracker, "w") as f:
        json.dump({"date": str(date.today()), "count": count}, f)
    return count


def run_contact_form_filler(dry_run: bool = False):
    """
    Main runner: fetch all leads without email,
    try to fill each contact form, update status in sheet.
    Rate limited to DAILY_FORM_LIMIT per day.
    """
    from sheets.sheets_client import get_all_leads, update_lead_status

    daily_limit = getattr(config, "DAILY_FORM_LIMIT", 15)
    today_count = _get_today_form_count()

    if today_count >= daily_limit:
        print(f"\n{Fore.YELLOW}⚠ Daily form limit reached ({today_count}/{daily_limit}){Style.RESET_ALL}")
        print(f"  Try again tomorrow or increase DAILY_FORM_LIMIT in config.py\n")
        return 0

    remaining = daily_limit - today_count

    leads = get_all_leads()
    no_email_leads = [
        (i + 2, l)
        for i, l in enumerate(leads)
        if (
            (l.get("Status") or "").strip().lower() in ("no email", "pending")
            and not (l.get("Email") or "").strip()
            and (l.get("Website") or "").startswith("http")
        )
    ]

    print(f"\n{Fore.CYAN}▶ Contact Form Filler {'(DRY RUN)' if dry_run else ''}{Style.RESET_ALL}")
    print(f"  Found {len(no_email_leads)} leads without email")
    print(f"  Today: {today_count}/{daily_limit} forms used → {remaining} remaining\n")

    if not no_email_leads:
        print(f"  {Fore.GREEN}✔ No leads need contact form submission{Style.RESET_ALL}\n")
        return 0

    success = 0
    failed  = 0

    for row_idx, lead in no_email_leads:
        # Rate limit check
        if success >= remaining:
            print(f"\n{Fore.YELLOW}⚠ Daily limit reached ({daily_limit}/day). Stopping.{Style.RESET_ALL}")
            break

        name    = (lead.get("Company Name") or "")[:40]
        website = lead.get("Website") or ""

        print(f"{Fore.CYAN}🌐 {name:<40}{Style.RESET_ALL} {website[:50]}")

        result = fill_contact_form(website, company_name=name, dry_run=dry_run)

        if result["success"]:
            success += 1
            print(f"  {Fore.GREEN}✔ Form {'would be ' if dry_run else ''}submitted → {result['url'][:60]}{Style.RESET_ALL}")
            print(f"  {Fore.GREEN}  Reason: {result['reason']}{Style.RESET_ALL}")
            if not dry_run:
                _increment_form_count()
                try:
                    update_lead_status(row_idx, "contacted-form", "")
                except Exception:
                    pass
        else:
            failed += 1
            print(f"  {Fore.YELLOW}✘ Skipped — {result['reason']}{Style.RESET_ALL}")

        time.sleep(1.5)

    final_count = _get_today_form_count() if not dry_run else today_count
    print(f"\n{Fore.GREEN}✔ Done — {success} forms {'would be ' if dry_run else ''}submitted, {failed} skipped{Style.RESET_ALL}")
    print(f"  Today total: {final_count}/{daily_limit}\n")
    return success
