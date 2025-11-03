# AWS Drift Detection - Quick Start & Testing Guide

## 5-Minute Quick Start

### 1. Verify Setup
```bash
cd /Users/angeport/Documents/GitHub/Senior-Project-Drift-Detection/ics496-drift/baseline

# Check Python and dependencies
python3 --version  # Should be 3.9+
pip list | grep -E "Flask|boto3"  # Should show Flask 3.0.0 and boto3

# Check AWS credentials
aws sts get-caller-identity  # Should return your AWS account info
```

### 2. Create Initial Baseline
```bash
# Take first snapshot
python enumerate_baseline.py

# You should see: "Wrote snapshot_2025-11-03T12-34-56Z.json"
# This is your reference baseline

# Copy it to Baseline.json
cp snapshot_*.json Baseline.json
```

### 3. Test via Web UI (Easiest)
```bash
python app.py
# Open http://127.0.0.1:5000 in your browser
```

**UI provides buttons to:**
- Take snapshots
- Compare snapshots
- Upload baselines
- View drift logs
- Start/stop monitor

### 4. Test via Command Line
```bash
# In separate terminal, make a change in AWS (e.g., via console)
# Then take another snapshot
python enumerate_baseline.py

# Compare against baseline
python compare_baseline.py Baseline.json snapshot_*.json

# You should see drift output with changes detected
```

---

## Step-by-Step Testing Workflow

### Test 1: Verify Basic Enumeration

**Objective:** Ensure AWS connectivity and data collection works

```bash
python enumerate_baseline.py
```

**Expected Output:**
```
Wrote snapshot_2025-11-03T15-30-45Z.json
```

**What to check:**
- ✅ File created in current directory
- ✅ File size > 1KB
- ✅ Contains valid JSON (view with `cat snapshot_*.json | head -50`)
- ✅ Has sections: meta, identity, iam, s3, ec2

**If it fails:**
```bash
# Check AWS credentials
aws sts get-caller-identity

# Check IAM permissions (should not get AccessDenied on most calls)
python enumerate_baseline.py 2>&1 | grep -i "error\|denied"
```

---

### Test 2: Verify Comparison Engine

**Objective:** Ensure drift detection logic works with sample data

```bash
# Take first snapshot and save as baseline
python enumerate_baseline.py
SNAP1=$(ls -t snapshot_*.json | head -1)
cp "$SNAP1" Baseline.json

# Wait a bit, take another snapshot
sleep 10
python enumerate_baseline.py
SNAP2=$(ls -t snapshot_*.json | head -1)

# Compare them (should show "No drift" if no changes made)
python compare_baseline.py Baseline.json "$SNAP2"
```

**Expected Output:**
```
================================================================================
Done.
```

(Nothing printed means no changes detected - this is OK for first test)

**What to check:**
- ✅ Script runs without errors
- ✅ Returns successfully
- ✅ No AccessDenied or connection errors

---

### Test 3: Trigger Real Drift Detection

**Objective:** Make an AWS change and verify it's detected

#### Option A: Create New IAM User
```bash
# Open AWS Console or use AWS CLI
aws iam create-user --user-name test-drift-user-$(date +%s)

# Wait 10 seconds, take snapshot
sleep 10
python enumerate_baseline.py

# Compare
SNAP=$(ls -t snapshot_*.json | head -1)
python compare_baseline.py Baseline.json "$SNAP"
```

**Expected Output:**
```
================================================================================
IAM changes
================================================================================
- User added: test-drift-user-1730645445
```

#### Option B: Modify Security Group
```bash
# Get a security group ID
aws ec2 describe-security-groups --query 'SecurityGroups[0].GroupId' --output text

# Authorize a new inbound rule
aws ec2 authorize-security-group-ingress \
  --group-id sg-xxxxxxxx \
  --protocol tcp \
  --port 9999 \
  --cidr 10.0.0.0/8

# Take snapshot and compare
sleep 10
python enumerate_baseline.py
SNAP=$(ls -t snapshot_*.json | head -1)
python compare_baseline.py Baseline.json "$SNAP"
```

**Expected Output:**
```
================================================================================
EC2 Security Group changes
================================================================================
- SG modified: sg-xxxxxxxx
  - InboundRules changed
    - was: [...]
    - now: [...]
```

#### Option C: Modify S3 Bucket
```bash
# List your S3 buckets
aws s3 ls

# Enable versioning on a bucket (if not already enabled)
aws s3api put-bucket-versioning \
  --bucket your-bucket-name \
  --versioning-configuration Status=Enabled

# Take snapshot and compare
sleep 10
python enumerate_baseline.py
SNAP=$(ls -t snapshot_*.json | head -1)
python compare_baseline.py Baseline.json "$SNAP"
```

