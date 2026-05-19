"""
scheduler.py
Background automation engine.
  - Runs all scrapers every 2 days at 08:00
    (Google + Instagram + Social Media + Web enrichment)
  - Runs the email checker every day at 09:00

Usage:
    python scheduler.py
"""

import logging
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from colorama import Fore, Style, init

init(autoreset=True)
logging.basicConfig(level=logging.WARNING)

import config
from sheets.sheets_client import ensure_sheets_exist, add_lead, get_all_leads
from scrapers.google_scraper import run_google_scraper
from scrapers.instagram_scraper import run_instagram_scraper
from scrapers.social_scraper import run_social_scraper
from scrapers.web_scraper import enrich_companies_with_web_data
from scrapers.deduplicator import deduplicate_batch, filter_existing_leads
from mailer.email_sender import run_email_sender
from mailer.contact_form import run_contact_form_outreach
from mailer.followup_sender import run_followup_sender
from mailer.reply_detector import run_reply_detector
from mailer.unsubscribe_handler import run_unsubscribe_handler


def scrape_job():
    """Full scrape cycle: Google + Instagram + Social + Web → Google Sheets."""
    print(f"\n{Fore.CYAN}{'='*55}")
    print(f"🕗 SCRAPE JOB — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*55}{Style.RESET_ALL}\n")

    companies = []

    # 1. Google (free search / SerpAPI / Maps API)
    print(f"{Fore.CYAN}▶ Google scraper...{Style.RESET_ALL}")
    companies.extend(run_google_scraper())

    # 2. Instagram
    print(f"\n{Fore.CYAN}▶ Instagram scraper...{Style.RESET_ALL}")
    companies.extend(run_instagram_scraper())

    # 3. Social Media (Facebook, LinkedIn, TikTok, Twitter/X, YouTube)
    print(f"\n{Fore.CYAN}▶ Social media scrapers...{Style.RESET_ALL}")
    companies.extend(run_social_scraper())

    # 4. Enrich with email/instagram from company websites
    print(f"\n{Fore.CYAN}▶ Website enrichment...{Style.RESET_ALL}")
    companies = enrich_companies_with_web_data(companies)

    # 5. Stage 1: deduplicate the in-memory batch (cross-source)
    companies = deduplicate_batch(companies)

    # 6. Stage 2: filter out companies already in Google Sheets
    existing_leads = get_all_leads()
    companies = filter_existing_leads(companies, existing_leads)

    # 7. Save only the new unique companies
    added = 0
    for company in companies:
        if add_lead(company):
            added += 1

    print(f"\n{Fore.GREEN}✔ Scrape complete — {added} new unique leads added{Style.RESET_ALL}\n")


def email_job():
    """Check for leads aged >= 5 days and send outreach emails."""
    run_email_sender()


def contact_form_job():
    """Submit contact forms for leads with no email address."""
    run_contact_form_outreach()


def followup_job():
    """Send follow-up emails to leads that haven't replied."""
    print(f"\n{Fore.CYAN}{'='*55}")
    print(f"🔄 FOLLOW-UP JOB — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*55}{Style.RESET_ALL}\n")
    run_followup_sender()


def reply_check_job():
    """Check Gmail inbox for replies from leads."""
    print(f"\n{Fore.CYAN}{'='*55}")
    print(f"📬 REPLY CHECK — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*55}{Style.RESET_ALL}\n")
    run_reply_detector()


def unsubscribe_job():
    """Scan inbox for unsubscribe requests and block those leads."""
    print(f"\n{Fore.CYAN}{'='*55}")
    print(f"🚫 UNSUBSCRIBE CHECK — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*55}{Style.RESET_ALL}\n")
    run_unsubscribe_handler()


def daily_report_job():
    """Send daily ntfy summary every morning at 08:00."""
    print(f"\n{Fore.CYAN}{'='*55}")
    print(f"📊 DAILY REPORT — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*55}{Style.RESET_ALL}\n")
    from tools.phone_notify import notify_daily_report
    notify_daily_report()


def _next_run_time(hour: int):
    """Return today's date at given hour, or tomorrow if already passed."""
    from datetime import datetime, timedelta
    now = datetime.now()
    run_time = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if run_time <= now:
        run_time += timedelta(days=1)
    return run_time


