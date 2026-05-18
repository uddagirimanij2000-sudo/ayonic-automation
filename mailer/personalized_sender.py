"""
mailer/personalized_sender.py

Scrapes each company's website → extracts their specifics →
builds a hyper-personalized bilingual email → sends it.
"""

from __future__ import annotations
import smtplib
import time
import re
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from colorama import Fore, Style
from bs4 import BeautifulSoup

import config

# ── Test emails ───────────────────────────────────────────────────────────────
TEST_EMAILS = [
    "uddagirimanoj2001@gmail.com",
    "uddagirimanij2000@gmail.com",
]

SENDER_NAME  = "Manoj"
SENDER_TITLE = "Founder, Ayonic"
SENDER_EMAIL = "info@ayonic.com"
SENDER_PHONE = "+49 30 28619101"
AYONIC_URL   = "https://ayonic.com"

AYONIC_DESC = (
    "an on-demand service booking platform that connects customers directly "
    "with trusted local cleaning professionals. Customers book verified experts, "
    "track appointments, and get instant quotes — all in one place."
)
AYONIC_DESC_DE = (
    "eine On-Demand-Buchungsplattform, die Kunden direkt mit verifizierten "
    "lokalen Reinigungsprofis verbindet. Kunden buchen einfach online, "
    "verfolgen Termine und erhalten sofortige Angebote – alles an einem Ort."
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


def scrape_company(website: str) -> dict:
    info = {"specialty": "", "district": "", "years": "", "usp": "", "raw_text": ""}
    if not website or not website.startswith("http"):
        return info
    try:
        resp = requests.get(website, headers=HEADERS, timeout=8)
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "head"]):
            tag.decompose()
        raw = re.sub(r"\s+", " ", soup.get_text(separator=" ", strip=True))[:2000]
        info["raw_text"] = raw
        raw_lower = raw.lower()

        districts = [
            "Mitte", "Charlottenburg", "Prenzlauer Berg", "Kreuzberg",
            "Friedrichshain", "Neukölln", "Schöneberg", "Tempelhof",
            "Spandau", "Steglitz", "Zehlendorf", "Reinickendorf", "Pankow",
            "Treptow", "Köpenick", "Lichtenberg", "Wedding", "Wilmersdorf",
        ]
        for d in districts:
            if d.lower() in raw_lower:
                info["district"] = d
                break

        year_match = re.search(r"(seit|since|gegründet|founded)\s*(in\s*)?(\d{4})", raw_lower)
        if year_match:
            yr = int(year_match.group(3))
            if 1980 <= yr <= 2025:
                info["years"] = str(2025 - yr)

        specs_map = {
            "büroreinigung": "Büroreinigung", "gebäudereinigung": "Gebäudereinigung",
            "fensterreinigung": "Fensterreinigung", "grundreinigung": "Grundreinigung",
            "teppichreinigung": "Teppichreinigung", "unterhaltsreinigung": "Unterhaltsreinigung",
            "polsterreinigung": "Polsterreinigung", "haushaltshilfe": "Haushaltshilfe",
            "baureinigung": "Baureinigung", "office cleaning": "office cleaning",
            "window cleaning": "window cleaning", "carpet cleaning": "carpet cleaning",
            "deep cleaning": "deep cleaning",
        }
        found = [v for k, v in specs_map.items() if k in raw_lower]
        info["specialty"] = ", ".join(found[:3])

        usps = {
            "umweltfreundlich": "umweltfreundliche Reinigungsmittel",
            "eco": "eco-friendly products", "24/7": "24/7 Verfügbarkeit",
            "zuverlässig": "zuverlässigen Service", "professionell": "professionelles Team",
            "erfahren": "langjährige Erfahrung", "flexibel": "flexible Terminvereinbarung",
        }
        for k, v in usps.items():
            if k in raw_lower:
                info["usp"] = v
                break
    except Exception:
        pass
    return info


