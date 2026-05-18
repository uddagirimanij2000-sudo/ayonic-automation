"""
tools/ai_categorizer.py

AI-powered lead categorizer using Groq.
Reads company name + website text and assigns a service category.

Categories:
  cleaning, office-cleaning, facility-management, pest-control,
  moving, painting, plumbing, electrical, handyman, gardening,
  security, construction, other

Usage:
    python main.py categorize              Categorize uncategorized leads
    python main.py categorize --dry-run    Preview without updating Sheet
"""

from __future__ import annotations
from colorama import Fore, Style
import config


CATEGORIES = [
    "cleaning",            # Reinigung, Gebäudereinigung
    "office-cleaning",     # Büroreinigung
    "facility-management", # Facility Management, Hausmeister
    "window-cleaning",     # Fensterreinigung, Glasreinigung
    "carpet-cleaning",     # Teppichreinigung
    "pest-control",        # Schädlingsbekämpfung
    "moving",              # Umzug
    "painting",            # Maler
    "plumbing",            # Klempner, Sanitär
    "electrical",          # Elektriker
    "handyman",            # Handwerker
    "gardening",           # Garten, Landschaftsbau
    "security",            # Sicherheit, Wachdienst
    "construction",        # Bau, Renovierung
    "other",               # Everything else
]


def categorize_single(company_name: str, website_text: str = "") -> str:
    """Use Groq AI to categorize a single company."""
    try:
        from groq import Groq
        client = Groq(api_key=config.GROQ_API_KEY)

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": f"""Categorize this company into EXACTLY ONE category.

Company: {company_name}
Website text: {website_text[:500]}

Categories: {', '.join(CATEGORIES)}

Reply with ONLY the category name, nothing else. Example: cleaning"""}],
            max_tokens=20,
            temperature=0,
        )

        result = response.choices[0].message.content.strip().lower()
        # Validate against known categories
        for cat in CATEGORIES:
            if cat in result:
                return cat
        return "other"

    except Exception:
        # Fallback: keyword-based categorization
        return _keyword_categorize(company_name, website_text)


def _keyword_categorize(company_name: str, website_text: str = "") -> str:
    """Fallback keyword-based categorizer."""
    text = f"{company_name} {website_text}".lower()

    keyword_map = {
        "office-cleaning": ["büroreinigung", "office cleaning", "büro reinigung"],
        "window-cleaning": ["fensterreinigung", "glasreinigung", "window clean"],
        "carpet-cleaning": ["teppichreinigung", "carpet clean", "polsterreinigung"],
        "facility-management": ["facility", "hausmeister", "gebäudemanagement", "hausverwaltung"],
        "pest-control": ["schädling", "pest", "kammerjäger"],
        "moving": ["umzug", "moving", "transport", "umzüge"],
        "painting": ["maler", "painting", "anstrich", "lackier"],
        "plumbing": ["klempner", "sanitär", "plumbing", "rohr"],
        "electrical": ["elektr", "electrical", "strom"],
        "handyman": ["handwerk", "handyman", "montage"],
        "gardening": ["garten", "garden", "landschaft", "grünpflege"],
        "security": ["sicherheit", "security", "wachdienst", "bewachung"],
        "construction": ["bau", "renovierung", "construction", "sanierung"],
        "cleaning": ["reinigung", "cleaning", "clean", "putzen", "sauber"],
    }

    for category, keywords in keyword_map.items():
        for kw in keywords:
            if kw in text:
                return category

    return "other"


def run_categorizer(dry_run: bool = False):
    """Categorize all uncategorized leads using AI."""
    from sheets.sheets_client import get_all_leads, update_lead_field

    leads = get_all_leads()

    # Find leads with empty or generic category
    uncategorized = []
    for i, lead in enumerate(leads):
        category = str(lead.get("Category", "")).strip()
        if not category or category.lower() in ("unknown", "general", ""):
            name = str(lead.get("Company Name", "")).strip()
            desc = str(lead.get("Description", "")).strip()
            if name:
                uncategorized.append({
                    "row_idx": i + 2,
                    "name": name,
                    "description": desc,
                })

    mode = "(DRY RUN)" if dry_run else ""
    print(f"\n{Fore.CYAN}▶ AI Lead Categorizer {mode}{Style.RESET_ALL}")
    print(f"  {len(uncategorized)} leads need categorization")

    if not uncategorized:
        print(f"\n{Fore.GREEN}✔ All leads already categorized{Style.RESET_ALL}\n")
        return

    # Batch categorize (up to 10 at a time to save API calls)
    batch_size = 10
    categorized = 0
    total = len(uncategorized)

    for batch_start in range(0, total, batch_size):
        batch = uncategorized[batch_start:batch_start + batch_size]

        # Try batch AI categorization
        try:
            from groq import Groq
            client = Groq(api_key=config.GROQ_API_KEY)

            company_list = "\n".join(
                [f"{i+1}. {c['name']} — {c['description'][:100]}" for i, c in enumerate(batch)]
            )

            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": f"""Categorize each company into EXACTLY ONE category.

Companies:
{company_list}

Categories: {', '.join(CATEGORIES)}

Reply with ONLY the numbers and categories, one per line:
1. cleaning
2. office-cleaning
etc."""}],
                max_tokens=200,
                temperature=0,
            )

            result = response.choices[0].message.content.strip()
            lines = result.split("\n")

            for j, company in enumerate(batch):
                # Parse AI response
                assigned = "other"
                for line in lines:
                    if line.strip().startswith(f"{j+1}"):
                        for cat in CATEGORIES:
                            if cat in line.lower():
                                assigned = cat
                                break
                        break

                progress = f"[{batch_start + j + 1}/{total}]"
                print(f"  {Fore.CYAN}{progress}{Style.RESET_ALL} {company['name'][:40]:<40} → {Fore.GREEN}{assigned}{Style.RESET_ALL}")

                if not dry_run:
                    update_lead_field(company["row_idx"], "Category", assigned)

                categorized += 1

        except Exception as e:
            # Fallback: keyword-based
            print(f"  {Fore.YELLOW}AI batch failed, using keywords: {e}{Style.RESET_ALL}")
            for j, company in enumerate(batch):
                assigned = _keyword_categorize(company["name"], company["description"])
                progress = f"[{batch_start + j + 1}/{total}]"
                print(f"  {Fore.CYAN}{progress}{Style.RESET_ALL} {company['name'][:40]:<40} → {Fore.YELLOW}{assigned} (keyword){Style.RESET_ALL}")

                if not dry_run:
                    update_lead_field(company["row_idx"], "Category", assigned)
                categorized += 1

    print(f"\n{Fore.GREEN}✔ Done — {categorized} leads categorized{Style.RESET_ALL}\n")
