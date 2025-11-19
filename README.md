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

7. Launch the Web Dashboard (optional)
python app.py

Then open your browser to: **http://127.0.0.1:5000**

🌐 Web Dashboard Guide

The `app.py` script launches a Flask web application for interactive baseline and drift management.

**Features:**
- 📸 Take snapshots of current AWS account state (IAM, S3, EC2 Security Groups)
- 📊 Compare any snapshot against baseline to detect configuration drift
- 🔍 View CloudTrail events correlated to detected changes (shows WHO made changes and FROM where)
- 💾 Upload/download baseline and snapshot files
- 📈 View detailed change logs with real-time monitoring
- 🌙 Dark mode toggle for comfortable viewing
- ⚠️ Warning indicators for account mismatches

**Quick Start:**

```bash
cd ics496-drift/baseline
python app.py
```

Visit **http://127.0.0.1:5000** in your browser.

**Main Sections:**

1. **Baseline Panel**
   - Upload a baseline (`Baseline.json`)
   - Download the current baseline
   - Status indicator showing if baseline exists

2. **Snapshots Panel**
   - **Take Snapshot**: Capture current AWS state
   - **Compare Latest vs Baseline**: Show changes between most recent snapshot and baseline
   - View, download, or compare individual snapshots

3. **Latest Log Panel**
   - Shows most recent comparison results
   - Displays three change categories (always visible):
     - **IAM users**: New/removed IAM user accounts
     - **S3 changes**: Added/removed S3 buckets
     - **EC2 Security Group changes**: New/removed/modified security groups
   - **CloudTrail Events** (right column): Shows AWS API calls linked to detected changes
     - Lists who made the changes (User/Principal)
     - Shows source IP addresses for audit purposes
   - ⚠️ **Warning Badge**: Alerts if snapshots are from different AWS accounts

4. **Log Panel**
   - Real-time monitoring and comparison logs
   - Searchable and downloadable

**Using the Dashboard:**

1. Start the app: `python app.py`
2. Upload a baseline JSON file using **Baseline Panel** (or use an existing one)
3. Click **Take Snapshot** to capture current AWS infrastructure state
4. Click **Compare Latest vs Baseline** to see changes
   - Shows all changes across IAM, S3, and EC2 Security Groups
   - Automatically fetches CloudTrail events from the past 10 minutes
5. View **Latest Log Panel** to see:
   - **Left column**: All infrastructure changes organized by category
   - **Right column**: CloudTrail events showing WHO made each change and FROM which IP
6. Use **🌙 Dark** button (top right) to toggle dark mode for comfortable viewing
7. Optional: Use **Start Monitor** to enable continuous real-time monitoring

**Example Workflow:**

```
Step 1: Setup
  - Start app: python app.py
  - Visit http://127.0.0.1:5000
  - Upload baseline JSON (or generate one with: python enumerate_baseline.py)

Step 2: Take Initial Snapshot
  - Click "Take Snapshot" in Snapshots Panel
  - App runs enumerate_baseline.py and captures current state
  - New baseline_TIMESTAMP.json file is created

Step 3: Simulate Infrastructure Changes
  - Make changes in AWS Console (add/remove security groups, users, S3 buckets)
  - OR manually modify the JSON files to test

Step 4: Take Another Snapshot
  - Click "Take Snapshot" again to capture new state
  - Another baseline_TIMESTAMP.json is created

Step 5: Compare for Drift
  - Click "Compare→Baseline" next to latest snapshot
  - App runs compare_baseline.py to show differences
  - CloudTrail events are automatically fetched and correlated

Step 6: Review Results in Latest Log Panel
  - Left column: All changes (IAM users, S3 buckets, Security Groups)
  - Right column: CloudTrail events showing WHO made changes and SOURCE IP
  - ⚠️ Warning badge shows if comparing different AWS accounts
```

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

