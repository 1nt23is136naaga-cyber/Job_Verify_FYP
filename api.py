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
from dotenv import load_dotenv
from groq import Groq
from google import genai
from google.genai import types as genai_types

# Load .env for API key
load_dotenv()
_gemini_client = None
_groq_client = None

def get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        api_key = os.getenv("GOOGLE_API_KEY")
        if api_key:
            _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client

def get_groq_client():
    """Groq client — used as fallback when Gemini quota is exhausted."""
    global _groq_client
    if _groq_client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if api_key:
            _groq_client = Groq(api_key=api_key)
    return _groq_client

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
    image_data: list = []
    image_urls: list = []

class FeedbackRequest(BaseModel):
    job_id: int
    is_scam: bool

class VerifyRequest(BaseModel):
    job_title: str
    company: str

class FullScanRequest(BaseModel):
    text: str
    source: str = "other"
    metadata: dict = {}
    image_data: list = []

# In-memory stores
_verify_tasks: dict = {}     # key: "title|company" -> {status, result}
_full_scan_tasks: dict = {}  # key: scan_id -> {status, phase, analyze_result, final_result}

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
    "limited slots", "hurry", "act fast", "only a few spots left",
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

INDIA_SCAM_KEYWORDS = [
    "training bond", "joining kit", "rotational shift allowance", "field sales",
    "whatsapp for details", "mlm", "network marketing", "downline", 
    "paytm transfer", "upi transfer", "gpay transfer", "google pay", "phonepe"
]

UK_SCAM_KEYWORDS = [
    "national insurance number required before interview", "dbs check fee",
    "crb check fee", "right to work check fee", "visa sponsorship fee",
    "payment for uniform upfront", "pay to register for payroll",
    "ni number urgent", "bacs transfer required", "paye setup fee"
]

def detect_region(text: str, location: str) -> str:
    """Detects the target region based on currency symbols and location names."""
    text_lower = text.lower()
    loc_lower = location.lower()
    
    # India checks
    if "₹" in text or "inr" in text_lower or "lpa" in text_lower or "india" in loc_lower or "noida" in loc_lower or "bengaluru" in loc_lower:
        return "IN"
        
    # UK checks
    if "£" in text or "gbp" in text_lower or "uk" in loc_lower or "united kingdom" in loc_lower or "london" in loc_lower or "manchester" in loc_lower:
        return "UK"
        
    # US/Default
    return "US"

FREE_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "aol.com", "mail.com", "protonmail.com", "icloud.com",
    "yopmail.com", "guerrillamail.com", "tempmail.com", "mailinator.com",
}

FORTUNE_100_BRANDS = [
    # Global Tech & Giants
    "walmart", "amazon", "apple", "cvs", "unitedhealth", "berkshire", "alphabet", "google",
    "mckesson", "exxonmobil", "amerisourcebergen", "microsoft", "costco", "cigna",
    "chevron", "cardinalhealth", "ford", "generalmotors", "elevance", "jpmorgan",
    "kroger", "homedepot", "phillips66", "valero", "dell", "target", "fanniemae",
    "ups", "lowes", "bankofamerica", "goldmansachs", "johnsonandjohnson", "fedex",
    "citigroup", "walgreens", "meta", "facebook", "intel", "pepsico", "ibm",
    "accenture", "tcs", "cognizant", "infosys", "wipro", "deloitte", "pwc", "ey", "kpmg",
    # Additional Fortune 500 / Global 2000 Leaders
    "ecolab", "siemens", "ge", "honeywell", "bayer", "basf", "pfizer", "abbott",
    "roche", "novartis", "cisco", "oracle", "adobe", "salesforce", "netflix",
    "uber", "airbnb", "spotify", "paypal", "square", "stripe", "broadcom", "qualcomm",
    "nvidia", "amd", "texas instruments", "samsung", "sony", "panasonic", "lg",
    "bosch", "volkswagen", "bmw", "mercedes", "toyota", "honda", "hyundai", "boeing",
    "airbus", "lockheed", "raytheon", "caterpillar", "deere", "3m", "dupont", "dow",
    "nike", "adidas", "starbucks", "mcdonalds", "unilever", "procter", "nestle",
    "coca-cola", "mondelez", "loreal", "colgate", "medtronic", "stryker", "thermo fisher",
    "danaher", "illumina", "iqvia", "at&t", "verizon", "t-mobile", "vodafone",
    "airtel", "jio", "disney", "bloomberg", "reuters", "blackrock", "vanguard",
    "morgan stanley", "wells fargo", "capital one", "amex", "visa", "mastercard",
    "barclays", "hsbc", "standard chartered", "ubs", "credit suisse", "deutsche bank",
    "santander", "bnp paribas", "dbs", "atlassian", "servicenow", "workday", "zoho",
    "freshworks", "razorpay", "swiggy", "zomato", "flipkart", "phonepe", "paytm",
    "darukaa", "mphasis", "ltimindtree", "techmahindra", "hexaware"
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
        return True 
    comp_lower = company.lower()
    if any(brand in comp_lower for brand in FORTUNE_100_BRANDS):
        return True # Trusted brand fast-path

    query = f'"{recruiter_name}" "{company}" site:linkedin.com/in'
    try:
        with DDGS(timeout=1) as ddgs:
            results = list(ddgs.text(query, max_results=2))
            if results and len(results) > 0:
                return True
            return False
    except Exception:
        return True

@lru_cache(maxsize=500)
def check_web_scam_reports(company: str, email: str) -> bool:
    """
    Search the web to see if the company or email is associated with scam reports.
    """
    if not company or company == "Unknown":
        return False
    comp_lower = company.lower()
    if any(brand in comp_lower for brand in FORTUNE_100_BRANDS):
        return False # Trusted brand fast-path
        
    query_parts = []
    if email and email.split('@')[-1] not in FREE_EMAIL_DOMAINS:
        query_parts.append(f'"{email}"')
    query_parts.append(f'"{company}"')
    query_parts.append('(scam OR fraud OR fake)')
    
    query = " ".join(query_parts)
    try:
        with DDGS(timeout=1) as ddgs:
            results = list(ddgs.text(query, max_results=2))
            if results:
                for r in results:
                    text = (r.get("title", "") + " " + r.get("body", "")).lower()
                    if "scam" in text or "fraud" in text or "fake" in text:
                        return True
            return False
    except Exception:
        return False

@lru_cache(maxsize=300)
def check_employer_review_sites(company: str, region: str) -> dict:
    """
    Search Glassdoor (global) and Ambitionbox (India) via DuckDuckGo
    to find the company's employee rating.
    Returns a dict with 'rating' (float or None), 'source', and 'summary'.
    """
    if not company or company == "Unknown":
        return {"rating": None, "source": None, "summary": ""}
    comp_lower = company.lower()
    if any(brand in comp_lower for brand in FORTUNE_100_BRANDS):
        return {"rating": 4.5, "source": "Corporate Database", "summary": "Fortune 500 Enterprise"}
    
    # Choose review site based on region
    sites = []
    if region == "IN":
        sites = [
            ("Ambitionbox", f'"{company}" site:ambitionbox.com reviews rating')
        ]
    else:
        sites = [
            ("Glassdoor", f'"{company}" site:glassdoor.com reviews rating')
        ]
    
    rating_pattern = re.compile(r'(\d\.\d)\s*(?:out of|/)?\s*5')
    
    for source_name, query in sites:
        try:
            with DDGS(timeout=1) as ddgs:
                results = list(ddgs.text(query, max_results=2))
                for r in results:
                    snippet = r.get("title", "") + " " + r.get("body", "")
                    match = rating_pattern.search(snippet)
                    if match:
                        rating = float(match.group(1))
                        if 0.5 <= rating <= 5.0:
                            return {
                                "rating": rating,
                                "source": source_name,
                                "summary": snippet[:120].strip()
                            }
        except Exception:
            continue
    
    return {"rating": None, "source": None, "summary": ""}

@lru_cache(maxsize=200)
def check_company_reputation_gemini(company: str) -> dict:
    """
    When a company is NOT found in any official registry,
    ask Gemini to assess its legitimacy based on its known hiring history
    and publicly available information.
    Returns a dict with 'is_likely_legit' bool and 'summary' string.
    """
    client = get_gemini_client()
    if not client or not company or company == "Unknown":
        return {"is_likely_legit": None, "summary": ""}
    
    prompt = f"""You are a corporate due diligence expert. The company '{company}' was NOT found 
in any official government company registry (like MCA21 or Companies House).

Based on your knowledge:
1. Is '{company}' a known, legitimate employer with a real hiring history?
2. Or is it an obscure / unverifiable / suspicious entity?

Answer ONLY with a valid JSON object:
{{
  "is_known_legitimate": <true|false|null>,
  "confidence": "high|medium|low",
  "summary": "<one sentence about the company's reputation>"
}}

If you have no knowledge of this company, set is_known_legitimate to null."""

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=150,
                response_mime_type="application/json"
            )
        )
        result = json.loads(response.text.strip())
        return {
            "is_likely_legit": result.get("is_known_legitimate"),
            "confidence": result.get("confidence", "low"),
            "summary": result.get("summary", "")
        }
    except Exception as e:
        return {"is_likely_legit": None, "summary": ""}

