# ==============================================================================
# AI JOB SCAM DETECTION AND RECRUITER VERIFICATION SYSTEM
# With Natural Language Input Parsing (NLP-Enhanced)
# Compatible with: Google Colab (Python 3.x)
# Author: Final Year Project
# ==============================================================================
# USAGE:
#   Run each cell in Google Colab sequentially.
#   When prompted, paste any natural-language job description.
#
# EXAMPLE INPUTS:
#   "Microsoft is hiring a Software Engineer. Contact recruiter Sarah Thompson
#    at sarah@microsoft.com. Apply at https://careers.microsoft.com."
#
#   "Urgent data entry job. Earn $500 weekly. Contact on Telegram.
#    Registration fee required."
# ==============================================================================


# ==============================================================================
# CELL 1 — Install Dependencies
# Run this cell once per Colab session.
# ==============================================================================

# !pip install -q spacy requests
# !python -m spacy download en_core_web_sm -q


# ==============================================================================
# CELL 2 — Imports
# ==============================================================================

import re
import json
import socket
import urllib.parse
from difflib import SequenceMatcher

# spaCy for Named Entity Recognition (NER)
import spacy

# Load the small English NLP model
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    # Fallback: download inline if not already installed
    import subprocess, sys
    subprocess.run([sys.executable, "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")

print("✅ Libraries loaded successfully.")


# ==============================================================================
# CELL 3 — Configuration & Scam Keyword List
# ==============================================================================

# Keywords commonly found in fraudulent job postings
SCAM_KEYWORDS = [
    # Financial bait
    "earn $", "earn up to", "weekly pay", "make money fast",
    "no experience needed", "work from home and earn",
    "guaranteed income", "unlimited earnings", "passive income",
    "$500 weekly", "$1000 weekly", "$2000 weekly", "daily payment", "daily income",

    # Urgency / pressure
    "urgent hiring", "immediate joining", "apply now", "limited slots",
    "hurry", "act fast", "only a few spots left", "immediate requirement",

    # Suspicious payment / fee
    "registration fee", "processing fee", "training fee", "pay to apply",
    "refundable deposit", "send money", "western union", "wire transfer",
    "training kit", "security deposit", "bitcoin payment", "crypto payment",

    # Informal contact channels (HIGH RISK)
    "contact on whatsapp", "contact on telegram", "dm for details",
    "chat on hangouts", "google hangout", "yahoo messenger",
    "message us on telegram", "whatsapp immediately", "signal app",

    # Vague roles
    "data entry", "form filling", "simple typing job",
    "part time online job", "home-based typing", "home typing job",

    # Too-good-to-be-true
    "no qualification required", "no interview", "direct selection",
    "100% job guarantee", "assured placement", "no interview needed",
    "easy money", "quick cash", "rich quick", "online tutor needed urgent",
]

# Free / disposable email providers (commonly used in scam recruiters)
FREE_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "aol.com", "mail.com", "protonmail.com", "icloud.com",
    "yopmail.com", "guerrillamail.com", "tempmail.com",
    "mailinator.com", "trashmail.com", "sharklasers.com",
    "dispostable.com", "maildrop.cc",
}

print("✅ Configuration loaded.")


# ==============================================================================
# CELL 4 — NLP Parser: Extract Structured Data from Natural Language
# ==============================================================================

def extract_email(text: str) -> str:
    """
    Use regex to extract the first email address found in text.
    Returns the email string, or empty string if none found.
    """
    pattern = r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
    match = re.search(pattern, text)
    return match.group(0).lower() if match else ""


def extract_url(text: str) -> str:
    """
    Use regex to extract the first URL found in text.
    Returns the URL string, or empty string if none found.
    """
    pattern = r"https?://[^\s,\)\]>\"\']*"
    match = re.search(pattern, text)
    return match.group(0).rstrip(".") if match else ""