**Expected Output:**
```
================================================================================
S3 changes
================================================================================
- Bucket modified: your-bucket-name
  - Versioning.Status changed
    - was: None
    - now: Enabled
```

---

### Test 4: Web Interface Testing

**Objective:** Test all web UI features

```bash
python app.py
# Navigate to http://127.0.0.1:5000
```

**Test each button:**

| Button | Test Action | Expected |
|--------|-------------|----------|
| "Take Snapshot" | Click button | New snapshot appears in list, download available |
| "Compare Latest vs Baseline" | After taking snapshot | Drift output shows in "Latest Drift Output" panel |
| "Download Baseline" | Click after uploading | File downloads (check Downloads folder) |
| "Upload Baseline.json" | Use file picker | Baseline.json updated in UI |
| "View" (snapshot) | Click for a snapshot | Snapshot JSON displays in new window |
| "Download" (snapshot) | Click for a snapshot | File downloads |
| "Compare→Baseline" (snapshot) | Click for a snapshot | Drift output shows |
| "Start Monitor" | Click button | Changes to "Stop Monitor", monitor starts logging |
| "Stop Monitor" | After starting | Changes back to "Start Monitor", monitor stops |
| "Open full log" | Click link | realtime_monitor.log displays |

---

### Test 5: Realtime Monitor Testing

**Objective:** Test continuous monitoring with CloudTrail integration

#### Terminal 1: Start Monitor
```bash
python realtime_monitor.py
# Should print: "[2025-11-03T...] Starting realtime monitor (every 20s)"
# Watch logs update every 20 seconds
```

#### Terminal 2: Make Changes
```bash
# Create a new security group
aws ec2 create-security-group \
  --group-name "test-drift-sg-$(date +%s)" \
  --description "Testing drift detection"

# Monitor in Terminal 1 should detect this within 20-40 seconds
```

**Expected in realtime_monitor.log:**
```
[2025-11-03T15-45-30Z] Captured snapshot: snapshot_2025-11-03T15-45-30Z.json
[2025-11-03T15-45-30Z] Drift detected between Baseline.json and snapshot_2025-11-03T15-45-30Z.json:
[2025-11-03T15-45-30Z] --- compare stdout begin ---
[2025-11-03T15-45-30Z]   - EC2 Security Group changes
[2025-11-03T15-45-30Z]   - SG added: sg-12345678
[2025-11-03T15-45-30Z] --- compare stdout end ---
[2025-11-03T15-45-30Z] Searching CloudTrail for keywords: sg-12345678
[2025-11-03T15-45-31Z] Found 1 CloudTrail event(s) related to the drift:
[2025-11-03T15-45-31Z]   - 2025-11-03T15:45:31Z CreateSecurityGroup by IAMUser:user@company.com from 203.0.113.45
```

#### Stop Monitor
```bash
# Terminal 1
Ctrl+C

# Terminal 2
pkill -f realtime_monitor.py
```

---

### Test 6: Snapshot Rotation Testing

**Objective:** Verify old snapshots are automatically cleaned up

```bash
# Start monitor (will take snapshots every 20 seconds)
python realtime_monitor.py &

# Wait 5+ minutes (takes at least ~12 snapshots)
sleep 300

# Check snapshot count (should be ≤ 10)
ls -1 snapshot_*.json | wc -l  # Should show ~10 or less

# Check logs for cleanup messages
grep "Removed old snapshot" realtime_monitor.log

# Stop monitor
pkill -f realtime_monitor.py
```

**Expected:**
```
[2025-11-03T15-55-30Z] Snapshot count (after trim): 10
[2025-11-03T15-55-30Z] Removed old snapshot: snapshot_2025-11-03T15-30-45Z.json
```

---

## Test Checklist

Use this checklist to verify all functionality:

```
BASIC ENUMERATION
  [ ] enumerate_baseline.py creates JSON files
  [ ] Files contain valid JSON
  [ ] Files include meta, identity, iam, s3, ec2 sections
  
COMPARISON ENGINE
  [ ] compare_baseline.py runs without errors
  [ ] Detects IAM user changes
  [ ] Detects S3 bucket changes
  [ ] Detects EC2 security group changes
  [ ] Correctly reports "No drift" when there are no changes
  
WEB INTERFACE
  [ ] Flask server starts on 127.0.0.1:5000
  [ ] Dashboard displays correctly
  [ ] Take Snapshot button works
  [ ] Compare Latest button works
  [ ] Upload Baseline button works
  [ ] Download buttons work
  [ ] View buttons display JSON correctly
  [ ] Start/Stop Monitor buttons work
  
REALTIME MONITOR
  [ ] Starts without errors
  [ ] Creates snapshots every 20 seconds
  [ ] Detects drift within 40 seconds of AWS change
  [ ] Logs to realtime_monitor.log
  [ ] Queries CloudTrail for event context
  [ ] Stops gracefully with Ctrl+C
  [ ] Keeps only last 10 snapshots
  
CLOUDTRAIL INTEGRATION
  [ ] Extracts keywords from drift output (SG IDs, etc.)
  [ ] Queries CloudTrail successfully
  [ ] Returns matching events with details
  [ ] Logs event times, usernames, IPs
```