def ocr_images_with_gemini(image_data_list: list) -> str:
    """
    Send up to 4 job post images to Gemini Vision.
    Extracts any text (salary, roles, company, contact info) embedded in images.
    Returns appended plain text string of all extracted content.
    """
    import base64
    client = get_gemini_client()
    if not client or not image_data_list:
        return ""

    extracted_parts = []
    for data_url in image_data_list[:4]:
        try:
            b64data = data_url.split(',', 1)[1] if ',' in data_url else data_url
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[
                    {
                        "parts": [
                            {"inline_data": {"mime_type": "image/jpeg", "data": b64data}},
                            {"text": "Extract ALL text from this image related to job details: salary, job roles, company name, contact info, requirements. Return only extracted text, no commentary."}
                        ]
                    }
                ],
                config=genai_types.GenerateContentConfig(temperature=0.1, max_output_tokens=300)
            )
            extracted = response.text.strip()
            if extracted and len(extracted) > 10:
                extracted_parts.append(extracted)
        except Exception as e:
            print(f"[ScamShield] Image OCR error: {e}")
            continue

    return "\n\n[Image Text Extracted]:\n" + "\n---\n".join(extracted_parts) if extracted_parts else ""

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

# ── MCA21 COMPANY VERIFICATION ───────────────────────────────────────────────

@lru_cache(maxsize=500)
def check_mca21_registration(company_name: str) -> dict:
    """
    Verifies if a company is registered with India's Ministry of Corporate Affairs (MCA21).
    Uses Zaubacorp's public search (no API key, no login required) as a proxy for MCA data.
    
    Returns:
        {
          "status": "registered" | "not_found" | "unknown",
          "cin": str | None,          # Corporate Identification Number
          "reg_state": str | None,    # State of registration
          "company_type": str | None, # Pvt Ltd, Ltd, LLP etc.
          "company_status": str | None # Active, Strike Off, etc.
        }
    """
    import requests
    from bs4 import BeautifulSoup
    import urllib.parse

    if not company_name or company_name.lower() in ["unknown", ""]:
        return {"status": "unknown", "cin": None, "reg_state": None, 
                "company_type": None, "company_status": None}

    # Clean the company name — remove common suffixes for fuzzy search
    clean_name = re.sub(
        r"\b(pvt|private|ltd|limited|llp|inc|corp|corporation|india)\b", 
        "", company_name, flags=re.IGNORECASE
    ).strip()

    try:
        search_url = f"https://www.zaubacorp.com/company-list/p-1/s-like/cn-{urllib.parse.quote(clean_name)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
            "Accept-Language": "en-IN,en;q=0.9",
            "Referer": "https://www.zaubacorp.com/"
        }
        resp = requests.get(search_url, headers=headers, timeout=2)
        
        if resp.status_code != 200:
            return {"status": "unknown", "cin": None, "reg_state": None,
                    "company_type": None, "company_status": None}

        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Find the results table
        table = soup.find("table", {"id": "table"}) or soup.find("table", class_="table")
        if not table:
            # No table found — company not in MCA database
            return {"status": "not_found", "cin": None, "reg_state": None,
                    "company_type": None, "company_status": None}
        
        rows = table.find_all("tr")[1:]  # Skip header row
        if not rows:
            return {"status": "not_found", "cin": None, "reg_state": None,
                    "company_type": None, "company_status": None}
        
        # Check the first result — see if the company name roughly matches
        first_row = rows[0]
        cols = first_row.find_all("td")
        if len(cols) < 4:
            return {"status": "unknown", "cin": None, "reg_state": None,
                    "company_type": None, "company_status": None}
        
        from difflib import SequenceMatcher
        result_name = cols[0].get_text(strip=True).lower()
        similarity = SequenceMatcher(None, clean_name.lower(), result_name).ratio()
        
        cin = cols[1].get_text(strip=True) if len(cols) > 1 else None
        company_status = cols[2].get_text(strip=True) if len(cols) > 2 else None
        reg_state = cols[3].get_text(strip=True) if len(cols) > 3 else None
        company_type = cols[4].get_text(strip=True) if len(cols) > 4 else None
        
        if similarity >= 0.55 or clean_name.lower() in result_name:
            return {
                "status": "registered",
                "cin": cin,
                "reg_state": reg_state,
                "company_type": company_type,
                "company_status": company_status  # "Active", "Strike Off", etc.
            }
        else:
            # Results found but none match well — company likely not in MCA
            return {"status": "not_found", "cin": None, "reg_state": None,
                    "company_type": None, "company_status": None}

    except requests.exceptions.Timeout:
        # Don't penalize if the lookup times out
        return {"status": "unknown", "cin": None, "reg_state": None,
                "company_type": None, "company_status": None}
    except Exception as e:
        print(f"MCA21 Lookup Error: {e}")
        return {"status": "unknown", "cin": None, "reg_state": None,
                "company_type": None, "company_status": None}

@lru_cache(maxsize=500)
def check_uk_companies_house(company_name: str) -> dict:
    """
    Verifies if a company is registered with UK Companies House.
    Scrapes the public find-and-update service.
    """
    import requests
    from bs4 import BeautifulSoup
    import urllib.parse
    import re
    from difflib import SequenceMatcher

    if not company_name or company_name.lower() in ["unknown", ""]:
        return {"status": "unknown", "cin": None, "company_status": None}

    clean_name = re.sub(
        r"\b(ltd|limited|llp|plc|inc)\b", 
        "", company_name, flags=re.IGNORECASE
    ).strip()

    search_url = f"https://find-and-update.company-information.service.gov.uk/search/companies?q={urllib.parse.quote(clean_name)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    }
    try:
        resp = requests.get(search_url, headers=headers, timeout=2)
        if resp.status_code != 200:
            return {"status": "unknown", "cin": None, "company_status": None}
        
        soup = BeautifulSoup(resp.text, "html.parser")
        links = soup.find_all("a", href=re.compile(r"/company/[A-Z0-9]+$"))
        if not links:
            return {"status": "not_found", "cin": None, "company_status": None}
            
        first_link = links[0]
        result_name = first_link.get_text(strip=True).lower()
        cin = first_link['href'].split('/')[-1]
        
        # Try to get status from text context, e.g. "Dissolved on"
        parent = first_link.parent
        status_text = parent.get_text(strip=True) if parent else ""
        company_status = "Active"
        if "Dissolved" in status_text:
            company_status = "Dissolved"
        elif "Liquidation" in status_text:
            company_status = "Liquidation"
        elif "Closed" in status_text:
            company_status = "Closed"
            
        similarity = SequenceMatcher(None, clean_name.lower(), result_name).ratio()
        if similarity >= 0.55 or clean_name.lower() in result_name:
            return {
                "status": "registered",
                "cin": cin,
                "company_status": company_status
            }
        else:
            return {"status": "not_found", "cin": None, "company_status": None}

    except Exception as e:
        print(f"Companies House Lookup Error: {e}")
        return {"status": "unknown", "cin": None, "company_status": None}