def _build_ai_prompt(company_name: str, website: str, raw_text: str, info: dict) -> str:
    """Build the AI prompt for email generation."""
    city = info.get("district", "Berlin") or "Berlin"
    lang = getattr(config, "EMAIL_LANGUAGE", "both")

    # Language instruction
    if lang == "en":
        lang_rule = "Write ONLY in English. Do NOT include German."
    elif lang == "de":
        lang_rule = "Write ONLY in German. Do NOT include English."
    else:
        lang_rule = 'Write in BOTH English and German (English first, then "---", then German).'

    return f"""You are Manoj Uddagiri, founder of Ayonic (ayonic.com).
Ayonic helps cleaning companies get more customers by listing them on a booking platform — free to join.

Write a SHORT personal email to {company_name} ({website}) in {city}.

Here is what we know about them from their website:
- Specialty: {info.get('specialty', 'cleaning services')}
- City/District: {city}
- Years in business: {info.get('years', 'unknown')}
- USP: {info.get('usp', 'unknown')}
- Website text excerpt: {raw_text[:800]}

CRITICAL RULES (Gmail will filter this, so follow exactly):

1. Subject line: Write something short and personal, like "Quick question" or "Saw your website" or "Hi from {city}". Do NOT use words like "cooperation", "inquiry", "partnership", "opportunity" in the subject.

2. {lang_rule}

3. Keep it VERY SHORT — max 80 words per language. Write like you're texting a business owner, not writing a formal letter.

4. Start with "Hi" or "Hallo", NOT "Hello Team of". Use the company name naturally.

5. Mention ONE specific thing from their website (a service they offer, something you noticed). This is the most important part — it proves you actually looked at their site.

6. Explain what Ayonic does in ONE sentence: "We connect people who need cleaning with local pros like you."

7. Ask a simple question at the end: "Would a quick call make sense?" or "Is this something you'd be open to?"

8. Do NOT use these words: "platform", "marketing", "acquisition", "orders", "capacity", "cooperation inquiry", "non-binding"

9. Sign off simply:
   Manoj Uddagiri
   Ayonic | {AYONIC_URL}
   {SENDER_PHONE}

10. Add unsubscribe line: "Reply 'stop' to unsubscribe."

11. Do NOT use emojis or bullet points

12. The email should read like a real person wrote it — casual, warm, brief. NOT a sales pitch.

Format your response EXACTLY as:
SUBJECT: [your subject here]
BODY:
[your email here]
"""


def _clean_company_name(name: str) -> str:
    """Strip long descriptions from Sheet company names."""
    # "B&D Reinigungs Experte (UG) | Gebäudereinigung..." → "B&D Reinigungs Experte"
    for sep in [" | ", " - ", " – ", " — "]:
        if sep in name:
            name = name.split(sep)[0].strip()
    # Remove (UG), (GmbH) etc if name is still long
    if len(name) > 40:
        import re
        name = re.sub(r'\s*\(.*?\)\s*', ' ', name).strip()
    return name[:50]


def _parse_ai_response(text: str, company_name: str) -> tuple:
    """Parse AI response into subject and body."""
    text = text.strip()
    if "SUBJECT:" in text and "BODY:" in text:
        subject = text.split("SUBJECT:")[1].split("BODY:")[0].strip()
        body = text.split("BODY:")[1].strip()
    else:
        subject = f"Quick question, {company_name}"
        body = text

    # Remove any leaked "SUBJECT:" line from body
    lines = body.split("\n")
    cleaned = [l for l in lines if not l.strip().upper().startswith("SUBJECT:")]
    body = "\n".join(cleaned).strip()

    return subject, body


def _generate_with_groq(company_name: str, website: str, raw_text: str,
                         info: dict) -> tuple:
    """Use Groq AI (free, no card) to write a unique personalized email."""
    try:
        from groq import Groq
        client = Groq(api_key=config.GROQ_API_KEY)

        prompt = _build_ai_prompt(company_name, website, raw_text, info)

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.7,
        )

        text = response.choices[0].message.content
        subject, body = _parse_ai_response(text, company_name)
        print(f"{Fore.GREEN}  AI email generated (Groq){Style.RESET_ALL}")
        return subject, body

    except Exception as e:
        print(f"{Fore.YELLOW}  Groq error: {e}{Style.RESET_ALL}")
        return None, None


