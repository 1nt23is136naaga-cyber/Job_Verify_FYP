import json
import time
import requests

API_URL = "http://localhost:8000"

TEST_JOBS = [
    # ── GENUINE ENTERPRISE & FORTUNE 500 (1-10) ──────────────────────────────────
    {
        "id": 1,
        "name": "Google — Senior Distributed Systems Engineer",
        "expected": "GENUINE",
        "source": "linkedin",
        "metadata": {
            "title": "Senior Software Engineer - Distributed Systems",
            "company": "Google",
            "poster_name": "Sarah Jenkins",
            "poster_headline": "Senior Tech Recruiter at Google",
            "poster_url": "https://www.linkedin.com/in/sarah-jenkins-google",
            "is_poster_verified": True,
            "company_url": "https://www.linkedin.com/company/google",
            "location": "Bengaluru, Karnataka, India",
            "applicants": "342 applicants",
            "company_size": "10,001+ employees"
        },
        "text": """About the job\nGoogle is looking for a Senior Software Engineer to join our Core Infrastructure team in Bengaluru.\nResponsibilities: Design, develop, test, deploy, maintain, and improve large-scale distributed systems. 5+ years of experience with C++, Java, or Go. BS/MS degree in Computer Science."""
    },
    {
        "id": 2,
        "name": "Microsoft — Cloud Solution Architect (Azure)",
        "expected": "GENUINE",
        "source": "linkedin",
        "metadata": {
            "title": "Cloud Solution Architect - Azure",
            "company": "Microsoft",
            "poster_name": "Rajesh Sharma",
            "poster_headline": "Talent Acquisition Specialist @ Microsoft",
            "poster_url": "https://www.linkedin.com/in/rajesh-sharma-msft",
            "is_poster_verified": True,
            "company_url": "https://www.linkedin.com/company/microsoft",
            "location": "Hyderabad, Telangana, India",
            "applicants": "189 applicants",
            "company_size": "10,001+ employees"
        },
        "text": """Microsoft Azure Enterprise Team is hiring a Cloud Solution Architect in Hyderabad.\nDrive Azure architecture design and cloud migration for enterprise customers. Provide technical guidance on AKS and Serverless. 6+ years experience."""
    },
    {
        "id": 3,
        "name": "Ecolab — AI/ML Engineer (Direct Listing)",
        "expected": "GENUINE",
        "source": "linkedin",
        "metadata": {
            "title": "AI Engineer",
            "company": "Ecolab",
            "poster_name": "Not listed",
            "poster_headline": "",
            "poster_url": "",
            "is_poster_verified": False,
            "company_url": "https://www.linkedin.com/company/ecolab",
            "location": "Bengaluru East, Karnataka, India",
            "applicants": "120 applicants",
            "company_size": "10,001+ employees"
        },
        "text": """About the job\nJob Characteristics: Independently design, implement, and deploy intelligent systems powered by large language models (LLMs) and agent orchestration frameworks. Ecolab (NYSE:ECL) is a global sustainability leader with $16 billion annual sales and 48,000 associates."""
    },
    {
        "id": 4,
        "name": "Amazon — Software Development Engineer II (AWS)",
        "expected": "GENUINE",
        "source": "linkedin",
        "metadata": {
            "title": "Software Development Engineer II (SDE-II)",
            "company": "Amazon",
            "poster_name": "Priya Nair",
            "poster_headline": "Technical Recruiter at Amazon Web Services (AWS)",
            "poster_url": "https://www.linkedin.com/in/priya-nair-aws",
            "is_poster_verified": True,
            "company_url": "https://www.linkedin.com/company/amazon",
            "location": "Bengaluru, Karnataka, India",
            "applicants": "512 applicants",
            "company_size": "10,001+ employees"
        },
        "text": """AWS Database Services team is looking for an SDE II in Bengaluru. Build high-throughput, low-latency storage engines. 3+ years experience with Java, C++, or Go. Strong algorithms and system design."""
    },
    {
        "id": 5,
        "name": "Apple — iOS Software Engineer (Maps)",
        "expected": "GENUINE",
        "source": "linkedin",
        "metadata": {
            "title": "iOS Software Engineer - Maps & Location",
            "company": "Apple",
            "poster_name": "Chris Taylor",
            "poster_headline": "Executive Recruiter at Apple",
            "poster_url": "https://www.linkedin.com/in/chris-taylor-apple",
            "is_poster_verified": True,
            "company_url": "https://www.linkedin.com/company/apple",
            "location": "Hyderabad, Telangana, India",
            "applicants": "160 applicants",
            "company_size": "10,001+ employees"
        },
        "text": """Apple Maps team in Hyderabad is hiring an iOS Software Engineer. Deep understanding of Swift, Objective-C, Cocoa Touch, and Metal. 4+ years of shipping commercial iOS apps."""
    },
    {
        "id": 6,
        "name": "Meta — AI Research Scientist (FAIR)",
        "expected": "GENUINE",
        "source": "linkedin",
        "metadata": {
            "title": "AI Research Scientist - Foundation Models",
            "company": "Meta",
            "poster_name": "Dr. Elena Rostova",
            "poster_headline": "FAIR Research Recruiter @ Meta",
            "poster_url": "https://www.linkedin.com/in/elena-rostova-meta",
            "is_poster_verified": True,
            "company_url": "https://www.linkedin.com/company/meta",
            "location": "Bengaluru, Karnataka, India",
            "applicants": "85 applicants",
            "company_size": "10,001+ employees"
        },
        "text": """Fundamental AI Research (FAIR) at Meta is seeking AI Research Scientists in Bengaluru. PhD in Computer Science or Machine Learning with top-tier publications (NeurIPS, ICML, CVPR). PyTorch and large distributed training."""
    },
    {
        "id": 7,
        "name": "Siemens — Embedded Firmware Engineer",
        "expected": "GENUINE",
        "source": "linkedin",
        "metadata": {
            "title": "Embedded Firmware Engineer - Industrial IoT",
            "company": "Siemens",
            "poster_name": "Not listed",
            "poster_headline": "",
            "poster_url": "",
            "is_poster_verified": False,
            "company_url": "https://www.linkedin.com/company/siemens",
            "location": "Bengaluru, Karnataka, India",
            "applicants": "95 applicants",
            "company_size": "10,001+ employees"
        },
        "text": """Siemens Technology India is hiring Embedded Firmware Engineers. Develop RTOS-based control firmware for industrial automation drives. C/C++, ARM Cortex, CAN/Modbus protocols. 3-6 years experience."""
    },
    {
        "id": 8,
        "name": "Deloitte — Cyber Risk Advisory Consultant",
        "expected": "GENUINE",
        "source": "linkedin",
        "metadata": {
            "title": "Cybersecurity Risk Consultant",
            "company": "Deloitte",
            "poster_name": "Vikram Sethi",
            "poster_headline": "Talent Acquisition Manager at Deloitte USI",
            "poster_url": "https://www.linkedin.com/in/vikram-sethi-deloitte",
            "is_poster_verified": True,
            "company_url": "https://www.linkedin.com/company/deloitte",
            "location": "Gurugram, Haryana, India",
            "applicants": "110 applicants",
            "company_size": "10,001+ employees"
        },
        "text": """Deloitte Risk & Financial Advisory is looking for Cybersecurity Consultants in Gurugram. Perform penetration testing, cloud security audits, and ISO 27001 assessments. CISSP or CEH preferred."""
    },
    {
        "id": 9,
        "name": "Optum / UHG — Lead Healthcare Data Analyst",
        "expected": "GENUINE",
        "source": "linkedin",
        "metadata": {
            "title": "Lead Data Analyst - Healthcare Analytics",
            "company": "Optum",
            "poster_name": "Kavita Reddy",
            "poster_headline": "Lead Recruiter @ Optum UnitedHealth Group",
            "poster_url": "https://www.linkedin.com/in/kavita-reddy-optum",
            "is_poster_verified": True,
            "company_url": "https://www.linkedin.com/company/optum",
            "location": "Bengaluru, Karnataka, India",
            "applicants": "210 applicants",
            "company_size": "10,001+ employees"
        },
        "text": """Optum Global Solutions (UnitedHealth Group) is hiring a Lead Data Analyst in Bengaluru. Work on US healthcare claims datasets (ICD-10, CPT), SQL, Tableau, and Python ETL pipelines."""
    },
    {
        "id": 10,
        "name": "IBM — Quantum Computing Software Engineer",
        "expected": "GENUINE",
        "source": "linkedin",
        "metadata": {
            "title": "Quantum Software Developer - Qiskit",
            "company": "IBM",
            "poster_name": "Sunil Verma",
            "poster_headline": "Senior Tech Talent Partner at IBM",
            "poster_url": "https://www.linkedin.com/in/sunil-verma-ibm",
            "is_poster_verified": True,
            "company_url": "https://www.linkedin.com/company/ibm",
            "location": "Bengaluru, Karnataka, India",
            "applicants": "75 applicants",
            "company_size": "10,001+ employees"
        },
        "text": """IBM Quantum is hiring Software Developers in Bengaluru. Build open-source quantum algorithms using Qiskit and Python. Experience with linear algebra, quantum circuits, and high-performance computing."""
    },

    # ── INDIAN CORPORATE LEADERS & BANKS (11-15) ────────────────────────────────
    {
        "id": 11,
        "name": "TCS — Java Full Stack Developer (iBegin)",
        "expected": "GENUINE",
        "source": "linkedin",
        "metadata": {
            "title": "Java Full Stack Developer",
            "company": "Tata Consultancy Services",
            "poster_name": "Anil Kumar",
            "poster_headline": "Lead Recruiter | TCS iBegin",
            "poster_url": "https://www.linkedin.com/in/anil-kumar-tcs",
            "is_poster_verified": False,
            "company_url": "https://www.linkedin.com/company/tata-consultancy-services",
            "location": "Chennai, Tamil Nadu, India",
            "applicants": "620 applicants",
            "company_size": "10,001+ employees"
        },
        "text": """Tata Consultancy Services (TCS) is hiring Java Full Stack Developers for our Banking Financial Services (BFS) business unit in Chennai. Java 11+, Spring Boot, React.js, CI/CD pipelines. Official registration via TCS iBegin portal."""
    },
    {
        "id": 12,
        "name": "Infosys — Senior SAP S/4HANA Consultant",
        "expected": "GENUINE",
        "source": "linkedin",
        "metadata": {
            "title": "Senior Associate Consultant - SAP",
            "company": "Infosys",
            "poster_name": "Meera Joshi",
            "poster_headline": "Talent Acquisition Lead at Infosys",
            "poster_url": "https://www.linkedin.com/in/meera-joshi-infy",
            "is_poster_verified": True,
            "company_url": "https://www.linkedin.com/company/infosys",
            "location": "Pune, Maharashtra, India",
            "applicants": "145 applicants",
            "company_size": "10,001+ employees"
        },
        "text": """Infosys Enterprise Solutions unit is seeking SAP S/4HANA Finance consultants in Pune. 5+ years experience in SAP FICO, S/4HANA implementations, GL, AP, and Asset Accounting."""
    },
    {
        "id": 13,
        "name": "Wipro — Cloud DevOps Engineer",
        "expected": "GENUINE",
        "source": "linkedin",
        "metadata": {
            "title": "Cloud DevOps Engineer",
            "company": "Wipro",
            "poster_name": "Not listed",
            "poster_headline": "",
            "poster_url": "",
            "is_poster_verified": False,
            "company_url": "https://www.linkedin.com/company/wipro",
            "location": "Hyderabad, Telangana, India",
            "applicants": "310 applicants",
            "company_size": "10,001+ employees"
        },
        "text": """Wipro Digital is hiring Cloud DevOps Engineers in Hyderabad. Hands-on experience with AWS/Azure, Kubernetes, Terraform, Docker, and Jenkins pipelines. 3-5 years experience."""
    },
    {
        "id": 14,
        "name": "HDFC Bank — Senior Data Engineer (Risk)",
        "expected": "GENUINE",
        "source": "linkedin",
        "metadata": {
            "title": "Senior Data Engineer - Risk Analytics",
            "company": "HDFC Bank",
            "poster_name": "Sanjay Pillai",
            "poster_headline": "Head of IT Recruitment @ HDFC Bank",
            "poster_url": "https://www.linkedin.com/in/sanjay-pillai-hdfc",
            "is_poster_verified": True,
            "company_url": "https://www.linkedin.com/company/hdfc-bank",
            "location": "Mumbai, Maharashtra, India",
            "applicants": "190 applicants",
            "company_size": "10,001+ employees"
        },
        "text": """HDFC Bank Risk Analytics Division in Mumbai is hiring Senior Data Engineers. Build PySpark ETL data pipelines, credit scoring models, and fraud monitoring systems. 4+ years banking data engineering."""
    },
    {
        "id": 15,
        "name": "Tata Motors — EV Battery Management Systems Engineer",
        "expected": "GENUINE",
        "source": "linkedin",
        "metadata": {
            "title": "BMS Controls Engineer - EV Division",
            "company": "Tata Motors",
            "poster_name": "Not listed",
            "poster_headline": "",
            "poster_url": "",
            "is_poster_verified": False,
            "company_url": "https://www.linkedin.com/company/tata-motors",
            "location": "Pune, Maharashtra, India",
            "applicants": "140 applicants",
            "company_size": "10,001+ employees"
        },
        "text": """Tata Passenger Electric Mobility is hiring Battery Management System (BMS) Controls Engineers in Pune. MATLAB/Simulink modeling, state-of-charge estimation, and ISO 26262 functional safety."""
    },

    # ── STARTUPS & UNICORNS (16-20) ──────────────────────────────────────────────
    {
        "id": 16,
        "name": "Razorpay — Backend Platform Engineer (Go/Kafka)",
        "expected": "GENUINE",
        "source": "linkedin",
        "metadata": {
            "title": "Backend Engineer - Payments Core",
            "company": "Razorpay",
            "poster_name": "Deepak Mehta",
            "poster_headline": "Engineering Recruiter @ Razorpay",
            "poster_url": "https://www.linkedin.com/in/deepak-mehta-razorpay",
            "is_poster_verified": False,
            "company_url": "https://www.linkedin.com/company/razorpay",
            "location": "Bengaluru, Karnataka, India",
            "applicants": "415 applicants",
            "company_size": "1,001-5,000 employees"
        },
        "text": """Razorpay is hiring Backend Engineers for Payments Core Infrastructure. Stack: Go, Python, MySQL, Kafka, Redis, AWS. 2-5 years experience building highly concurrent transactional systems processing 100M+ API requests."""
    },
    {
        "id": 17,
        "name": "Swiggy — Senior Product Manager (Instamart)",
        "expected": "GENUINE",
        "source": "linkedin",
        "metadata": {
            "title": "Product Manager - Instamart Logistics",
            "company": "Swiggy",
            "poster_name": "Aakanksha Roy",
            "poster_headline": "Product Hiring Lead at Swiggy",
            "poster_url": "https://www.linkedin.com/in/aakanksha-roy-swiggy",
            "is_poster_verified": True,
            "company_url": "https://www.linkedin.com/company/swiggy",
            "location": "Bengaluru, Karnataka, India",
            "applicants": "380 applicants",
            "company_size": "5,001-10,000 employees"
        },
        "text": """Swiggy Instamart product team is seeking a Product Manager. Optimize dark store fulfillment algorithms and last-mile delivery routes. 3+ years PM experience in quick commerce, e-commerce, or logistics."""
    },
    {
        "id": 18,
        "name": "Zoho — Software Engineer (C++ / Java)",
        "expected": "GENUINE",
        "source": "linkedin",
        "metadata": {
            "title": "Software Developer - Cloud Apps",
            "company": "Zoho",
            "poster_name": "Karthik Subramanian",
            "poster_headline": "HR Lead @ Zoho Corporation",
            "poster_url": "https://www.linkedin.com/in/karthik-subramanian-zoho",
            "is_poster_verified": True,
            "company_url": "https://www.linkedin.com/company/zoho",
            "location": "Chennai, Tamil Nadu, India",
            "applicants": "450 applicants",
            "company_size": "10,001+ employees"
        },
        "text": """Zoho Corporation is hiring Software Developers in Chennai. Strong data structures, problem solving, C/C++ or Java expertise required. Work on Zoho CRM, Desk, or Mail product suites."""
    },
    {
        "id": 19,
        "name": "Atlassian — Remote Site Reliability Engineer",
        "expected": "GENUINE",
        "source": "linkedin",
        "metadata": {
            "title": "Site Reliability Engineer (SRE) - Cloud",
            "company": "Atlassian",
            "poster_name": "Siddharth Rao",
            "poster_headline": "Global Talent Acquisition @ Atlassian",
            "poster_url": "https://www.linkedin.com/in/siddharth-rao-atlassian",
            "is_poster_verified": True,
            "company_url": "https://www.linkedin.com/company/atlassian",
            "location": "Remote, India",
            "applicants": "270 applicants",
            "company_size": "10,001+ employees"
        },
        "text": """Atlassian is hiring Remote SREs in India to manage Jira and Confluence Cloud infrastructure. Stack: Terraform, Kubernetes, AWS, Python, Datadog. 4+ years in SRE/DevOps."""
    },
    {
        "id": 20,
        "name": "Flipkart — Lead Machine Learning Engineer",
        "expected": "GENUINE",
        "source": "linkedin",
        "metadata": {
            "title": "Lead Machine Learning Engineer - Search & Recs",
            "company": "Flipkart",
            "poster_name": "Not listed",
            "poster_headline": "",
            "poster_url": "",
            "is_poster_verified": False,
            "company_url": "https://www.linkedin.com/company/flipkart",
            "location": "Bengaluru, Karnataka, India",
            "applicants": "310 applicants",
            "company_size": "10,001+ employees"
        },
        "text": """Flipkart Search and Recommendation systems team is looking for Lead ML Engineers in Bengaluru. Build vector search, semantic ranking, and transformer models for 200M+ catalog items."""
    },

    # ── VERIFIED DIRECT LISTINGS & TECH FIRMS (21-25) ────────────────────────────
    {
        "id": 21,
        "name": "DARUKAA Earth — AI/ML Intern (Direct Posting)",
        "expected": "GENUINE",
        "source": "linkedin",
        "metadata": {
            "title": "AI/ML Engineer Intern",
            "company": "Darukaa.Earth",
            "poster_name": "Not listed",
            "poster_headline": "",
            "poster_url": "",
            "is_poster_verified": False,
            "company_url": "",
            "location": "Mumbai / Remote, India",
            "applicants": "65 applicants",
            "company_size": "11-50 employees"
        },
        "text": """AI/ML Engineer Internship at Darukaa.Earth. Climate-tech and nature intelligence models. Work on computer vision for satellite imagery and biodiversity datasets. Python, PyTorch, OpenCV."""
    },
    {
        "id": 22,
        "name": "Freshworks — Frontend Engineer (React/TypeScript)",
        "expected": "GENUINE",
        "source": "linkedin",
        "metadata": {
            "title": "Frontend Engineer II",
            "company": "Freshworks",
            "poster_name": "Arun Prakash",
            "poster_headline": "Senior Technical Recruiter at Freshworks",
            "poster_url": "https://www.linkedin.com/in/arun-prakash-freshworks",
            "is_poster_verified": True,
            "company_url": "https://www.linkedin.com/company/freshworks",
            "location": "Chennai, Tamil Nadu, India",
            "applicants": "155 applicants",
            "company_size": "5,001-10,000 employees"
        },
        "text": """Freshworks is hiring Frontend Engineers for Freshdesk. Strong JavaScript fundamentals, React, Redux, TypeScript, and modern web performance optimization. 3-5 years experience."""
    },
    {
        "id": 23,
        "name": "ServiceNow — Senior Full Stack Developer",
        "expected": "GENUINE",
        "source": "linkedin",
        "metadata": {
            "title": "Senior Staff Software Engineer",
            "company": "ServiceNow",
            "poster_name": "Not listed",
            "poster_headline": "",
            "poster_url": "",
            "is_poster_verified": False,
            "company_url": "https://www.linkedin.com/company/servicenow",
            "location": "Hyderabad, Telangana, India",
            "applicants": "180 applicants",
            "company_size": "10,001+ employees"
        },
        "text": """ServiceNow is looking for Senior Software Engineers in Hyderabad. Build core platform workflow engines. Java, JavaScript, relational databases, distributed systems. 5+ years experience."""
    },
    {
        "id": 24,
        "name": "Capgemini — GenAI Solutions Developer",
        "expected": "GENUINE",
        "source": "linkedin",
        "metadata": {
            "title": "Generative AI Specialist",
            "company": "Capgemini",
            "poster_name": "Not listed",
            "poster_headline": "",
            "poster_url": "",
            "is_poster_verified": False,
            "company_url": "https://www.linkedin.com/company/capgemini",
            "location": "Bengaluru East, Karnataka, India",
            "applicants": "240 applicants",
            "company_size": "10,001+ employees"
        },
        "text": """Capgemini Insights & Data practice is hiring Generative AI Developers in Bengaluru. Build RAG pipelines, LangChain integrations, and vector database embeddings. 3+ years experience."""
    },
    {
        "id": 25,
        "name": "Zomato — iOS App Developer (Blinkit)",
        "expected": "GENUINE",
        "source": "linkedin",
        "metadata": {
            "title": "iOS Developer - Blinkit Engineering",
            "company": "Zomato",
            "poster_name": "Karan Singhal",
            "poster_headline": "Engineering Hiring @ Zomato & Blinkit",
            "poster_url": "https://www.linkedin.com/in/karan-singhal-zomato",
            "is_poster_verified": True,
            "company_url": "https://www.linkedin.com/company/zomato",
            "location": "Gurugram, Haryana, India",
            "applicants": "290 applicants",
            "company_size": "5,001-10,000 employees"
        },
        "text": """Zomato & Blinkit mobile team is hiring iOS Developers in Gurugram. Build high-performance Swift/SwiftUI mobile consumer applications used by 50M+ users daily."""
    },

    # ── ADVANCE-FEE & TRAINING KIT SCAMS (26-30) ────────────────────────────────
    {
        "id": 26,
        "name": "Quick Cash Typing — Home Typing Deposit Trap (SCAM)",
        "expected": "SCAM",
        "source": "linkedin",
        "metadata": {
            "title": "Part Time Home Typing & Data Entry",
            "company": "Quick Cash Typing Ltd",
            "poster_name": "Ramesh Kumar",
            "poster_headline": "Direct HR Manager",
            "poster_url": "",
            "is_poster_verified": False,
            "company_url": "",
            "location": "Work From Home",
            "applicants": "12 applicants",
            "company_size": "1-10 employees"
        },
        "text": """URGENT REQUIREMENT: Home Typing Job & Simple Data Entry!\nEarn up to $1500 weekly or ₹40,000 monthly working just 2 hours daily from home.\n- No experience needed!\n- No interview required! Direct selection!\n- 100% job guarantee!\n- Daily payment via Paytm, GPay, or UPI!\n- Refundable security deposit of ₹1,500 required for training kit & soft copies.\nContact HR immediately on WhatsApp: +91 9876543210."""
    },
    {
        "id": 27,
        "name": "Apex Document Verification — ₹3,500 Registration Fee (SCAM)",
        "expected": "SCAM",
        "source": "linkedin",
        "metadata": {
            "title": "Software Engineer Fresher (50 LPA)",
            "company": "Global Talent Placement",
            "poster_name": "Pooja Verma",
            "poster_headline": "Placement Officer",
            "poster_url": "",
            "is_poster_verified": False,
            "company_url": "",
            "location": "Noida, India",
            "applicants": "5 applicants",
            "company_size": "1-10 employees"
        },
        "text": """Special Hiring Offer for Freshers: Earn 50 LPA starting package!\nNo technical test needed. Guaranteed job guarantee placement.\nInstructions:\n1. Pay refundable registration fee ₹3,500 for document verification.\n2. Send screenshot on WhatsApp +91 9123456789.\n3. Receive appointment letter within 24 hours. Hurry! Only 3 slots left!"""
    },
    {
        "id": 28,
        "name": "Digital Data Work — ₹2,000 Software License Fee (SCAM)",
        "expected": "SCAM",
        "source": "linkedin",
        "metadata": {
            "title": "Remote Data Formatting Executive",
            "company": "Fast Data Processors",
            "poster_name": "Amit Shah",
            "poster_headline": "Recruiter",
            "poster_url": "",
            "is_poster_verified": False,
            "company_url": "",
            "location": "Remote",
            "applicants": "8 applicants"
        },
        "text": """Work from home typing simple PDF text into Word.\nEarn ₹1,200 per page completed. Unlimited earnings guaranteed.\nBefore allocation of work files, applicants must pay a refundable software license fee of ₹2,000 via Google Pay or PhonePe. Contact on WhatsApp for registration."""
    },
    {
        "id": 29,
        "name": "United Placement Services — ₹5,000 Security Deposit (SCAM)",
        "expected": "SCAM",
        "source": "linkedin",
        "metadata": {
            "title": "Direct Selection Assistant Manager",
            "company": "United Placement Bureau",
            "poster_name": "Suresh Raina",
            "poster_headline": "Independent Agent",
            "poster_url": "",
            "is_poster_verified": False,
            "company_url": "",
            "location": "Delhi, India",
            "applicants": "4 applicants"
        },
        "text": """Direct selection for Assistant Manager role without interview.\nSalary: ₹8 LPA starting package.\nCandidates must deposit ₹5,000 as refundable security deposit for background screening. Direct appointment letter will be issued immediately upon payment confirmation."""
    },
    {
        "id": 30,
        "name": "Global Proofreading — ₹1,800 Training Material Charge (SCAM)",
        "expected": "SCAM",
        "source": "linkedin",
        "metadata": {
            "title": "English Proofreader / Content Editor",
            "company": "Star Publishing Hub",
            "poster_name": "Anita Roy",
            "poster_headline": "HR Coordinator",
            "poster_url": "",
            "is_poster_verified": False,
            "company_url": "",
            "location": "Work from home",
            "applicants": "9 applicants"
        },
        "text": """Proofread English books and articles from home.\nWeekly payout of $600. No qualification or experience required.\nTraining kit fee of ₹1,800 must be sent via UPI transfer to activate your employee portal login ID."""
    },

    # ── WHATSAPP / TELEGRAM TASK TRAPS (31-35) ──────────────────────────────────
    {
        "id": 31,
        "name": "Telegram Video Liking & Task Scam (SCAM)",
        "expected": "SCAM",
        "source": "linkedin",
        "metadata": {
            "title": "Online Video Reviewer & YouTube Liker",
            "company": "Viral Media Boosters",
            "poster_name": "Alex Vance",
            "poster_headline": "Social Media Operations",
            "poster_url": "",
            "is_poster_verified": False,
            "company_url": "",
            "location": "Remote",
            "applicants": "20 applicants"
        },
        "text": """Earn ₹3,000 to ₹8,000 daily by simply watching and liking YouTube videos and Google reviews.\nDaily income paid immediately to your UPI/bank account.\nNo interview required. Direct selection.\nContact our team on telegram @media_tasks_india immediately to start your daily tasks! Do not apply via email."""
    },
    {
        "id": 32,
        "name": "WhatsApp Hotel Rating Task Scheme (SCAM)",
        "expected": "SCAM",
        "source": "linkedin",
        "metadata": {
            "title": "Google Maps & Travel Rating Assistant",
            "company": "Global Hospitality Ratings",
            "poster_name": "Priya Sharma",
            "poster_headline": "Task Coordinator",
            "poster_url": "",
            "is_poster_verified": False,
            "company_url": "",
            "location": "Remote",
            "applicants": "15 applicants"
        },
        "text": """We are hiring part-time review assistants. Just rate hotels 5 stars on Google Maps and earn ₹200 per review.\nEarn up to ₹50,000 monthly from home. Daily payment via Paytm or GPay.\nMessage on WhatsApp +91 9988776655 to receive your first task."""
    },
    {
        "id": 33,
        "name": "Telegram E-Commerce Order Booster (SCAM)",
        "expected": "SCAM",
        "source": "linkedin",
        "metadata": {
            "title": "Order Optimization Specialist",
            "company": "E-Commerce Merchants Hub",
            "poster_name": "David Clark",
            "poster_headline": "Regional Agent",
            "poster_url": "",
            "is_poster_verified": False,
            "company_url": "",
            "location": "Work from Home",
            "applicants": "7 applicants"
        },
        "text": """Help e-commerce merchants boost order volume. Earn 20% commission on every simulated prepaid purchase.\nPassive income with guaranteed earnings. Contact us on telegram @ecommerce_boost_official to register."""
    },
    {
        "id": 34,
        "name": "WhatsApp Movie Reviewer Task Trap (SCAM)",
        "expected": "SCAM",
        "source": "linkedin",
        "metadata": {
            "title": "Part Time Movie Reviewer",
            "company": "Cinematic Ratings Agency",
            "poster_name": "Sneha Patel",
            "poster_headline": "HR Associate",
            "poster_url": "",
            "is_poster_verified": False,
            "company_url": "",
            "location": "Remote",
            "applicants": "18 applicants"
        },
        "text": """Rate trailers and movies from home. Earn ₹500 per movie reviewed.\nDaily payout promised. Contact whatsapp for details: +91 8877665544. Limited slots available, hurry!"""
    },
    {
        "id": 35,
        "name": "Telegram App Tester & Downline Scheme (SCAM)",
        "expected": "SCAM",
        "source": "linkedin",
        "metadata": {
            "title": "Mobile App Quality Tester",
            "company": "App Rewarders Network",
            "poster_name": "Vikram Das",
            "poster_headline": "Lead Affiliate",
            "poster_url": "",
            "is_poster_verified": False,
            "company_url": "",
            "location": "Remote",
            "applicants": "11 applicants"
        },
        "text": """Test new Android applications and earn daily cash. Build your downline network marketing team to multiply passive income. Chat on telegram @app_rewards_2026 to receive test APKs."""
    },

    # ── BRAND TYPOSQUATTING & IMPERSONATION (36-40) ──────────────────────────────
    {
        "id": 36,
        "name": "Rnicrosoft — Typosquatting Microsoft Scam (SCAM)",
        "expected": "SCAM",
        "source": "linkedin",
        "metadata": {
            "title": "Remote Systems Administrator",
            "company": "Microsoft",
            "poster_name": "Steve Miller",
            "poster_headline": "Senior HR @ Microsoft",
            "poster_url": "https://www.linkedin.com/in/steve-miller-fake",
            "is_poster_verified": False,
            "company_url": "",
            "location": "Remote",
            "applicants": "8 applicants",
            "company_size": "1-10 employees"
        },
        "text": """Microsoft is hiring Remote Systems Administrators.\nSend your resume to recruiter@rnicrosoft.com immediately.\nNote: A training kit fee of $200 must be sent via Western Union or wire transfer before starting work."""
    },
    {
        "id": 37,
        "name": "Goog1e Careers — Fake Google Recruiter Phishing (SCAM)",
        "expected": "SCAM",
        "source": "linkedin",
        "metadata": {
            "title": "AI Prompt Engineer",
            "company": "Google",
            "poster_name": "Mark Johnson",
            "poster_headline": "Google Talent Sourcing",
            "poster_url": "https://www.linkedin.com/in/mark-johnson-goog1e",
            "is_poster_verified": False,
            "company_url": "",
            "location": "Remote",
            "applicants": "14 applicants",
            "company_size": "1-10 employees"
        },
        "text": """Google is hiring AI Prompt Engineers.\nPackage: $120,000 / year.\nSend resume and passport copy to careers@goog1e-jobs.com.\nRegistration processing fee of $150 required for background check processing."""
    },
    {
        "id": 38,
        "name": "Inf0sys HR — Free Gmail Recruiter Impersonation (SCAM)",
        "expected": "SCAM",
        "source": "linkedin",
        "metadata": {
            "title": "Software Developer Trainee",
            "company": "Infosys",
            "poster_name": "Kiran Rao",
            "poster_headline": "Campus Recruiter",
            "poster_url": "",
            "is_poster_verified": False,
            "company_url": "",
            "location": "Bengaluru",
            "applicants": "35 applicants",
            "company_size": "1-10 employees"
        },
        "text": """Infosys off-campus drive for freshers. Direct appointment without technical interview.\nSend resume to infosys.hr.recruitment2026@gmail.com.\nSelected candidates must pay ₹2,500 for uniform and ID card processing."""
    },
    {
        "id": 39,
        "name": "Amaz0n Logistics — Typosquatting Delivery Coordinator (SCAM)",
        "expected": "SCAM",
        "source": "linkedin",
        "metadata": {
            "title": "Operations Supervisor",
            "company": "Amazon",
            "poster_name": "Daniel White",
            "poster_headline": "Logistics Hiring",
            "poster_url": "",
            "is_poster_verified": False,
            "company_url": "",
            "location": "Hyderabad",
            "applicants": "19 applicants",
            "company_size": "1-10 employees"
        },
        "text": """Amazon Warehouse is hiring Operations Supervisors.\nApply by emailing hr@amaz0n-logistics.com.\nRefundable laptop security deposit $300 required via wire transfer."""
    },
    {
        "id": 40,
        "name": "Apple Care Phishing — Fake Free Email Recruiter (SCAM)",
        "expected": "SCAM",
        "source": "linkedin",
        "metadata": {
            "title": "Apple Customer Support Advisor",
            "company": "Apple",
            "poster_name": "Robert Brown",
            "poster_headline": "Apple Support Hiring",
            "poster_url": "",
            "is_poster_verified": False,
            "company_url": "",
            "location": "Remote",
            "applicants": "25 applicants",
            "company_size": "1-10 employees"
        },
        "text": """Apple is hiring remote Customer Support Advisors. Work from home and earn $45/hour.\nSubmit details to apple.talent.recruiting@yahoo.com.\nPre-employment background verification fee $120 must be paid upfront."""
    },

    # ── TRAINING BONDS & UNREALISTIC SALARY TRAPS (41-45) ────────────────────────
    {
        "id": 41,
        "name": "FakeCorp Solutions — Mandatory ₹12,000 Training Bond (SCAM)",
        "expected": "SCAM",
        "source": "linkedin",
        "metadata": {
            "title": "Junior Web Developer Intern",
            "company": "FakeCorp Solutions Pvt Ltd",
            "poster_name": "Suresh Gupta",
            "poster_headline": "Director",
            "poster_url": "",
            "is_poster_verified": False,
            "company_url": "",
            "location": "Bengaluru",
            "applicants": "40 applicants"
        },
        "text": """Web Developer internship with 100% job guarantee placement after 3 months.\nCandidates must sign a mandatory training bond and pay joining kit charge of ₹12,000 prior to onboarding. Contact whatsapp for details."""
    },
    {
        "id": 42,
        "name": "Unrealistic 45 LPA Fresher Data Entry Bait (SCAM)",
        "expected": "SCAM",
        "source": "linkedin",
        "metadata": {
            "title": "Fresher Data Entry Associate (45 LPA)",
            "company": "Global Data Analytics",
            "poster_name": "Rajesh V",
            "poster_headline": "Hiring Specialist",
            "poster_url": "",
            "is_poster_verified": False,
            "company_url": "",
            "location": "Bengaluru",
            "applicants": "50 applicants"
        },
        "text": """Urgent hiring for fresher data entry operators.\nOffering 45 LPA salary package with no experience needed.\nDirect selection guaranteed. Pay refundable security deposit ₹4,000 to reserve your seat."""
    },
    {
        "id": 43,
        "name": "CyberTech Placement — ₹8,000 Certificate Bond (SCAM)",
        "expected": "SCAM",
        "source": "linkedin",
        "metadata": {
            "title": "Python Developer Trainee",
            "company": "CyberTech Placement Services",
            "poster_name": "Manoj Tiwari",
            "poster_headline": "Recruiter",
            "poster_url": "",
            "is_poster_verified": False,
            "company_url": "",
            "location": "Pune",
            "applicants": "15 applicants"
        },
        "text": """Guaranteed placement as Python Developer in MNC.\nCandidates must undergo mandatory corporate training with ₹8,000 training bond fee. 100% job guarantee or money back."""
    },
    {
        "id": 44,
        "name": "FastTrack Career — ₹15,000 Offer Letter Fee (SCAM)",
        "expected": "SCAM",
        "source": "linkedin",
        "metadata": {
            "title": "Assistant Network Engineer",
            "company": "FastTrack Career Consultants",
            "poster_name": "Deepa Sen",
            "poster_headline": "Placement Officer",
            "poster_url": "",
            "is_poster_verified": False,
            "company_url": "",
            "location": "Kolkata",
            "applicants": "8 applicants"
        },
        "text": """Direct appointment letter for Network Engineer role in telecom firm.\nPay ₹15,000 processing fee before appointment letter release. No interview required."""
    },
    {
        "id": 45,
        "name": "CloudNine Infotech — Mandatory ₹6,500 Onboarding Charge (SCAM)",
        "expected": "SCAM",
        "source": "linkedin",
        "metadata": {
            "title": "Junior QA Automation Tester",
            "company": "CloudNine Infotech",
            "poster_name": "Ravi Shastri",
            "poster_headline": "Technical Recruiter",
            "poster_url": "",
            "is_poster_verified": False,
            "company_url": "",
            "location": "Hyderabad",
            "applicants": "22 applicants"
        },
        "text": """QA Automation Tester role for freshers. Assured placement.\nMandatory joining kit fee of ₹6,500 must be transferred via Google Pay prior to issuing the employee badge and laptop."""
    },

    # ── CRYPTO, GIG, & UK/VISA SCAMS (46-50) ─────────────────────────────────────
    {
        "id": 46,
        "name": "Crypto Earn Global — 2 BTC Monthly Reviewer (SCAM)",
        "expected": "SCAM",
        "source": "linkedin",
        "metadata": {
            "title": "Online Video Reviewer & Crypto Trader",
            "company": "Crypto Earn Global",
            "poster_name": "Alex Vance",
            "poster_headline": "Crypto Operations",
            "poster_url": "",
            "is_poster_verified": False,
            "company_url": "",
            "location": "Work From Home",
            "applicants": "15 applicants"
        },
        "text": """Earn 2 BTC monthly rating online videos!\n- Guaranteed income with unlimited earnings!\n- Daily payment via bitcoin payment / USDT wire transfer!\n- Contact message us on telegram immediately!\n- Registration processing fee required."""
    },
    {
        "id": 47,
        "name": "UK NHS Visa Sponsorship Fee Trap (SCAM)",
        "expected": "SCAM",
        "source": "linkedin",
        "metadata": {
            "title": "Healthcare Assistant - UK Tier 2 Visa",
            "company": "UK Care Recruitment Hub",
            "poster_name": "Dr. Arthur Pendelton",
            "poster_headline": "International Healthcare Sourcing",
            "poster_url": "",
            "is_poster_verified": False,
            "company_url": "",
            "location": "London, United Kingdom",
            "applicants": "45 applicants"
        },
        "text": """NHS UK Tier 2 visa sponsorship guaranteed for international nurses and assistants.\nSalary: £35,000 GBP per annum.\nVisa sponsorship fee £450 and CRB check fee £85 must be paid upfront via BACS transfer to our London immigration account before interview scheduling."""
    },
    {
        "id": 48,
        "name": "London Hospitality DBS Fee Trap (SCAM)",
        "expected": "SCAM",
        "source": "linkedin",
        "metadata": {
            "title": "Hotel Receptionist - London",
            "company": "Royal London Hospitality",
            "poster_name": "Sarah Collins",
            "poster_headline": "Recruiter",
            "poster_url": "",
            "is_poster_verified": False,
            "company_url": "",
            "location": "London, UK",
            "applicants": "28 applicants"
        },
        "text": """Immediate opening for Hotel Receptionist in central London. £28k salary.\nNational insurance number required before interview and mandatory DBS check fee £65 must be transferred via BACS prior to interview."""
    },
    {
        "id": 49,
        "name": "US Remote Data Entry $180k Gig Scheme (SCAM)",
        "expected": "SCAM",
        "source": "linkedin",
        "metadata": {
            "title": "Simple Typing & Data Entry Assistant",
            "company": "American Data Bureau",
            "poster_name": "John Miller",
            "poster_headline": "Recruitment Specialist",
            "poster_url": "",
            "is_poster_verified": False,
            "company_url": "",
            "location": "Remote, US",
            "applicants": "30 applicants"
        },
        "text": """Work from home typing simple tasks. Simple typing job paying $180k per year with weekly payout.\nContact on signal app or google hangout to start immediately. Wire transfer setup fee $100 required."""
    },
    {
        "id": 50,
        "name": "MLM Affiliate Network Marketing Downline Trap (SCAM)",
        "expected": "SCAM",
        "source": "linkedin",
        "metadata": {
            "title": "Independent Business Associate",
            "company": "Wealth Builders Global",
            "poster_name": "Rohan Deshmukh",
            "poster_headline": "Diamond Executive",
            "poster_url": "",
            "is_poster_verified": False,
            "company_url": "",
            "location": "Mumbai",
            "applicants": "16 applicants"
        },
        "text": """Become a self-employed millionaire through our network marketing mlm program.\nEarn unlimited earnings from your downline team members.\nPurchase mandatory starter joining kit for ₹9,999 to activate your account. WhatsApp for details."""
    }
]