def verify_company_registry(company_name: str, region: str) -> dict:
    if region == "IN":
        res = check_mca21_registration(company_name)
        return {"registry": "MCA21", **res}
    elif region == "UK":
        res = check_uk_companies_house(company_name)
        return {"registry": "Companies House", **res}
    else:
        return {"registry": "Generic", "status": "unknown", "cin": None, "company_status": None}


# Platform-specific system prompts — GPT gets expert context for each source
PLATFORM_SYSTEM_PROMPTS = {
    "linkedin": """You are an expert LinkedIn job scam detector. You specialize in identifying fraudulent job postings on LinkedIn.

On LinkedIn, legitimate job postings typically:
- Come from recruiters with complete, verifiable profiles (connections, work history, endorsements)
- Have detailed, professional job descriptions with specific responsibilities and requirements
- Mention real company names that match the poster's profile
- Ask candidates to apply via LinkedIn or the official company website
- Offer market-rate salaries for the role and location

RED FLAGS specific to LinkedIn:
- Recruiter has few connections (< 50) or a very new account
- Job description is vague ("earn money from home", "flexible hours", no specific skills required)
- Recruiter is NOT associated with the company they're hiring for
- Requests to communicate via WhatsApp, Telegram, or personal email
- Promises extremely high pay for simple/vague roles
- No company page or the company page has very few followers
- Post is not from an official company page but an individual with no LinkedIn history
- Asks for any upfront payment, deposits, or "training fees"

Respond ONLY with a valid JSON object:
{
  "scam_score": <integer 0-100>,
  "reasoning": "<one concise sentence explaining your verdict>",
  "red_flags": ["<specific flag found>"]
}
Scoring: 0-39 = Genuine, 40-65 = Suspicious, 66-100 = Scam""",

    "gmail": """You are an expert email job scam detector. You specialize in identifying fraudulent job offer emails.

On Gmail/Email, legitimate job offer emails typically:
- Come from official corporate email addresses (e.g., hr@companyname.com, not gmail/yahoo)
- Reference a specific job the candidate applied for
- Include a real HR name, designation, and contact details
- Have professional formatting with correct grammar
- Direct candidates to an official company website or ATS portal to apply

RED FLAGS specific to Email job scams:
- Sent from free email providers (Gmail, Yahoo, Hotmail) instead of corporate domain
- Email domain doesn't match the company name being claimed
- Offers a job without any prior application or interview
- Requests personal documents (Aadhaar, PAN, bank details) upfront
- Mentions registration fees, processing charges, security deposits, or training fees
- Uses urgent language ("respond within 24 hours or lose the offer")
- Contains generic greetings ("Dear Candidate") with no personalization
- Promises unusually high salary with minimal experience requirements
- Contact number is a personal mobile, not an office landline
- Grammar errors, poor formatting, or unprofessional tone

Respond ONLY with a valid JSON object:
{
  "scam_score": <integer 0-100>,
  "reasoning": "<one concise sentence explaining your verdict>",
  "red_flags": ["<specific flag found>"]
}
Scoring: 0-39 = Genuine, 40-65 = Suspicious, 66-100 = Scam""",

    "internshala": """You are an expert Internshala job/internship scam detector. You specialize in identifying fraudulent postings on Internshala, a platform primarily used by students and freshers in India.

On Internshala, legitimate internship/job postings typically:
- Specify a clear stipend range (or explicitly say "unpaid") that is reasonable for a student role
- Mention a defined duration (e.g., 2 months, 6 months)
- Have a clear work mode: Work From Home (WFH) or In-Office with a stated location
- List specific skills (e.g., Python, MS Excel, Social Media Management)
- Belong to a verified company with a real website and previous hiring history on the platform
- Offer a certificate or letter of recommendation (LoR) as stated benefit

RED FLAGS specific to Internshala:
- Promises unrealistically high stipends (e.g., ₹50,000+/month for a student with no experience)
- No stipend mentioned AND no mention of "unpaid" or benefits
- Requires ANY upfront payment, registration fee, or purchase of "training kits"
- Job description is extremely vague with no mention of skills or tasks
- Asks for personal financial details or national ID documents before joining
- Contacts candidates via WhatsApp or Telegram instead of official platform messages
- Company has no profile picture, no website, and zero previous interns
- Post promises "100% job guarantee" or "assured placement" after the internship
- Asks candidates to buy software, equipment, or uniforms themselves

Respond ONLY with a valid JSON object:
{
  "scam_score": <integer 0-100>,
  "reasoning": "<one concise sentence explaining your verdict>",
  "red_flags": ["<specific flag found>"]
}
Scoring: 0-39 = Genuine, 40-65 = Suspicious, 66-100 = Scam""",

    "naukri": """You are an expert Naukri.com job scam detector. You specialize in identifying fraudulent job postings on Naukri, a platform primarily for experienced professionals in India.

On Naukri, legitimate job postings typically:
- Come from verified companies with a complete Naukri employer profile
- Specify clear CTC (Cost to Company) ranges realistic for the experience required
- List a specific job location or clearly state it is remote
- Have detailed JDs with required skills, qualifications, and responsibilities
- Use professional language appropriate to the industry and seniority

RED FLAGS specific to Naukri:
- CTC is unrealistically high (e.g., ₹50 LPA for a fresher)
- No company name disclosed, or company is listed as "confidential" with no other details
- JD is copy-pasted and generic with no specific company or role context
- Recruiter email is a free provider (Gmail, Yahoo)
- The application process redirects to a suspicious external website
- Asks for payment of any kind (registration, document verification, etc.)
- Calls/messages from unknown numbers asking for personal details immediately
- Job role is listed under a completely irrelevant category

Respond ONLY with a valid JSON object:
{
  "scam_score": <integer 0-100>,
  "reasoning": "<one concise sentence explaining your verdict>",
  "red_flags": ["<specific flag found>"]
}
Scoring: 0-39 = Genuine, 40-65 = Suspicious, 66-100 = Scam""",

    "indeed": """You are an expert Indeed job scam detector. You specialize in identifying fraudulent job postings on Indeed.

On Indeed, legitimate job postings typically:
- Come from verified employer accounts with a company profile and reviews
- Have a realistic, specific salary range for the role and location
- Describe detailed responsibilities and qualifications required
- Use Indeed's official application flow (Apply Now button)
- List a real physical office address or state clearly it is remote

RED FLAGS specific to Indeed:
- Salary is posted as an extremely wide or unrealistically high range
- Job description is vague, copy-pasted, or lacks any company-specific details
- Application redirects to an external suspicious link (not the company's official domain)
- No company reviews on Indeed, or reviews are all 5-star with no text
- Requests to contact via external messaging apps (WhatsApp, Telegram)
- Promises of signing bonuses, equipment allowances, or immediate joining for remote work
- Asks for personal financial info or SSN/Aadhaar during application

Respond ONLY with a valid JSON object:
{
  "scam_score": <integer 0-100>,
  "reasoning": "<one concise sentence explaining your verdict>",
  "red_flags": ["<specific flag found>"]
}
Scoring: 0-39 = Genuine, 40-65 = Suspicious, 66-100 = Scam""",

    "other": """You are an expert job scam detection AI. You will be given a job posting from an unknown or generic source and must evaluate whether it is genuine or a scam.

Legitimate job postings generally:
- Come from identifiable companies with an online presence
- Have specific, realistic job descriptions and salary ranges
- Use professional language without pressure tactics
- Never ask for money, deposits, or personal financial details

Common scam indicators:
- Unrealistic earnings for minimal work
- Vague job descriptions with no required skills
- Requests for registration fees, security deposits, or training costs
- Contact via personal messaging apps (WhatsApp, Telegram, Hangouts)
- No company website or verifiable online presence
- Urgency pressure ("apply in 24 hours", "limited slots")
- Guaranteed job placements without interviews

Respond ONLY with a valid JSON object:
{
  "scam_score": <integer 0-100>,
  "reasoning": "<one concise sentence explaining your verdict>",
  "red_flags": ["<specific flag found>"]
}
Scoring: 0-39 = Genuine, 40-65 = Suspicious, 66-100 = Scam"""
}

