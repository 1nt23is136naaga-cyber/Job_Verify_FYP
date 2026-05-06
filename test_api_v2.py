import requests
import json

url = "http://127.0.0.1:8000/analyze"
data = {
    "text": "Google is hiring a Senior Software Engineer. Contact recruiter John Doe at john.doe@gmail.com. Apply at https://careers.google.com",
    "source": "linkedin"
}

response = requests.post(url, json=data)
print(json.dumps(response.json(), indent=2))

data_scam = {
    "text": "URGENT! data entry job. earn $500 weekly. No experience. Contact on Telegram @jobscam.",
    "source": "other"
}
response_scam = requests.post(url, json=data_scam)
print(json.dumps(response_scam.json(), indent=2))