def run_50_suite():
    print("=" * 90, flush=True)
    print("🚀 SCAMSHIELD 50-JOB REAL-TIME BENCHMARK SUITE (DIVERSE EDGE CASES)", flush=True)
    print("=" * 90, flush=True)

    correct_count = 0
    total = len(TEST_JOBS)
    results = []
    
    tp = 0 # true positive: scam predicted as scam
    tn = 0 # true negative: genuine predicted as genuine
    fp = 0 # false positive: genuine wrongly flagged as scam
    fn = 0 # false negative: scam wrongly passed as genuine

    for item in TEST_JOBS:
        print(f"\n--- [{item['id']:02d}/{total}] {item['name']} ---", flush=True)
        payload = {
            "text": item["text"],
            "source": item["source"],
            "metadata": item["metadata"]
        }

        try:
            start_t = time.time()
            res = requests.post(f"{API_URL}/analyze", json=payload, timeout=20)
            elapsed = time.time() - start_t

            if res.status_code != 200:
                print(f"❌ API Error ({res.status_code}): {res.text}", flush=True)
                continue

            data = res.json()
            risk_score = data.get("risk_score", 50)
            trust_score = 100 - risk_score
            verdict = data.get("verdict", "Unknown")
            is_expected_genuine = (item["expected"] == "GENUINE")

            # Classification rule:
            # Genuine: risk_score <= 45 (Trust >= 55)
            # Scam: risk_score > 45 (Trust < 55)
            is_predicted_genuine = (risk_score <= 45)
            
            passed = (is_predicted_genuine == is_expected_genuine)
            if passed:
                correct_count += 1
                if is_expected_genuine:
                    tn += 1
                else:
                    tp += 1
            else:
                if is_expected_genuine:
                    fp += 1
                else:
                    fn += 1

            status_icon = "✅ PASS" if passed else "❌ FAIL"
            print(f"Outcome: {status_icon} | Expected: {item['expected']} | Predicted: {'GENUINE' if is_predicted_genuine else 'SCAM'} | Risk: {risk_score}/100 | Trust: {trust_score}/100 ({elapsed:.2f}s)", flush=True)
            
            if data.get("risk_factors"):
                print("Top Risk Signals:", flush=True)
                for rf in data["risk_factors"][:3]:
                    print(f"  • {rf}", flush=True)

            results.append({
                "id": item["id"],
                "name": item["name"],
                "expected": item["expected"],
                "predicted": "GENUINE" if is_predicted_genuine else "SCAM",
                "risk_score": risk_score,
                "trust_score": trust_score,
                "verdict": verdict,
                "pass": passed,
                "time_sec": round(elapsed, 2)
            })

        except Exception as e:
            print(f"❌ Exception: {e}", flush=True)

    accuracy = (correct_count / total) * 100
    precision = (tp / (tp + fp)) * 100 if (tp + fp) > 0 else 0
    recall = (tp / (tp + fn)) * 100 if (tp + fn) > 0 else 0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0

    print("\n" + "=" * 90, flush=True)
    print("📊 50-JOB BENCHMARK EVALUATION METRICS", flush=True)
    print("=" * 90, flush=True)
    print(f"Total Jobs Tested    : {total}")
    print(f"Correctly Classified : {correct_count} / {total}")
    print(f"Accuracy             : {accuracy:.2f}%")
    print(f"Precision (Scams)    : {precision:.2f}%")
    print(f"Recall (Scams)       : {recall:.2f}%")
    print(f"F1-Score             : {f1:.2f}%")
    print(f"True Positives (TP)  : {tp} (Scams caught)")
    print(f"True Negatives (TN)  : {tn} (Genuine verified)")
    print(f"False Positives (FP) : {fp} (Genuine falsely flagged)")
    print(f"False Negatives (FN) : {fn} (Scams missed)")
    print("=" * 90, flush=True)

    print("\n📋 DETAILED BENCHMARK MATRIX:")
    print(f"{'ID':<4} | {'Expected':<8} | {'Predicted':<9} | {'Trust':<6} | {'Risk':<5} | {'Job Description Name':<45} | {'Status'}")
    print("-" * 95)
    for r in results:
        status_str = "✅ PASS" if r["pass"] else "❌ FAIL"
        print(f"{r['id']:<4} | {r['expected']:<8} | {r['predicted']:<9} | {r['trust_score']:>3}/100 | {r['risk_score']:>3}/100 | {r['name'][:43]:<45} | {status_str}")
    print("=" * 95, flush=True)

if __name__ == "__main__":
    run_50_suite()