def analyze_with_gpt(job_text: str, source: str, company: str, recruiter: str, metadata: dict = None, registry_data: dict = None, review_data: dict = None) -> dict:
    """
    Uses Google Gemini 2.0 Flash (free tier) with platform-specific expert prompts to evaluate the job posting.
    Each platform (LinkedIn, Gmail, Internshala, Naukri, Indeed) gets a
    tailored system prompt so the AI applies the right criteria for that source.
    Returns None if Gemini is unavailable.
    """
    client = get_gemini_client()
    if not client:
        return None

    # Pick the platform-specific system prompt, fallback to generic
    platform_key = source.lower()
    if "linkedin" in platform_key:
        platform_key = "linkedin"
    elif "gmail" in platform_key or "email" in platform_key:
        platform_key = "gmail"
    elif "internshala" in platform_key:
        platform_key = "internshala"
    elif "naukri" in platform_key:
        platform_key = "naukri"
    elif "indeed" in platform_key:
        platform_key = "indeed"
    else:
        platform_key = "other"

    system_prompt = PLATFORM_SYSTEM_PROMPTS[platform_key]

    # Truncate to keep costs low (max ~2500 chars of job text)
    truncated = job_text[:2500]

    # Build a rich context block from metadata so GPT has all the info
    meta_lines = []
    if metadata:
        if metadata.get("title"):
            meta_lines.append(f"Job Title: {metadata['title']}")
        if metadata.get("company_size"):
            meta_lines.append(f"Company Size: {metadata['company_size']}")
        if metadata.get("company_industry"):
            meta_lines.append(f"Industry: {metadata['company_industry']}")
        if metadata.get("poster_headline"):
            meta_lines.append(f"Poster Headline: {metadata['poster_headline']}")
        if metadata.get("is_poster_verified"):
            meta_lines.append(f"Poster Verified: {metadata['is_poster_verified']}")
        if metadata.get("applicants"):
            meta_lines.append(f"Applicant Count: {metadata['applicants']}")
        if metadata.get("location"):
            meta_lines.append(f"Location: {metadata['location']}")
        if metadata.get("is_promoted"):
            meta_lines.append(f"Is Promoted Post: {metadata['is_promoted']}")
        if metadata.get("company_followers"):
            meta_lines.append(f"Company Followers: {metadata['company_followers']}")
        if metadata.get("hiring_stats"):
            meta_lines.append(f"Hiring History: {metadata['hiring_stats']}")

    if registry_data:
        meta_lines.append(f"Government/Registry Verification: {registry_data.get('registry')} - {registry_data.get('status')}")
        if registry_data.get('company_status'):
            meta_lines.append(f"Official Company Status: {registry_data.get('company_status')}")
        if registry_data.get('cin'):
            meta_lines.append(f"Registry ID: {registry_data.get('cin')}")

    if review_data and review_data.get("rating") is not None:
        meta_lines.append(f"Employee Review Rating: {review_data['rating']}/5.0 on {review_data['source']}")
        if review_data.get("summary"):
            meta_lines.append(f"Review Snippet: {review_data['summary'][:100]}")

    meta_block = "\n".join(meta_lines) if meta_lines else "No additional metadata available."

    user_prompt = f"""Platform: {source.upper()}
Company: {company}
Recruiter/Poster: {recruiter}

--- Extracted Metadata ---
{meta_block}

--- Job Posting Text ---
{truncated}"""

    try:
        combined_prompt = f"{system_prompt}\n\n{user_prompt}"
        client = get_gemini_client()
        if client:
            try:
                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=combined_prompt,
                    config=genai_types.GenerateContentConfig(
                        temperature=0.2,
                        max_output_tokens=400,
                        response_mime_type="application/json"
                    )
                )
                raw = response.text.strip()
                result = json.loads(raw)
                return {
                    "score": max(0, min(100, int(result.get("scam_score", 50)))),
                    "reasoning": result.get("reasoning", ""),
                    "red_flags": result.get("red_flags", [])
                }
            except Exception as gemini_err:
                if "429" in str(gemini_err) or "RESOURCE_EXHAUSTED" in str(gemini_err):
                    print("[ScamShield] Gemini quota exhausted — falling back to Groq Llama 3.1")
                else:
                    raise gemini_err
        
        # Groq fallback
        groq_client = get_groq_client()
        if groq_client:
            response = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                max_tokens=400,
                response_format={"type": "json_object"}
            )
            result = json.loads(response.choices[0].message.content)
            return {
                "score": max(0, min(100, int(result.get("scam_score", 50)))),
                "reasoning": result.get("reasoning", ""),
                "red_flags": result.get("red_flags", [])
            }
        return None
    except Exception as e:
        print(f"Gemini Analysis Error: {e}")
        return None

# ── HUMAN-FRIENDLY SCORING NOTATION ─────────────────────────────────────────
def humanize_factors(factors: list) -> list:
    """
    Converts internal scam-score notation to human-friendly trust notation.
    (+X) means penalty to scam score  → shown as [-X pts] (bad for user)
    (-X) means bonus reducing scam    → shown as [+X pts] (good for user)
    """
    result = []
    for f in factors:
        # (+X) = bad signal = show as -X pts
        f = re.sub(r'\(\+(\d+)\)', r'[-\1 pts]', f)
        # (-X) = good signal = show as +X pts
        f = re.sub(r'\(-(\d+)\)', r'[+\1 pts]', f)
        result.append(f)
    return result

# ── SCORING ENGINE ───────────────────────────────────────────────────────────

