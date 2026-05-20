import os
from dotenv import load_dotenv

load_dotenv()

# ── Search Settings ─────────────────────────────────────────────────────────
# 🧹 CLEANING ONLY — testing mode
# To re-enable other services, uncomment them below

KEYWORDS = [
    # ── Cleaning (EN + DE) ────────────────────────────────────────────
    "cleaning company", "cleaning service", "house cleaning",
    "office cleaning", "deep cleaning", "window cleaning",
    "carpet cleaning", "end of tenancy cleaning",
    "post construction cleaning", "upholstery cleaning", "ironing service",
    "Reinigungsfirma", "Gebäudereinigung", "Haushaltsreinigung",
    "Büroreinigung", "Reinigungsservice", "Fensterreinigung",
    "Teppichreinigung", "Grundreinigung", "Polsterreinigung",
    "Baureinigung", "Unterhaltsreinigung",

    # ── Plumbing (EN + DE) ────────────────────────────────────────────
    "plumber", "plumbing service", "drain cleaning",
    "pipe repair", "boiler repair", "bathroom installation",
    "water heater service",
    "Klempner", "Sanitär", "Rohrreinigung",
    "Rohrbruch", "Heizungsinstallation", "Badinstallation",

    # ── Electrical (EN + DE) ──────────────────────────────────────────
    "electrician", "electrical service", "wiring service",
    "lighting installation", "fuse box repair",
    "smart home installation", "EV charger installation",
    "Elektriker", "Elektroinstallation", "Elektroservice",
    "Beleuchtung Installation", "Sicherungskasten",

    # ── Handyman (EN + DE) ────────────────────────────────────────────
    "handyman", "furniture assembly", "wall mounting service",
    "painting service", "decorator", "tiling service",
    "flooring installation", "door repair", "lock repair",
    "Handwerker", "Möbelmontage", "Malerarbeiten",
    "Fliesenleger", "Bodenleger", "Türreparatur",

    # ── Home Services (EN + DE) ───────────────────────────────────────
    "locksmith", "pest control", "moving company",
    "garden service", "landscaping", "AC installation",
    "AC repair", "heating service", "appliance repair", "roofing service",
    "Schlüsseldienst", "Schädlingsbekämpfung", "Umzugsunternehmen",
    "Gartenpflege", "Klimaanlage", "Heizungswartung",
    "Haushaltsgeräte Reparatur", "Dachdecker",

    # ── Renovation & Interior (EN + DE) ──────────────────────────────
    "home renovation", "apartment renovation", "kitchen renovation",
    "bathroom renovation", "interior designer", "architect",
    "drywall installation", "plastering service",
    "Wohnungsrenovierung", "Küchenmontage", "Badsanierung",
    "Innenarchitekt", "Trockenbau", "Verputzer",

    # ── Kitchen & Bath Installation (EN + DE) ────────────────────────
    "kitchen installation", "kitchen fitter", "worktop installation",
    "bathroom fitter", "shower installation",
    "Kücheneinbau", "Küchenmonteur", "Arbeitsplatte Montage",
    "Badmontage", "Duschmontage",

    # ── Pool & Outdoor (EN + DE) ─────────────────────────────────────
    "pool cleaning", "pool maintenance", "swimming pool service",
    "garden landscaping", "tree service", "hedge trimming",
    "Poolreinigung", "Poolwartung", "Schwimmbadservice",
    "Gartengestaltung", "Baumfällung", "Heckenschnitt",

    # ── Solar & Energy (EN + DE) ─────────────────────────────────────
    "solar panel installation", "solar energy", "photovoltaic installer",
    "heat pump installation", "insulation service",
    "Solaranlage", "Photovoltaik", "Wärmepumpe Installation",
    "Dämmung", "Energieberater",

    # ── Security & Alarm (EN + DE) ───────────────────────────────────
    "home security", "alarm system installation", "CCTV installation",
    "security camera", "smart lock installation",
    "Alarmanlage", "Sicherheitstechnik", "Videoüberwachung",
    "Schließanlage",

    # ── Childcare & Elderly Care (EN + DE) ───────────────────────────
    "babysitter", "nanny service", "childcare at home",
    "elderly care", "senior care at home", "home care service",
    "Babysitter", "Kinderbetreuung", "Tagesmutter",
    "Seniorenbetreuung", "Altenpflege", "häusliche Pflege",

    # ── Delivery & Courier (EN + DE) ─────────────────────────────────
    "courier service", "same day delivery", "parcel delivery",
    "furniture delivery", "office relocation",
    "Kurierdienst", "Eilzustellung", "Möbeltransport",
    "Büroumzug",

    # ── IT & Tech Support (EN + DE) ──────────────────────────────────
    "IT support", "computer repair", "laptop repair",
    "network setup", "smart home setup", "WiFi installation",
    "PC Reparatur", "Computerservice", "Netzwerkinstallation",
    "WLAN Einrichtung",

    # ── Photography & Events (EN + DE) ───────────────────────────────
    "event photographer", "real estate photographer",
    "corporate photographer", "event planner", "wedding planner",
    "Fotograf", "Immobilienfotograf", "Eventplanung",
    "Hochzeitsplaner",

    # ── Catering & Food (EN + DE) ────────────────────────────────────
    "catering service", "private chef", "meal prep service",
    "office catering", "party catering",
    "Catering", "Partyservice", "Privatkoch",
    "Büro Catering", "Essenslieferung",

    # ── Tutoring & Education (EN + DE) ───────────────────────────────
    "private tutor", "math tutor", "language tutor",
    "music teacher at home", "yoga instructor",
    "Nachhilfe", "Privatlehrer", "Sprachunterricht",
    "Musiklehrer", "Yogalehrer",

    # ── Other Services (EN + DE) ──────────────────────────────────────
    "car wash service", "laundry service", "dry cleaning",
    "beauty service at home", "pet care", "dog walking",
    "personal trainer at home", "massage at home",
    "Autowäsche", "Wäscheservice", "Hundebetreuung",
    "Massage Zuhause", "Friseur Zuhause",
]


