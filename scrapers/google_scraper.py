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


def search_google(keyword: str, location: str, existing_names: set = None, existing_phones: set = None, existing_websites: set = None, max_new: int = 20) -> list[dict]:
    """
    Search for businesses matching keyword + location.
    Priority:
      1. SerpAPI           → if SERPAPI_KEY is set (best results)
      2. Free Google Search → always works, no API key needed
      3. Google Maps API   → only if GOOGLE_MAPS_API_KEY set (needs billing)
    """
    existing_names = existing_names or set()
    existing_phones = existing_phones or set()
    existing_websites = existing_websites or set()

    if config.SERPAPI_KEY:
        results = _search_serpapi(keyword, location, existing_names, existing_phones, existing_websites, max_new)
        if results:
            return results

    # Always fall back to free search (works without any API key)
    return _search_google_free(keyword, location, existing_names, existing_phones, existing_websites, max_new)


def _search_google_free(keyword: str, location: str, existing_names: set, existing_phones: set, existing_websites: set, max_new: int) -> list[dict]:
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
            # Fetch more results to find new unique leads among duplicates
            for r in ddgs.text(query, max_results=100):
                if len(results) >= max_new:
                    break

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

                # Deduplicate instantly
                name_key = title.lower().strip()
                phone_key = re.sub(r"\D", "", phone) if phone else ""
                web_key = href.lower().strip()

                if name_key in existing_names:
                    continue
                if phone_key and phone_key in existing_phones:
                    continue
                if web_key and web_key in existing_websites:
                    continue

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

        time.sleep(1)

    except Exception as e:
        print(f"{Fore.RED}✘ DuckDuckGo search error: {e}{Style.RESET_ALL}")
        return []

    if results:
        print(f"{Fore.GREEN}  → Found {len(results)} NEW results{Style.RESET_ALL}")
    return results


def _search_serpapi(keyword: str, location: str, existing_names: set, existing_phones: set, existing_websites: set, max_new: int) -> list[dict]:
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

        for place in places:
            if len(results) >= max_new:
                break

            name = place.get("title", "").strip()
            phone = place.get("phone", "").strip()
            website = place.get("website", "").strip()

            name_key = name.lower()
            phone_key = re.sub(r"\D", "", phone) if phone else ""
            web_key = website.lower()

            if name_key in existing_names or (phone_key and phone_key in existing_phones) or (web_key and web_key in existing_websites):
                continue

            results.append({
                "name": name,
                "category": keyword,
                "location": location,
                "phone": phone,
                "email": "",
                "website": website,
                "instagram": "",
                "source": "SerpAPI",
            })

        if results:
            print(f"{Fore.GREEN}  → Found {len(results)} NEW results{Style.RESET_ALL}")
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


def run_google_scraper(existing_names: set = None, existing_phones: set = None, existing_websites: set = None) -> list[dict]:
    """Run the Google scraper for all keyword + location combos until the target of new leads is met."""
    all_companies = []
    existing_names = existing_names or set()
    existing_phones = existing_phones or set()
    existing_websites = existing_websites or set()
    
    target_new = getattr(config, "MAX_NEW_LEADS_PER_SCRAPE", 15)

    for location in config.LOCATIONS:
        for keyword in config.KEYWORDS:
            if len(all_companies) >= target_new:
                break
                
            companies = search_google(
                keyword, location, 
                existing_names, existing_phones, existing_websites, 
                max_new=(target_new - len(all_companies))
            )
            
            for c in companies:
                all_companies.append(c)
                existing_names.add(c["name"].lower().strip())
                if c.get("phone"):
                    existing_phones.add(re.sub(r"\D", "", c["phone"]))
                if c.get("website"):
                    existing_websites.add(c["website"].lower().strip())
            
            time.sleep(config.REQUEST_DELAY_SECONDS)
            
        if len(all_companies) >= target_new:
            break

    print(f"\n{Fore.GREEN}✔ Google scraper done — {len(all_companies)} NEW unique results{Style.RESET_ALL}")
    return all_companies
