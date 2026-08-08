# Privacy Policy — ScamShield (AI Job Scam Detector)
**Last updated:** August 2026

## 1. Overview
ScamShield is a cybersecurity and scam detection browser extension designed to protect job seekers from employment fraud, phishing, advance-fee training scams, and fake job postings on platforms including LinkedIn, Gmail, Internshala, and Naukri.

## 2. Information We Collect and Process
When a user explicitly triggers a scan:
- **Job Description & Metadata**: The text of the active job posting (role title, company name, compensation mention, and recruiter headline) is transmitted securely via HTTPS to the ScamShield classification engine.
- **Embedded Post Images**: Images explicitly embedded in the job description area are scanned on-demand for embedded text (such as hidden WhatsApp numbers or payment QR codes) using optical character recognition.
- **Local History**: Scan scores are stored strictly locally in your browser's `chrome.storage.local` sandbox for your review and history tab.

## 3. How We Use Your Data
- Data is processed in real time solely to evaluate scam probabilities using deterministic heuristic rules, machine learning models, and large language model APIs.
- We do **NOT** sell, rent, or monetize your data.
- We do **NOT** collect your personal browser history, passwords, cookies, or non-job related web activity.

## 4. Third-Party AI Services
To perform real-time neural verification:
- Anonymized job post text is evaluated via Google Gemini API and Groq LLaMA APIs.
- No user-identifiable personal data is retained by these third-party model providers.

## 5. User Control & Data Deletion
- Users can clear their entire scan history at any time directly in the extension popup via the **"Clear History"** button.
- Uninstalling the extension immediately removes all stored local data.

## 6. Contact
For any privacy questions or developer inquiries regarding ScamShield:
- **Repository**: [https://github.com/naagasumukh8/Job_Verify_FYP](https://github.com/naagasumukh8/Job_Verify_FYP)
