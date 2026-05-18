from __future__ import annotations
"""
scrapers/web_scraper.py
Visit each company's website and extract ALL business info:
  - Email addresses
  - Phone numbers
  - Physical address / location
  - Social media links (Instagram, Facebook, LinkedIn, TikTok, Twitter, YouTube)
  - Company description
  - Schema.org structured data (JSON-LD) — most accurate source

Pages checked: homepage, /contact, /about, /about-us, /contacto, /kontakt
"""

import re
import json
import time
import requests
from bs4 import BeautifulSoup
from colorama import Fore, Style
import config

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Pages to check on each site
CONTACT_PAGES = ["", "/contact", "/about", "/about-us", "/contacto", "/kontakt", "/contacts", "/reach-us"]

# ── Regex patterns ────────────────────────────────────────────────────────────
EMAIL_PATTERN     = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_PATTERN     = re.compile(r"(\+?[\d][\d\s\-().]{7,}\d)")
ADDRESS_PATTERN   = re.compile(r"\d{1,5}\s[\w\s]{3,40}(?:street|st|avenue|ave|road|rd|lane|ln|drive|dr|boulevard|blvd|way|place|pl|court|ct)", re.IGNORECASE)

# Social media patterns
INSTAGRAM_PATTERN = re.compile(r"instagram\.com/([a-zA-Z0-9_.]+)")
FACEBOOK_PATTERN  = re.compile(r"facebook\.com/([a-zA-Z0-9_./-]+)")
LINKEDIN_PATTERN  = re.compile(r"linkedin\.com/(?:company|in)/([a-zA-Z0-9_.-]+)")
TIKTOK_PATTERN    = re.compile(r"tiktok\.com/@([a-zA-Z0-9_.]+)")
TWITTER_PATTERN   = re.compile(r"(?:twitter|x)\.com/([a-zA-Z0-9_]+)")
YOUTUBE_PATTERN   = re.compile(r"youtube\.com/(?:channel|c|@)/([a-zA-Z0-9_.-]+)")

# Blacklists
EMAIL_BLACKLIST = {
    "example.com", "domain.com", "email.com", "yoursite.com",
    "sentry.io", "w3.org", "schema.org", "test.com", "wordpress.com",
    "wix.com", "squarespace.com", "godaddy.com", "google.com",
}
SOCIAL_BLACKLIST = {
    "p", "explore", "accounts", "stories", "sharer", "share",
    "plugins", "badges", "pages", "help", "legal", "ads",
    "company", "pub", "policy", "about", "blog",
}


# ── Main scraper function ─────────────────────────────────────────────────────

def scrape_website(url: str) -> dict:
    """
    Visit a company website and extract all available business info.

    Returns dict with keys:
      email, phone, address, instagram, facebook, linkedin,
      tiktok, twitter, youtube, description
    """
    result = {
        "email": "", "phone": "", "address": "",
        "instagram": "", "facebook": "", "linkedin": "",
        "tiktok": "", "twitter": "", "youtube": "",
        "description": "",
    }

    if not url:
        return result

    if not url.startswith("http"):
        url = "https://" + url

    for path in CONTACT_PAGES:
        page_url = url.rstrip("/") + path
        soup, text, html = _fetch_page(page_url)

        if not soup:
            continue

        # 1. Try Schema.org JSON-LD first (most reliable)
        schema_data = _extract_schema_org(soup)
        _merge_result(result, schema_data)

        # 2. Extract from page text
        if not result["email"]:
            emails = _filter_emails(EMAIL_PATTERN.findall(text))
            if emails:
                result["email"] = emails[0]

        if not result["phone"]:
            phones = _filter_phones(PHONE_PATTERN.findall(text))
            if phones:
                result["phone"] = phones[0]

        if not result["address"]:
            addr = _extract_address(soup, text)
            if addr:
                result["address"] = addr

        # 3. Extract social media links from HTML
        _extract_social_links(html, result)

        # 4. Extract description
        if not result["description"]:
            result["description"] = _extract_description(soup)

        # Stop early if we have everything important
        if result["email"] and result["phone"] and result["instagram"]:
            break

        time.sleep(0.5)

    return result


# ── Schema.org extraction ─────────────────────────────────────────────────────

