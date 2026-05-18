from __future__ import annotations
"""
scrapers/social_scraper.py
Search for businesses across social media platforms.

FREE methods (no API keys):
  - Facebook via DuckDuckGo (site:facebook.com)
  - LinkedIn via DuckDuckGo (site:linkedin.com)
  - Instagram via DuckDuckGo (site:instagram.com)

API methods (need keys):
  - Facebook Pages API
  - LinkedIn via RapidAPI
  - TikTok via RapidAPI
  - Twitter/X via RapidAPI
  - YouTube Data API
"""

import time
import re
import requests
from colorama import Fore, Style
import config

PHONE_PATTERN = re.compile(r"(\+?\d[\d\s\-().]{7,}\d)")


# ══════════════════════════════════════════════════════════════════════════════
# FREE SOCIAL SEARCH (No API keys needed)
# ══════════════════════════════════════════════════════════════════════════════

def _ddg_site_search(site: str, keyword: str, location: str, platform: str) -> list[dict]:
    """Search DuckDuckGo with site: filter to find social media profiles."""
    try:
        from ddgs import DDGS
    except ImportError:
        return []

    query = f"site:{site} {keyword} {location}"
    results = []

    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=10):
                href = r.get("href", "")
                title = r.get("title", "")
                body = r.get("body", "")

                if not title or not href:
                    continue
                if site not in href:
                    continue

                # Extract phone from body
                phone = ""
                phone_match = PHONE_PATTERN.search(body)
                if phone_match:
                    phone = phone_match.group(1).strip()

                # Extract email from body
                email = ""
                email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", body)
                if email_match:
                    email = email_match.group(0)

                # Clean company name from title
                name = title
                for remove in [" | Facebook", " - Facebook", " | LinkedIn",
                               " - LinkedIn", " (@", " • Instagram"]:
                    name = name.split(remove)[0]

                results.append({
                    "name":       name.strip(),
                    "category":   keyword,
                    "location":   location,
                    "phone":      phone,
                    "email":      email,
                    "website":    "",
                    "instagram":  href if "instagram" in site else "",
                    "source":     f"{platform} (free)",
                    "social_url": href,
                })

        time.sleep(1)
    except Exception as e:
        print(f"{Fore.RED}✘ {platform} search error: {e}{Style.RESET_ALL}")

    return results


def search_facebook_free(keyword: str, location: str) -> list[dict]:
    """Search Facebook pages via DuckDuckGo — FREE."""
    print(f"{Fore.MAGENTA}📘 Facebook (free): '{keyword} {location}'{Style.RESET_ALL}")
    results = _ddg_site_search("facebook.com", keyword, location, "Facebook")
    print(f"{Fore.GREEN}  → Found {len(results)}{Style.RESET_ALL}")
    return results


def search_linkedin_free(keyword: str, location: str) -> list[dict]:
    """Search LinkedIn company pages via DuckDuckGo — FREE."""
    print(f"{Fore.BLUE}🔗 LinkedIn (free): '{keyword} {location}'{Style.RESET_ALL}")
    results = _ddg_site_search("linkedin.com/company", keyword, location, "LinkedIn")
    print(f"{Fore.GREEN}  → Found {len(results)}{Style.RESET_ALL}")
    return results


def search_instagram_free(keyword: str, location: str) -> list[dict]:
    """Search Instagram profiles via DuckDuckGo — FREE."""
    print(f"{Fore.YELLOW}📸 Instagram (free): '{keyword} {location}'{Style.RESET_ALL}")
    results = _ddg_site_search("instagram.com", keyword, location, "Instagram")
    print(f"{Fore.GREEN}  → Found {len(results)}{Style.RESET_ALL}")
    return results


# ══════════════════════════════════════════════════════════════════════════════
# API-BASED SEARCH (Need API keys)
# ══════════════════════════════════════════════════════════════════════════════

