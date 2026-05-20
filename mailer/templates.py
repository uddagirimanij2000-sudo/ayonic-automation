"""
mailer/templates.py
Category-specific email templates for Ayonic lead outreach.

CLEANING companies get the Ayonic-branded bilingual template
with AI-injected personalization from the scraped website.

All other categories use the default partnership template.

Variables available in templates:
  {company_name}  - Company name
  {city}          - City/location
  {contact_name}  - Contact name or "Team of [company]"
  {ai_detail}     - AI-injected detail from website (EN)
  {ai_detail_de}  - AI-injected detail from website (DE)
  {sender_name}   - Your full name
  {sender_email}  - Your Gmail
  {ayonic_link}   - Your platform URL
"""

from __future__ import annotations
import config

# ── AI Detail Injection ───────────────────────────────────────────────────────

# Fallback details when no website description is available
_CLEANING_DETAILS_EN = [
    "your professional approach to home and office cleaning",
    "your reliable and flexible cleaning service",
    "your commitment to high-quality cleaning results",
    "your focus on client satisfaction in every clean",
    "your experienced team and attention to detail",
]

_CLEANING_DETAILS_DE = [
    "Ihren professionellen Ansatz bei der Haus- und Büroreinigung",
    "Ihren zuverlässigen und flexiblen Reinigungsservice",
    "Ihr Engagement für hochwertige Reinigungsergebnisse",
    "Ihren Fokus auf Kundenzufriedenheit bei jeder Reinigung",
    "Ihr erfahrenes Team und Ihre Liebe zum Detail",
]


def _extract_ai_detail(description: str, language: str = "en") -> str:
    """
    Generate a personalized detail from the website description.
    Falls back to a sensible default if description is empty.
    """
    if not description or len(description.strip()) < 20:
        # Use a good default
        if language == "de":
            return _CLEANING_DETAILS_DE[0]
        return _CLEANING_DETAILS_EN[0]

    desc = description.strip()

    # Try to extract the most meaningful phrase from description
    # Priority keywords to highlight
    en_highlights = {
        "eco": "your focus on eco-friendly and sustainable cleaning products",
        "environment": "your commitment to environmentally friendly cleaning",
        "green": "your use of green and non-toxic cleaning products",
        "office": "your reliable service for office and commercial buildings",
        "residential": "your professional residential cleaning service",
        "flexible": "your flexibility and customised cleaning schedules",
        "reliable": "your reputation for reliable and consistent service",
        "professional": "your professional and experienced cleaning team",
        "family": "your family-run approach and personalised service",
        "guarantee": "your satisfaction guarantee on every clean",
        "fast": "your quick and efficient cleaning service",
        "deep": "your thorough deep cleaning capabilities",
        "commercial": "your commercial cleaning expertise",
        "domestic": "your domestic cleaning service for homes and families",
    }

    de_highlights = {
        "öko": "Ihren Fokus auf umweltfreundliche Reinigungsmittel",
        "umwelt": "Ihr Engagement für umweltfreundliche Reinigung",
        "büro": "Ihren zuverlässigen Service für Bürogebäude",
        "gewerbe": "Ihre Expertise in der Gewerbereinigung",
        "flexibel": "Ihre Flexibilität bei der Unterhaltsreinigung",
        "zuverlässig": "Ihren zuverlässigen und pünktlichen Service",
        "professionell": "Ihr professionelles und erfahrenes Reinigungsteam",
        "familien": "Ihren familiären Ansatz und persönlichen Service",
        "tief": "Ihre gründliche Tiefenreinigung",
        "schnell": "Ihren schnellen und effizienten Reinigungsservice",
        "hauswirtschaft": "Ihren Haushaltsreinigungsservice",
    }

    highlights = de_highlights if language == "de" else en_highlights
    desc_lower = desc.lower()

    for keyword, phrase in highlights.items():
        if keyword in desc_lower:
            return phrase

    # Generic fallback using description snippet
    snippet = desc[:80].rstrip(",. ") if len(desc) > 30 else desc
    if language == "de":
        return f"Ihren Service – besonders: \"{snippet}\""
    return f"your service – specifically: \"{snippet}\""


# ── Cleaning Template (Ayonic) — English ─────────────────────────────────────

CLEANING_EN = {
    "subject": "Kurze Frage – {company_name}",
    "body": """\
Hello {contact_name},

I recently came across your website and was particularly impressed by {ai_detail}.

We are currently launching Ayonic – a new platform that connects private individuals \
and businesses looking for professional home and office cleaning directly with the best \
local service providers. Since we are currently expanding our capacity in {city}, your \
service would be an excellent fit for our platform.

The goal is simple: We bring you additional orders for residential or commercial \
cleaning services without you having to worry about acquisition or marketing.

Would you have time next week for a short, completely non-binding 5-minute phone call?

Best regards,
Team Ayonic
info@ayonic.com
{ayonic_link}
""",
}

# ── Cleaning Template (Ayonic) — German ──────────────────────────────────────

