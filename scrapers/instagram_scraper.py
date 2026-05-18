"""
scrapers/instagram_scraper.py
Search Instagram for business profiles using hashtags.
Uses instagrapi (free) by default. Set APIFY_TOKEN in .env to use Apify instead.
"""

import time
import requests
from colorama import Fore, Style
import config


# ── Apify-based scraper (reliable, paid) ─────────────────────────────────────

def search_instagram_apify(keyword: str, location: str) -> list[dict]:
    """
    Use Apify's Instagram Hashtag Scraper actor.
    Requires APIFY_TOKEN in .env
    """
    hashtag = f"{keyword.replace(' ', '')}_{location.replace(' ', '').lower()}"
    url = (
        f"https://api.apify.com/v2/acts/apify~instagram-hashtag-scraper/run-sync-get-dataset-items"
        f"?token={config.APIFY_TOKEN}"
    )
    payload = {
        "hashtags": [hashtag],
        "resultsLimit": 20,
    }
    print(f"{Fore.CYAN}📸 Apify Instagram: #{hashtag}{Style.RESET_ALL}")
    try:
        resp = requests.post(url, json=payload, timeout=120)
        if resp.status_code == 200:
            items = resp.json()
            return _parse_apify_results(items, keyword, location)
    except Exception as e:
        print(f"{Fore.RED}✘ Apify error: {e}{Style.RESET_ALL}")
    return []


def _parse_apify_results(items: list, keyword: str, location: str) -> list[dict]:
    companies = []
    for item in items:
        owner = item.get("ownerUsername", "")
        if not owner:
            continue
        companies.append({
            "name":      owner,
            "category":  keyword,
            "location":  location,
            "phone":     item.get("phoneNumber", ""),
            "email":     item.get("publicEmail", ""),
            "website":   item.get("externalUrl", ""),
            "instagram": f"https://instagram.com/{owner}",
            "source":    "Instagram (Apify)",
        })
    return companies


# ── instagrapi-based scraper (free, requires IG account) ─────────────────────

def search_instagram_instagrapi(keyword: str, location: str) -> list[dict]:
    """
    Use instagrapi to search Instagram hashtags.
    Requires INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD in .env
    """
    try:
        from instagrapi import Client
    except ImportError:
        print(f"{Fore.RED}✘ instagrapi not installed. Run: pip install instagrapi{Style.RESET_ALL}")
        return []

    if not config.INSTAGRAM_USERNAME or not config.INSTAGRAM_PASSWORD:
        print(f"{Fore.YELLOW}⚠ Instagram credentials not set — skipping Instagram scrape{Style.RESET_ALL}")
        return []

    hashtag = f"{keyword.replace(' ', '')}{location.replace(' ', '').lower()}"
    print(f"{Fore.CYAN}📸 instagrapi Instagram: #{hashtag}{Style.RESET_ALL}")

    try:
        cl = Client()
        cl.login(config.INSTAGRAM_USERNAME, config.INSTAGRAM_PASSWORD)

        medias = cl.hashtag_medias_recent(hashtag, amount=15)
        companies = []
        seen_users = set()

        for media in medias:
            user_id = media.user.pk
            if user_id in seen_users:
                continue
            seen_users.add(user_id)

            try:
                user_info = cl.user_info(user_id)
                time.sleep(2)  # Avoid rate limiting

                # Only include business/professional accounts
                if not user_info.is_business:
                    continue

                companies.append({
                    "name":      user_info.full_name or user_info.username,
                    "category":  keyword,
                    "location":  location,
                    "phone":     str(user_info.contact_phone_number or ""),
                    "email":     str(user_info.public_email or ""),
                    "website":   str(user_info.external_url or ""),
                    "instagram": f"https://instagram.com/{user_info.username}",
                    "source":    "Instagram (instagrapi)",
                })
            except Exception:
                continue

        cl.logout()
        return companies

    except Exception as e:
        print(f"{Fore.RED}✘ instagrapi error for #{hashtag}: {e}{Style.RESET_ALL}")
        return []


def run_instagram_scraper() -> list[dict]:
    """
    Run Instagram scraper for all keywords + locations.
    Uses Apify if APIFY_TOKEN is set, otherwise uses instagrapi.
    """
    all_companies = []
    use_apify = bool(config.APIFY_TOKEN)

    for location in config.LOCATIONS:
        for keyword in config.KEYWORDS:
            if use_apify:
                results = search_instagram_apify(keyword, location)
            else:
                results = search_instagram_instagrapi(keyword, location)

            all_companies.extend(results)
            time.sleep(config.REQUEST_DELAY_SECONDS)

    print(f"\n{Fore.GREEN}✔ Instagram scraper done — {len(all_companies)} total{Style.RESET_ALL}")
    return all_companies
