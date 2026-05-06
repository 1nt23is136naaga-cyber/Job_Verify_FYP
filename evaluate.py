# -*- coding: utf-8 -*-
"""
evaluate.py — Model Evaluation Script
AI Job Scam Detection and Recruiter Verification System

Computes:
  - Accuracy
  - Precision
  - Recall
  - F1 Score
  - Confusion Matrix
  - Per-example breakdown table

Labels:
  0 = Legitimate/Genuine
  1 = Scam / Suspicious

Usage:
  python -X utf8 evaluate.py
"""

import re
import socket
import urllib.parse
from difflib import SequenceMatcher

import spacy

nlp = spacy.load("en_core_web_sm")

# ==============================================================================
# CONFIG (same as main system)
# ==============================================================================

SCAM_KEYWORDS = [
    # Financial bait
    "earn $", "earn up to", "weekly pay", "make money fast",
    "no experience needed", "work from home and earn",
    "guaranteed income", "unlimited earnings", "passive income",
    "$500 weekly", "$1000 weekly", "daily payment", "daily income",

    # Urgency / pressure
    "urgent hiring", "immediate joining", "apply now", "limited slots",
    "hurry", "act fast", "only a few spots left", "immediate requirement",

    # Suspicious payment / fee
    "registration fee", "processing fee", "training fee", "pay to apply",
    "refundable deposit", "send money", "western union", "wire transfer",
    "training kit", "security deposit",

    # Informal contact channels (HIGH RISK)
    "contact on whatsapp", "contact on telegram", "dm for details",
    "chat on hangouts", "google hangout", "yahoo messenger",
    "message us on telegram", "whatsapp immediately",

    # Vague roles
    "data entry", "form filling", "simple typing job",
    "part time online job", "home-based typing", "home typing job",

    # Too-good-to-be-true
    "no qualification required", "no interview", "direct selection",
    "100% job guarantee", "assured placement", "no interview needed",
]

FREE_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "aol.com", "mail.com", "protonmail.com", "icloud.com",
    "yopmail.com", "guerrillamail.com", "tempmail.com", "mailinator.com",
}

# ==============================================================================
# LABELED TEST DATASET
# Each entry: (description_text, true_label)
#   true_label = 0 → Legitimate
#   true_label = 1 → Scam / Suspicious
# ==============================================================================