CLEANING_DE = {
    "subject": "Kurze Anfrage – {company_name}",
    "body": """\
Hallo {contact_name},

ich bin gerade auf Ihre Webseite gestoßen und mir ist besonders {ai_detail_de} \
positiv aufgefallen.

Wir starten aktuell mit Ayonic – einer neuen Plattform, die Privatkunden und Unternehmen \
auf der Suche nach professioneller Haus- und Büroreinigung direkt mit den besten lokalen \
Dienstleistern verbindet. Da wir in {city} gerade unsere Kapazitäten ausbauen, würden \
Sie mit Ihrem Service hervorragend auf unsere Plattform passen.

Das Ziel ist simpel: Wir bringen Ihnen zusätzliche Aufträge für Haushalts- oder \
Gewerbereinigungen, ohne dass Sie sich um die Akquise oder das Marketing kümmern müssen.

Hätten Sie nächste Woche Zeit für ein kurzes, völlig unverbindliches 5-Minuten-Telefonat?

Mit freundlichen Grüßen,
Team Ayonic
info@ayonic.com
{ayonic_link}
""",
}

# ── Cleaning Template — Both Languages (DE first, EN below) ──────────────────

CLEANING_BOTH = {
    "subject": "Kurze Frage zu {company_name}",
    "body": """\
Hallo {contact_name},

ich bin gerade auf Ihre Webseite gestoßen und mir ist besonders {ai_detail_de} positiv aufgefallen.

Wir starten aktuell mit Ayonic – einer neuen Plattform, die Privatkunden und Unternehmen auf der Suche nach professioneller Haus- und Bueroreinigung direkt mit den besten lokalen Dienstleistern verbindet. Da wir in {city} gerade unsere Kapazitaeten ausbauen, wuerden Sie mit Ihrem Service hervorragend auf unsere Plattform passen.

Das Ziel ist simpel: Wir bringen Ihnen zusaetzliche Auftraege fuer Haushalts- oder Gewerbereinigungen, ohne dass Sie sich um die Akquise oder das Marketing kuemmern muessen.

Haetten Sie naechste Woche Zeit fuer ein kurzes, voellig unverbindliches 5-Minuten-Telefonat?

Mit freundlichen Gruessen,
Team Ayonic
info@ayonic.com
{ayonic_link}

---

Hello {contact_name},

I recently came across your website and was particularly impressed by {ai_detail}.

We are currently launching Ayonic – a new platform that connects private individuals and businesses looking for professional home and office cleaning directly with the best local service providers. Since we are currently expanding our capacity in {city}, your service would be an excellent fit for our platform.

The goal is simple: We bring you additional orders for residential or commercial cleaning services without you having to worry about acquisition or marketing.

Would you have time next week for a short, completely non-binding 5-minute phone call?

Best regards,
Team Ayonic
info@ayonic.com
{ayonic_link}
""",
}

# ── Other Category Templates (non-cleaning) ───────────────────────────────────

TEMPLATES = {
    "plumber": {
        "subject": "Kurze Frage – {company_name}",
        "body": """\
Hi {contact_name},

I came across your plumbing business and was impressed by your service.

I work with local businesses to help them attract more clients through targeted \
outreach — and I'd love to see if we'd be a good fit.

Would you be open to a quick 15-minute call this week?

Best regards,
Team Ayonic
info@ayonic.com
{ayonic_link}
""",
    },

    "electrician": {
        "subject": "Mehr Auftraege fuer {company_name}",
        "body": """\
Hi {contact_name},

I found your electrical services business and was really impressed by your expertise.

I help electricians get in front of homeowners actively searching for electrical work.

Would you be open to a quick 15-minute chat this week?

Best regards,
Team Ayonic
info@ayonic.com
{ayonic_link}
""",
    },

    "painter": {
        "subject": "Mehr Auftraege fuer {company_name}",
        "body": """\
Hi {contact_name},

I came across your painting business and love the quality of your work.

I help painting contractors fill their schedules with consistent, high-value projects.

Would you have 15 minutes this week to explore what this could look like?

Best regards,
Team Ayonic
info@ayonic.com
{ayonic_link}
""",
    },
}

# ── Cleaning categories (all map to Ayonic template) ─────────────────────────

CLEANING_KEYWORDS = {
    "cleaner", "cleaning", "cleaning company", "cleaning service",
    "reinigung", "reinigungsservice", "haushalt", "hausreinigung",
    "office cleaning", "domestic cleaning", "commercial cleaning",
    "post construction cleaning", "construction cleaning", "baureinigung",
    "maid", "housekeeping", "janitor", "janitorial", "gebaeudeservice", "gebaudeservice",
}

# ── Default fallback ──────────────────────────────────────────────────────────