def _extract_schema_org(soup: BeautifulSoup) -> dict:
    """Extract business info from JSON-LD schema.org markup."""
    result = {}

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if not isinstance(data, dict):
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            r = _parse_schema_item(item)
                            result.update({k: v for k, v in r.items() if v and not result.get(k)})
                continue
            r = _parse_schema_item(data)
            result.update({k: v for k, v in r.items() if v and not result.get(k)})
        except Exception:
            continue

    return result


def _parse_schema_item(data: dict) -> dict:
    """Parse a single schema.org JSON-LD item."""
    result = {}

    # Email
    for key in ["email", "contactPoint"]:
        val = data.get(key, "")
        if isinstance(val, str) and "@" in val:
            result["email"] = val.replace("mailto:", "")
        elif isinstance(val, dict):
            result["email"] = val.get("email", "").replace("mailto:", "")

    # Phone
    phone = data.get("telephone", "") or data.get("phone", "")
    if phone:
        result["phone"] = str(phone)

    # Address
    addr = data.get("address", {})
    if isinstance(addr, dict):
        parts = [
            addr.get("streetAddress", ""),
            addr.get("addressLocality", ""),
            addr.get("postalCode", ""),
            addr.get("addressCountry", ""),
        ]
        result["address"] = ", ".join(p for p in parts if p)
    elif isinstance(addr, str):
        result["address"] = addr

    # Description
    result["description"] = data.get("description", "")[:200]

    # Social media from sameAs
    same_as = data.get("sameAs", [])
    if isinstance(same_as, str):
        same_as = [same_as]

    for url in same_as:
        _match_social_url(url, result)

    return result


# ── Address extraction ────────────────────────────────────────────────────────

def _extract_address(soup: BeautifulSoup, text: str) -> str:
    """Try multiple methods to find company address."""

    # Method 1: common semantic elements
    for selector in ["address", "[class*='address']", "[itemprop='address']",
                     "[class*='location']", "[class*='contact-info']"]:
        el = soup.select_one(selector)
        if el:
            addr = el.get_text(" ", strip=True)
            if len(addr) > 5:
                return addr[:150]

    # Method 2: regex in text
    match = ADDRESS_PATTERN.search(text)
    if match:
        return match.group(0).strip()

    return ""


# ── Social media extraction ───────────────────────────────────────────────────

def _extract_social_links(html: str, result: dict):
    """Extract all social media links from page HTML."""
    patterns = {
        "instagram": INSTAGRAM_PATTERN,
        "facebook":  FACEBOOK_PATTERN,
        "linkedin":  LINKEDIN_PATTERN,
        "tiktok":    TIKTOK_PATTERN,
        "twitter":   TWITTER_PATTERN,
        "youtube":   YOUTUBE_PATTERN,
    }

    base_urls = {
        "instagram": "https://instagram.com/",
        "facebook":  "https://facebook.com/",
        "linkedin":  "https://linkedin.com/company/",
        "tiktok":    "https://tiktok.com/@",
        "twitter":   "https://x.com/",
        "youtube":   "https://youtube.com/",
    }

    for platform, pattern in patterns.items():
        if result.get(platform):
            continue
        match = pattern.search(html)
        if match:
            handle = match.group(1).rstrip("/")
            if handle.lower() not in SOCIAL_BLACKLIST:
                result[platform] = base_urls[platform] + handle


def _match_social_url(url: str, result: dict):
    """Match a social media URL and store it in result."""
    for platform, pattern in [
        ("instagram", INSTAGRAM_PATTERN), ("facebook", FACEBOOK_PATTERN),
        ("linkedin",  LINKEDIN_PATTERN),  ("tiktok",   TIKTOK_PATTERN),
        ("twitter",   TWITTER_PATTERN),   ("youtube",  YOUTUBE_PATTERN),
    ]:
        if not result.get(platform):
            match = pattern.search(url)
            if match:
                handle = match.group(1).rstrip("/")
                if handle.lower() not in SOCIAL_BLACKLIST:
                    result[platform] = url
                    break


# ── Description extraction ────────────────────────────────────────────────────

def _extract_description(soup: BeautifulSoup) -> str:
    """Extract a short company description."""
    # Try meta description first
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        return meta["content"][:200]

    # Try og:description
    og = soup.find("meta", property="og:description")
    if og and og.get("content"):
        return og["content"][:200]

    return ""


# ── Utilities ─────────────────────────────────────────────────────────────────

