from __future__ import annotations
"""
scrapers/google_scraper.py
Search for businesses using FREE Google Search scraping.
No API key or billing required.
"""

import time
import re
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

PHONE_PATTERN = re.compile(r"(\+?\d[\d\s\-().]{7,}\d)")


def search_google(keyword: str, location: str) -> list[dict]:
    """
    Search for businesses matching keyword + location.
    Priority:
      1. SerpAPI           → if SERPAPI_KEY is set (best results)
      2. Free Google Search → always works, no API key needed
      3. Google Maps API   → only if GOOGLE_MAPS_API_KEY set (needs billing)
    """
    if config.SERPAPI_KEY:
        results = _search_serpapi(keyword, location)
        if results:
            return results

    # Always fall back to free search (works without any API key)
    return _search_google_free(keyword, location)


def _search_google_free(keyword: str, location: str) -> list[dict]:
    """
    Free search using duckduckgo-search library.
    Handles rate limits and bot detection automatically.
    No API key needed.
    """
    print(f"{Fore.CYAN}🔍 DuckDuckGo: '{keyword} in {location}'{Style.RESET_ALL}")
    results = []

    try:
        from ddgs import DDGS
        query = f"{keyword} {location}"

        skip_domains = [
            "wikipedia.org", "youtube.com", "facebook.com", "instagram.com",
            "yelp.com", "tripadvisor.com", "yellowpages.com", "indeed.com",
            "linkedin.com", "twitter.com", "kompass.com", "gobester.com",
            "duckduckgo.com", "google.com",
        ]

        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=config.MAX_RESULTS_PER_QUERY + 5):
                href = r.get("href", "")
                title = r.get("title", "")
                body = r.get("body", "")

                if not title or not href:
                    continue
                if any(d in href for d in skip_domains):
                    continue

                # Extract phone from body
                phone = ""
                phone_match = PHONE_PATTERN.search(body)
                if phone_match:
                    phone = phone_match.group(1).strip()

                results.append({
                    "name":      title,
                    "category":  keyword,
                    "location":  location,
                    "phone":     phone,
                    "email":     "",
                    "website":   href,
                    "instagram": "",
                    "source":    "DuckDuckGo",
                })

                if len(results) >= config.MAX_RESULTS_PER_QUERY:
                    break

        time.sleep(1)

    except Exception as e:
        print(f"{Fore.RED}✘ DuckDuckGo search error: {e}{Style.RESET_ALL}")
        return []

    print(f"{Fore.GREEN}  → Found {len(results)} results{Style.RESET_ALL}")
    return results


def _search_serpapi(keyword: str, location: str) -> list[dict]:
    """Use SerpAPI for more reliable results (free tier: 100 searches/month)."""
    query = f"{keyword} in {location}"
    url = "https://serpapi.com/search.json"
    params = {
        "q": query,
        "engine": "google_maps",
        "api_key": config.SERPAPI_KEY,
        "type": "search",
    }

    print(f"{Fore.CYAN}🔍 SerpAPI: '{query}'{Style.RESET_ALL}")

    try:
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()
        places = data.get("local_results", [])
        results = []

        for place in places[:config.MAX_RESULTS_PER_QUERY]:
            results.append({
                "name": place.get("title", ""),
                "category": keyword,
                "location": location,
                "phone": place.get("phone", ""),
                "email": "",
                "website": place.get("website", ""),
                "instagram": "",
                "source": "SerpAPI",
            })

        print(f"{Fore.GREEN}  → Found {len(results)} results{Style.RESET_ALL}")
        return results

    except Exception as e:
        print(f"{Fore.RED}✘ SerpAPI error: {e}{Style.RESET_ALL}")
        return []


def _search_google_maps(keyword: str, location: str) -> list[dict]:
    """Use Google Maps Places API (requires billing enabled)."""
    import googlemaps

    client = googlemaps.Client(key=config.GOOGLE_MAPS_API_KEY)
    query = f"{keyword} in {location}"
    results = []

    print(f"{Fore.CYAN}🔍 Google Maps API: '{query}'{Style.RESET_ALL}")

    try:
        response = client.places(query=query, language="en")
        places = response.get("results", [])

        for place in places[:config.MAX_RESULTS_PER_QUERY]:
            place_id = place.get("place_id")
            fields = ["name", "formatted_address", "formatted_phone_number", "website"]
            try:
                detail_resp = client.place(place_id=place_id, fields=fields, language="en")
                details = detail_resp.get("result", {})
            except Exception:
                details = place

            name = details.get("name", "").strip()
            if not name or details.get("business_status") == "CLOSED_PERMANENTLY":
                continue

            results.append({
                "name": name,
                "category": keyword,
                "location": location,
                "phone": details.get("formatted_phone_number", ""),
                "email": "",
                "website": details.get("website", ""),
                "instagram": "",
                "source": "Google Maps",
            })
            time.sleep(config.REQUEST_DELAY_SECONDS)

    except Exception as e:
        print(f"{Fore.RED}✘ Google Maps error: {e}{Style.RESET_ALL}")

    print(f"{Fore.GREEN}  → Found {len(results)} results{Style.RESET_ALL}")
    return results


def run_google_scraper() -> list[dict]:
    """Run the Google scraper for all keyword + location combos."""
    all_companies = []
    for location in config.LOCATIONS:
        for keyword in config.KEYWORDS:
            companies = search_google(keyword, location)
            all_companies.extend(companies)
            time.sleep(config.REQUEST_DELAY_SECONDS)
    print(f"\n{Fore.GREEN}✔ Google scraper done — {len(all_companies)} total results{Style.RESET_ALL}")
    return all_companies