def search_facebook(keyword: str, location: str) -> list[dict]:
    """Search Facebook Pages API for businesses."""
    token = getattr(config, "FACEBOOK_ACCESS_TOKEN", "")
    if not token:
        return []

    url = "https://graph.facebook.com/v18.0/pages/search"
    params = {
        "q": f"{keyword} {location}",
        "fields": "name,phone,emails,website,single_line_address,link",
        "access_token": token,
        "limit": config.MAX_RESULTS_PER_QUERY,
    }

    print(f"{Fore.MAGENTA}📘 Facebook API: '{keyword} {location}'{Style.RESET_ALL}")

    try:
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()
        results = []

        for page in data.get("data", []):
            emails = page.get("emails", [])
            results.append({
                "name": page.get("name", ""),
                "category": keyword,
                "location": location,
                "phone": page.get("phone", ""),
                "email": emails[0] if emails else "",
                "website": page.get("website", ""),
                "instagram": "",
                "source": "Facebook",
                "social_url": page.get("link", ""),
            })

        print(f"{Fore.GREEN}  → Found {len(results)} on Facebook{Style.RESET_ALL}")
        return results

    except Exception as e:
        print(f"{Fore.RED}✘ Facebook error: {e}{Style.RESET_ALL}")
        return []


def search_linkedin(keyword: str, location: str) -> list[dict]:
    """Search LinkedIn company profiles via RapidAPI."""
    api_key = getattr(config, "RAPIDAPI_KEY", "")
    if not api_key:
        return []

    url = "https://linkedin-data-api.p.rapidapi.com/search-companies"
    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": "linkedin-data-api.p.rapidapi.com",
    }
    params = {
        "keywords": f"{keyword} {location}",
        "limit": str(config.MAX_RESULTS_PER_QUERY),
    }

    print(f"{Fore.BLUE}🔗 LinkedIn API: '{keyword} {location}'{Style.RESET_ALL}")

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        data = resp.json()
        results = []

        for company in data.get("items", []):
            results.append({
                "name": company.get("name", ""),
                "category": keyword,
                "location": location,
                "phone": "",
                "email": "",
                "website": company.get("websiteUrl", ""),
                "instagram": "",
                "source": "LinkedIn",
                "social_url": company.get("url", ""),
            })

        print(f"{Fore.GREEN}  → Found {len(results)} on LinkedIn{Style.RESET_ALL}")
        return results

    except Exception as e:
        print(f"{Fore.RED}✘ LinkedIn error: {e}{Style.RESET_ALL}")
        return []


def search_tiktok(keyword: str, location: str) -> list[dict]:
    """Search TikTok business profiles via RapidAPI."""
    api_key = getattr(config, "RAPIDAPI_KEY", "")
    if not api_key:
        return []

    url = "https://tiktok-api23.p.rapidapi.com/api/search/user"
    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": "tiktok-api23.p.rapidapi.com",
    }
    params = {"keyword": f"{keyword} {location}", "count": "20"}

    print(f"{Fore.CYAN}🎵 TikTok: '{keyword} {location}'{Style.RESET_ALL}")

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        data = resp.json()
        results = []

        for user in data.get("user_list", []):
            user_info = user.get("user_info", {})
            results.append({
                "name": user_info.get("nickname", ""),
                "category": keyword,
                "location": location,
                "phone": "",
                "email": "",
                "website": "",
                "instagram": "",
                "source": "TikTok",
                "social_url": f"https://tiktok.com/@{user_info.get('unique_id', '')}",
            })

        print(f"{Fore.GREEN}  → Found {len(results)} on TikTok{Style.RESET_ALL}")
        return results

    except Exception as e:
        print(f"{Fore.RED}✘ TikTok error: {e}{Style.RESET_ALL}")
        return []


