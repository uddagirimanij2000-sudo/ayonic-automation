from __future__ import annotations
"""
sheets/sheets_client.py
Read and write complete company profiles to Google Sheets.
Every field collected by all scrapers is stored — A to Z, no duplicates.
"""

import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from colorama import Fore, Style
import config

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ── Complete column headers — ALL company information ─────────────────────────
LEADS_HEADERS = [
    # Identity
    "Company Name",
    "Category",
    "Location",

    # Contact
    "Phone",
    "Email",
    "Website",
    "Address",

    # Social Media
    "Instagram",
    "Facebook",
    "LinkedIn",
    "TikTok",
    "Twitter/X",
    "YouTube",

    # Discovery
    "Source",
    "Social Profile URL",
    "Description",

    # Tracking
    "Date Found",
    "Days Since Found",
    "Email Send Date",
    "Status",
    "Notes",
]

EMAIL_LOG_HEADERS = [
    "Company Name", "Email", "Category", "Source",
    "Sent Date", "Template Used", "Reply Received", "Notes",
]

# Map company dict keys → sheet column names
FIELD_MAP = {
    "name":        "Company Name",
    "category":    "Category",
    "location":    "Location",
    "phone":       "Phone",
    "email":       "Email",
    "website":     "Website",
    "address":     "Address",
    "instagram":   "Instagram",
    "facebook":    "Facebook",
    "linkedin":    "LinkedIn",
    "tiktok":      "TikTok",
    "twitter":     "Twitter/X",
    "youtube":     "YouTube",
    "source":      "Source",
    "social_url":  "Social Profile URL",
    "description": "Description",
}


# ── Auth & Caching ────────────────────────────────────────────────────────────

_cached_client = None
_cached_spreadsheet = None
_cached_leads_ws = None
_cached_email_log_ws = None
_cached_leads_headers = None

def _get_client():
    global _cached_client
    if _cached_client is None:
        creds = Credentials.from_service_account_file(
            config.GOOGLE_CREDENTIALS_FILE, scopes=SCOPES
        )
        _cached_client = gspread.authorize(creds)
    return _cached_client


def _get_spreadsheet():
    global _cached_spreadsheet
    if _cached_spreadsheet is None:
        _cached_spreadsheet = _get_client().open_by_key(config.GOOGLE_SHEET_ID)
    return _cached_spreadsheet


def _get_leads_ws():
    global _cached_leads_ws
    if _cached_leads_ws is None:
        _cached_leads_ws = _get_spreadsheet().worksheet(config.LEADS_SHEET_NAME)
    return _cached_leads_ws


def _get_email_log_ws():
    global _cached_email_log_ws
    if _cached_email_log_ws is None:
        _cached_email_log_ws = _get_spreadsheet().worksheet(config.EMAIL_LOG_SHEET_NAME)
    return _cached_email_log_ws


def _get_leads_headers():
    global _cached_leads_headers
    if _cached_leads_headers is None:
        _cached_leads_headers = _get_leads_ws().row_values(1)
    return _cached_leads_headers


# ── Sheet setup ───────────────────────────────────────────────────────────────

def ensure_sheets_exist():
    """Create the Leads and Email Log tabs if they don't exist."""
    spreadsheet = _get_spreadsheet()
    existing = [ws.title for ws in spreadsheet.worksheets()]

    if config.LEADS_SHEET_NAME not in existing:
        ws = spreadsheet.add_worksheet(
            title=config.LEADS_SHEET_NAME, rows=5000, cols=len(LEADS_HEADERS) + 2
        )
        ws.append_row(LEADS_HEADERS)
        _format_header(ws)
        print(f"{Fore.GREEN}✔ Created '{config.LEADS_SHEET_NAME}' tab with {len(LEADS_HEADERS)} columns{Style.RESET_ALL}")
    else:
        # Ensure all columns exist (migration for existing sheets)
        _ensure_columns(spreadsheet.worksheet(config.LEADS_SHEET_NAME))

    if config.EMAIL_LOG_SHEET_NAME not in existing:
        ws = spreadsheet.add_worksheet(
            title=config.EMAIL_LOG_SHEET_NAME, rows=5000, cols=10
        )
        ws.append_row(EMAIL_LOG_HEADERS)
        _format_header(ws)
        print(f"{Fore.GREEN}✔ Created '{config.EMAIL_LOG_SHEET_NAME}' tab{Style.RESET_ALL}")


