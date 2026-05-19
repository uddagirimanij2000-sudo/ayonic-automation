# 🚀 GitHub Actions Setup Guide

This guide sets up the full automation to run **24/7 on GitHub** — no laptop needed.

---

## Daily Schedule (Berlin Time)

| Time  | Job                    | What it does                              |
|-------|------------------------|-------------------------------------------|
| 08:00 | 📊 Daily Report        | Sends ntfy summary to your phone          |
| 11:00 | 🔍 Scraper (every 3d)  | Scrapes new leads → Google Sheets         |
| 12:45 | 🚫 Unsubscribe Check   | Blocks leads who requested removal        |
| 13:00 | ✉️ Send Emails         | Sends outreach + follow-ups (400/day max) |
| 14:30 | 📬 Reply Check         | Detects replies → instant ntfy alert      |

---

## Step 1 — Push Code to GitHub

```bash
cd "/Users/manoj/Documents/unwanted photos/automation"

git init
git remote add origin https://github.com/YOUR_USERNAME/ayonic-automation.git
git add .
git commit -m "Initial commit — Ayonic lead automation"
git push -u origin main
```

> ⚠️ **Make sure `.env` and `credentials.json` are in `.gitignore` (they already are)**

---

## Step 2 — Add GitHub Secrets

Go to your repo → **Settings → Secrets and variables → Actions → New repository secret**

Add these secrets one by one:

| Secret Name               | Where to find it                          |
|---------------------------|-------------------------------------------|
| `GMAIL_USER`              | `team@ayonic.com`                         |
| `GMAIL_APP_PASSWORD`      | Your Gmail app password (from `.env`)     |
| `GOOGLE_SHEET_ID`         | From your `.env` file                     |
| `NTFY_TOPIC`              | From your `.env` (e.g. `ayonic-leads`)    |
| `GOOGLE_CREDENTIALS_JSON` | See Step 3 below ↓                        |
| `GEMINI_API_KEY`          | From your `.env` (optional)               |
| `GROQ_API_KEY`            | From your `.env` (optional)               |
| `GOOGLE_MAPS_API_KEY`     | From your `.env` (optional)               |

---

## Step 3 — Encode credentials.json as Base64

Run this on your Mac terminal:

```bash
base64 -i "/Users/manoj/Documents/unwanted photos/automation/credentials.json" | pbcopy
```

Then paste the output as the value of `GOOGLE_CREDENTIALS_JSON` secret.

---

## Step 4 — Verify It Works

1. Go to your repo → **Actions** tab
2. Click **"1. Daily Report"** → **"Run workflow"** → **Run**
3. Check your phone for the ntfy notification
4. If it works → all other jobs will run automatically on schedule ✅

---

## Manual Triggers

You can trigger any job manually from GitHub Actions → select workflow → "Run workflow"

Useful for:
- Running the scraper immediately
- Testing the email sender
- Checking for replies on demand

---

## Cost

GitHub Actions is **completely free** for this usage:
- Public repo: unlimited minutes
- Private repo: 2,000 min/month free (we use ~400 min/month)

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Workflow not running | Check cron syntax — GitHub uses UTC |
| `credentials.json` error | Re-encode and update `GOOGLE_CREDENTIALS_JSON` secret |
| Email not sending | Verify `GMAIL_USER` + `GMAIL_APP_PASSWORD` secrets |
| ntfy not working | Check `NTFY_TOPIC` secret matches your ntfy subscription |