TEST_DATASET = [
    # ── GENUINE (label = 0) ──────────────────────────────────────────────────
    (
        "Microsoft is hiring a Software Engineer. Contact Sarah Thompson at "
        "sarah@microsoft.com. Apply at https://careers.microsoft.com. "
        "The role involves Azure cloud services development.",
        0
    ),
    (
        "Google is looking for a Senior Data Scientist. Reach out to recruiter "
        "James Carter at jcarter@google.com. Visit https://careers.google.com to apply.",
        0
    ),
    (
        "Amazon Web Services is hiring a Solutions Architect. Contact recruiter "
        "Emily Davis at emily.davis@amazon.com. Careers page: https://www.amazon.jobs.",
        0
    ),
    (
        "Infosys is seeking a Java Developer with 3 years of experience. "
        "Send resume to hr@infosys.com. More info at https://www.infosys.com/careers.",
        0
    ),
    (
        "Deloitte is hiring a Business Analyst for their consulting team. "
        "Recruiter: Rachel Green at rgreen@deloitte.com. "
        "Apply at https://careers.deloitte.com.",
        0
    ),
    (
        "Tata Consultancy Services is looking for a Python Developer. "
        "Email your CV to recruit@tcs.com. Visit https://www.tcs.com/careers.",
        0
    ),
    (
        "Wipro is hiring a Network Engineer. Contact hr.wipro@wipro.com for details. "
        "Official careers portal: https://careers.wipro.com.",
        0
    ),
    (
        "IBM is looking for a Machine Learning Engineer. "
        "Contact john.smith@ibm.com. Apply at https://ibm.com/us-en/employment.",
        0
    ),
    (
        "Accenture is seeking a Cloud Consultant. "
        "Reach recruiter Nina Patel at npatel@accenture.com. "
        "Interview process: phone screening, then technical round.",
        0
    ),
    (
        "JPMorgan Chase is hiring a Risk Analyst for their finance team. "
        "Contact talent@jpmchase.com. Official site: https://careers.jpmorgan.com.",
        0
    ),

    # ── SCAM (label = 1) ────────────────────────────────────────────────────
    (
        "URGENT! Earn $500 weekly with our data entry job. No experience needed. "
        "Work from home. Contact on Telegram. Registration fee required. Apply now!",
        1
    ),
    (
        "Make money fast! Simple form filling job. Earn up to $1000 weekly. "
        "No qualification required. DM for details on WhatsApp immediately.",
        1
    ),
    (
        "Immediate joining required for part time online job. Guaranteed income. "
        "Send payment via Western Union for training kit. No interview needed.",
        1
    ),
    (
        "Work from home and earn $800 per week. 100% job guarantee. "
        "No experience needed. Limited slots available. Pay registration fee to start.",
        1
    ),
    (
        "Hurry! Only a few spots left for our data entry work from home job. "
        "Earn daily payment. Contact on Google Hangouts. Processing fee applies.",
        1
    ),
    (
        "Amazon job — work from home data entry. Earn $500 weekly. "
        "Contact recruiter at amazonjobs.recruiter@gmail.com for details. "
        "Registration fee: $50 refundable deposit.",
        1
    ),
    (
        "Google hiring for home-based typing job. Earn $200 daily. "
        "No experience. No interview. Direct selection. "
        "Contact hrrecruiter99@yahoo.com. Act fast!",
        1
    ),
    (
        "Simple online job. Earn unlimited earnings from home. "
        "Passive income guaranteed. Contact agent on Telegram now. "
        "Training fee applies. Apply immediately.",
        1
    ),
    (
        "Infosys BPO data entry job. $1000 weekly pay. No experience needed. "
        "Send your details to infosysjobs.hiring@gmail.com. "
        "Pay processing fee of Rs.500 to register.",
        1
    ),
    (
        "Microsoft is hiring for home typing job. Earn $300 per day. "
        "No qualification required. 100% job guarantee. "
        "Contact microsoftwork@hotmail.com. Registration fee required.",
        1
    ),

    # ── BORDERLINE / EDGE CASES ─────────────────────────────────────────────
    # (labelled as scam = 1 because of suspicious signals)
    (
        "Accenture is looking for a Business Analyst. "
        "Send CV to mikejohnson.recruiter@gmail.com. "
        "Guaranteed placement. No interview required.",
        1
    ),
    (
        "TCS hiring Python Developer. Contact tcs.recruiter2024@yahoo.com. "
        "Urgent requirement. Immediate joining. WhatsApp for faster response.",
        1
    ),
    # (labelled as genuine = 0 — corporate email, no red flags)
    (
        "Cognizant is hiring a Cybersecurity Analyst. "
        "Contact recruiter@cognizant.com for details. "
        "Apply at https://careers.cognizant.com. 5+ years experience required.",
        0
    ),
    (
        "HCL Technologies is looking for a UI/UX Designer. "
        "Send portfolio to design.hr@hcl.com. "
        "Official careers: https://www.hcltech.com/careers.",
        0
    ),
]

# ==============================================================================
# DETECTION PIPELINE (inline copy — no import dependency)
# ==============================================================================

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
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip().title()
    return "Not Detected"

def parse_natural_input(raw_text):
    email = extract_email(raw_text)
    website = extract_url(raw_text)
    ner = extract_entities_spacy(raw_text)
    return {
        "job_title": extract_job_title(raw_text, ner["company"]),
        "company": ner["company"] or "Unknown",
        "recruiter_name": ner["recruiter_name"] or "Unknown",
        "recruiter_email": email,
        "company_website": website,
        "job_description": raw_text.strip(),
        "salary_mention": ner["salary_mention"],
    }

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
    score += len(scam_keywords) * 10
    if not domain_exists and has_email:
        score += 15
    if salary_mention and is_free_email:
        score += 10
    if has_website and domain_exists:
        score -= 10
    if has_email and not is_free_email:
        score -= 5
    return max(0, min(score, 100))