def _generate_with_gemini(company_name: str, website: str, raw_text: str,
                           info: dict) -> tuple:
    """Use Gemini AI to write a unique personalized email."""
    try:
        import google.generativeai as genai
        genai.configure(api_key=config.GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")

        prompt = _build_ai_prompt(company_name, website, raw_text, info)
        response = model.generate_content(prompt)
        text = response.text.strip()

        subject, body = _parse_ai_response(text, company_name)
        print(f"{Fore.GREEN}  AI email generated (Gemini){Style.RESET_ALL}")
        return subject, body

    except Exception as e:
        print(f"{Fore.YELLOW}  Gemini error: {e}{Style.RESET_ALL}")
        return None, None


def build_personalized_email(company_name: str, website: str,
                             address: str = "", category: str = "") -> tuple:
    company_name = _clean_company_name(company_name)
    print(f"  🔍 Scraping {website[:50]}...", end=" ", flush=True)
    info = scrape_company(website)
    print("done")

    raw_text = info.get("raw_text", "")

    # Try Groq first (free, no card needed)
    if config.GROQ_API_KEY:
        subject, body = _generate_with_groq(company_name, website, raw_text, info)
        if subject and body:
            return subject, body

    # Try Gemini second
    if config.GEMINI_API_KEY:
        subject, body = _generate_with_gemini(company_name, website, raw_text, info)
        if subject and body:
            return subject, body
    spec = info["specialty"]
    dist = info["district"] or "Berlin"
    yrs  = info["years"]
    usp  = info["usp"]

    # Build personalized detail line
    if spec and usp:
        detail_en = f"your {spec} service and especially {usp}"
        detail_de = f"Ihren {spec}-Service und insbesondere {usp}"
    elif spec:
        detail_en = f"your professional {spec} service"
        detail_de = f"Ihren professionellen {spec}-Service"
    elif usp:
        detail_en = f"your {usp}"
        detail_de = f"Ihr {usp}"
    else:
        detail_en = "your professional cleaning services"
        detail_de = "Ihre professionellen Reinigungsdienstleistungen"

    yrs_note_en = f" With {yrs} years of experience, your expertise speaks for itself." if yrs else ""
    yrs_note_de = f" Mit {yrs} Jahren Erfahrung spricht Ihre Expertise fuer sich." if yrs else ""

    subject = f"Cooperation Inquiry: Ayonic & {company_name} in {dist}"

    body = f"""Hello Team of {company_name},

I recently came across your website and was particularly impressed by {detail_en}.{yrs_note_en}

We are currently launching Ayonic - a new platform that connects private individuals and businesses looking for professional home and office cleaning directly with the best local service providers. Since we are currently expanding our capacity in {dist}, your service would be an excellent fit for our platform.

The goal is simple: We bring you additional orders for residential or commercial cleaning services without you having to worry about acquisition or marketing.

Would you have time next week for a short, completely non-binding 5-minute phone call to see if this is of interest to you?

Best regards,
Manoj Uddagiri
Founder, Ayonic
Web: {AYONIC_URL}
Tel: {SENDER_PHONE}
Email: {SENDER_EMAIL}

---

Hallo Team von {company_name},

ich bin vor Kurzem auf Ihre Website gestossen und war besonders beeindruckt von {detail_de}.{yrs_note_de}

Wir starten gerade Ayonic - eine neue Plattform, die Privatpersonen und Unternehmen, die professionelle Haus- und Bueroreinigung suchen, direkt mit den besten lokalen Dienstleistern verbindet. Da wir derzeit unsere Kapazitaeten in {dist} ausbauen, wuerde Ihr Service hervorragend auf unsere Plattform passen.

Das Ziel ist einfach: Wir bringen Ihnen zusaetzliche Auftraege fuer Wohn- oder Gewerbereinigung, ohne dass Sie sich um Akquise oder Marketing kuemmern muessen.

Haetten Sie naechste Woche Zeit fuer ein kurzes, voellig unverbindliches 5-Minuten-Telefonat, um zu sehen, ob das fuer Sie interessant ist?

Mit freundlichen Gruessen,
Manoj Uddagiri
Gruender, Ayonic
Web: {AYONIC_URL}
Tel: {SENDER_PHONE}
Email: {SENDER_EMAIL}

--
If you do not wish to receive further emails, simply reply with "unsubscribe".
"""

    return subject, body


def _get_daily_counter_path() -> str:
    """Path to the daily email counter file."""
    import os
    return os.path.join(os.path.dirname(__file__), ".daily_email_count.json")


def _get_today_count() -> int:
    """Read how many emails were sent today."""
    import json, os
    from datetime import date
    path = _get_daily_counter_path()
    if not os.path.exists(path):
        return 0
    try:
        with open(path) as f:
            data = json.load(f)
        if data.get("date") == str(date.today()):
            return data.get("count", 0)
        return 0  # new day, reset
    except Exception:
        return 0


def _increment_daily_count(n: int = 1):
    """Add n to today's sent count."""
    import json
    from datetime import date
    path = _get_daily_counter_path()
    current = _get_today_count()
    with open(path, "w") as f:
        json.dump({"date": str(date.today()), "count": current + n}, f)


def _get_warmup_limit() -> int:
    """Calculate today's email limit based on warm-up schedule."""
    import json, os
    from datetime import date

    if not getattr(config, "WARMUP_ENABLED", False):
        return getattr(config, "DAILY_EMAIL_LIMIT", 400)

    warmup_file = os.path.join(os.path.dirname(__file__), ".warmup_start.json")

    # Get or set warm-up start date
    if os.path.exists(warmup_file):
        try:
            with open(warmup_file) as f:
                start_date = date.fromisoformat(json.load(f)["start"])
        except Exception:
            start_date = date.today()
            with open(warmup_file, "w") as f:
                json.dump({"start": str(start_date)}, f)
    else:
        start_date = date.today()
        with open(warmup_file, "w") as f:
            json.dump({"start": str(start_date)}, f)

    days_active = (date.today() - start_date).days + 1
    schedule = getattr(config, "WARMUP_SCHEDULE", {999: 400})

    for threshold in sorted(schedule.keys()):
        if days_active <= threshold:
            return schedule[threshold]

    return getattr(config, "DAILY_EMAIL_LIMIT", 400)


def send_personalized_emails(dry_run: bool = False, test_mode: bool = False):
    from sheets.sheets_client import get_all_leads, update_lead_status, log_email_sent

    # ── Daily limit check (warm-up aware) ─────────────────────────────────
    daily_limit = _get_warmup_limit()
    delay_secs  = getattr(config, "EMAIL_DELAY_SECONDS", 3)
    already_sent_today = _get_today_count()
    remaining = max(0, daily_limit - already_sent_today)

    leads = get_all_leads()
    pending = [
        (i + 2, l) for i, l in enumerate(leads)
        if str(l.get("Status", "")).strip() == "pending"
        and str(l.get("Email", "")).strip()
        and str(l.get("Website", "")).strip().startswith("http")
    ]

    mode = "(TEST)" if test_mode else "(DRY RUN)" if dry_run else ""
    print(f"\n{Fore.CYAN}▶ Personalized Email Sender {mode}{Style.RESET_ALL}")
    print(f"  {len(pending)} pending leads with email + website")
    print(f"  📊 Daily limit: {daily_limit} | Sent today: {already_sent_today} | Remaining: {remaining}")

    if remaining == 0 and not dry_run:
        print(f"\n{Fore.YELLOW}⚠ Daily limit of {daily_limit} reached! Try again tomorrow.{Style.RESET_ALL}\n")
        return

    # Cap batch to remaining daily quota
    if not dry_run and len(pending) > remaining:
        print(f"  ⚡ Will send {remaining} of {len(pending)} (daily limit)")
        pending = pending[:remaining]

    # ── Email verification step ───────────────────────────────────────────
    if pending and not dry_run:
        try:
            from tools.email_verifier import verify_email
            print(f"{Fore.CYAN}  🔍 Verifying email addresses...{Style.RESET_ALL}")
            verified_pending = []
            invalid_count = 0
            for row_idx, lead in pending:
                email = str(lead.get("Email", "")).strip()
                result = verify_email(email, timeout=5)
                if result["valid"]:
                    verified_pending.append((row_idx, lead))
                else:
                    invalid_count += 1
                    print(f"  {Fore.RED}✘ {email} — {result['reason']}{Style.RESET_ALL}")
                    update_lead_status(row_idx, "invalid-email", "")
            if invalid_count:
                print(f"  {Fore.YELLOW}⚠ {invalid_count} invalid emails removed from batch{Style.RESET_ALL}")
                try:
                    from tools.phone_notify import notify_verification_warning
                    notify_verification_warning(invalid_count, len(pending))
                except Exception:
                    pass
            pending = verified_pending
            print(f"  {Fore.GREEN}✔ {len(pending)} verified emails ready to send{Style.RESET_ALL}")
        except ImportError:
            pass  # email_verifier not installed — skip verification

    print()

    if not dry_run:
        server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT)
        server.starttls()
        server.login(config.GMAIL_USER, config.GMAIL_APP_PASSWORD)

    sent = failed = 0
    for idx, (row_idx, lead) in enumerate(pending):
        company  = str(lead.get("Company Name", "") or "")
        email    = str(lead.get("Email", "") or "")
        website  = str(lead.get("Website", "") or "")
        address  = str(lead.get("Address", "") or "")
        category = str(lead.get("Category", "") or "")

        progress = f"[{idx+1}/{len(pending)}]"
        print(f"{Fore.CYAN}{progress} 📧 {company[:42]:<42}{Style.RESET_ALL}")
        try:
            subject, body = build_personalized_email(company, website, address, category)
            if dry_run:
                print(f"  SUBJECT: {subject}")
                print(f"  PREVIEW: {body[:200]}...")
                continue

            recipients = TEST_EMAILS if test_mode else [email]
            for to_addr in recipients:
                import uuid
                from email.utils import formatdate, make_msgid

                # ── Anti-spam: Append unsubscribe footer if missing ──
                if "unsubscribe" not in body.lower():
                    body += "\n\n--\nIf you do not wish to receive further emails, simply reply with \"unsubscribe\".\n"

                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"]    = f"Manoj Uddagiri <{config.GMAIL_USER}>"
                msg["To"]      = to_addr
                msg["Reply-To"] = "info@ayonic.com"
                msg["Date"]    = formatdate(localtime=True)
                msg["Message-ID"] = make_msgid(domain="ayonic.com")

                # Keep headers clean — no bulk/marketing markers
                # (List-Unsubscribe and Precedence:bulk push to Promotions tab)

                msg.attach(MIMEText(body, "plain", "utf-8"))
                server.sendmail(config.GMAIL_USER, to_addr, msg.as_string())

            if not test_mode:
                update_lead_status(row_idx, "emailed", "")
                log_email_sent(company, email, subject)
                _increment_daily_count(1)

            remaining_now = daily_limit - _get_today_count()
            print(f"  {Fore.GREEN}✔ Sent → {', '.join(recipients)} | {remaining_now} left today{Style.RESET_ALL}")
            sent += 1

            # Phone notification for each send
            try:
                from tools.phone_notify import notify_email_sent
                notify_email_sent(company, email, remaining_now)
            except Exception:
                pass

            time.sleep(delay_secs)
        except Exception as e:
            print(f"  {Fore.RED}✘ Failed — {e}{Style.RESET_ALL}")
            failed += 1

    if not dry_run:
        server.quit()

    total_today = _get_today_count()
    print(f"\n{Fore.GREEN}✔ Done — {sent} sent, {failed} failed{Style.RESET_ALL}")
    print(f"{Fore.CYAN}📊 Total sent today: {total_today}/{daily_limit}{Style.RESET_ALL}\n")

    # Daily summary notification
    if sent > 0 and not dry_run:
        try:
            from tools.phone_notify import notify_daily_summary
            notify_daily_summary(sent, failed, replies=0)
        except Exception:
            pass