@app.post("/analyze")
def analyze_job(req: AnalyzeRequest):
    raw_text = req.text

    # 0. Image OCR — extract text from images embedded in the job post (salary flyers, banners, etc.)
    if req.image_data:
        print(f"[ScamShield] Running Gemini Vision OCR on {len(req.image_data)} image(s)...")
        image_text = ocr_images_with_gemini(req.image_data)
        if image_text:
            raw_text = raw_text + image_text
            print(f"[ScamShield] Image OCR added {len(image_text)} chars of extracted text")

    # 1. NLP Parse
    email = extract_email(raw_text)
    website = extract_url(raw_text)
    ner = extract_entities_spacy(raw_text)
    
    # Metadata overrides/hints
    meta = req.metadata or {}
    company = meta.get("company") or ner["company"] or "Unknown"

    # Recruiter: ONLY use metadata poster_name if metadata was provided.
    # If metadata was provided but poster_name is empty, it means no hiring card
    # was found — do NOT fall back to NLP which picks up investor/company names.
    if meta:
        recruiter = meta.get("poster_name") or "Not listed"
    else:
        recruiter = ner["recruiter_name"] or "Unknown"

    job_title = meta.get("title") or extract_job_title(raw_text, company)
    salary_mention = ner["salary_mention"]
    
    # Pre-compute trusted brand flag (used throughout scoring)
    company_lower = company.lower()
    is_trusted_brand = any(re.search(rf"\b{re.escape(brand)}\b", company_lower) for brand in FORTUNE_100_BRANDS)
    
    # 2. Basic Checks
    is_free_email = False
    email_domain = ""
    domain_exists = False
    
    if email:
        email_domain = email.split("@")[-1].lower()
        is_free_email = email_domain in FREE_EMAIL_DOMAINS
        domain_exists = check_domain_exists_dns(email_domain)

    scam_keywords = [kw for kw in SCAM_KEYWORDS if kw.lower() in raw_text.lower()]
    
    # Detect Region
    location = meta.get("location", "")
    region = detect_region(raw_text, location)
    
    india_scam_keywords = []
    uk_scam_keywords = []
    if region == "IN":
        india_scam_keywords = [kw for kw in INDIA_SCAM_KEYWORDS if kw.lower() in raw_text.lower()]
    elif region == "UK":
        uk_scam_keywords = [kw for kw in UK_SCAM_KEYWORDS if kw.lower() in raw_text.lower()]
    
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
    import ml_engine
    duplicate_count = ml_engine.get_duplicate_count(raw_text)
    has_scam_reports = check_web_scam_reports(company, email)
    review_data = check_employer_review_sites(company, region)
    
    # 4. COMPUTE RISK SCORE
    score = 0
    risk_factors = []
    
    # Bulk Spam Detection
    if duplicate_count >= 5:
        score += 30
        risk_factors.append(f"Bulk Spam: This exact job text has been seen {duplicate_count} times globally (+30)")

    # Web Scam Reports
    if has_scam_reports:
        score += 40
        risk_factors.append(f"Web OSINT: Found negative scam/fraud reports for '{company}' or '{email}' online (+40)")
        
    # Social Proof Scoring
    followers = meta.get("company_followers", "")
    hiring_stats = meta.get("hiring_stats", "").lower()
    
    if followers:
        num_match = re.search(r"([\d,]+)", followers)
        if num_match:
            try:
                num_followers = int(num_match.group(1).replace(",", ""))
                if num_followers < 100:
                    score += 15
                    risk_factors.append(f"Low Social Proof: Company has only {num_followers} followers (+15)")
                elif num_followers > 10000:
                    score -= 10
                    risk_factors.append(f"High Social Proof: Company has {num_followers:,} followers (-10)")
            except ValueError:
                pass
                
    if hiring_stats:
        if "first" in hiring_stats or "0 hired" in hiring_stats:
            score += 10
            risk_factors.append("First-time Hirer: Company has no past hiring history (+10)")

    # Glassdoor / Ambitionbox / Indeed Review Rating
    if review_data["rating"] is not None:
        rating = review_data["rating"]
        source = review_data["source"]
        if rating >= 4.0:
            score -= 15
            risk_factors.append(f"⭐ {source} Rating: {rating}/5.0 — Highly rated employer (-15)")
        elif rating >= 3.0:
            score -= 5
            risk_factors.append(f"⭐ {source} Rating: {rating}/5.0 — Average employer rating (-5)")
        elif rating < 2.5:
            score += 15
            risk_factors.append(f"⚠️ {source} Rating: {rating}/5.0 — Very poor employee reviews (+15)")
        else:
            risk_factors.append(f"⭐ {source} Rating: {rating}/5.0 — Below average employer rating")
    else:
        if company != "Unknown" and not is_trusted_brand:
            risk_factors.append(f"No reviews found on Glassdoor/Ambitionbox for '{company}'")
    
    # Keyword penalty
    if scam_keywords:
        kw_pts = len(scam_keywords) * 10
        score += kw_pts
        risk_factors.append(f"Found {len(scam_keywords)} global scam keywords (+{kw_pts})")
        
    if india_scam_keywords:
        in_kw_pts = len(india_scam_keywords) * 15
        score += in_kw_pts
        risk_factors.append(f"Found {len(india_scam_keywords)} India-specific scam keywords (+{in_kw_pts})")
        
    if uk_scam_keywords:
        uk_kw_pts = len(uk_scam_keywords) * 15
        score += uk_kw_pts
        risk_factors.append(f"Found {len(uk_scam_keywords)} UK-specific scam keywords (+{uk_kw_pts})")
        
    # Regional Salary Sanity Check
    lower_text = raw_text.lower()
    is_fresher_job = any(k in lower_text for k in ["fresher", "0-1 years", "no experience", "entry level"])
    
    if region == "IN":
        if "lpa" in lower_text or "lakh" in lower_text:
            lpa_matches = re.findall(r"(\d+(?:\.\d+)?)\s*(?:lpa|lakhs? per annum)", lower_text)
            if lpa_matches:
                try:
                    max_lpa = max(float(m) for m in lpa_matches)
                    if is_fresher_job and max_lpa > 10:
                        score += 15
                        risk_factors.append(f"Unrealistic Salary: Fresher role offering > 10 LPA ({max_lpa} LPA) (+15)")
                except ValueError:
                    pass
    elif region == "UK":
        if "£" in lower_text or "gbp" in lower_text:
            # Look for 80k, 100k, £80,000 etc
            pound_matches = re.findall(r"£\s*(\d{2,3})(?:,\d{3}|k)", lower_text)
            if pound_matches:
                try:
                    max_k = max(float(m) for m in pound_matches)
                    if is_fresher_job and max_k > 80:
                        score += 15
                        risk_factors.append(f"Unrealistic Salary: Entry-level role offering > £80k (£{max_k}k+) (+15)")
                except ValueError:
                    pass
    else: # US/Default
        if "$" in lower_text and ("data entry" in lower_text or "typing" in lower_text):
            dollar_matches = re.findall(r"\$\s*(\d{2,3})(?:,\d{3}|k)", lower_text)
            if dollar_matches:
                try:
                    max_k = max(float(m) for m in dollar_matches)
                    if max_k > 150:
                        score += 15
                        risk_factors.append(f"Unrealistic Salary: Simple task role offering > $150k (${max_k}k+) (+15)")
                except ValueError:
                    pass
                
    if "weekly payout" in lower_text or "paid weekly" in lower_text:
        score += 20
        risk_factors.append("Gig Indicator: Promises weekly payouts (+20)")
        
    # WhatsApp / Telegram contact = red flag
    if re.search(r'whatsapp|telegram|wa\.me|t\.me', lower_text):
        score += 25
        risk_factors.append("Messaging App Contact: Recruiter uses WhatsApp/Telegram instead of email (+25)")
    
    # Phone number in job post (early contact pressure)
    source = req.source.lower()
    phone_match = re.search(r'(\+?\d[\d\s\-]{8,}\d)', raw_text)
    if phone_match and source == "linkedin":
        score += 10
        risk_factors.append("Phone number shared in LinkedIn job post — unusual (+10)")
        
    # APP-SPECIFIC RULES
    if source == "linkedin":
        # --- LINKEDIN LOGIC ---
        poster_url = meta.get("poster_url", "")
        company_url = meta.get("company_url", "")
        headline = meta.get("poster_headline", "").lower()
        is_verified = meta.get("is_poster_verified", False)
        comp_size = meta.get("company_size", "").lower()
        
        # Determine if this is a company-page post (no individual recruiter)
        is_company_page_post = "linkedin.com/company/" in company_url
        
        if is_verified:
            score -= 45
            risk_factors.append("Verified Recruiter: LinkedIn confirmed identity (-45)")
        
        if is_company_page_post:
            # Jobs posted directly from an official company page are fine
            score -= 10
            risk_factors.append("Posted from Official Company LinkedIn Page (-10)")
        elif not poster_url:
            # On LinkedIn, most enterprise jobs are posted directly without personal recruiter profiles
            if is_trusted_brand:
                score -= 10
                risk_factors.append(f"Direct Enterprise Job Listing: {company} (-10)")
            else:
                # Neutral signal for standard company listings without an individual recruiter
                risk_factors.append("Direct Job Listing (no individual recruiter profile attached)")
        elif "linkedin.com/in/" in poster_url:
            score -= 15
            risk_factors.append("Valid LinkedIn Recruiter Profile Attached (-15)")
        elif "linkedin.com/company/" not in poster_url:
            score += 25
            risk_factors.append(f"External/Suspicious poster URL detected: {poster_url} (+25)")
        
        # Brand Impersonation via Company Size
        if is_trusted_brand and any(s in comp_size for s in ["1-10", "11-50", "51-200"]):
            score += 65
            risk_factors.append(f"High Impersonation Risk: Tiny company size ({comp_size}) claiming to be {company} (+65)")
        
        # Applicant count as trust signal
        applicants_text = meta.get("applicants", "").lower()
        if applicants_text:
            ap_match = re.search(r'([\d,]+)', applicants_text)
            if ap_match:
                try:
                    num_ap = int(ap_match.group(1).replace(",", ""))
                    if num_ap > 200:
                        score -= 10
                        risk_factors.append(f"High Applicant Count: {num_ap}+ applicants — widely circulated posting (-10)")
                except ValueError:
                    pass
        
        # Recruiter Headline Matching
        if headline and company != "Unknown":
            comp_words = [w for w in re.findall(r"\w+", company.lower()) if len(w) > 2]
            if any(w in headline for w in comp_words):
                score -= 20
                risk_factors.append(f"Recruiter Verified: Headline matches company '{company}' (-20)")
        
        # NLP Company name mismatch — ONLY flag if company name is NOT in text and NLP extracted a genuine different company
        nlp_company = ner.get("company", "")
        common_job_tokens = {"engineer", "developer", "manager", "intern", "analyst", "lead", "designer", 
                             "specialist", "executive", "officer", "associate", "consultant", "science", 
                             "intelligence", "learning", "data", "full stack", "degree", "equal opportunity", 
                             "culture", "inclusion", "belonging", "work", "job", "career", "applicant", 
                             "bangalore", "bengaluru", "mumbai", "noida", "hyderabad", "pune", "chennai", "delhi", "gurugram"}
        
        is_nlp_spurious = any(token in nlp_company.lower() for token in common_job_tokens) or len(nlp_company.strip()) <= 3
        is_company_in_text = (company.lower() in raw_text.lower()) if (company and company != "Unknown") else False
        
        if nlp_company and company != "Unknown" and nlp_company.lower() != company.lower() and not is_nlp_spurious and not is_company_in_text:
            from difflib import SequenceMatcher
            # Forgive third-party recruiters based on headline
            if any(k in headline for k in ["recruiter", "talent", "staffing", "acquisition", "sourcer", "hiring"]):
                risk_factors.append(f"Third-Party Recruiter detected: Ignoring company name mismatch for '{nlp_company}'")
            elif SequenceMatcher(None, nlp_company.lower(), company.lower()).ratio() < 0.5:
                penalty = 5 if is_trusted_brand else 15
                score += penalty
                risk_factors.append(f"Company name mismatch: Page says '{company}', text says '{nlp_company}' (+{penalty})")
                
        # Email checks on LinkedIn — absence is NORMAL, don't penalize
        # Only apply scores if an email is actually found in the post
        if email:
            if is_free_email:
                # Scammers post Gmail/Yahoo on LinkedIn — heavy flag
                score += 45
                risk_factors.append("Suspicious: Free email address used in LinkedIn job post (+45)")
            elif domain_matches:
                # Corporate email matching the company name — trust signal
                score -= 10
                risk_factors.append(f"Valid Corporate Email: {email} matches company domain (-10)")
            else:
                score += 20
                risk_factors.append("Email domain does not match company name (+20)")
        # No email found on LinkedIn = normal, no penalty

    elif source == "gmail" or source == "email":
        # --- EMAIL LOGIC ---
        # Email source always has a sender, so absence = suspicious
        if not email:
            score += 30
            risk_factors.append("No sender email found in scan (+30)")
        else:
            if is_free_email:
                score += 25
                risk_factors.append("Uses a free email address for hiring (+25)")
            elif domain_matches:
                # Corporate email matches company name — reward
                score -= 10
                risk_factors.append(f"Valid Corporate Email: {email} matches company domain (-10)")
            else:
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

    # Registry-aware Gemini Company Legitimacy Check
    # If company IS registered → trust bonus (already handled above)
    # If company is NOT registered → ask Gemini to assess based on known hiring history
    registry_result = {"registry": "Generic", "status": "unknown", "cin": None, "company_status": None}
    gemini_company_check = {"is_likely_legit": None, "summary": ""}
    
    if company and company != "Unknown":
        if is_trusted_brand:
            registry_result = {
                "registry": "Global Trust List",
                "status": "registered",
                "cin": "VERIFIED-CORP",
                "company_status": "Active"
            }
        else:
            registry_result = verify_company_registry(company, region)
            
        reg_status = registry_result["status"]
        reg_name = registry_result["registry"]
        
        if reg_status == "registered":
            comp_status = registry_result.get("company_status", "") or ""
            cin = registry_result.get("cin", "")
            if "strike" in comp_status.lower() or "defunct" in comp_status.lower() or "dissolved" in comp_status.lower() or "liquidation" in comp_status.lower():
                score += 50
                risk_factors.append(f"⚠️ {reg_name}: Company '{company}' is registered but marked STRUCK OFF/DISSOLVED (+50)")
            else:
                score -= 10
                cin_text = f" (ID: {cin})" if cin else ""
                risk_factors.append(f"✅ {reg_name} Verified: '{company}' is an active registered company{cin_text} (-10)")
        elif reg_status == "not_found" and region in ["IN", "UK"]:
            score += 20
            risk_factors.append(f"⚠️ {reg_name}: '{company}' not found in official {region} company registry (+20)")
            # Ask Gemini to assess legitimacy since registry check failed
            gemini_company_check = check_company_reputation_gemini(company)
            if gemini_company_check["is_likely_legit"] is True:
                score -= 15
                risk_factors.append(f"🤖 Gemini Company Check: '{company}' appears to be a known legitimate employer (-15) — {gemini_company_check['summary']}")
            elif gemini_company_check["is_likely_legit"] is False:
                score += 25
                risk_factors.append(f"🤖 Gemini Company Check: '{company}' is not a known legitimate employer (+25) — {gemini_company_check['summary']}")
            elif gemini_company_check["summary"]:
                risk_factors.append(f"🤖 Gemini Company Check: {gemini_company_check['summary']}")

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
    ml_prob = ml_engine.predict_ml(raw_text)
    
    if ml_prob is not None:
        ml_score = int(ml_prob * 100)
        risk_factors.append(f"Machine Learning Model scam probability: {ml_score}%")
        
        # Average the ML score to prevent false positives from generic ML uncertainty
        if ml_score > 75:
            final_score = int((score * 0.3) + (ml_score * 0.7))
            risk_factors.append("ML model heavily weighted due to high confidence (>75%)")
        else:
            final_score = int((score * 0.5) + (ml_score * 0.5))
    else:
        final_score = score
        
    final_score = max(0, min(final_score, 100))

    # 5b. BERT + ExtraTrees ML PREDICTION (Part 3 — Neural Deep Analysis)
    # Uses BERT mean-pool embeddings (768-dim) stacked with TF-IDF (5000-dim)
    # trained on the fake_job_postings dataset with ADASYN oversampling.
    # Gracefully skipped if model files haven't been generated yet.
    bert_prob = None
    try:
        import ml_engine_bert
        if ml_engine_bert.is_model_ready():
            bert_prob = ml_engine_bert.predict_bert(raw_text)
            if bert_prob is not None:
                bert_score = int(bert_prob * 100)
                risk_factors.append(f"🧠 BERT Neural Model (Part 3) scam probability: {bert_score}%")
                # High-confidence BERT result gets 60% weight; uncertain gets 30%
                if bert_score > 70:
                    final_score = int((final_score * 0.4) + (bert_score * 0.6))
                    risk_factors.append("BERT neural model highly confident — weighted heavily")
                elif bert_score < 25:
                    final_score = int((final_score * 0.5) + (bert_score * 0.5))
                    risk_factors.append("BERT neural model indicates low scam probability")
                else:
                    final_score = int((final_score * 0.7) + (bert_score * 0.3))
                final_score = max(0, min(final_score, 100))
        else:
            print("[ScamShield] BERT model not trained yet — run train_bert_model.py to enable Part 3 ML")
    except Exception as bert_err:
        print(f"[ScamShield] BERT ML skipped: {bert_err}")

    # 6. Gemini / Groq AI ANALYSIS (platform-aware)
    gpt_result = analyze_with_gpt(raw_text, source, company, recruiter, metadata=meta, registry_data=registry_result, review_data=review_data)
    gpt_score = None
    gpt_reasoning = None
    gpt_red_flags = []
    
    if gpt_result:
        gpt_score = gpt_result["score"]
        gpt_reasoning = gpt_result["reasoning"]
        gpt_red_flags = gpt_result["red_flags"]
        
        risk_factors.append(f"🤖 Gemini 2.0 Flash Score: {gpt_score}/100 — {gpt_reasoning}")
        for flag in gpt_red_flags:
            risk_factors.append(f"🚩 AI Flag: {flag}")
        
        # Blend AI score: 40% AI, 60% existing combined score
        # If AI is highly confident either way, give it more weight
        if gpt_score >= 75 or gpt_score <= 20:
            final_score = int((final_score * 0.4) + (gpt_score * 0.6))
            risk_factors.append("Groq AI confidence is high — weighted heavily in final verdict")
        else:
            final_score = int((final_score * 0.6) + (gpt_score * 0.4))
        
        final_score = max(0, min(final_score, 100))
    
    # Verdict
    if final_score < 35:
        verdict = "✅ Likely Genuine"
        color = "green"
    elif final_score <= 60:
        verdict = "⚠️ Possibly Suspicious"
        color = "orange"
    elif final_score <= 80:
        verdict = "🚫 Likely Fraudulent"
        color = "red"
    else:
        verdict = "🚨 Very Likely Fraudulent"
        color = "red"

    # Save to SQLite Database
    job_id = ml_engine.save_job(raw_text, final_score)
    
    # Convert scoring notation to human-friendly format
    risk_factors = humanize_factors(risk_factors)

    return {
        "job_id": job_id,
        "job_title": job_title,
        "company": company,
        "recruiter": recruiter,
        "email": email,
        "risk_score": final_score,
        "rules_score_base": score,
        "ml_probability": ml_prob,
        "bert_probability": bert_prob,
        "gpt_score": gpt_score,
        "gpt_reasoning": gpt_reasoning,
        "registry_name": registry_result.get("registry", "Generic"),
        "registry_status": registry_result.get("status"),
        "registry_id": registry_result.get("cin"),
        "registry_company_status": registry_result.get("company_status"),
        "has_scam_reports": has_scam_reports,
        "duplicate_scan_count": duplicate_count,
        "verdict": verdict,
        "color": color,
        "scam_keywords": scam_keywords,
        "domain_age_days": domain_age_days,
        "is_impersonating": is_impersonating,
        "target_brand": target_brand,
        "has_online_presence": has_online_presence,
        "risk_factors": risk_factors
    }

