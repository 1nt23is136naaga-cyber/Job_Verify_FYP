import requests
import json

url = "http://127.0.0.1:8000/analyze"

# Case 1: LinkedIn Job with no email but legit looking metadata
data_legit = {
    "text": "Join our team at Microsoft as a Senior Developer. We are building the future of AI.",
    "source": "linkedin",
    "metadata": {
        "company": "Microsoft",
        "title": "Senior Software Engineer",
        "poster_name": "Satya Nadella",
        "poster_url": "https://www.linkedin.com/in/satyanadella/"
    }
}
response_legit = requests.post(url, json=data_legit)
print("--- Legit LinkedIn Job ---")
print(json.dumps(response_legit.json(), indent=2))

# Case 2: LinkedIn Job with no email and suspicious poster URL
data_scam = {
    "text": "URGENT! data entry. earn $500 weekly.",
    "source": "linkedin",
    "metadata": {
        "company": "FastCash Inc",
        "title": "Data Entry Specialist",
        "poster_name": "Unknown Person",
        "poster_url": "https://bit.ly/suspicious-profile"
    }
}
response_scam = requests.post(url, json=data_scam)
print("\n--- Suspicious LinkedIn Job ---")
print(json.dumps(response_scam.json(), indent=2))
