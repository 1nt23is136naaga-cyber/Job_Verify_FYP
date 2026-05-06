import sqlite3
import ml_engine

scams = [
    "Google is hiring an urgently driven remote data entry specialist. $1000 weekly payment. No exact requirements. DM me on WhatsApp at +123456789 or message on Telegram @recruiter immediately. Registration fee of $50 required to process application. Contact Mike on mike.hiring@gmail.com",
    "URGENT HIRING!!! Work from home typing jobs. Make $500 a day. No experience needed. Immediate joiners only. Pay a small refundable security deposit of $30 to start. WhatsApp me ASAP.",
    "Congratulations! Your resume has been shortlisted for the Data Analyst role. Salary is $85,000. Before we proceed, please click this link to purchase your home office equipment using our approved vendor.",
    "Hiring virtual assistants. Kindly message our HR on Telegram @HR_recruiter. We pay in cryptocurrency. No interview required, start immediately.",
    "Immediate requirement for remote customer service. You will receive a check to buy software. Deposit the check and send the remaining funds via Zelle to our vendor."
]

safes = [
    "We are looking for a Software Engineer to join our core infrastructure team. Requirements: 3+ years of experience with Python and AWS. Bachelor's degree in Computer Science. Please apply through our career portal at careers.legitcompany.com.",
    "Marketing Manager needed for a fast-growing startup in New York. Typical duties include running campaigns, managing social media, and leading a team of 3. Salary range: $90k - $120k + benefits. Apply online.",
    "Join our hospital as a Registered Nurse. Must have valid state nursing license and 1 year of clinical experience. We offer comprehensive health, dental, and retirement plans.",
    "Hiring a full-time Accountant. CPA required. The role involves managing general ledger, preparing financial statements, and coordinating audits. Our office is located in downtown Chicago.",
    "Looking for an experienced UX Designer to revamp our mobile app. You should have a strong portfolio demonstrating user-centered design principles. Figma expertise is a must."
]

conn = sqlite3.connect('jobs.db')
c = conn.cursor()

# Ensure table schema has expected columns (they should exist based on api.py)
for text in scams:
    c.execute("INSERT INTO jobs (raw_text, user_label) VALUES (?, ?)", (text, 1))
for text in safes:
    c.execute("INSERT INTO jobs (raw_text, user_label) VALUES (?, ?)", (text, 0))

conn.commit()
conn.close()

ml_engine.retrain_model()
print("Successfully injected extreme scam/safe examples and retrained!")

# Test the fake again
print("New Scam Prob for test fake:", ml_engine.predict_ml("Google is hiring an urgently driven remote data entry specialist. $1000 weekly payment. No exact requirements. DM me on WhatsApp at +123456789 or message on Telegram @recruiter immediately. Registration fee of $50 required to process application. Contact Mike on mike.hiring@gmail.com"))