def predict(raw_text):
    """
    Run full pipeline and return:
      - predicted_label: 0 (Genuine) or 1 (Scam/Suspicious)
      - risk_score: 0-100
      - verdict string
    """
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
    # Threshold: score >= 20 → predicted scam (1), else genuine (0)
    predicted_label = 1 if risk_score >= 20 else 0
    if risk_score < 20:
        verdict = "LIKELY GENUINE"
    elif risk_score <= 59:
        verdict = "SUSPICIOUS"
    else:
        verdict = "HIGH SCAM RISK"
    return predicted_label, risk_score, verdict

# ==============================================================================
# METRICS CALCULATION (manual — no sklearn dependency)
# ==============================================================================

def compute_metrics(y_true, y_pred):
    """
    Compute Accuracy, Precision, Recall, F1 from binary label lists.

    Definitions (positive class = 1 = Scam):
      TP: predicted scam,    actually scam
      FP: predicted scam,    actually genuine
      TN: predicted genuine, actually genuine
      FN: predicted genuine, actually scam
    """
    TP = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    FP = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    TN = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
    FN = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)

    total = len(y_true)
    accuracy  = (TP + TN) / total if total else 0
    precision = TP / (TP + FP) if (TP + FP) else 0
    recall    = TP / (TP + FN) if (TP + FN) else 0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) else 0)

    return {
        "accuracy":  round(accuracy  * 100, 2),
        "precision": round(precision * 100, 2),
        "recall":    round(recall    * 100, 2),
        "f1_score":  round(f1        * 100, 2),
        "TP": TP, "FP": FP, "TN": TN, "FN": FN,
    }

# ==============================================================================
# MAIN EVALUATION RUNNER
# ==============================================================================

def run_evaluation():
    print("\n" + "=" * 65)
    print("  EVALUATION — AI Job Scam Detection System")
    print(f"  Test samples: {len(TEST_DATASET)}")
    print("=" * 65)

    y_true = []
    y_pred = []
    results = []

    for i, (text, true_label) in enumerate(TEST_DATASET, 1):
        pred_label, risk_score, verdict = predict(text)
        y_true.append(true_label)
        y_pred.append(pred_label)
        correct = (pred_label == true_label)
        results.append({
            "id": i,
            "text_snippet": text[:60].replace("\n", " ") + "...",
            "true": "SCAM" if true_label == 1 else "GENUINE",
            "pred": "SCAM" if pred_label == 1 else "GENUINE",
            "score": risk_score,
            "verdict": verdict,
            "correct": correct,
        })

    # ── Per-Example Table ──────────────────────────────────────────────────
    print(f"\n{'#':>3}  {'TRUE':<8}  {'PRED':<8}  {'SCORE':>5}  {'OK?':<4}  SNIPPET")
    print("-" * 65)
    for r in results:
        ok = "OK" if r["correct"] else "FAIL"
        print(f"{r['id']:>3}  {r['true']:<8}  {r['pred']:<8}  {r['score']:>5}  {ok:<4}  {r['text_snippet']}")

    # ── Metrics ────────────────────────────────────────────────────────────
    m = compute_metrics(y_true, y_pred)

    print("\n" + "=" * 65)
    print("  METRICS SUMMARY")
    print("=" * 65)
    print(f"  Accuracy   : {m['accuracy']:.2f}%")
    print(f"  Precision  : {m['precision']:.2f}%  (of all scam predictions, how many were right)")
    print(f"  Recall     : {m['recall']:.2f}%  (of all actual scams, how many were caught)")
    print(f"  F1 Score   : {m['f1_score']:.2f}%  (harmonic mean of precision & recall)")
    print("=" * 65)

    # ── Confusion Matrix ───────────────────────────────────────────────────
    print("""
  CONFUSION MATRIX
                  Predicted GENUINE   Predicted SCAM
  Actual GENUINE       TN = {TN}              FP = {FP}
  Actual SCAM          FN = {FN}              TP = {TP}
""".format(**m))

    # ── False Positives / Negatives detail ────────────────────────────────
    wrong = [r for r in results if not r["correct"]]
    if wrong:
        print(f"  MISCLASSIFIED ({len(wrong)} samples):")
        for r in wrong:
            print(f"    Sample {r['id']}: TRUE={r['true']}, PRED={r['pred']}, "
                  f"Score={r['score']} — \"{r['text_snippet']}\"")
    else:
        print("  All samples classified correctly!")

    print("=" * 65 + "\n")


if __name__ == "__main__":
    run_evaluation()
