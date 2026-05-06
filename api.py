import re
import socket
import urllib.parse
from datetime import datetime
import whois
import jellyfish
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from duckduckgo_search import DDGS
import spacy
import json
import os
from functools import lru_cache

# Load spaCy
try:
    nlp = spacy.load("en_core_web_sm")
except Exception:
    import subprocess, sys
    subprocess.run([sys.executable, "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")

app = FastAPI(title="Job Scam API", version="1.0")

# Enable CORS for Chrome Extension
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    text: str
    source: str = "other"
    metadata: dict = {}

class FeedbackRequest(BaseModel):
    job_id: int
    is_scam: bool

REPUTATION_FILE = "reputation_db.json"

def load_reputation():
    if not os.path.exists(REPUTATION_FILE):
        return {}
    try:
        with open(REPUTATION_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_reputation(data):
    with open(REPUTATION_FILE, "w") as f:
        json.dump(data, f, indent=2)

def update_reputation(company, is_scam):
    if not company or company == "Unknown":
        return
    db = load_reputation()
    comp_key = company.lower().strip()
    if comp_key not in db:
        db[comp_key] = {"genuine": 0, "scam": 0}
    if is_scam:
        db[comp_key]["scam"] += 1
    else:
        db[comp_key]["genuine"] += 1
    save_reputation(db)

@app.post("/feedback")
def submit_feedback(req: FeedbackRequest):
    import ml_engine
    try:
        # 1. Update ML model
        ml_engine.submit_feedback(req.job_id, req.is_scam)
        
        # 2. Update Local Reputation
        # Need to find the company for this job_id
        import sqlite3
        conn = sqlite3.connect("scam_detector.db")
        c = conn.cursor()
        c.execute("SELECT content FROM jobs WHERE id=?", (req.job_id,))
        row = c.fetchone()
        if row:
            ner = extract_entities_spacy(row[0])
            update_reputation(ner["company"], req.is_scam)
        conn.close()
        
        return {"status": "success", "message": "Feedback saved. Model and reputation updated."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ── CONFIG ──────────────────────────────────────────────────────────────────
SCAM_KEYWORDS = [
    "earn $", "earn up to", "weekly pay", "make money fast",
    "no experience needed", "work from home and earn",
    "guaranteed income", "unlimited earnings", "passive income",
    "$500 weekly", "$1000 weekly", "$2000 weekly", "daily payment", "daily income",
    "urgent hiring", "immediate joining", "apply now", "limited slots",
    "hurry", "act fast", "only a few spots left", "immediate requirement",
    "registration fee", "processing fee", "training fee", "pay to apply",
    "refundable deposit", "send money", "western union", "wire transfer",
    "training kit", "security deposit", "bitcoin payment", "crypto payment",
    "contact on whatsapp", "contact on telegram", "dm for details",
    "chat on hangouts", "google hangout", "yahoo messenger",
    "message us on telegram", "whatsapp immediately", "signal app",
    "data entry", "form filling", "simple typing job",
    "part time online job", "home-based typing", "home typing job",
    "no qualification required", "no interview", "direct selection",
    "100% job guarantee", "assured placement", "no interview needed",
    "easy money", "quick cash", "rich quick", "online tutor needed urgent",
]

FREE_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "aol.com", "mail.com", "protonmail.com", "icloud.com",
    "yopmail.com", "guerrillamail.com", "tempmail.com", "mailinator.com",
}

FORTUNE_100_BRANDS = [
    "walmart", "amazon", "apple", "cvs", "unitedhealth", "berkshire", "alphabet", "google",
    "mckesson", "exxonmobil", "amerisourcebergen", "microsoft", "costco", "cigna",
    "chevron", "cardinalhealth", "ford", "generalmotors", "elevance", "jpmorgan",
    "kroger", "homedepot", "phillips66", "valero", "dell", "target", "fanniemae",
    "ups", "lowes", "bankofamerica", "goldmansachs", "johnsonandjohnson", "fedex",
    "citigroup", "walgreens", "meta", "facebook", "intel", "pepsico", "ibm",
    "accenture", "tcs", "cognizant", "infosys", "wipro", "deloitte", "pwc", "ey", "kpmg"
]

# ── NLP EXTRACTION (from script) ──────────────────────────────────────────────
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
        r"seeking\s+(?:a |an )?([A-Za-z][A-Za-z\s\-/]{2,40}?)(?:\.|,|$|\n)",
        r"vacancy for (?:a|an)\s+([A-Za-z][A-Za-z\s\-/]{2,40}?)(?:\.|,|$|\n)",
        r"position of\s+([A-Za-z][A-Za-z\s\-/]{2,40}?)(?:\.|,|$|\n)",
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

# ── NEW ADVANCED METRICS ─────────────────────────────────────────────────────

@lru_cache(maxsize=500)
def check_domain_exists_dns(domain):
    if not domain:
        return False
    try:
        socket.getaddrinfo(domain, None)
        return True
    except socket.error:
        return False

@lru_cache(maxsize=500)
def check_whois_age(domain):
    """Returns domain age in days. If lookup fails, returns -1."""
    if not domain or domain in FREE_EMAIL_DOMAINS:
        return -1
    try:
        w = whois.whois(domain)
        creation_date = w.creation_date
        if type(creation_date) is list:
            creation_date = creation_date[0]
        if creation_date:
            age = (datetime.now() - creation_date).days
            return age
        return -1
    except Exception:
        return -1

@lru_cache(maxsize=500)
def check_brand_impersonation(domain):
    """
    Check if the domain looks like a major brand typo (e.g. rnicrosoft.com).
    Returns (True, brand) if impersonating, (False, None) otherwise.
    """
    if not domain or domain in FREE_EMAIL_DOMAINS:
        return False, None
    domain_name = domain.split('.')[0].lower() # e.g. "rnicrosoft"
    
    for brand in FORTUNE_100_BRANDS:
        if domain_name == brand:
            return False, None # This is the exact brand, no penalty
        
        # Calculate fuzzy text distance (Levenshtein)
        distance = jellyfish.levenshtein_distance(domain_name, brand)
        if distance == 1 or distance == 2:
            return True, brand
            
    return False, None

@lru_cache(maxsize=500)
def check_online_presence(recruiter_name, company):
    """
    Search LinkedIn via DuckDuckGo to see if the recruiter works at the company.
    Returns True if found, False otherwise.
    """
    if not recruiter_name or recruiter_name == "Unknown" or not company or company == "Unknown":
        # Cannot verify
        return True 

    query = f'"{recruiter_name}" "{company}" site:linkedin.com/in'
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
            if results and len(results) > 0:
                return True
            return False
    except Exception:
        # If API fails, don't penalize
        return True

@lru_cache(maxsize=500)
def check_mx_records(domain):
    """Check if the email domain can actually receive emails (has MX records)."""
    if not domain:
        return False
    import dns.resolver
    try:
        dns.resolver.resolve(domain, 'MX')
        return True
    except Exception:
        return False

# ── SCORING ENGINE ───────────────────────────────────────────────────────────

@app.post("/analyze")
def analyze_job(req: AnalyzeRequest):
    raw_text = req.text
    
    # 1. NLP Parse
    email = extract_email(raw_text)
    website = extract_url(raw_text)
    ner = extract_entities_spacy(raw_text)
    
    # Metadata overrides/hints
    meta = req.metadata or {}
    company = meta.get("company") or ner["company"] or "Unknown"
    recruiter = meta.get("poster_name") or ner["recruiter_name"] or "Unknown"
    job_title = meta.get("title") or extract_job_title(raw_text, company)
    salary_mention = ner["salary_mention"]
    
    # 2. Basic Checks
    is_free_email = False
    email_domain = ""
    domain_exists = False
    
    if email:
        email_domain = email.split("@")[-1].lower()
        is_free_email = email_domain in FREE_EMAIL_DOMAINS
        domain_exists = check_domain_exists_dns(email_domain)

    scam_keywords = [kw for kw in SCAM_KEYWORDS if kw.lower() in raw_text.lower()]
    domain_matches = False
    if email_domain and company and company != "Unknown" and not is_free_email:
        email_name = email_domain.split(".")[0]
        for token in re.findall(r"[a-zA-Z]+", company.lower()):
            from difflib import SequenceMatcher
            if SequenceMatcher(None, email_name, token).ratio() >= 0.75:
                domain_matches = True
                break
                
    # 3. ADVANCED METRICS
    domain_age_days = check_whois_age(email_domain) if not is_free_email else -1
    is_impersonating, target_brand = check_brand_impersonation(email_domain)
    has_online_presence = check_online_presence(recruiter, company)
    
    # 4. COMPUTE RISK SCORE
    score = 0
    risk_factors = []
    
    # Keyword penalty
    if scam_keywords:
        kw_pts = len(scam_keywords) * 10
        score += kw_pts
        risk_factors.append(f"Found {len(scam_keywords)} scam keywords (+{kw_pts})")
        
    source = req.source.lower()
    is_trusted_brand = company.lower() in FORTUNE_100_BRANDS
    
    # APP-SPECIFIC RULES
    if source == "linkedin":
        # --- LINKEDIN LOGIC ---
        poster_url = meta.get("poster_url", "")
        headline = meta.get("poster_headline", "").lower()
        is_verified = meta.get("is_poster_verified", False)
        comp_size = meta.get("company_size", "").lower()
        
        if is_verified:
            score -= 45
            risk_factors.append("Verified Recruiter: LinkedIn confirmed identity (-45)")
            
        if not poster_url:
            penalty = 5 if is_trusted_brand else 20
            score += penalty
            risk_factors.append(f"Anonymous posting: No recruiter profile provided (+{penalty})")
        elif poster_url:
            if "linkedin.com/in/" not in poster_url and "linkedin.com/company/" not in poster_url:
                score += 40
                risk_factors.append(f"External/Suspicious poster URL detected: {poster_url} (+40)")
        
        # Brand Impersonation via Company Size
        if is_trusted_brand and any(s in comp_size for s in ["1-10", "11-50", "51-200"]):
            score += 65
            risk_factors.append(f"High Impersonation Risk: Tiny company size ({comp_size}) claiming to be {company} (+65)")
        
        # Recruiter Headline Matching
        if headline and company != "Unknown":
            comp_words = [w for w in re.findall(r"\w+", company.lower()) if len(w) > 2]
            if any(w in headline for w in comp_words):
                score -= 20
                risk_factors.append(f"Recruiter Verified: Headline matches company '{company}' (-20)")
        
        # NLP Company name mismatch
        nlp_company = ner["company"]
        if nlp_company and company != "Unknown" and nlp_company.lower() != company.lower():
            from difflib import SequenceMatcher
            if SequenceMatcher(None, nlp_company.lower(), company.lower()).ratio() < 0.5:
                penalty = 5 if is_trusted_brand else 15
                score += penalty
                risk_factors.append(f"Company name mismatch: Page says '{company}', text says '{nlp_company}' (+{penalty})")
                
        # Only penalize emails heavily if they're actually provided in the text
        if email:
            if is_free_email:
                score += 45
                risk_factors.append("Uses a free email address on a LinkedIn post (+45)")
            elif not domain_matches:
                score += 20
                risk_factors.append("Email domain does not match company name (+20)")

    elif source == "gmail" or source == "email":
        # --- EMAIL LOGIC ---
        if not email:
            score += 30
            risk_factors.append("No sender email found in scan (+30)")
        else:
            if is_free_email:
                score += 25
                risk_factors.append("Uses a free email address for hiring (+25)")
            elif not domain_matches:
                score += 20
                risk_factors.append("Email domain does not match company name (+20)")
                
            if not domain_exists:
                score += 30
                risk_factors.append("Email domain DNS does not exist (+30)")
                
            if domain_age_days != -1 and domain_age_days < 180:
                score += 40
                risk_factors.append(f"Domain registered only {domain_age_days} days ago (+40)")
                
            if is_impersonating:
                score += 60
                risk_factors.append(f"Domain appears to be typosquatting '{target_brand}' (+60)")

        if salary_mention and is_free_email:
            score += 10
            risk_factors.append("Salary financial bait combined with free email (+10)")
            
        if not has_online_presence:
            score += 15
            risk_factors.append("Recruiter has no LinkedIn footprint with this company (+15)")

    else:
        # --- FALLBACK LOGIC ---
        if is_free_email:
            score += 25
            risk_factors.append("Uses a free email address (+25)")
        elif email and not domain_matches:
            score += 20
            risk_factors.append("Email domain does not match company name (+20)")

    # Reputation Database Check
    reputation = load_reputation().get(company.lower().strip())
    if reputation:
        g = reputation.get("genuine", 0)
        s = reputation.get("scam", 0)
        if g > s:
            bonus = min(25, g * 5)
            score -= bonus
            risk_factors.append(f"Positive Reputation: Users marked {company} as genuine {g} times (-{bonus})")
        elif s > g:
            penalty = min(50, s * 15)
            score += penalty
            risk_factors.append(f"Negative Reputation: Users flagged {company} as scam {s} times (+{penalty})")

    # Reward Trusted Brands
    if is_trusted_brand:
        if score > 0:
            score -= 15
            risk_factors.append(f"Trusted Brand Discount: {company} is a verified major corporation (-15)")
        # Final decisiveness: trusted brands with no red flags should be VERY green
        if len([rf for rf in risk_factors if "(+" in rf]) == 0:
            score = 10 
        
    # Bound base rules score
    score = max(0, min(score, 100))
    
    # 5. ML ENGINE PREDICTION & ADAPTIVE LEARNING
    import ml_engine
    ml_prob = ml_engine.predict_ml(raw_text)
    
    if ml_prob is not None:
        ml_score = int(ml_prob * 100)
        risk_factors.append(f"Machine Learning Model scam probability: {ml_score}%")
        
        # Adaptive weight: if rules score is very low, trust ML less (prevent false positives)
        if score < 20 and ml_score > 60:
            final_score = int((score * 0.7) + (ml_score * 0.3))
            risk_factors.append("ML model overridden by strong legitimacy rules")
        else:
            # ML model has independent veto power if it detects a high-confidence scam
            final_score = max(ml_score, int((score * 0.5) + (ml_score * 0.5)))
    else:
        final_score = score
        
    final_score = max(0, min(final_score, 100))
    
    # Verdict
    if final_score < 30:
        verdict = "✅ Likely Genuine"
        color = "green"
    elif final_score <= 65:
        verdict = "⚠️ Suspicious"
        color = "orange"
    else:
        verdict = "🚨 High Scam Risk"
        color = "red"

    # Save to SQLite Database
    job_id = ml_engine.save_job(raw_text, final_score)

    return {
        "job_id": job_id,
        "job_title": job_title,
        "company": company,
        "recruiter": recruiter,
        "email": email,
        "risk_score": final_score,
        "rules_score_base": score,
        "ml_probability": ml_prob,
        "verdict": verdict,
        "color": color,
        "scam_keywords": scam_keywords,
        "domain_age_days": domain_age_days,
        "is_impersonating": is_impersonating,
        "target_brand": target_brand,
        "has_online_presence": has_online_presence,
        "risk_factors": risk_factors
    }

if __name__ == "__main__":
    import uvicorn
    # Make sure to run the server on port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
