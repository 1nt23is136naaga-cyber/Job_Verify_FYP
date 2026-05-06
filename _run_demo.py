# -*- coding: utf-8 -*-
"""
Standalone verification runner for job_scam_detection_nlp.py
Copies only the logic needed to run run_demo() — no box-drawing chars.
"""

import re, json, socket, urllib.parse
from difflib import SequenceMatcher

import spacy
nlp = spacy.load("en_core_web_sm")

# ── Config ──────────────────────────────────────────────────────────────────
SCAM_KEYWORDS = [
    "earn $", "earn up to", "weekly pay", "make money fast",
    "no experience needed", "work from home and earn",
    "guaranteed income", "unlimited earnings", "passive income",
    "$500 weekly", "$1000 weekly", "daily payment",
    "urgent hiring", "immediate joining", "apply now", "limited slots",
    "hurry", "act fast", "only a few spots left",
    "registration fee", "processing fee", "training fee", "pay to apply",
    "refundable deposit", "send money", "western union", "wire transfer",
    "contact on whatsapp", "contact on telegram", "dm for details",
    "chat on hangouts", "google hangout", "yahoo messenger",
    "data entry", "form filling", "simple typing job", "part time online job",
    "no qualification required", "no interview", "direct selection",
    "100% job guarantee", "assured placement",
]

FREE_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "aol.com", "mail.com", "protonmail.com", "icloud.com",
    "yopmail.com", "guerrillamail.com", "tempmail.com", "mailinator.com",
}

# ── NLP Extraction ───────────────────────────────────────────────────────────
def extract_email(text):
    m = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)
    return m.group(0).lower() if m else ""

def extract_url(text):
    m = re.search(r"https?://[^\s,\)\]>\"\']*", text)
    return m.group(0).rstrip(".") if m else ""

def extract_entities_spacy(text):
    doc = nlp(text)
    company = recruiter_name = salary_mention = ""
    for ent in doc.ents:
        if ent.label_ == "ORG" and not company:
            company = ent.text.strip()
        elif ent.label_ == "PERSON" and not recruiter_name:
            recruiter_name = ent.text.strip()
        elif ent.label_ == "MONEY" and not salary_mention:
            salary_mention = ent.text.strip()
    return {"company": company, "recruiter_name": recruiter_name, "salary_mention": salary_mention}