def _format_header(ws):
    """Bold and freeze the header row."""
    try:
        ws.format("1:1", {"textFormat": {"bold": True}})
        ws.freeze(rows=1)
    except Exception:
        pass


def _ensure_columns(ws):
    """Add any missing columns to an existing sheet (migration)."""
    existing_headers = ws.row_values(1)
    missing = [h for h in LEADS_HEADERS if h not in existing_headers]
    if not missing:
        return

    # Resize sheet if needed to fit all columns
    needed_cols = len(LEADS_HEADERS) + 2
    try:
        ws.resize(rows=5000, cols=needed_cols)
    except Exception:
        pass

    for col_name in missing:
        col_idx = len(existing_headers) + 1
        ws.update_cell(1, col_idx, col_name)
        existing_headers.append(col_name)
        print(f"{Fore.CYAN}  Added column: {col_name}{Style.RESET_ALL}")


def clear_sheet(which: str = "leads"):
    """
    Clear all data rows from the sheet (keeps the header row intact).

    Args:
        which: "leads"    → clear only the Leads tab
               "log"      → clear only the Email Log tab
               "all"      → clear both tabs
    """
    spreadsheet = _get_spreadsheet()

    def _clear_tab(sheet_name, headers):
        try:
            ws = spreadsheet.worksheet(sheet_name)
            # Get current row count
            all_rows = ws.get_all_values()
            if len(all_rows) <= 1:
                print(f"{Fore.YELLOW}  '{sheet_name}' is already empty.{Style.RESET_ALL}")
                return 0
            data_rows = len(all_rows) - 1  # exclude header

            # Clear everything then restore header
            ws.clear()
            ws.append_row(headers)
            _format_header(ws)

            print(f"{Fore.GREEN}  ✔ '{sheet_name}' cleared — {data_rows} rows removed.{Style.RESET_ALL}")
            return data_rows
        except gspread.exceptions.WorksheetNotFound:
            print(f"{Fore.RED}  ✘ Tab '{sheet_name}' not found.{Style.RESET_ALL}")
            return 0

    total = 0
    if which in ("leads", "all"):
        total += _clear_tab(config.LEADS_SHEET_NAME, LEADS_HEADERS)
    if which in ("log", "all"):
        total += _clear_tab(config.EMAIL_LOG_SHEET_NAME, EMAIL_LOG_HEADERS)

    return total



def get_all_leads() -> list[dict]:
    """Return all rows from the Leads sheet as list of dicts."""
    ws = _get_leads_ws()
    return ws.get_all_records()


# ── Write ─────────────────────────────────────────────────────────────────────

def _build_row(company: dict, headers: list, existing_leads: list = None) -> list | None:
    """
    Build a sheet row for a company. Returns the row list if new, None if duplicate.
    Pure logic — makes NO API calls (dedup is done against the in-memory cache).
    """
    from scrapers.deduplicator import get_fingerprint, is_duplicate

    name = company.get("name", "").strip()
    if not name:
        return None

    # Dedup check against in-memory cache (no API call)
    leads_to_check = existing_leads or []
    new_fp = get_fingerprint(company)
    for lead in leads_to_check:
        existing_fp = get_fingerprint({
            "name":      str(lead.get("Company Name", "") or ""),
            "phone":     str(lead.get("Phone", "") or ""),
            "website":   str(lead.get("Website", "") or ""),
            "instagram": str(lead.get("Instagram", "") or ""),
        })
        if is_duplicate(new_fp, existing_fp):
            return None

    today = datetime.now().strftime("%Y-%m-%d")
    status = "pending" if company.get("email") else "no email"

    data = {
        "Company Name":     name,
        "Category":         company.get("category", ""),
        "Location":         company.get("location", ""),
        "Phone":            company.get("phone", ""),
        "Email":            company.get("email", ""),
        "Website":          company.get("website", ""),
        "Address":          company.get("address", ""),
        "Instagram":        company.get("instagram", ""),
        "Facebook":         company.get("facebook", ""),
        "LinkedIn":         company.get("linkedin", ""),
        "TikTok":           company.get("tiktok", ""),
        "Twitter/X":        company.get("twitter", ""),
        "YouTube":          company.get("youtube", ""),
        "Source":           company.get("source", ""),
        "Social Profile URL": company.get("social_url", ""),
        "Description":      (company.get("description", "") or "")[:200],
        "Date Found":       today,
        "Days Since Found": 0,
        "Email Send Date":  "",
        "Status":           status,
        "Notes":            "",
    }
    return [data.get(h, "") for h in headers]


