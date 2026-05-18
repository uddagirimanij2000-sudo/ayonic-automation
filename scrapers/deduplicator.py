from __future__ import annotations
"""
scrapers/deduplicator.py
Cross-source deduplication engine.

Deduplication rules (ANY match = duplicate):
  1. Same company name (normalized)
  2. Same phone number (digits only)
  3. Same website domain (stripped of www/subdomains)
  4. Same Instagram handle

Works in two stages:
  1. In-memory: deduplicates the batch collected from all scrapers in one run
  2. Against Google Sheets: checks existing leads before saving
"""

import re
from urllib.parse import urlparse
from difflib import SequenceMatcher
from colorama import Fore, Style


# ── Normalization helpers ─────────────────────────────────────────────────────

def normalize_name(name: str) -> str:
    """Lowercase, strip punctuation/spaces for name comparison."""
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9\s]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    # Remove common business suffixes
    for suffix in ["ltd", "llc", "inc", "gmbh", "sl", "lda", "sa", "srl", "bv", "nv"]:
        name = re.sub(rf"\b{suffix}\b", "", name).strip()
    return name


def normalize_phone(phone) -> str:
    """Keep only digits for phone comparison. Accepts any type safely."""
    if not phone:
        return ""
    digits = re.sub(r"\D", "", str(phone))
    # Strip leading country code if too long (keep last 9 digits)
    return digits[-9:] if len(digits) > 9 else digits


def normalize_domain(url: str) -> str:
    """Extract base domain from URL, strip www."""
    if not url:
        return ""
    try:
        if not url.startswith("http"):
            url = "https://" + url
        domain = urlparse(url).netloc.lower()
        domain = re.sub(r"^www\d*\.", "", domain)  # strip www, www2, etc.
        domain = domain.split(":")[0]              # strip port
        return domain
    except Exception:
        return ""


def normalize_instagram(handle: str) -> str:
    """Extract handle from full URL or @handle."""
    if not handle:
        return ""
    handle = handle.lower().strip()
    # Extract from URL like instagram.com/handlename
    match = re.search(r"instagram\.com/([^/?#&]+)", handle)
    if match:
        handle = match.group(1)
    return handle.lstrip("@").strip("/")


def name_similarity(a: str, b: str) -> float:
    """Return similarity score 0-1 between two normalized names."""
    return SequenceMatcher(None, normalize_name(a), normalize_name(b)).ratio()


# ── Fingerprint builder ───────────────────────────────────────────────────────

def get_fingerprint(company: dict) -> dict:
    """Build a normalized fingerprint dict for a company."""
    return {
        "name":      normalize_name(company.get("name", "")),
        "phone":     normalize_phone(company.get("phone", "")),
        "domain":    normalize_domain(company.get("website", "")),
        "instagram": normalize_instagram(company.get("instagram", "")),
    }


def is_duplicate(fp_a: dict, fp_b: dict, name_threshold: float = 0.85) -> bool:
    """
    Returns True if two fingerprints represent the same company.
    Matches on: phone, domain, instagram, or high name similarity.
    """
    # Phone match (non-empty)
    if fp_a["phone"] and fp_b["phone"] and fp_a["phone"] == fp_b["phone"]:
        return True

    # Website domain match (non-empty)
    if fp_a["domain"] and fp_b["domain"] and fp_a["domain"] == fp_b["domain"]:
        return True

    # Instagram handle match (non-empty)
    if fp_a["instagram"] and fp_b["instagram"] and fp_a["instagram"] == fp_b["instagram"]:
        return True

    # Name similarity (fuzzy match)
    if fp_a["name"] and fp_b["name"]:
        sim = SequenceMatcher(None, fp_a["name"], fp_b["name"]).ratio()
        if sim >= name_threshold:
            return True

    return False


# ── Stage 1: In-memory deduplication ─────────────────────────────────────────

def deduplicate_batch(companies: list[dict]) -> list[dict]:
    """
    Remove duplicates from a batch of companies collected in one scrape run.
    If a company appears in multiple sources, keep the one with the most info
    (prefer records with email, phone, website).
    """
    if not companies:
        return []

    print(f"\n{Fore.CYAN}🔍 Deduplicating batch of {len(companies)} companies...{Style.RESET_ALL}")

    unique = []
    fingerprints = []

    for company in companies:
        fp = get_fingerprint(company)

        # Check against already-accepted companies
        matched_idx = None
        for i, existing_fp in enumerate(fingerprints):
            if is_duplicate(fp, existing_fp):
                matched_idx = i
                break

        if matched_idx is None:
            # New unique company
            unique.append(company)
            fingerprints.append(fp)
        else:
            # Merge: keep the record with the most data
            existing = unique[matched_idx]
            merged = _merge_records(existing, company)
            unique[matched_idx] = merged
            fingerprints[matched_idx] = get_fingerprint(merged)

    removed = len(companies) - len(unique)
    print(f"{Fore.GREEN}  ✔ {len(unique)} unique companies ({removed} duplicates removed){Style.RESET_ALL}")
    return unique


def _merge_records(a: dict, b: dict) -> dict:
    """
    Merge two records for the same company.
    Keep non-empty values, prefer the one with more data.
    Combine source names.
    """
    merged = dict(a)

    for key in ["phone", "email", "website", "instagram", "category", "location"]:
        if not merged.get(key) and b.get(key):
            merged[key] = b[key]

    # Combine sources
    src_a = a.get("source", "")
    src_b = b.get("source", "")
    if src_b and src_b not in src_a:
        merged["source"] = f"{src_a} + {src_b}" if src_a else src_b

    # Combine social URLs
    if b.get("social_url") and not merged.get("social_url"):
        merged["social_url"] = b["social_url"]

    return merged


# ── Stage 2: Dedup against Google Sheets ─────────────────────────────────────

def filter_existing_leads(companies: list[dict], existing_leads: list[dict]) -> list[dict]:
    """
    Filter out companies that already exist in Google Sheets.
    Returns only truly new companies.
    """
    if not existing_leads:
        return companies

    existing_fps = [get_fingerprint({
        "name": str(lead.get("Company Name", "") or ""),
        "phone": str(lead.get("Phone", "") or ""),
        "website": str(lead.get("Website", "") or ""),
        "instagram": str(lead.get("Instagram", "") or ""),
    }) for lead in existing_leads]

    new_companies = []
    skipped = 0

    for company in companies:
        fp = get_fingerprint(company)
        is_existing = any(is_duplicate(fp, efp) for efp in existing_fps)

        if is_existing:
            print(f"{Fore.YELLOW}  ⚠ Already in sheet: {company.get('name', '')}{Style.RESET_ALL}")
            skipped += 1
        else:
            new_companies.append(company)

    if skipped:
        print(f"{Fore.YELLOW}  Skipped {skipped} companies already in Google Sheets{Style.RESET_ALL}")

    return new_companies