def main():
    ensure_sheets_exist()

    scheduler = BlockingScheduler(timezone="Europe/Berlin")

    # Scrape every 2 days
    scheduler.add_job(
        scrape_job,
        trigger=IntervalTrigger(
            days=config.SCRAPE_INTERVAL_DAYS,
            start_date=_next_run_time(config.SCRAPE_HOUR)
        ),
        id="scrape_job",
        name="Scrape companies (all sources)",
        misfire_grace_time=3600,
        replace_existing=True,
    )

    # Email check every day
    scheduler.add_job(
        email_job,
        trigger=CronTrigger(hour=config.EMAIL_CHECK_HOUR, minute=0),
        id="email_job",
        name="Send outreach emails",
        misfire_grace_time=3600,
        replace_existing=True,
    )

    # Contact form check daily (30 min after email job)
    scheduler.add_job(
        contact_form_job,
        trigger=CronTrigger(hour=config.EMAIL_CHECK_HOUR, minute=30),
        id="contact_form_job",
        name="Submit contact forms (no-email leads)",
        misfire_grace_time=3600,
        replace_existing=True,
    )

    # Follow-up emails daily (1 hour after initial emails)
    followup_hour = config.EMAIL_CHECK_HOUR + 1
    scheduler.add_job(
        followup_job,
        trigger=CronTrigger(hour=followup_hour, minute=0),
        id="followup_job",
        name="Send follow-up emails (3d + 7d)",
        misfire_grace_time=3600,
        replace_existing=True,
    )

    # Reply detection — runs 30 min before follow-ups
    scheduler.add_job(
        reply_check_job,
        trigger=CronTrigger(hour=followup_hour - 1, minute=30),
        id="reply_check_job",
        name="Check Gmail for replies",
        misfire_grace_time=3600,
        replace_existing=True,
    )

    # Unsubscribe check — runs 15 min before email job (so blocked leads are skipped)
    unsub_hour   = config.EMAIL_CHECK_HOUR
    unsub_minute = 45  # runs at 12:45 before email job at 13:00
    scheduler.add_job(
        unsubscribe_job,
        trigger=CronTrigger(hour=unsub_hour - 1, minute=unsub_minute),
        id="unsubscribe_job",
        name="Check inbox for unsubscribe requests",
        misfire_grace_time=3600,
        replace_existing=True,
    )

    # Daily morning report via ntfy — runs at 08:00 every day
    scheduler.add_job(
        daily_report_job,
        trigger=CronTrigger(hour=8, minute=0),
        id="daily_report_job",
        name="Daily ntfy summary report",
        misfire_grace_time=3600,
        replace_existing=True,
    )

    print(f"\n{Fore.GREEN}{'='*55}")
    print(f"🤖 Lead Generation Scheduler — RUNNING")
    print(f"{'='*55}")
    print(f"  Daily report  : every morning at 08:00 (ntfy)")
    print(f"  Scrape        : every {config.SCRAPE_INTERVAL_DAYS} days at {config.SCRAPE_HOUR:02d}:00")
    print(f"  Sources       : Google + Instagram + FB + LinkedIn + TikTok + Twitter/X + YouTube")
    print(f"  Emails        : daily at {config.EMAIL_CHECK_HOUR:02d}:00 (leads >= {config.EMAIL_DELAY_DAYS} days old)")
    print(f"  Follow-ups    : daily at {followup_hour:02d}:00 (3d + 7d auto)")
    print(f"  Reply check   : daily at {followup_hour-1:02d}:30 (auto-detect replies + ntfy)")
    print(f"  Unsubscribes  : daily at {unsub_hour-1:02d}:{unsub_minute} (block before email job)")
    print(f"  Contact forms : daily at {config.EMAIL_CHECK_HOUR:02d}:30 (no-email leads)")
    print(f"{'='*55}{Style.RESET_ALL}\n")
    print("Press Ctrl+C to stop.\n")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print(f"\n{Fore.YELLOW}Scheduler stopped.{Style.RESET_ALL}")


if __name__ == "__main__":
    main()
