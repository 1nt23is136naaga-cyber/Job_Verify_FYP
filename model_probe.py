import urllib.request
import json
import sys
import os
from dotenv import load_dotenv

load_dotenv()
sys.stdout.reconfigure(encoding='utf-8')

API_KEY = os.getenv("GOOGLE_API_KEY", "")
models = ["gemini-flash-latest", "gemini-3.6-flash", "gemini-3.1-flash-lite"]

prompt = (
    "You are ScamShield AI. Analyze this job posting: 'Work from home data entry $1000/day on telegram'. "
    "Classify the risk level. "
    "Respond with JSON format: "
    "{\"risk_score\": <integer from 0 to 100 where 100 is maximum scam risk>, "
    "\"verdict\": \"<Low Risk Posting | Moderate Risk | High Risk Posting | Very High Risk>\", "
    "\"color\": \"<green | orange | red>\", "
    "\"reasoning\": \"<explanation>\", "
    "\"risk_factors\": [\"<factor 1>\", \"<factor 2>\"]}"
)

for m in models:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 1500,
            "responseMimeType": "application/json"
        }
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            candidate = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(candidate)
            print(f"=== ✅ {m} SUCCESS ===")
            print(json.dumps(parsed, indent=2))
    except Exception as e:
        print(f"=== ❌ {m} FAILED: {e} ===")
