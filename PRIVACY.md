# Privacy Policy — ScamShield (AI Job Scam Detector)

**Last updated:** August 2026  
**Extension ID:** kkklbgoocfdakheahjgflakolahiggmj  
**Developer:** Jagadeesh (naagasumukh8)  
**Contact:** [https://github.com/naagasumukh8/Job_Verify_FYP/issues](https://github.com/naagasumukh8/Job_Verify_FYP/issues)

---

## 1. Overview

ScamShield is a browser extension that helps job seekers identify potentially fraudulent job postings on LinkedIn, Gmail, Internshala, and Naukri. It uses AI-powered pattern analysis to assess risk indicators in job posting text. **ScamShield does not collect, store, or transmit any personal data about the user.**

---

## 2. What Data Is Processed

ScamShield processes the following data **only when the user explicitly clicks "Analyze Now"**:

| Data Type | What | Why | Stored? |
|-----------|------|-----|---------|
| **Website content** | Text of the active job posting page (job title, company name, job description text) | Required to perform scam pattern analysis | ❌ Not stored server-side |
| **Personal communications** | Text of an email open in Gmail (only when user clicks Analyze on a Gmail page) | Required to detect email job scams | ❌ Not stored |
| **Scan history** | Risk score + job title + company name + page URL of each analyzed posting | Displayed locally in the History tab | ✅ Stored locally in `chrome.storage.local` only — never transmitted |

**ScamShield does NOT collect:**
- Your name, email address, passwords, or any account credentials
- Your general browsing history (only the specific page you choose to scan)
- Cookies, form data, or payment information
- Any data from pages you have not explicitly chosen to scan

---

## 3. How Data Is Used

Job posting text submitted for analysis is:

1. **Sent via HTTPS** to the Google Gemini API (`generativelanguage.googleapis.com`) for AI-powered risk assessment
2. Optionally sent to a self-hosted backend server (if configured by the user) for deeper analysis including company registry checks
3. **Never used** for advertising, profiling, or any purpose unrelated to job scam detection
4. **Never sold or shared** with any third party beyond the AI API services required to perform the analysis

---

## 4. Third-Party Services

| Service | Purpose | Privacy Policy |
|---------|---------|----------------|
| Google Gemini API | AI analysis of job posting patterns | [Google Privacy Policy](https://policies.google.com/privacy) |
| Groq API (optional backend) | AI fallback model | [Groq Privacy Policy](https://groq.com/privacy-policy/) |
| DuckDuckGo Search (optional backend) | Web OSINT signal lookup | [DuckDuckGo Privacy Policy](https://duckduckgo.com/privacy) |

Job posting text sent to these APIs is **not linked to any user identity** and is not retained by ScamShield beyond the duration of a single analysis request.

---

## 5. User Controls & Data Deletion

- **Clear History**: Users can delete all local scan history at any time via the "Clear" button in the History tab
- **Uninstall**: Removing the extension immediately and permanently deletes all locally stored data (`chrome.storage.local` is cleared by Chrome on uninstall)
- **No account required**: ScamShield has no login, no account creation, and no server-side user profile

---

## 6. Permissions Justification

| Permission | Reason |
|-----------|--------|
| `activeTab` | Required to read job posting text from the page the user is currently viewing |
| `storage` | Required to save scan history and user settings (API URL, Gemini key) locally |
| `host_permissions` (LinkedIn, Gmail, Internshala, Naukri) | Required to inject the content script that extracts job text from supported platforms |
| `host_permissions` (generativelanguage.googleapis.com) | Required to call the Gemini API directly from the extension for AI analysis |
| `host_permissions` (*.onrender.com) | Required if user configures a self-hosted cloud backend |

---

## 7. Children's Privacy

ScamShield is not directed at children under 13 and does not knowingly collect data from children.

---

## 8. Changes to This Policy

Any updates to this privacy policy will be reflected in this document with an updated "Last updated" date and a new version of the extension in the Chrome Web Store.

---

## 9. Contact

For privacy concerns or questions:  
**GitHub Issues:** [https://github.com/naagasumukh8/Job_Verify_FYP/issues](https://github.com/naagasumukh8/Job_Verify_FYP/issues)