LOCATIONS = [
    "Berlin",
    "Berlin Mitte",
    "Berlin Charlottenburg",
]

# ── Schedule Settings ─────────────────────────────────────────────────────────
SCRAPE_INTERVAL_DAYS = 3       # Run scraper every 3 days
EMAIL_DELAY_DAYS     = 5       # Only email leads that are >= 5 days old
SCRAPE_HOUR          = 11      # Scraper runs at 11:00
EMAIL_CHECK_HOUR     = 13      # Email sender runs at 13:00

# ── Email Limits (Gmail safe) ─────────────────────────────────────────────────
DAILY_EMAIL_LIMIT    = 100     # Max 100 emails per send run (every 2 days)
EMAILS_PER_MINUTE    = 20      # Max 20 emails per minute
EMAIL_DELAY_SECONDS  = 3       # 60s / 20 = 3s between each email

# ── Warm-Up Protection (prevents Gmail block on new accounts) ────────────────
# Day 1-3: 20/day → Day 4-7: 50/day → Day 8-14: 100/day → Day 15+: 400/day
WARMUP_ENABLED       = True    # Set to False once account is warmed up
WARMUP_SCHEDULE = {
    3:  20,     # Days 1-3:  max 20 emails/day
    7:  50,     # Days 4-7:  max 50 emails/day
    14: 100,    # Days 8-14: max 100 emails/day
    21: 200,    # Days 15-21: max 200 emails/day
    999: 400,   # Day 22+:  full speed
}

# ── Contact Form Limits ──────────────────────────────────────────────────────
DAILY_FORM_LIMIT     = 15      # Max contact forms per day (10-15 is safe)

# ── Google Sheets ─────────────────────────────────────────────────────────────
GOOGLE_SHEET_ID          = os.getenv("GOOGLE_SHEET_ID", "")
GOOGLE_CREDENTIALS_FILE  = "credentials.json"   # Service account key file
LEADS_SHEET_NAME         = "Leads"
EMAIL_LOG_SHEET_NAME     = "Email Log"

# ── Google Maps Places API ────────────────────────────────────────────────────
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

# ── SerpAPI (optional alternative) ───────────────────────────────────────────
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")

# ── Gmail SMTP ────────────────────────────────────────────────────────────────
GMAIL_USER         = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
SMTP_HOST          = "smtp.gmail.com"
SMTP_PORT          = 587

# ── Instagram ─────────────────────────────────────────────────────────────────
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME", "")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD", "")
APIFY_TOKEN        = os.getenv("APIFY_TOKEN", "")

# ── Social Media APIs ─────────────────────────────────────────────────────────
# Facebook Pages API (get from developers.facebook.com)
FACEBOOK_ACCESS_TOKEN = os.getenv("FACEBOOK_ACCESS_TOKEN", "")

# RapidAPI key — covers LinkedIn, TikTok, Twitter/X scrapers
# Get free key at: rapidapi.com
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")

# YouTube Data API v3 (free, from Google Cloud — same project)
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

# Google Gemini API (free — AI-powered email writing)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Groq API (free — AI-powered email writing, no card needed)
GROQ_API_KEY  = os.getenv("GROQ_API_KEY", "")
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY", "")  # Free at deepl.com/pro-api

# ── Email Template ────────────────────────────────────────────────────────────
EMAIL_SUBJECT = "Partnership Opportunity — {company_name}"

EMAIL_BODY = """\
Hi {company_name} team,

I came across your {category} business and I'm impressed with what you offer.

I'd love to explore how we can work together to help grow your customer base 
and streamline your operations.

Would you be open to a quick 15-minute call this week?

Looking forward to hearing from you.

Best regards,
{sender_name}
{sender_email}
"""

SENDER_NAME    = "Manoj"                    # ← Your full name
SENDER_COMPANY = "Ayonic"                   # ← Platform name
SENDER_PHONE   = ""                         # ← Your phone (optional)
AYONIC_LINK    = "https://ayonic.com"       # ← Your platform link
EMAIL_LANGUAGE = "both"                    # ← "en" = English only, "de" = German only, "both" = bilingual

# ── Scraper Settings ──────────────────────────────────────────────────────────
REQUEST_DELAY_SECONDS  = 0.5  # Pause between web requests
MAX_RESULTS_PER_QUERY  = 20   # Max companies per keyword+location combo
