"""
main.py
Manual CLI for testing and triggering jobs on demand.

Usage:
    python main.py setup               Create Sheets tabs (run once first)
    python main.py scrape              Run ALL scrapers now
    python main.py scrape --google     Run Google scraper only
    python main.py scrape --social     Run social media scrapers only
    python main.py scrape --instagram  Run Instagram scraper only
    python main.py send-emails         Send emails to ready leads
    python main.py send-emails --dry-run   Preview without sending
    python main.py follow-up           Send follow-up emails (3d + 7d)
    python main.py follow-up --dry-run Preview follow-ups without sending
    python main.py check-replies       Detect replies in Gmail inbox
    python main.py check-replies --dry-run Preview without updating Sheet
    python main.py categorize          AI-categorize all leads
    python main.py categorize --dry-run Preview categories without updating
    python main.py status              Show Google Sheets summary
"""

import sys
import config
from colorama import Fore, Style, init

init(autoreset=True)


def cmd_scrape(sources: list):
    from scrapers.google_scraper import run_google_scraper
    from scrapers.instagram_scraper import run_instagram_scraper
    from scrapers.social_scraper import run_social_scraper
    from scrapers.web_scraper import enrich_companies_with_web_data
    from scrapers.deduplicator import deduplicate_batch, filter_existing_leads
    from sheets.sheets_client import add_leads_batch, ensure_sheets_exist, get_all_leads

    ensure_sheets_exist()
    companies = []

    run_all = not sources  # If no flag given, run everything

    if run_all or "google" in sources:
        print(f"\n{Fore.CYAN}▶ Google scraper (free search)...{Style.RESET_ALL}")
        companies.extend(run_google_scraper())

    if run_all or "instagram" in sources:
        print(f"\n{Fore.CYAN}▶ Instagram scraper...{Style.RESET_ALL}")
        companies.extend(run_instagram_scraper())

    if run_all or "social" in sources:
        print(f"\n{Fore.CYAN}▶ Social media scrapers (Facebook/LinkedIn/TikTok/Twitter/YouTube)...{Style.RESET_ALL}")
        companies.extend(run_social_scraper())

    print(f"\n{Fore.CYAN}▶ Enriching with website data...{Style.RESET_ALL}")
    companies = enrich_companies_with_web_data(companies)

    # Stage 1: In-memory cross-source deduplication
    companies = deduplicate_batch(companies)

    # Stage 2: Load existing leads once for dedup
    print(f"\n{Fore.CYAN}▶ Checking for existing leads in Google Sheets...{Style.RESET_ALL}")
    existing_leads = get_all_leads()
    companies = filter_existing_leads(companies, existing_leads)

    # Stage 3: Write ALL new leads in ONE batch call (no 429 write quota errors)
    print(f"\n{Fore.CYAN}▶ Saving {len(companies)} new leads to Google Sheets...{Style.RESET_ALL}")
    added = add_leads_batch(companies, existing_leads=existing_leads)

    print(f"\n{Fore.GREEN}✔ Done — {added} new unique leads saved{Style.RESET_ALL}\n")


def cmd_send_emails(dry_run: bool = False, max_emails: int = None):
    from sheets.sheets_client import ensure_sheets_exist
    from mailer.email_sender import run_email_sender

    ensure_sheets_exist()
    run_email_sender(dry_run=dry_run, max_emails=max_emails)


def cmd_status():
    from sheets.sheets_client import get_stats

    stats = get_stats()
    print(f"\n{Fore.CYAN}{'─'*50}")
    print(f"  📊 Lead Generation — Google Sheets Status")
    print(f"{'─'*50}{Style.RESET_ALL}")
    print(f"  Total leads    : {stats['total']}")
    print(f"  Pending emails : {Fore.YELLOW}{stats['pending']}{Style.RESET_ALL}")
    print(f"  Emailed        : {Fore.GREEN}{stats['emailed']}{Style.RESET_ALL}")
    print(f"  No email found : {Fore.RED}{stats['no_email']}{Style.RESET_ALL}")
    print(f"\n  Data richness:")
    print(f"  With phone     : {stats.get('with_phone', 0)}")
    print(f"  With address   : {stats.get('with_address', 0)}")
    print(f"  With Instagram : {stats.get('with_instagram', 0)}")
    print(f"  With Facebook  : {stats.get('with_facebook', 0)}")
    print(f"  With LinkedIn  : {stats.get('with_linkedin', 0)}")
    print(f"{Fore.CYAN}{'─'*50}{Style.RESET_ALL}\n")


def cmd_setup():
    from sheets.sheets_client import ensure_sheets_exist
    ensure_sheets_exist()
    print(f"{Fore.GREEN}✔ Google Sheets tabs ready{Style.RESET_ALL}")