def extract_entities_spacy(text: str) -> dict:
    """
    Use spaCy Named Entity Recognition (NER) to extract:
      - ORG   → Company name
      - PERSON → Recruiter name
      - MONEY  → Salary hints (used as a red flag signal)

    Returns a dict with keys: 'company', 'recruiter_name', 'salary_mention'
    """
    doc = nlp(text)
    company = ""
    recruiter_name = ""
    salary_mention = ""

    for ent in doc.ents:
        label = ent.label_
        value = ent.text.strip()

        if label == "ORG" and not company:
            company = value

        elif label == "PERSON" and not recruiter_name:
            recruiter_name = value

        elif label == "MONEY" and not salary_mention:
            salary_mention = value

    return {
        "company": company,
        "recruiter_name": recruiter_name,
        "salary_mention": salary_mention,
    }


def extract_job_title(text: str, company: str) -> str:
    """
    Attempt to extract job title using common patterns like:
      - "hiring a/an <Title>"
      - "looking for a/an <Title>"
      - "position of <Title>"
      - "role of <Title>"
      - Fallback: first NOUN PHRASE that doesn't match company name
    """
    patterns = [
        r"hiring (?:a|an)\s+([A-Za-z][A-Za-z\s\-/]{2,40}?)(?:\.|,|$|\n)",
        r"looking for (?:a|an)\s+([A-Za-z][A-Za-z\s\-/]{2,40}?)(?:\.|,|$|\n)",
        r"position of\s+([A-Za-z][A-Za-z\s\-/]{2,40}?)(?:\.|,|$|\n)",
        r"role of\s+([A-Za-z][A-Za-z\s\-/]{2,40}?)(?:\.|,|$|\n)",
        r"vacancy for\s+([A-Za-z][A-Za-z\s\-/]{2,40}?)(?:\.|,|$|\n)",
        r"opening for\s+([A-Za-z][A-Za-z\s\-/]{2,40}?)(?:\.|,|$|\n)",
        r"seeking\s+(?:a |an )?([A-Za-z][A-Za-z\s\-/]{2,40}?)(?:\.|,|$|\n)",
    ]

    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            # Remove trailing common words
            title = re.sub(r"\s+(to|and|for|with|at|in)$", "", title, flags=re.IGNORECASE)
            return title.title()

    # Fallback: use spaCy noun chunks, pick one that looks like a job title
    doc = nlp(text)
    job_keywords = ["engineer", "manager", "developer", "analyst", "designer",
                    "consultant", "officer", "executive", "intern", "assistant",
                    "coordinator", "specialist", "director", "lead", "entry"]
    for chunk in doc.noun_chunks:
        chunk_lower = chunk.text.lower()
        if any(kw in chunk_lower for kw in job_keywords):
            return chunk.text.strip().title()

    return "Not Detected"


def parse_natural_input(raw_text: str) -> dict:
    """
    Master NLP extraction function.

    Takes a raw natural-language job description string and returns a
    structured job_data dictionary with the following keys:
      - job_title
      - company
      - recruiter_name
      - recruiter_email
      - company_website
      - job_description   (original text, kept for keyword scanning)
      - salary_mention    (bonus field for risk scoring)

    Steps:
      1. Regex → extract email, URL
      2. spaCy NER → extract ORG (company), PERSON (recruiter), MONEY (salary)
      3. Pattern matching → extract job title
    """
    print("\n🔍 Parsing natural language input...")

    # Step 1: Regex extraction
    email = extract_email(raw_text)
    website = extract_url(raw_text)

    # Step 2: spaCy NER
    ner_results = extract_entities_spacy(raw_text)
    company = ner_results["company"]
    recruiter_name = ner_results["recruiter_name"]
    salary_mention = ner_results["salary_mention"]

    # Step 3: Job title extraction
    job_title = extract_job_title(raw_text, company)

    # Build structured job_data
    job_data = {
        "job_title": job_title,
        "company": company if company else "Unknown",
        "recruiter_name": recruiter_name if recruiter_name else "Unknown",
        "recruiter_email": email,
        "company_website": website,
        "job_description": raw_text.strip(),
        "salary_mention": salary_mention,   # used internally for scoring
    }

    print("✅ Extraction complete.")
    return job_data


# ==============================================================================
# CELL 5 — Verification Modules (Fraud Detection Pipeline)
# ==============================================================================

def check_free_email(email: str) -> bool:
    """
    Returns True if the email uses a free/public email provider.
    Free email in a recruiter's contact is a suspicious signal.
    """
    if not email or "@" not in email:
        return False
    domain = email.split("@")[-1].lower()
    return domain in FREE_EMAIL_DOMAINS