def extract_job_title(text, company):
    patterns = [
        r"hiring (?:a|an)\s+([A-Za-z][A-Za-z\s\-/]{2,40}?)(?:\.|,|$|\n)",
        r"looking for (?:a|an)\s+([A-Za-z][A-Za-z\s\-/]{2,40}?)(?:\.|,|$|\n)",
        r"position of\s+([A-Za-z][A-Za-z\s\-/]{2,40}?)(?:\.|,|$|\n)",
        r"role of\s+([A-Za-z][A-Za-z\s\-/]{2,40}?)(?:\.|,|$|\n)",
        r"vacancy for\s+([A-Za-z][A-Za-z\s\-/]{2,40}?)(?:\.|,|$|\n)",
        r"seeking\s+(?:a |an )?([A-Za-z][A-Za-z\s\-/]{2,40}?)(?:\.|,|$|\n)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            title = re.sub(r"\s+(to|and|for|with|at|in)$", "", m.group(1).strip(), flags=re.IGNORECASE)
            return title.title()
    doc = nlp(text)
    job_kw = ["engineer","manager","developer","analyst","designer","consultant",
              "officer","executive","intern","assistant","coordinator","specialist",
              "director","lead","entry"]
    for chunk in doc.noun_chunks:
        if any(k in chunk.text.lower() for k in job_kw):
            return chunk.text.strip().title()
    return "Not Detected"

def parse_natural_input(raw_text):
    email = extract_email(raw_text)
    website = extract_url(raw_text)
    ner = extract_entities_spacy(raw_text)
    job_title = extract_job_title(raw_text, ner["company"])
    return {
        "job_title": job_title,
        "company": ner["company"] or "Unknown",
        "recruiter_name": ner["recruiter_name"] or "Unknown",
        "recruiter_email": email,
        "company_website": website,
        "job_description": raw_text.strip(),
        "salary_mention": ner["salary_mention"],
    }

# ── Verification ─────────────────────────────────────────────────────────────
def check_free_email(email):
    if not email or "@" not in email:
        return False
    return email.split("@")[-1].lower() in FREE_EMAIL_DOMAINS

def get_email_domain(email):
    if not email or "@" not in email:
        return ""
    return email.split("@")[-1].lower()

def domain_matches_company(email, company, website):
    email_domain = get_email_domain(email)
    if not email_domain:
        return False
    if website:
        try:
            site_domain = urllib.parse.urlparse(website).netloc.lower().lstrip("www.")
            if email_domain == site_domain or email_domain.endswith("." + site_domain):
                return True
        except Exception:
            pass
    if company and company.lower() != "unknown":
        email_name = email_domain.split(".")[0]
        for token in re.findall(r"[a-zA-Z]+", company.lower()):
            if SequenceMatcher(None, email_name, token).ratio() >= 0.75:
                return True
    return False

def detect_scam_keywords(text):
    text_lower = text.lower()
    return [kw for kw in SCAM_KEYWORDS if kw.lower() in text_lower]

def check_domain_exists(domain):
    if not domain:
        return False
    try:
        socket.setdefaulttimeout(4)
        socket.getaddrinfo(domain, None)
        return True
    except:
        return False

def calculate_risk_score(is_free_email, domain_matches, scam_keywords,
                          domain_exists, salary_mention, has_email, has_website):
    score = 0
    if is_free_email:
        score += 25
    if has_email and not domain_matches:
        score += 20
    score += min(len(scam_keywords) * 5, 30)
    if not domain_exists and has_email:
        score += 15
    if salary_mention and is_free_email:
        score += 10
    if has_website and domain_exists:
        score -= 10
    if has_email and not is_free_email:
        score -= 5
    return max(0, min(score, 100))

def get_verdict(score):
    if score <= 30:
        return "LIKELY GENUINE"
    elif score <= 59:
        return "SUSPICIOUS"
    else:
        return "HIGH SCAM RISK"

# ── Report ───────────────────────────────────────────────────────────────────
def generate_report(job_data, analysis):
    kw_display = ", ".join(analysis["scam_keywords"]) if analysis["scam_keywords"] else "None"
    return f"""
{'='*55}
       JOB VERIFICATION REPORT
{'='*55}
  Job Title           : {job_data['job_title']}
  Company             : {job_data['company']}
  Recruiter Name      : {job_data['recruiter_name']}
  Recruiter Email     : {job_data['recruiter_email'] or 'Not Provided'}
  Company Website     : {job_data['company_website'] or 'Not Provided'}
{'-'*55}
  Email Domain        : {analysis['email_domain'] or 'N/A'}
  Free Email Used     : {'YES' if analysis['is_free_email'] else 'No'}
  Domain Matches Co.  : {'Yes' if analysis['domain_matches'] else 'NO'}
  Domain Exists (DNS) : {'Yes' if analysis['domain_exists'] else 'NO'}
{'-'*55}
  Scam Keywords Found : {kw_display}
  Salary Mention      : {job_data.get('salary_mention') or 'None'}
{'-'*55}
  Risk Score          : {analysis['risk_score']} / 100
  Final Verdict       : {get_verdict(analysis['risk_score'])}
{'='*55}"""

# ── Pipeline ─────────────────────────────────────────────────────────────────
def run_detection_pipeline(raw_text):
    job_data = parse_natural_input(raw_text)
    email = job_data["recruiter_email"]
    has_email = bool(email)
    is_free_email = check_free_email(email)
    email_domain = get_email_domain(email)
    domain_matches = domain_matches_company(email, job_data["company"], job_data["company_website"])
    domain_exists = check_domain_exists(email_domain) if email_domain else False
    scam_keywords = detect_scam_keywords(job_data["job_description"])
    risk_score = calculate_risk_score(
        is_free_email, domain_matches, scam_keywords, domain_exists,
        job_data.get("salary_mention", ""), has_email, bool(job_data["company_website"])
    )
    analysis = {
        "email_domain": email_domain, "is_free_email": is_free_email,
        "domain_matches": domain_matches, "domain_exists": domain_exists,
        "scam_keywords": scam_keywords, "risk_score": risk_score,
    }
    print(generate_report(job_data, analysis))

# ── Demo ──────────────────────────────────────────────────────────────────────
examples = [
    ("Example 1 - Legitimate (Microsoft)",
     "Microsoft is hiring a Software Engineer. Contact recruiter Sarah Thompson "
     "at sarah@microsoft.com. Apply at https://careers.microsoft.com. "
     "The role involves working on Azure cloud services."),

    ("Example 2 - Obvious Scam",
     "URGENT! Data entry job. Earn $500 weekly. No experience needed. "
     "Work from home. Contact us on Telegram or WhatsApp. "
     "Registration fee required. Limited slots available. Apply now!"),

    ("Example 3 - Suspicious (corporate name + Gmail)",
     "Accenture is looking for a Business Analyst. "
     "Send your CV to recruiter Mike Johnson at mikejohnson.recruiter@gmail.com. "
     "Guaranteed placement. No interview required."),
]

# ── Interactive Mode ─────────────────────────────────────────────────────────
print("""
=======================================================
  AI Job Scam Detection - Interactive Mode
=======================================================
Paste any job description in plain English and press Enter.
Type  EXIT  to quit.
""")

while True:
    print("-" * 55)
    raw = input("Paste job description:\n> ").strip()

    if raw.upper() == "EXIT":
        print("Goodbye!")
        break

    if len(raw) < 10:
        print("Too short — please paste a fuller description.")
        continue

    run_detection_pipeline(raw)
    print()
