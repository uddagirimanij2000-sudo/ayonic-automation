"""
test_one.py — Quick test: search for 1 company and save to Google Sheets.
"""
import sys
sys.path.insert(0, ".")

from sheets.sheets_client import add_lead, ensure_sheets_exist, get_stats
from scrapers.google_scraper import search_google
from scrapers.web_scraper import scrape_website
from colorama import Fore, Style, init

init(autoreset=True)

def main():
    ensure_sheets_exist()

    # Search for just 1 plumber in Lisbon (free, no API key needed)
    print(f"\n{Fore.CYAN}🔍 Searching: 1 plumber in Lisbon (free Google search)...{Style.RESET_ALL}\n")

    companies = search_google("plumber", "Lisbon")

    if not companies:
        print(f"{Fore.RED}✘ No results found.{Style.RESET_ALL}")
        return

    # Take just the first result
    company = companies[0]
    print(f"\n{Fore.GREEN}✔ Found: {company['name']}{Style.RESET_ALL}")
    print(f"  Phone:   {company.get('phone', 'N/A')}")
    print(f"  Website: {company.get('website', 'N/A')}")
    print(f"  Source:  {company.get('source', 'N/A')}")

    # Try to get email from website
    if company.get("website"):
        print(f"\n{Fore.CYAN}🌐 Scraping website for email...{Style.RESET_ALL}")
        web_data = scrape_website(company["website"])
        if web_data.get("email"):
            company["email"] = web_data["email"]
            print(f"  Email: {company['email']}")
        if web_data.get("instagram"):
            company["instagram"] = web_data["instagram"]
            print(f"  Instagram: {company['instagram']}")

    # Save to Google Sheets
    print(f"\n{Fore.CYAN}📄 Saving to Google Sheets...{Style.RESET_ALL}")
    added = add_lead(company)

    if added:
        print(f"{Fore.GREEN}✔ Company saved to Google Sheets!{Style.RESET_ALL}")
    else:
        print(f"{Fore.YELLOW}⚠ Already exists (duplicate){Style.RESET_ALL}")

    # Show stats
    stats = get_stats()
    print(f"\n📊 Sheet stats: {stats['total']} total | {stats['pending']} pending | {stats['emailed']} emailed\n")


if __name__ == "__main__":
    main()
