import requests
import json

API_URL = "http://localhost:8000/analyze"

cases = [
    {
        "name": "Obvious Scam (Data Entry)",
        "text": "Google is hiring an urgently driven remote data entry specialist. $1000 weekly payment. No exact requirements. DM me on WhatsApp at +123456789 or message on Telegram @recruiter immediately. Registration fee of $50 required to process application. Contact Mike on mike.hiring@gmail.com"
    },
    {
        "name": "Subtle Scam (Typing Job)",
        "text": "URGENT HIRING!!! Work from home typing jobs. Make $500 a day. No experience needed. Immediate joiners only. Pay a small refundable security deposit of $30 to start. WhatsApp me ASAP."
    },
    {
        "name": "Legit Tech Job",
        "text": "We are looking for a Software Engineer to join our core infrastructure team. Requirements: 3+ years of experience with Python and AWS. Bachelor's degree in Computer Science. Please apply through our career portal at careers.legitcompany.com."
    },
    {
        "name": "Legit Marketing Job",
        "text": "Marketing Manager needed for a fast-growing startup in New York. Typical duties include running campaigns, managing social media, and leading a team of 3. Salary range: $90k - $120k + benefits. Apply online."
    }
]

print("Testing ScamShield API...")
for c in cases:
    print(f"\nEvaluating: {c['name']}")
    try:
        r = requests.post(API_URL, json={"text": c["text"]})
        data = r.json()
        print(f"Risk Score: {data['risk_score']}/100")
        print(f"Verdict:    {data['verdict']}")
    except Exception as e:
        print(f"FAILED: {e}")