def get_email_domain(email: str) -> str:
    """Extract the domain part from an email address."""
    if not email or "@" not in email:
        return ""
    return email.split("@")[-1].lower()


def domain_matches_company(email: str, company: str, website: str) -> bool:
    """
    Checks whether the email domain matches the company name or website domain.

    Matching logic (in order):
      1. If website URL is provided, compare email domain to website domain.
      2. Else if company name is provided, do a fuzzy similarity check.
      3. Return False if neither is available.
    """
    email_domain = get_email_domain(email)
    if not email_domain:
        return False

    # Strip leading 'www.' from website domain
    if website:
        try:
            parsed = urllib.parse.urlparse(website)
            site_domain = parsed.netloc.lower().lstrip("www.")
            if email_domain == site_domain:
                return True
            # Check if email domain is a subdomain of the site domain
            if email_domain.endswith("." + site_domain):
                return True
        except Exception:
            pass

    # Fuzzy match: compare email domain (strip TLD) against company name tokens
    if company and company.lower() != "unknown":
        email_name = email_domain.split(".")[0]  # e.g. "microsoft" from "microsoft.com"
        company_tokens = re.findall(r"[a-zA-Z]+", company.lower())
        for token in company_tokens:
            ratio = SequenceMatcher(None, email_name, token).ratio()
            if ratio >= 0.75:
                return True

    return False


def detect_scam_keywords(text: str) -> list:
    """
    Scan job_description for known scam/fraud indicator phrases.
    Returns a list of matched keywords (lowercased).
    """
    text_lower = text.lower()
    found = []
    for kw in SCAM_KEYWORDS:
        if kw.lower() in text_lower:
            found.append(kw)
    return found


def check_domain_exists(domain: str) -> bool:
    """
    Attempt a DNS resolution to verify whether the domain is a real,
    reachable hostname on the internet.
    Returns True if the domain resolves (exists), False otherwise.
    """
    if not domain:
        return False
    try:
        socket.setdefaulttimeout(4)
        socket.getaddrinfo(domain, None)
        return True
    except (socket.gaierror, socket.timeout):
        return False


def search_recruiter_online(recruiter_name: str, company: str) -> dict:
    """
    Produce search query suggestions for manual recruiter verification.
    (Actual web scraping requires an API key; this generates ready-to-use
    search URLs for LinkedIn, Google, and a scam report site.)

    Returns:
        dict with keys: linkedin_url, google_url, scam_check_url
    """
    if recruiter_name == "Unknown" and company == "Unknown":
        return {}

    query_parts = []
    if recruiter_name and recruiter_name != "Unknown":
        query_parts.append(recruiter_name)
    if company and company != "Unknown":
        query_parts.append(company)

    query = " ".join(query_parts)
    encoded = urllib.parse.quote_plus(query)

    return {
        "linkedin_url": f"https://www.linkedin.com/search/results/people/?keywords={encoded}",
        "google_url": f"https://www.google.com/search?q={encoded}+recruiter+scam",
        "scam_check_url": f"https://www.scamadviser.com/check-website/{urllib.parse.quote_plus(get_email_domain(query))}",
    }


# ==============================================================================
# CELL 6 — Risk Scoring Engine
# ==============================================================================

def calculate_risk_score(
    is_free_email: bool,
    domain_matches: bool,
    scam_keywords: list,
    domain_exists: bool,
    salary_mention: str,
    has_email: bool,
    has_website: bool,
) -> int:
    """
    Compute a risk score from 0 to 100. Higher = more likely a scam.

    Scoring weights:
      +25  Free/personal email used by recruiter
      +20  Domain does NOT match company name or website
      +5   Each scam keyword found (capped at 30 points)
      +15  Domain does NOT exist / cannot be resolved
      +10  Salary mention detected AND free email used (financial bait combo)
      -10  Has a verifiable website (legitimacy signal)
      -5   Has a corporate email (legitimacy signal)
    """
    score = 0

    if is_free_email:
        score += 25

    if has_email and not domain_matches:
        score += 20

    # Scam keywords: 10 pts each, no max cap (more red flags = higher score)
    keyword_score = len(scam_keywords) * 10
    score += keyword_score

    if not domain_exists and has_email:
        score += 15

    # Financial bait combo: salary claim + free email
    if salary_mention and is_free_email:
        score += 10

    # Legitimacy deductions
    if has_website and domain_exists:
        score -= 10

    if has_email and not is_free_email:
        score -= 5

    # Clamp to [0, 100]
    return max(0, min(score, 100))