def search_twitter(keyword: str, location: str) -> list[dict]:
    """Search Twitter/X for business accounts via RapidAPI."""
    api_key = getattr(config, "RAPIDAPI_KEY", "")
    if not api_key:
        return []

    url = "https://twitter-api45.p.rapidapi.com/search.php"
    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": "twitter-api45.p.rapidapi.com",
    }
    params = {"query": f"{keyword} {location}", "search_type": "People"}

    print(f"{Fore.CYAN}🐦 Twitter/X: '{keyword} {location}'{Style.RESET_ALL}")

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        data = resp.json()
        results = []

        for user in data.get("timeline", []):
            results.append({
                "name": user.get("name", ""),
                "category": keyword,
                "location": location,
                "phone": "",
                "email": "",
                "website": user.get("website", ""),
                "instagram": "",
                "source": "Twitter/X",
                "social_url": f"https://x.com/{user.get('screen_name', '')}",
            })

        print(f"{Fore.GREEN}  → Found {len(results)} on Twitter/X{Style.RESET_ALL}")
        return results

    except Exception as e:
        print(f"{Fore.RED}✘ Twitter/X error: {e}{Style.RESET_ALL}")
        return []


def search_youtube(keyword: str, location: str) -> list[dict]:
    """Search YouTube channels via YouTube Data API v3 (free)."""
    api_key = getattr(config, "YOUTUBE_API_KEY", "")
    if not api_key:
        return []

    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": f"{keyword} {location}",
        "type": "channel",
        "maxResults": config.MAX_RESULTS_PER_QUERY,
        "key": api_key,
    }

    print(f"{Fore.RED}📺 YouTube: '{keyword} {location}'{Style.RESET_ALL}")

    try:
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()
        results = []

        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            channel_id = item.get("id", {}).get("channelId", "")
            results.append({
                "name": snippet.get("title", ""),
                "category": keyword,
                "location": location,
                "phone": "",
                "email": "",
                "website": "",
                "instagram": "",
                "source": "YouTube",
                "social_url": f"https://youtube.com/channel/{channel_id}",
            })

        print(f"{Fore.GREEN}  → Found {len(results)} on YouTube{Style.RESET_ALL}")
        return results

    except Exception as e:
        print(f"{Fore.RED}✘ YouTube error: {e}{Style.RESET_ALL}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
# Main runner
# ══════════════════════════════════════════════════════════════════════════════

def run_social_scraper() -> list[dict]:
    """Run all social media scrapers — free ones always, API ones if keys set."""
    all_companies = []

    # Free scrapers (always run)
    free_platforms = {
        "Facebook (free)":  search_facebook_free,
        "LinkedIn (free)":  search_linkedin_free,
        "Instagram (free)": search_instagram_free,
    }

    # API scrapers (only if keys set)
    api_platforms = {}
    if getattr(config, "FACEBOOK_ACCESS_TOKEN", ""):
        api_platforms["Facebook API"] = search_facebook
    if getattr(config, "RAPIDAPI_KEY", ""):
        api_platforms["LinkedIn API"] = search_linkedin
        api_platforms["TikTok"] = search_tiktok
        api_platforms["Twitter/X"] = search_twitter
    if getattr(config, "YOUTUBE_API_KEY", ""):
        api_platforms["YouTube"] = search_youtube

    all_platforms = {**free_platforms, **api_platforms}

    print(f"\n{Fore.CYAN}📱 Social Media Scraper{Style.RESET_ALL}")
    print(f"  Free: {', '.join(free_platforms.keys())}")
    if api_platforms:
        print(f"  API:  {', '.join(api_platforms.keys())}")
    print()

    # Use a subset of keywords for social (top categories only)
    social_keywords = [
        "cleaning company", "Reinigungsfirma",
        "plumber", "Klempner",
        "electrician", "Elektriker",
        "handyman", "Handwerker",
        "locksmith", "Schlüsseldienst",
        "moving company", "Umzugsunternehmen",
        "garden service", "Gartenpflege",
        "pest control", "Schädlingsbekämpfung",
    ]

    for location in config.LOCATIONS:
        for keyword in social_keywords:
            for platform_name, search_fn in all_platforms.items():
                results = search_fn(keyword, location)
                all_companies.extend(results)
                time.sleep(1.5)

    print(f"\n{Fore.GREEN}✔ Social scraper done — {len(all_companies)} total{Style.RESET_ALL}")
    return all_companies