---

## Troubleshooting Tests

### If enumerate_baseline.py fails:

```bash
# Test 1: Check credentials
aws sts get-caller-identity
# Should return JSON with Account, UserId, Arn

# Test 2: Test each AWS service individually
python3 << 'EOF'
import boto3
try:
    sts = boto3.client('sts')
    print("✓ STS:", sts.get_caller_identity()['Account'])
except Exception as e:
    print("✗ STS:", e)

try:
    iam = boto3.client('iam')
    print("✓ IAM: users =", len(iam.list_users()['Users']))
except Exception as e:
    print("✗ IAM:", e)

try:
    s3 = boto3.client('s3')
    print("✓ S3: buckets =", len(s3.list_buckets()['Buckets']))
except Exception as e:
    print("✗ S3:", e)

try:
    ec2 = boto3.client('ec2')
    print("✓ EC2: SGs =", len(ec2.describe_security_groups()['SecurityGroups']))
except Exception as e:
    print("✗ EC2:", e)
EOF
```

### If comparison shows no changes (but you made changes):

```bash
# Check if changes are recent (CloudTrail has lag)
# Compare two fresh snapshots 10+ seconds apart
python enumerate_baseline.py
sleep 15
python enumerate_baseline.py

# Check if you have permissions to see your own changes
aws iam get-user  # Should work
```

### If web interface won't start:

```bash
# Check if port is in use
lsof -i :5000

# Use different port
python3 -c "
from app import app
app.run(host='127.0.0.1', port=5001, debug=True)
"
```

### If CloudTrail integration not working:

```bash
# Check if CloudTrail is enabled
aws cloudtrail describe-trails --query 'trailList[*].TrailARN' --output text

# Manually query CloudTrail
python3 << 'EOF'
import boto3
from datetime import datetime, timedelta, timezone
ct = boto3.client('cloudtrail')
result = ct.lookup_events(
    StartTime=datetime.now(timezone.utc) - timedelta(hours=1),
    EndTime=datetime.now(timezone.utc),
    MaxResults=10
)
print(f"Found {len(result['Events'])} events in past hour")
EOF
```

---

## Performance Testing

### Baseline Enumeration Time

```bash
time python enumerate_baseline.py
```

**Expected times:**
- IAM-only accounts: 2-5 seconds
- Small S3 (< 10 buckets): 3-8 seconds
- Large S3 (> 100 buckets): 10-30 seconds
- EC2 with many SGs: 5-15 seconds
- **Total typical:** 10-30 seconds per enumeration

### Comparison Time

```bash
time python compare_baseline.py Baseline.json snapshot_*.json
```

**Expected:** < 1 second

### Monitor Overhead

```bash
# Monitor CPU usage
top -b -p $(pgrep -f realtime_monitor.py)

# Monitor memory usage
ps aux | grep realtime_monitor.py
```

**Expected:**
- CPU: < 5% (mostly idle between enumerations)
- Memory: < 100MB

---

## Data Privacy & Security Notes

⚠️ **Important for production use:**

1. **Snapshots contain sensitive data:**
   - IAM policy documents (could contain secrets)
   - S3 bucket policies (could contain principals)
   - Security group rules (could expose internal architecture)
   
2. **Protect snapshot files:**
   - Restrict file permissions: `chmod 600 *.json`
   - Store in secure location
   - Enable encryption at rest
   - Don't commit to Git without `.gitignore`

3. **Logs may contain sensitive info:**
   - Stored in `realtime_monitor.log`
   - Contains resource IDs, timestamps, user identities
   - Implement log rotation and retention policies

4. **Web interface:**
   - Currently `127.0.0.1` only (localhost)
   - No authentication
   - Don't expose to public network
   - For production: add authentication, HTTPS, API key

---

## Next: Production Deployment

Once testing is complete, consider:

1. **Containerization:** Docker/Kubernetes
2. **Persistent Storage:** S3 for snapshots and logs
3. **Alerts:** Slack, PagerDuty, SNS
4. **Dashboard:** CloudWatch metrics, Datadog
5. **Automation:** Lambda, EventBridge for scheduled runs
6. **Multi-Region:** Monitor multiple AWS regions
7. **Multi-Account:** Support AWS Organizations