# ── DEEP VERIFICATION (scraper2.py integration) ──────────────────────────────

import threading

def _run_deep_verify(task_key: str, job_title: str, company: str):
    """
    Runs scraper2.py's async engine in a background thread.
    Checks 14 job platforms + Google + company careers page.
    Stores result in _verify_tasks[task_key].
    """
    try:
        from scraper2 import (
            clean_job_title, clean_company_name,
            _async_verify, aggregate_verdict,
        )
        import asyncio, re, sys

        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

        clean_title   = clean_job_title(job_title)
        clean_company = clean_company_name(company)

        # Capture printed output to parse results
        import io, sys
        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf

        asyncio.run(_async_verify(clean_title, clean_company, job_title))

        sys.stdout = old_stdout
        output = buf.getvalue()

        # Parse final verdict from output
        verdict_real     = "✅  REAL" in output
        verdict_uncertain = "⚠️  UNCERTAIN" in output
        verdict_suspicious = "⛔  SUSPICIOUS" in output

        is_known_brand = any(re.search(rf"\b{re.escape(brand)}\b", company.lower()) for brand in FORTUNE_100_BRANDS)

        if verdict_real or is_known_brand:
            status_label = "Confirmed Real"
            color = "green"
        elif verdict_uncertain:
            status_label = "Uncertain — Direct Portal Listing"
            color = "orange"
        else:
            status_label = "Unconfirmed on Portals"
            color = "orange" if is_known_brand else "red"

        # Extract platforms confirmed/not-found
        confirmed_str = re.findall(r"Confirmed on\s*:\s*(.+)", output)
        not_found_str = re.findall(r"Not found on\s*:\s*(.+)", output)
        careers_url   = re.findall(r"Careers URL\s*:\s*(\S+)", output)
        time_taken    = re.findall(r"Total time\s*:\s*([\d.]+)s", output)

        confirmed_list = [p.strip() for p in confirmed_str[0].split(",") if p.strip()] if confirmed_str else []
        not_found_list = [p.strip() for p in not_found_str[0].split(",") if p.strip()] if not_found_str else []

        # ── Platform-count-based score adjustment ─────────────────────────
        job_portals = {"Naukri","Indeed","LinkedIn","Glassdoor","Shine","Foundit",
                       "TimesJobs","Monster","SimplyHired","Internshala","Wellfound",
                       "iimjobs","Cutshort","Instahyre"}
        portal_hits = sum(1 for p in confirmed_list if p in job_portals)
        has_careers  = "Careers page" in confirmed_list
        has_google   = "Google" in confirmed_list

        if portal_hits == 0 and not has_careers and not has_google:
            if is_known_brand:
                score_adjustment = -10
                adj_reason = f"Verified enterprise direct listing ({company}) (-10)"
            else:
                score_adjustment = +5
                adj_reason = f"Not confirmed on external job platforms (+5 risk)"
        elif portal_hits <= 2:
            score_adjustment = -10
            adj_reason = f"Found on {portal_hits} platform(s) (-10 risk)"
        elif portal_hits <= 5:
            score_adjustment = -20
            adj_reason = f"Found on {portal_hits} platforms (-20 risk)"
        else:
            score_adjustment = -30
            adj_reason = f"Found on {portal_hits}+ platforms (-30 risk)"

        if has_careers:
            score_adjustment -= 10
            adj_reason += " + Careers page verified (-10)"
        if has_google:
            score_adjustment -= 5
            adj_reason += " + Google confirmed (-5)"

        score_adjustment = max(-50, min(score_adjustment, +25))  # cap range
        # ─────────────────────────────────────────────────────────────────

        _verify_tasks[task_key] = {
            "status": "done",
            "result": {
                "verdict": status_label,
                "color": color,
                "confirmed_on": confirmed_list,
                "not_found_on": not_found_list,
                "portal_hits": portal_hits,
                "score_adjustment": score_adjustment,
                "adj_reason": adj_reason,
                "careers_url": careers_url[0] if careers_url else None,
                "time_taken": float(time_taken[0]) if time_taken else None,
                "raw_output": output[-1500:] if len(output) > 1500 else output
            }
        }

    except Exception as e:
        _verify_tasks[task_key] = {
            "status": "done",
            "result": {
                "verdict": "Verification Error",
                "color": "grey",
                "error": str(e),
                "confirmed_on": [],
                "not_found_on": []
            }
        }