def add_leads_batch(companies: list, existing_leads: list = None) -> int:
    """
    Write all new companies to the sheet in ONE append_rows() call.
    This avoids 429 write quota errors that happen with per-row writes.
    Returns the number of companies added.
    """
    if not companies:
        return 0

    ws = _get_leads_ws()
    headers = _get_leads_headers()

    rows = []
    added_names = []
    for company in companies:
        row = _build_row(company, headers, existing_leads)
        if row is not None:
            rows.append(row)
            added_names.append(company.get("name", "").strip())
            # Print what we're adding
            has_email  = "✉" if company.get("email") else " "
            has_phone  = "📞" if company.get("phone") else " "
            has_social = "📱" if any(company.get(s) for s in ["instagram","facebook","linkedin","tiktok","twitter","youtube"]) else " "
            name = company.get("name", "").strip()
            print(f"{Fore.GREEN}✔ Added: {name:<35} {has_email} {has_phone} {has_social} [{company.get('source','')}]{Style.RESET_ALL}")

    if rows:
        ws.append_rows(rows, value_input_option="USER_ENTERED")

    return len(rows)


def add_lead(company: dict, existing_leads: list = None,
             ws=None, headers: list = None) -> bool:
    """
    Add a single company. Use add_leads_batch() for batch inserts.
    Returns True if added, False if duplicate.
    """
    row = _build_row(company, headers or [], existing_leads)
    if row is None:
        return False

    if ws is None or headers is None:
        ws = _get_leads_ws()
        headers = _get_leads_headers()
        row = _build_row(company, headers, existing_leads)
        if row is None:
            return False

    ws.append_row(row)
    name = company.get("name", "").strip()
    has_email  = "✉" if company.get("email") else " "
    has_phone  = "📞" if company.get("phone") else " "
    has_social = "📱" if any(company.get(s) for s in ["instagram","facebook","linkedin","tiktok","twitter","youtube"]) else " "
    print(f"{Fore.GREEN}✔ Added: {name:<35} {has_email} {has_phone} {has_social} [{company.get('source','')}]{Style.RESET_ALL}")
    return True


# ── Update ────────────────────────────────────────────────────────────────────

def update_lead_status(row_index: int, status: str, email_send_date: str = None, days_old: int = None):
    """Update Status, Email Send Date, and Days Since Found for a lead."""
    ws = _get_leads_ws()
    headers = _get_leads_headers()

    if status == "emailed" and not email_send_date:
        email_send_date = datetime.now().strftime("%Y-%m-%d")

    def col(name):
        try:
            return headers.index(name) + 1
        except ValueError:
            return None

    updates = [
        ("Status", status),
    ]
    if email_send_date:
        updates.append(("Email Send Date", email_send_date))
    if days_old is not None:
        updates.append(("Days Since Found", days_old))

    cells_to_update = []
    for col_name, value in updates:
        c = col(col_name)
        if c is not None:
            cells_to_update.append(gspread.cell.Cell(row=row_index, col=c, value=value))

    if cells_to_update:
        ws.update_cells(cells_to_update, value_input_option='USER_ENTERED')


def update_lead_field(row_index: int, field: str, value: str):
    """Update any single field for a lead row."""
    ws = _get_leads_ws()
    headers = _get_leads_headers()
    try:
        col = headers.index(field) + 1
        ws.update_cell(row_index, col, value)
    except ValueError:
        pass