def get_verdict(score: int) -> str:
    """
    Convert numerical risk score to a human-readable verdict.
    Thresholds:
      0–19  → Likely Genuine
      20–59 → Suspicious
      60+   → High Scam Risk
    """
    if score < 20:
        return "✅ Likely Genuine"
    elif score <= 59:
        return "⚠️  Suspicious"
    else:
        return "🚨 High Scam Risk"


# ==============================================================================
# CELL 7 — Report Generator
# ==============================================================================

def generate_report(job_data: dict, analysis: dict) -> str:
    """
    Format and return the final job verification report as a string.

    Parameters:
        job_data : dict — structured job information extracted from NLP
        analysis : dict — results from the fraud detection pipeline
    """
    verdict = get_verdict(analysis["risk_score"])
    kw_display = (", ".join(analysis["scam_keywords"])
                  if analysis["scam_keywords"] else "None")

    report = f"""
{'=' * 55}
        AI JOB SCAM DETECTION — VERIFICATION REPORT
{'=' * 55}
  Job Title           : {job_data['job_title']}
  Company             : {job_data['company']}
  Recruiter Name      : {job_data['recruiter_name']}
  Recruiter Email     : {job_data['recruiter_email'] or 'Not Provided'}
  Company Website     : {job_data['company_website'] or 'Not Provided'}
{'─' * 55}
  Email Domain        : {analysis['email_domain'] or 'N/A'}
  Free Email Used     : {'YES ⚠️' if analysis['is_free_email'] else 'No'}
  Domain Matches Co.  : {'Yes ✅' if analysis['domain_matches'] else 'NO ⚠️'}
  Domain Exists (DNS) : {'Yes ✅' if analysis['domain_exists'] else 'NO ⚠️'}
{'─' * 55}
  Scam Keywords Found : {kw_display}
  Salary Mention      : {job_data.get('salary_mention') or 'None'}
{'─' * 55}
  Risk Score          : {analysis['risk_score']} / 100
  Final Verdict       : {verdict}
{'=' * 55}"""

    # Append recruiter search links if available
    links = analysis.get("search_links", {})
    if links:
        report += "\n\n  🔎 Verify Recruiter:\n"
        if "linkedin_url" in links:
            report += f"     LinkedIn  → {links['linkedin_url']}\n"
        if "google_url" in links:
            report += f"     Google    → {links['google_url']}\n"

    return report


# ==============================================================================
# CELL 8 — Main Pipeline Orchestrator
# ==============================================================================

def run_detection_pipeline(raw_text: str) -> None:
    """
    Master function that runs the full detection pipeline:

    Step 1: NLP Extraction — parse natural-language text → job_data dict
    Step 2: Email Analysis — free email check, domain extraction
    Step 3: Domain Verification — domain match + DNS resolution
    Step 4: Scam Keywords — scan job description
    Step 5: Risk Scoring — compute 0–100 score
    Step 6: Report Generation — print formatted report

    Parameters:
        raw_text : str — any natural-language job posting text
    """
    print("\n" + "=" * 55)
    print("  🚀 Starting Job Scam Detection Pipeline...")
    print("=" * 55)

    # ── Step 1: NLP Extraction ──────────────────────────────────────
    job_data = parse_natural_input(raw_text)
    print("\n📋 Extracted Job Data:")
    for key, value in job_data.items():
        if key != "job_description":  # skip printing full text again
            print(f"   {key:<20}: {value}")

    # ── Step 2: Email Analysis ──────────────────────────────────────
    email = job_data["recruiter_email"]
    has_email = bool(email)
    is_free_email = check_free_email(email)
    email_domain = get_email_domain(email)

    # ── Step 3: Domain Verification ─────────────────────────────────
    domain_matches = domain_matches_company(
        email, job_data["company"], job_data["company_website"]
    )
    domain_exists = check_domain_exists(email_domain) if email_domain else False

    # ── Step 4: Scam Keyword Detection ──────────────────────────────
    scam_keywords = detect_scam_keywords(job_data["job_description"])

    # ── Step 5: Risk Scoring ─────────────────────────────────────────
    risk_score = calculate_risk_score(
        is_free_email=is_free_email,
        domain_matches=domain_matches,
        scam_keywords=scam_keywords,
        domain_exists=domain_exists,
        salary_mention=job_data.get("salary_mention", ""),
        has_email=has_email,
        has_website=bool(job_data["company_website"]),
    )

    # ── Recruiter Search Links ────────────────────────────────────────
    search_links = search_recruiter_online(
        job_data["recruiter_name"], job_data["company"]
    )

    # Bundle analysis results
    analysis = {
        "email_domain": email_domain,
        "is_free_email": is_free_email,
        "domain_matches": domain_matches,
        "domain_exists": domain_exists,
        "scam_keywords": scam_keywords,
        "risk_score": risk_score,
        "search_links": search_links,
    }

    # ── Step 6: Print Report ──────────────────────────────────────────
    print(generate_report(job_data, analysis))


