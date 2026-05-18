# Lead Generation Automation

Automatically finds local service businesses (cleaners, plumbers, electricians, etc.) on **Google Maps** and **Instagram**, extracts contact info, stores everything in **Google Sheets**, and sends outreach emails after a 5-day delay.

---

## 📋 How It Works

```
Every 2 days → Scrape Google Maps + Instagram + Company Websites
                    ↓
              Save to Google Sheets (Leads tab)
                    ↓
Every day   → Check: is any lead >= 5 days old?
                    ↓
              Yes → Send personalized email
                    ↓
              Update Google Sheets (status = "emailed")
```

---

## ⚙️ Setup (One Time)

### 1. Install Python dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Create your `.env` file
```bash
cp .env.example .env
```
Then fill in your values:

| Key | Where to get it |
|-----|----------------|
| `GOOGLE_SHEET_ID` | From your Google Sheet URL: `...spreadsheets/d/THIS_PART/edit` |
| `GOOGLE_MAPS_API_KEY` | [Google Cloud Console](https://console.cloud.google.com) → Enable Places API |
| `GMAIL_USER` | Your Gmail address |
| `GMAIL_APP_PASSWORD` | Gmail → Account → Security → App Passwords |
| `APIFY_TOKEN` | [apify.com](https://apify.com) (optional, for Instagram) |

### 3. Add Google Service Account
1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a project → Enable **Google Sheets API** + **Google Drive API**
3. Create a **Service Account** → Download `credentials.json`
4. Place `credentials.json` in the `automation/` folder
5. Share your Google Sheet with the service account email (Editor access)

### 4. Configure keywords & locations
Edit `config.py`:
```python
KEYWORDS  = ["cleaner", "plumber", "electrician", ...]
LOCATIONS = ["Lisbon", "Porto", ...]
```

### 5. First-time setup
```bash
python main.py setup
```
This creates the **Leads** and **Email Log** tabs in your Google Sheet.

---

## 🚀 Running

### Option A — Automatic (Recommended)
```bash
python scheduler.py
```
Runs in the background. Scrapes every 2 days, emails every day (if leads are ≥ 5 days old). Keep the terminal open (or use `nohup`).

### Option B — Manual (for testing)
```bash
python main.py scrape               # Run scraper right now
python main.py send-emails          # Send emails right now
python main.py send-emails --dry-run # Preview without sending
python main.py status               # Show lead counts
```

---

## 📊 Google Sheets Structure

### Leads tab
| Column | Description |
|--------|-------------|
| Company Name | Business name |
| Category | e.g. "plumber" |
| Location | e.g. "Lisbon" |
| Phone | Phone number |
| Email | Contact email |
| Website | Company website |
| Instagram | Instagram profile URL |
| Source | "Google Maps" or "Instagram" |
| Date Found | When scraped |
| Days Since Found | Auto-calculated |
| Email Send Date | When email was sent |
| Status | `pending` / `emailed` / `no email` |

### Email Log tab
Tracks every email sent — company, address, date, and template used.

---

## 🔑 API Keys Summary

| API | Free Tier | Required? |
|-----|-----------|-----------|
| Google Sheets API | Free | ✅ Yes |
| Google Maps Places API | $200/month free credit | ✅ Yes |
| Gmail App Password | Free | ✅ Yes |
| Apify (Instagram) | $5/month | ⚠️ Optional |
| instagrapi (Instagram) | Free | ⚠️ Optional |

---

## 📁 Project Structure

```
automation/
├── main.py           → Manual CLI
├── scheduler.py      → Automatic background runner
├── config.py         → All settings (keywords, locations, timing)
├── .env              → Your secret API keys (never commit!)
├── credentials.json  → Google Service Account key (never commit!)
├── scrapers/
│   ├── google_scraper.py    → Google Maps scraper
│   ├── instagram_scraper.py → Instagram scraper
│   └── web_scraper.py       → Website email extractor
├── sheets/
│   └── sheets_client.py     → Google Sheets read/write
└── mailer/
    └── email_sender.py      → Email sender with 5-day delay
```