# ── Email helpers ─────────────────────────────────────────────────────────────

def get_leads_ready_to_email(delay_days: int = None) -> list[dict]:
    """
    Return leads where:
    - Status = 'pending'
    - Email is not empty
    - Date Found >= delay_days ago
    """
    if delay_days is None:
        delay_days = config.EMAIL_DELAY_DAYS

    spreadsheet = _get_spreadsheet()
    ws = spreadsheet.worksheet(config.LEADS_SHEET_NAME)
    all_rows = ws.get_all_records()
    today = datetime.now().date()
    ready = []

    # --- Berlin-only filter ---
    # A lead is accepted if ANY of these are true:
    #   1. Email domain ends in .de or .berlin
    #   2. Company name contains 'berlin'
    #   3. Description contains 'berlin'
    #   4. Company name contains a German legal entity type (GmbH, UG, AG, KG, e.K.)
    # A lead is REJECTED if company name contains a known non-German city

    NON_GERMAN_CITIES = [
        'kolkata', 'mumbai', 'delhi', 'india', 'dubai', 'abu dhabi', 'uae',
        'london', 'los angeles', 'new york', 'nyc', 'toronto', 'sydney',
        'singapore', 'paris', 'moscow', 'russia', 'ukraine', 'crimea',
    ]

    GERMAN_ENTITY_TYPES = ['gmbh', ' ug ', ' ag ', ' kg ', 'e.k.', 'ohg', 'gbr', 'e.v.']

    for idx, row in enumerate(all_rows, start=2):
        status         = str(row.get("Status", "")).strip().lower()
        email          = str(row.get("Email", "")).strip().rstrip('.')
        date_found_str = str(row.get("Date Found", "")).strip()
        company_name   = str(row.get("Company Name", "")).strip().lower()
        description    = str(row.get("Description", "")).strip().lower()

        if status != "pending" or not email:
            continue

        # Hard reject: obvious non-German city in name
        if any(city in company_name for city in NON_GERMAN_CITIES):
            continue

        # Extract email domain
        domain = email.split('@')[-1].lower() if '@' in email else ''

        # Accept if Berlin/German
        is_de_domain      = domain.endswith('.de') or domain.endswith('.berlin')
        has_berlin        = 'berlin' in company_name or 'berlin' in description
        is_german_entity  = any(t in company_name for t in GERMAN_ENTITY_TYPES)

        if not (is_de_domain or has_berlin or is_german_entity):
            continue  # Skip — not a Berlin/German lead

        try:
            date_found = datetime.strptime(date_found_str, "%Y-%m-%d").date()
            days_old = (today - date_found).days
        except ValueError:
            continue

        if days_old >= delay_days:
            ready.append({"row_index": idx, "days_old": days_old, **row})

    return ready


def log_email_sent(company_name: str, email: str, category: str,
                   source: str = "", template: str = "default"):
    """Append a row to the Email Log sheet."""
    ws = _get_email_log_ws()
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    ws.append_row([company_name, email, category, source, today, template, "", ""])


# ── Stats ─────────────────────────────────────────────────────────────────────

def get_stats() -> dict:
    """Return summary stats of leads by status."""
    leads = get_all_leads()
    stats = {
        "total":    len(leads),
        "pending":  0,
        "emailed":  0,
        "no_email": 0,
        "with_phone":    sum(1 for l in leads if l.get("Phone")),
        "with_address":  sum(1 for l in leads if l.get("Address")),
        "with_instagram":sum(1 for l in leads if l.get("Instagram")),
        "with_facebook": sum(1 for l in leads if l.get("Facebook")),
        "with_linkedin": sum(1 for l in leads if l.get("LinkedIn")),
    }
    for lead in leads:
        s = str(lead.get("Status", "")).strip().lower()
        if s == "pending":
            stats["pending"] += 1
        elif s in ["emailed", "follow-up-1", "follow-up-2", "no-reply", "replied", "unsubscribed"]:
            stats["emailed"] += 1
        elif s == "no email":
            stats["no_email"] += 1
    return stats