@app.post("/verify")
def start_deep_verify(req: VerifyRequest):
    """
    Starts a background deep verification using scraper2.py (14 platforms + Google + Careers).
    Returns a task_key immediately — poll /verify_status/{task_key} for results.
    Takes 30-120 seconds to complete.
    """
    task_key = f"{req.job_title.lower().strip()}|{req.company.lower().strip()}"

    if task_key in _verify_tasks and _verify_tasks[task_key]["status"] == "done":
        return {"task_key": task_key, "status": "done", **_verify_tasks[task_key]["result"]}

    if task_key not in _verify_tasks:
        _verify_tasks[task_key] = {"status": "pending", "result": None}
        t = threading.Thread(target=_run_deep_verify, args=(task_key, req.job_title, req.company), daemon=True)
        t.start()
        print(f"[ScamShield] Deep verify started: {req.job_title} @ {req.company}")

    return {"task_key": task_key, "status": "pending"}


@app.get("/verify_status/{task_key:path}")
def get_verify_status(task_key: str):
    """Poll this endpoint after calling /verify. Returns status + result when done."""
    task = _verify_tasks.get(task_key)
    if not task:
        return {"status": "not_found"}
    if task["status"] == "pending":
        return {"task_key": task_key, "status": "pending"}
    return {"task_key": task_key, "status": "done", **task["result"]}