def cmd_preview_emails():
    """Preview what emails look like for each category."""
    from mailer.templates import TEMPLATES, render_email
    import config

    print(f"\n{Fore.CYAN}{'='*55}")
    print(f"  📧 EMAIL TEMPLATE PREVIEWS")
    print(f"{'='*55}{Style.RESET_ALL}\n")

    all_categories = list(TEMPLATES.keys()) + ["unknown category"]
    company_names = {
        "plumber": "ABC Plumbing",
        "cleaner": "Lisboa Clean",
        "cleaning company": "Porto Cleaning Co",
        "electrician": "Bright Electric",
        "painter": "Color Works",
        "carpenter": "Wood & Craft",
        "hvac": "CoolAir HVAC",
        "locksmith": "FastKey Locks",
        "handyman": "FixIt Pro",
        "unknown category": "Generic Business",
    }

    for category in all_categories:
        name = company_names.get(category, f"Example {category.title()}")
        subject, body = render_email(name, category, config.SENDER_NAME, config.GMAIL_USER)
        print(f"{Fore.CYAN}[{category}]{Style.RESET_ALL}")
        print(f"  Subject: {subject}")
        print(f"  Body preview: {body.split(chr(10))[2][:80]}...")
        print()


def print_help():
    print(f"""
{Fore.CYAN}Lead Generation Automation — Manual CLI{Style.RESET_ALL}

Usage:
  python main.py setup                   Create Sheets tabs (run this first!)
  python main.py clear-sheet             Clear ALL data from Leads tab (keeps headers)
  python main.py clear-sheet --all       Clear Leads + Email Log tabs
  python main.py clear-sheet --log       Clear Email Log tab only
  python main.py scrape                  Run ALL scrapers
  python main.py scrape --google         Google only
  python main.py scrape --instagram      Instagram only
  python main.py scrape --social         Facebook/LinkedIn/TikTok/Twitter/YouTube
  python main.py send-emails             Send emails to ready leads
  python main.py send-emails --dry-run   Preview without sending
  python main.py follow-up               Send follow-up emails (3d + 7d auto)
  python main.py follow-up --dry-run     Preview follow-ups without sending
  python main.py check-replies           Detect replies in Gmail inbox
  python main.py check-replies --dry-run Preview without updating Sheet
  python main.py categorize              AI-categorize all leads by service type
  python main.py categorize --dry-run    Preview without updating
  python main.py contact-forms           Auto-fill contact forms (no-email leads)
  python main.py contact-forms --dry-run Preview which forms would be submitted
  python main.py verify-emails           Verify email addresses (MX + SMTP check)
  python main.py verify-emails --dry-run Preview verification without updating Sheet
  python main.py preview-emails          Show all email templates by category
  python main.py status                  Show lead counts

Social media APIs to add in .env:
  FACEBOOK_ACCESS_TOKEN   → developers.facebook.com
  RAPIDAPI_KEY            → rapidapi.com (LinkedIn, TikTok, Twitter/X)
  YOUTUBE_API_KEY         → Google Cloud Console (same project)

For automatic scheduling:
  python scheduler.py
""")


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help", "help"):
        print_help()

    elif args[0] == "setup":
        cmd_setup()

    elif args[0] == "clear-sheet":
        from sheets.sheets_client import clear_sheet
        if "--all" in args:
            which = "all"
        elif "--log" in args:
            which = "log"
        else:
            which = "leads"

        label = {"leads": "Leads tab", "log": "Email Log tab", "all": "ALL tabs"}[which]
        confirm = input(f"\n⚠️  This will DELETE all data from {label}. Type 'yes' to confirm: ")
        if confirm.strip().lower() == "yes":
            print()
            clear_sheet(which)
            print(f"{Fore.GREEN}✔ Done!{Style.RESET_ALL}\n")
        else:
            print(f"{Fore.YELLOW}Cancelled.{Style.RESET_ALL}\n")

    elif args[0] == "scrape":
        # Parse optional source flags
        sources = []
        if "--google" in args:
            sources.append("google")
        if "--instagram" in args:
            sources.append("instagram")
        if "--social" in args:
            sources.append("social")
        cmd_scrape(sources)

    elif args[0] == "send-emails":
        dry = "--dry-run" in args
        # Support --limit N flag
        limit = None
        if "--limit" in args:
            idx = args.index("--limit")
            if idx + 1 < len(args):
                limit = int(args[idx + 1])
        cmd_send_emails(dry_run=dry, max_emails=limit)

    elif args[0] in ("contact-forms", "fill-forms"):
        from outreach.contact_form_filler import run_contact_form_filler
        dry = "--dry-run" in args
        run_contact_form_filler(dry_run=dry)

    elif args[0] == "preview-emails":
        cmd_preview_emails()

    elif args[0] == "follow-up":
        from mailer.followup_sender import run_followup_sender
        dry = "--dry-run" in args
        run_followup_sender(dry_run=dry)

    elif args[0] == "check-replies":
        from mailer.reply_detector import run_reply_detector
        dry = "--dry-run" in args
        run_reply_detector(dry_run=dry)

    elif args[0] == "check-unsubs":
        from mailer.unsubscribe_handler import run_unsubscribe_handler
        dry = "--dry-run" in args
        run_unsubscribe_handler(dry_run=dry)

    elif args[0] == "categorize":
        from tools.ai_categorizer import run_categorizer
        dry = "--dry-run" in args
        run_categorizer(dry_run=dry)

    elif args[0] == "verify-emails":
        from tools.email_verifier import verify_leads_from_sheet
        dry = "--dry-run" in args
        verify_leads_from_sheet(dry_run=dry)

    elif args[0] == "status":
        cmd_status()

    else:
        print(f"{Fore.RED}Unknown command: {args[0]}{Style.RESET_ALL}")
        print_help()
        sys.exit(1)