def _fetch_page(url: str) -> tuple:
    """Fetch URL, return (BeautifulSoup, plain_text, raw_html). Returns (None,'','') on error."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=5, allow_redirects=True)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "lxml")
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            return soup, soup.get_text(separator=" "), resp.text
    except Exception:
        pass
    return None, "", ""


def _filter_emails(emails: list) -> list:
    """Remove invalid/generic emails."""
    filtered = []
    for email in emails:
        email = email.lower().strip()
        domain = email.split("@")[-1]
        if domain not in EMAIL_BLACKLIST and "." in domain and len(email) > 5:
            filtered.append(email)
    return list(dict.fromkeys(filtered))


def _filter_phones(phones: list) -> list:
    """Keep only likely real phone numbers."""
    filtered = []
    for phone in phones:
        digits = re.sub(r"\D", "", phone)
        if 7 <= len(digits) <= 15:  # Valid phone length
            filtered.append(phone.strip())
    return filtered


def _merge_result(result: dict, new_data: dict):
    """Merge new_data into result, only filling empty fields."""
    for key, val in new_data.items():
        if val and not result.get(key):
            result[key] = val


# ── Batch enrichment ──────────────────────────────────────────────────────────

def _get_domain(url: str) -> str:
    """Extract base domain from URL."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # Remove www.
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return url


# Domains to skip — directories, marketplaces, not real cleaning companies
SKIP_DOMAINS = {
    "fixando.co.uk", "fixando.ie", "fixando.com.au", "fixando.co.nz",
    "fixando.pt", "fixando.com",
    "yelp.com", "tripadvisor.com", "yellowpages.com",
    "kompass.com", "europages.co.uk", "europages.com",
    "gobester.com", "localista.com", "locallista.com",
    "cleanersineurope.com", "expat.com",
    "portotheme.com",           # WordPress theme demo
    "brazilyello.com",
    "portugalyp.com",
    "indeed.com", "glassdoor.com",
    "houzz.com", "bark.com", "thumbtack.com",
    "bing.com",
}


def enrich_companies_with_web_data(companies: list[dict]) -> list[dict]:
    """
    For each company with a website:
    1. Pre-filter: skip known directories and list sites
    2. Pre-deduplicate: only visit each domain ONCE
    3. Scrape: extract email, phone, address, socials
    4. Merge scraped data back into all companies sharing that domain
    """
    from urllib.parse import urlparse

    # Step 1 — filter out directory/listing sites
    filtered = []
    skipped_dir = 0
    for c in companies:
        domain = _get_domain(c.get("website", ""))
        if not domain or domain in SKIP_DOMAINS:
            skipped_dir += 1
            continue
        filtered.append(c)

    if skipped_dir:
        print(f"{Fore.YELLOW}  ⚡ Skipped {skipped_dir} directory/listing sites{Style.RESET_ALL}")

    # Step 2 — group by domain, keeping first (representative) URL per domain
    domain_cache: dict[str, dict] = {}   # domain → scraped web_data
    domain_to_url: dict[str, str] = {}   # domain → URL to scrape

    for c in filtered:
        domain = _get_domain(c.get("website", ""))
        if domain and domain not in domain_to_url:
            domain_to_url[domain] = c["website"]

    unique_urls = list(domain_to_url.values())
    total = len(unique_urls)
    done  = 0

    # Step 3 — enrich unique domains only
    for domain, url in domain_to_url.items():
        done += 1
        print(f"{Fore.CYAN}🌐 [{done}/{total}] {url}{Style.RESET_ALL}")
        web_data = scrape_website(url)
        domain_cache[domain] = web_data

        if web_data.get("email"):
            print(f"  ✉ {web_data['email']}")
        if web_data.get("phone"):
            print(f"  📞 {web_data['phone']}")
        if web_data.get("address"):
            print(f"  📍 {web_data['address'][:60]}")
        if web_data.get("instagram"):
            print(f"  📸 {web_data['instagram']}")

        time.sleep(config.REQUEST_DELAY_SECONDS)

    # Step 4 — merge scraped data back into all matching companies
    fields = ["email", "phone", "address", "instagram", "facebook",
              "linkedin", "tiktok", "twitter", "youtube", "description"]

    for company in filtered:
        domain   = _get_domain(company.get("website", ""))
        web_data = domain_cache.get(domain, {})
        for field in fields:
            if web_data.get(field) and not company.get(field):
                company[field] = web_data[field]

    print(f"\n{Fore.GREEN}✔ Web enrichment done — {done} unique domains scraped "
          f"(was {len(companies)} raw results){Style.RESET_ALL}")
    return filtered