# ==============================================================================
# CELL 9 — Interactive Mode (Google Colab Entry Point)
# ==============================================================================

def main():
    """
    Interactive entry point for Google Colab.
    Prompts the user to paste a natural-language job description,
    then runs the full detection pipeline.
    Type 'EXIT' to quit.
    """
    print("""
╔══════════════════════════════════════════════════════╗
║   AI Job Scam Detection & Recruiter Verification     ║
║   Natural Language Input Mode  (NLP-Enhanced)        ║
╚══════════════════════════════════════════════════════╝

Paste a job description in plain English.
Type  EXIT  to quit.
""")

    while True:
        print("─" * 55)
        raw_input_text = input("📝 Enter job description:\n> ").strip()

        if raw_input_text.upper() == "EXIT":
            print("👋 Exiting. Goodbye!")
            break

        if len(raw_input_text) < 10:
            print("⚠️  Input too short. Please enter a more complete description.")
            continue

        run_detection_pipeline(raw_input_text)
        print("\n")


# ==============================================================================
# CELL 10 — Run Demo with Built-in Examples
# ==============================================================================

def run_demo():
    """
    Runs the pipeline on three built-in example inputs:
      1. Legitimate job (Microsoft)
      2. Obvious scam (data entry / fee-based)
      3. Borderline suspicious (Accenture with Gmail)
    """
    examples = [
        # ── Example 1: Legitimate ──────────────────────────────────────────
        (
            "Example 1 — Legitimate Job Posting",
            "Microsoft is hiring a Software Engineer. "
            "Contact recruiter Sarah Thompson at sarah@microsoft.com. "
            "Apply at https://careers.microsoft.com. "
            "The role involves working on Azure cloud services."
        ),

        # ── Example 2: Obvious Scam ───────────────────────────────────────
        (
            "Example 2 — Obvious Scam",
            "URGENT! Data entry job. Earn $500 weekly. No experience needed. "
            "Work from home. Contact us on Telegram or WhatsApp. "
            "Registration fee required. Limited slots available. Apply now!"
        ),

        # ── Example 3: Borderline Suspicious ─────────────────────────────
        (
            "Example 3 — Suspicious (Corporate name + Gmail)",
            "Accenture is looking for a Business Analyst. "
            "If interested, send your CV to recruiter Mike Johnson at "
            "mikejohnson.recruiter@gmail.com. Guaranteed placement. "
            "No interview required."
        ),
    ]

    for title, text in examples:
        print(f"\n{'#' * 55}")
        print(f"  🧪 DEMO: {title}")
        print(f"{'#' * 55}")
        print(f"  Input Text:\n  \"{text}\"\n")
        run_detection_pipeline(text)
        print()


# ==============================================================================
# CELL 11 — Choose Mode and Run
# ==============================================================================
# Uncomment ONE of the following lines in Google Colab:
#
# Option A: Run built-in demo examples (no input required)
run_demo()
#
# Option B: Run in interactive mode (paste your own input)
# main()
