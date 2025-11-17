Continuous Cloud Security Posture Drift Detection (PoC)

This repository contains a Proof-of-Concept (PoC) system for Continuous Cloud Security Posture Management (CCSPM) focused on detecting configuration drift within AWS environments.
The project was developed as part of ICS 496 – Software Engineering Project (Fall 2025) in collaboration with NIWC Atlantic, supporting efforts to improve automated visibility into DoD cloud subscriber environments.

📌 Project Overview

Cybersecurity analysts are frequently overwhelmed by large volumes of undifferentiated cloud security data, making it difficult to identify high-impact configuration changes. This PoC addresses that challenge by providing automated:

Enumeration of AWS security-related configurations

Baseline generation for known-good cloud states

Detection of drift from the baseline

Basic reporting/logging of changes over time

The goal is to demonstrate a minimal viable workflow for continuous monitoring of AWS account posture and highlight challenges and recommendations for future multi-cloud or hybrid implementations.

🛠 Features
Baseline Enumeration

The system collects a predefined set of AWS security controls, including (but not limited to):

IAM policies

Security Groups

S3 bucket policies

CloudTrail metadata

These are stored as JSON baseline files.

Drift Detection

The tool compares current account configurations against the established baseline and reports changes such as:

Newly added or removed configurations

Modified IAM policies or Security Groups

Changes to S3 access control

Drift identified through AWS CloudTrail activity

Real-Time Monitoring (PoC)

A lightweight monitoring script polls AWS metadata at intervals and logs detected changes to:

realtime_monitor.log

CloudTrail Integration

CloudTrail events can be fetched and analyzed to correlate configuration drift with API activity.

Web-Based Component (Planned/Prototype)

A simple web application (app.py) demonstrates how a UI could present baseline and drift results in a deployed environment.

📂 Repository Structure
ics496-drift/
└── baseline/
    ├── Baseline.json                     # Current baseline snapshot
    ├── baseline_*.json                   # Historical snapshots
    ├── enumerate_baseline.py             # Baseline generation
    ├── compare_baseline.py               # Drift comparison logic
    ├── realtime_monitor.py               # Live monitoring proof-of-concept
    ├── cloudtrail_fetch.py               # CloudTrail event retrieval tool
    ├── app.py                            # Minimal web app (PoC)
    ├── requirements.txt                  # Python dependencies
    └── .venv/                            # Optional local development env

🚀 Getting Started
1. Clone the Repository
git clone https://github.com/<your-org>/Senior-Project-Drift-Detection.git
cd ics496-drift/baseline

2. Install Dependencies
pip install -r requirements.txt

3. Configure AWS Access

You must have access to a sandbox AWS account and valid AWS credentials (e.g., via aws configure).

4. Generate a Baseline
python enumerate_baseline.py

5. Compare for Drift
python compare_baseline.py

6. Start Real-Time Monitoring (optional)
python realtime_monitor.py

📊 Acceptance Criteria (Met by PoC)

Authenticate to a single AWS sandbox account

Enumerate key security configurations

Generate and store static baseline snapshots

Detect configuration drift and report changes

Provide minimal logging/UI output

Operate within the NIWC Cyber Innovation Range (CIR)

Document limitations and recommendations for future expansion

📚 Future Enhancements

Multi-account / multi-cloud support (Azure, GCP)

Automated alerts (SNS, email, SIEM feeds)

Full-featured web dashboard and API

Deeper integration with CloudTrail and GuardDuty

RBAC, session auditing, and hardened architecture for DoD use cases

