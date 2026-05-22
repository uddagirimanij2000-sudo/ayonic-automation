"""
sheets/excel_client.py

Microsoft Graph API client for SharePoint Excel.
Replaces sheets/sheets_client.py — same public API, different backend.

Setup:
  Add to .env:
    MICROSOFT_CLIENT_ID=01116eb2-4fe1-4ff9-87ce-9965d9251314
    MICROSOFT_TENANT_ID=98b4974a-3b6d-45ac-a4fa-480b9d01b60c
    MICROSOFT_CLIENT_SECRET=5c88Q~5ePSAf3HrBsYds_lBUbyr3SgI.6eas.bjB
    SHAREPOINT_USER_EMAIL=Manoj.uddagiri@kyaani.com
    EXCEL_FILE_NAME=Lead Automation1
"""

import os
import sys
import time
from datetime import datetime, timedelta
from typing import Optional

import requests
from colorama import Fore, Style

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

# ── Column headers (must match Excel file exactly) ─────────────────────────────
LEADS_HEADERS = [
    "Company Name", "Category", "Location", "Phone", "Email",
    "Website", "Address", "Instagram", "Facebook", "LinkedIn",
    "TikTok", "Twitter/X", "YouTube", "Source", "Social Profile URL",
    "Description", "Date Found", "Days Since Found",
    "Email Send Date", "Status", "Notes",
]

TEST_HEADERS = ["name", "email", "description"]

# ── Auth ───────────────────────────────────────────────────────────────────────
_token_cache: dict = {}


def _get_access_token() -> str:
    """Get Microsoft Graph access token using client credentials."""
    now = time.time()
    if _token_cache.get("expires_at", 0) > now + 60:
        return _token_cache["token"]

    tenant_id     = config.MICROSOFT_TENANT_ID
    client_id     = config.MICROSOFT_CLIENT_ID
    client_secret = config.MICROSOFT_CLIENT_SECRET

    url  = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    data = {
        "grant_type":    "client_credentials",
        "client_id":     client_id,
        "client_secret": client_secret,
        "scope":         "https://graph.microsoft.com/.default",
    }
    resp = requests.post(url, data=data, timeout=15)
    resp.raise_for_status()
    result = resp.json()
    _token_cache["token"]      = result["access_token"]
    _token_cache["expires_at"] = now + result.get("expires_in", 3600)
    return _token_cache["token"]


def _headers() -> dict:
    return {"Authorization": f"Bearer {_get_access_token()}", "Content-Type": "application/json"}


# ── File discovery ─────────────────────────────────────────────────────────────
_file_item_id_cache: Optional[str] = None


def _get_file_item_id() -> str:
    """Find the Excel file in the user's OneDrive by name."""
    global _file_item_id_cache
    if _file_item_id_cache:
        return _file_item_id_cache

    user_email = config.SHAREPOINT_USER_EMAIL
    file_name  = config.EXCEL_FILE_NAME  # "Lead Automation1"

    # Search in user's OneDrive
    url  = f"https://graph.microsoft.com/v1.0/users/{user_email}/drive/root/search(q='{file_name}')"
    resp = requests.get(url, headers=_headers(), timeout=15)
    resp.raise_for_status()
    items = resp.json().get("value", [])

    for item in items:
        if file_name.lower() in item.get("name", "").lower() and item["name"].endswith((".xlsx", ".xlsm")):
            _file_item_id_cache = item["id"]
            print(f"  📊 Found Excel file: {item['name']} (id: {item['id'][:8]}...)")
            return _file_item_id_cache

    # Fallback: try by name directly
    url  = f"https://graph.microsoft.com/v1.0/users/{user_email}/drive/root:/{file_name}.xlsx"
    resp = requests.get(url, headers=_headers(), timeout=15)
    if resp.status_code == 200:
        _file_item_id_cache = resp.json()["id"]
        return _file_item_id_cache

    raise FileNotFoundError(f"Excel file '{file_name}' not found in OneDrive for {user_email}")


def _workbook_url(path: str = "") -> str:
    user_email = config.SHAREPOINT_USER_EMAIL
    item_id    = _get_file_item_id()
    return f"https://graph.microsoft.com/v1.0/users/{user_email}/drive/items/{item_id}/workbook{path}"