# ── UNIFIED FULL SCAN (analyze + deep scraper → one final result) ─────────────

import uuid

def _run_full_scan(scan_id: str, req_dict: dict):
    """
    Background thread:
    1. Runs the fast /analyze scoring engine
    2. Runs scraper2.py deep verify (14 platforms + Google + Careers)
    3. Merges scores → stores final combined result
    """
    try:
        # Phase 1: Fast analyze
        _full_scan_tasks[scan_id]["phase"] = "analyzing"

        # Re-construct the AnalyzeRequest and call analyze_job directly
        from fastapi.testclient import TestClient
        import json as _json

        # Call the analyze logic directly (avoid HTTP roundtrip)
        ar = AnalyzeRequest(**req_dict)
        analyze_result = analyze_job(ar)

        job_title = analyze_result.get("job_title", "")
        company   = analyze_result.get("company", "")
        base_risk = analyze_result.get("risk_score", 50)

        _full_scan_tasks[scan_id]["analyze_result"] = analyze_result
        _full_scan_tasks[scan_id]["phase"] = "deep_scanning"

        # Phase 2: Deep scraper (only if we have title + company)
        score_adjustment = 0
        adj_reason = ""
        deep_data = {}

        if job_title and company and job_title != "Unknown" and company != "Unknown":
            task_key = f"{job_title.lower().strip()}|{company.lower().strip()}"
            _verify_tasks[task_key] = {"status": "pending", "result": None}
            _run_deep_verify(task_key, job_title, company)   # blocking call
            dv = _verify_tasks.get(task_key, {}).get("result") or {}
            score_adjustment = dv.get("score_adjustment", 0)
            adj_reason       = dv.get("adj_reason", "")
            deep_data        = dv
        else:
            deep_data = {"verdict": "Skipped — no title/company", "confirmed_on": [], "not_found_on": [], "portal_hits": 0}

        # Phase 3: Merge
        final_risk  = max(0, min(100, base_risk + score_adjustment))
        final_trust = 100 - final_risk

        # Rebuild verdict with final score
        if final_risk <= 35:
            verdict = "Likely Genuine"
            color   = "green"
        elif final_risk <= 60:
            verdict = "Possibly Suspicious"
            color   = "orange"
        else:
            verdict = "Likely Fraudulent"
            color   = "red"

        # Merge risk factors with scraper result
        risk_factors = analyze_result.get("risk_factors", [])
        if adj_reason:
            risk_factors = risk_factors + [f"🌐 Platform Verification: {adj_reason}"]

        final_result = {
            **analyze_result,
            "risk_score": final_risk,
            "verdict": verdict,
            "color": color,
            "risk_factors": risk_factors,
            "deep_verify": deep_data,
            "score_adjustment": score_adjustment,
        }

        _full_scan_tasks[scan_id]["status"]       = "done"
        _full_scan_tasks[scan_id]["phase"]        = "done"
        _full_scan_tasks[scan_id]["final_result"] = final_result

    except Exception as e:
        import traceback
        _full_scan_tasks[scan_id]["status"]       = "done"
        _full_scan_tasks[scan_id]["phase"]        = "error"
        _full_scan_tasks[scan_id]["final_result"] = {
            "error": str(e),
            "verdict": "Scan Error",
            "color": "grey",
            "risk_score": 50
        }
        print(f"[ScamShield] Full scan error: {traceback.format_exc()}")


@app.post("/full_scan")
def start_full_scan(req: FullScanRequest):
    """
    Starts a unified full scan: fast analyze + deep scraper.
    Returns scan_id immediately — poll /full_scan_status/{scan_id} for result.
    Typically completes in 30–120 seconds.
    """
    scan_id = str(uuid.uuid4())[:8]
    req_dict = {
        "text": req.text,
        "source": req.source,
        "metadata": req.metadata,
        "image_data": req.image_data,
        "image_urls": []
    }
    _full_scan_tasks[scan_id] = {
        "status": "pending",
        "phase": "starting",
        "analyze_result": None,
        "final_result": None
    }
    t = threading.Thread(target=_run_full_scan, args=(scan_id, req_dict), daemon=True)
    t.start()
    print(f"[ScamShield] Full scan started: {scan_id}")
    return {"scan_id": scan_id, "status": "pending"}


@app.get("/full_scan_status/{scan_id}")
def get_full_scan_status(scan_id: str):
    """Poll after /full_scan. Returns phase updates while running, final result when done."""
    task = _full_scan_tasks.get(scan_id)
    if not task:
        return {"status": "not_found"}
    if task["status"] == "pending":
        return {
            "scan_id": scan_id,
            "status": "pending",
            "phase": task.get("phase", "starting"),
            # Return fast analyze result as soon as it's available for early display
            "analyze_result": task.get("analyze_result")
        }
    return {
        "scan_id": scan_id,
        "status": "done",
        **task["final_result"]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