DEFAULT_SUBJECT = "Kurze Frage zu {company_name}"
DEFAULT_BODY = """Hallo {contact_name},

ich bin auf {company_name} gestossen und war beeindruckt von {ai_detail_de}.

Ayonic ist eine Plattform, die Kunden direkt mit den besten lokalen Dienstleistern in {city} verbindet. Kunden buchen geprueft Experten, verfolgen Termine und erhalten sofortige Preisangebote – alles an einem Ort.

Wir expandieren gerade in {city} und suchen zuverlaessige Servicepartner. Mit Ayonic erhalten Sie direkte Auftragsanfragen von Kunden in Ihrer Region, ohne zusaetzlichen Aufwand Ihrerseits.

So funktioniert die Zusammenarbeit mit Ayonic:

- Direkte Buchungsanfragen von Kunden in Ihrer Naehe
- Kein Aufwand fuer Werbung oder Marketing
- Volle Kontrolle ueber Ihren Zeitplan und Ihre Verfuegbarkeit

{company_name} waere eine hervorragende Ergaenzung fuer unsere Plattform.

Haetten Sie diese Woche Zeit fuer ein kurzes 5-Minuten-Gespraech?

Mit freundlichen Gruessen,
Team Ayonic
info@ayonic.com
{ayonic_link}

---

Hello {contact_name},

I came across {company_name} and was genuinely impressed by {ai_detail}.

Ayonic is an on-demand service booking platform that connects customers directly with trusted local professionals in {city}. Customers book verified experts, track appointments, and get instant quotes — all in one place.

We are currently expanding in {city} and looking for reliable service partners. Joining our platform means you receive direct job requests from clients in your area, without any extra work on your end.

Here is what working with Ayonic looks like:

- Direct booking requests from clients in your area
- No need to manage advertising or promotions
- Full control over your schedule and availability

Your business would be a great fit for Ayonic, and we would love to feature {company_name} on our platform.

Would you be open for a quick 5-minute call this week to explore this?

Best regards,
Team Ayonic
info@ayonic.com
{ayonic_link}
"""


# ── Main functions ────────────────────────────────────────────────────────────

def _is_cleaning(category: str) -> bool:
    """Check if this is a cleaning category."""
    cat = category.lower().strip()
    for kw in CLEANING_KEYWORDS:
        if kw in cat or cat in kw:
            return True
    return False


def _get_cleaning_template() -> dict:
    """Return the right cleaning template based on EMAIL_LANGUAGE config."""
    lang = getattr(config, "EMAIL_LANGUAGE", "en").lower()
    if lang == "de":
        return CLEANING_DE
    elif lang == "both":
        return CLEANING_BOTH
    return CLEANING_EN


def render_email(company_name: str, category: str, sender_name: str,
                 sender_email: str, city: str = "", description: str = "",
                 contact_name: str = "",
                 ai_detail_de: str = "", ai_detail_en: str = "") -> tuple:
    """
    Render subject and body for a company.

    Args:
        company_name  - e.g. "Lisboa Clean"
        category      - e.g. "cleaner"
        sender_name   - your name
        sender_email  - your email
        city          - company location, e.g. "Lisbon"
        description   - scraped website description for AI inject
        contact_name  - specific contact name if known

    Returns:
        (subject, body) tuple — fully rendered, no placeholders left
    """
    # Resolve contact name — use company name directly, not "Team of X"
    if not contact_name:
        contact_name = company_name

    # Resolve city
    if not city:
        city = "your area"

    # AI-injected detail from website (use Groq translation if provided, else keyword-match)
    ai_detail_en = ai_detail_en if ai_detail_en else _extract_ai_detail(description, language="en")
    ai_detail_de = ai_detail_de if ai_detail_de else _extract_ai_detail(description, language="de")

    # Ayonic link
    ayonic_link = getattr(config, "AYONIC_LINK", "https://ayonic.com")

    ctx = {
        "company_name":  company_name,
        "category":      category,
        "city":          city,
        "contact_name":  contact_name,
        "ai_detail":     ai_detail_en,
        "ai_detail_de":  ai_detail_de,
        "sender_name":   sender_name,
        "sender_email":  sender_email,
        "ayonic_link":   ayonic_link,
    }

    # Choose template
    if _is_cleaning(category):
        template = _get_cleaning_template()
    else:
        # Non-cleaning: use category-specific or default
        cat_lower = category.lower().strip()
        template = TEMPLATES.get(cat_lower)

        if not template:
            # Fuzzy match
            for key, tmpl in TEMPLATES.items():
                if key in cat_lower or cat_lower in key:
                    template = tmpl
                    break

        if not template:
            template = {"subject": DEFAULT_SUBJECT, "body": DEFAULT_BODY}

    subject = template["subject"].format(**ctx)
    body    = template["body"].format(**ctx)
    return subject, body


def get_template(category: str) -> dict:
    """Return the raw template dict for a given category."""
    if _is_cleaning(category):
        return _get_cleaning_template()
    cat = category.lower().strip()
    return TEMPLATES.get(cat, {"subject": DEFAULT_SUBJECT, "body": DEFAULT_BODY})