# ── Worksheet helpers ──────────────────────────────────────────────────────────
def _get_sheet_data(sheet_name: str) -> list[list]:
    """Return all rows (list of lists) from a worksheet."""
    url  = _workbook_url(f"/worksheets/{sheet_name}/usedRange")
    resp = requests.get(url, headers=_headers(), timeout=30)
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    return resp.json().get("values", [])


def _append_row(sheet_name: str, row: list) -> None:
    """Append a single row to a worksheet."""
    data = _get_sheet_data(sheet_name)
    next_row = len(data) + 1  # 1-indexed

    col_count = len(row)
    # Convert column count to Excel letter (A, B, ... Z, AA ...)
    end_col   = _col_letter(col_count)
    address   = f"A{next_row}:{end_col}{next_row}"

    url  = _workbook_url(f"/worksheets/{sheet_name}/range(address='{address}')")
    body = {"values": [row]}
    resp = requests.patch(url, headers=_headers(), json=body, timeout=15)
    resp.raise_for_status()


def _update_cell(sheet_name: str, row_index: int, col_index: int, value) -> None:
    """Update a single cell (1-indexed row/col)."""
    col_letter = _col_letter(col_index)
    address    = f"{col_letter}{row_index}:{col_letter}{row_index}"
    url  = _workbook_url(f"/worksheets/{sheet_name}/range(address='{address}')")
    body = {"values": [[value]]}
    resp = requests.patch(url, headers=_headers(), json=body, timeout=15)
    resp.raise_for_status()


def _col_letter(n: int) -> str:
    """Convert 1-indexed column number to Excel letter (1→A, 26→Z, 27→AA)."""
    result = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        result = chr(65 + r) + result
    return result


# ── Public API (same as sheets_client.py) ─────────────────────────────────────

def ensure_sheets_exist() -> None:
    """Ensure Leads, test, and Email Log worksheets exist in the Excel file."""
    url  = _workbook_url("/worksheets")
    resp = requests.get(url, headers=_headers(), timeout=15)
    resp.raise_for_status()
    existing = [ws["name"] for ws in resp.json().get("value", [])]

    required = [
        (config.LEADS_SHEET_NAME,     LEADS_HEADERS),
        (config.TEST_SHEET_NAME,      TEST_HEADERS),
        (config.EMAIL_LOG_SHEET_NAME, ["Timestamp", "Company", "Email", "Subject", "Status", "Category"]),
    ]

    for sheet_name, headers in required:
        if sheet_name not in existing:
            # Add worksheet
            create_url  = _workbook_url("/worksheets/add")
            resp = requests.post(create_url, headers=_headers(), json={"name": sheet_name}, timeout=15)
            resp.raise_for_status()
            # Add header row
            _append_row(sheet_name, headers)
            print(f"{Fore.GREEN}✔ Created '{sheet_name}' tab in Excel{Style.RESET_ALL}")
        else:
            print(f"  ✓ Tab '{sheet_name}' exists")


def get_stats() -> dict:
    """Return counts by status from the Leads sheet."""
    data = _get_sheet_data(config.LEADS_SHEET_NAME)
    if len(data) < 2:
        return {"total": 0, "pending": 0, "emailed": 0, "replied": 0,
                "no_email": 0, "unsubscribed": 0}

    headers = data[0]
    try:
        status_col = headers.index("Status")
        email_col  = headers.index("Email")
    except ValueError:
        return {"total": len(data) - 1, "pending": 0, "emailed": 0,
                "replied": 0, "no_email": 0, "unsubscribed": 0}

    rows = data[1:]
    stats = {"total": len(rows), "pending": 0, "emailed": 0,
             "replied": 0, "no_email": 0, "unsubscribed": 0}

    for row in rows:
        status = (row[status_col] if len(row) > status_col else "").strip().lower()
        email  = (row[email_col]  if len(row) > email_col  else "").strip()

        if status == "emailed":
            stats["emailed"] += 1
        elif status == "replied":
            stats["replied"] += 1
        elif status == "unsubscribed":
            stats["unsubscribed"] += 1
        elif not email:
            stats["no_email"] += 1
        else:
            stats["pending"] += 1

    return stats


def get_leads_ready_to_email() -> list[dict]:
    """Return leads that have an email and are old enough (EMAIL_DELAY_DAYS)."""
    data = _get_sheet_data(config.LEADS_SHEET_NAME)
    if len(data) < 2:
        return []

    headers = data[0]
    cutoff  = datetime.now() - timedelta(days=config.EMAIL_DELAY_DAYS)
    leads   = []

    for row_idx, row in enumerate(data[1:], start=2):  # 1-indexed, skip header
        def cell(col_name):
            try:
                return str(row[headers.index(col_name)]).strip() if col_name in headers else ""
            except (IndexError, ValueError):
                return ""

        email       = cell("Email")
        status      = cell("Status").lower()
        date_found  = cell("Date Found")

        if not email or status in ("emailed", "replied", "unsubscribed", "bounced"):
            continue

        # Parse date
        try:
            dt = datetime.strptime(date_found[:10], "%Y-%m-%d")
        except Exception:
            continue

        if dt > cutoff:
            continue

        days_old = (datetime.now() - dt).days
        leads.append({
            "Company Name":       cell("Company Name"),
            "Category":           cell("Category"),
            "Location":           cell("Location"),
            "Email":              email,
            "Website":            cell("Website"),
            "Description":        cell("Description"),
            "Social Profile URL": cell("Social Profile URL"),
            "row_index":          row_idx,
            "days_old":           days_old,
        })

    return leads


def get_test_leads() -> list[dict]:
    """Return leads from the test sheet."""
    data = _get_sheet_data(config.TEST_SHEET_NAME)
    if len(data) < 2:
        return []
    headers = data[0]
    result  = []
    for row_idx, row in enumerate(data[1:], start=2):
        def cell(col):
            try:
                return str(row[headers.index(col)]).strip() if col in headers else ""
            except (IndexError, ValueError):
                return ""
        name  = cell("name")
        email = cell("email")
        desc  = cell("description")
        if email:
            result.append({
                "Company Name": name,
                "Email":        email,
                "Description":  desc,
                "row_index":    row_idx,
                "days_old":     999,
            })
    return result


def update_lead_status(row_index: int, status: str,
                       email_date: str = None, notes: str = None,
                       sheet_name: str = None) -> None:
    """Update Status (and optionally Email Send Date, Notes) for a lead row."""
    sname   = sheet_name or config.LEADS_SHEET_NAME
    data    = _get_sheet_data(sname)
    if not data:
        return
    headers = data[0]

    if "Status" in headers:
        _update_cell(sname, row_index, headers.index("Status") + 1, status)
    if email_date and "Email Send Date" in headers:
        _update_cell(sname, row_index, headers.index("Email Send Date") + 1, email_date)
    if notes and "Notes" in headers:
        _update_cell(sname, row_index, headers.index("Notes") + 1, notes)


def add_leads(leads: list[dict]) -> int:
    """Append new leads to the Leads sheet. Returns count added."""
    data    = _get_sheet_data(config.LEADS_SHEET_NAME)
    headers = data[0] if data else LEADS_HEADERS

    # Build set of existing emails for dedup
    existing_emails = set()
    if len(data) > 1:
        try:
            email_col = headers.index("Email")
            existing_emails = {str(r[email_col]).strip().lower()
                               for r in data[1:] if len(r) > email_col}
        except ValueError:
            pass

    added = 0
    for lead in leads:
        email = lead.get("Email", "").strip().lower()
        if email in existing_emails:
            continue
        row = [lead.get(h, "") for h in headers]
        _append_row(config.LEADS_SHEET_NAME, row)
        existing_emails.add(email)
        added += 1

    return added


def log_email_sent(company: str, email: str, subject: str,
                   status: str = "sent", category: str = "") -> None:
    """Append a row to the Email Log sheet."""
    row = [
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        company, email, subject, status, category,
    ]
    try:
        _append_row(config.EMAIL_LOG_SHEET_NAME, row)
    except Exception as e:
        print(f"  ⚠ Could not log email: {e}")
