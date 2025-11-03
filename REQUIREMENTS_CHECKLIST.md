# AWS Drift Detection System - Requirements Checklist

## Prerequisites & Setup Status

### ✅ System Requirements
- [x] macOS/Linux/Windows system
- [x] Python 3.9+ installed
- [x] Terminal access (`zsh` shell)
- [x] Git repository cloned
- [x] Internet connectivity for AWS APIs

**Current Status:** ✅ All present

---

## ✅ Python Environment

### Required Files
- [x] `.venv/` - Virtual environment exists
- [x] `requirements.txt` - Specifies Flask==3.0.0, boto3>=1.34.0
- [x] Core modules present:
  - [x] `app.py` (Flask web server)
  - [x] `enumerate_baseline.py` (AWS enumerator)
  - [x] `compare_baseline.py` (Comparison engine)
  - [x] `realtime_monitor.py` (Monitor daemon)
  - [x] `cloudtrail_fetch.py` (CloudTrail fetcher)

### Setup Steps Completed
- [x] Virtual environment created (`.venv/`)
- [x] Python packages installed

**Current Status:** ✅ Ready to use

**Verify with:**
```bash
cd /Users/angeport/Documents/GitHub/Senior-Project-Drift-Detection/ics496-drift/baseline
source .venv/bin/activate
python -c "import flask, boto3; print('✓ OK')"
```

---

## 🔑 AWS Credentials & Permissions

### Required Configuration
- [ ] AWS credentials configured (one of):
  - [ ] `~/.aws/credentials` file
  - [ ] `~/.aws/config` file
  - [ ] Environment variables: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
  - [ ] IAM role (if running on EC2)
  - [ ] `sandbox-instance.pem` for EC2 access

### Required IAM Permissions
- [ ] `sts:GetCallerIdentity` - Account identity
- [ ] `iam:ListUsers`, `iam:ListGroupsForUser`, `iam:ListAttachedUserPolicies`, `iam:ListUserPolicies` - IAM enumeration
- [ ] `s3:ListAllMyBuckets`, `s3:GetBucket*` - S3 enumeration
- [ ] `ec2:DescribeSecurityGroups` - EC2 enumeration
- [ ] `cloudtrail:LookupEvents` - CloudTrail querying

**Current Status:** ⚠️ Needs verification

**Verify with:**
```bash
aws sts get-caller-identity  # Should return Account, UserId, Arn
aws iam list-users --max-items 1  # Should succeed
aws s3 ls  # Should succeed
aws ec2 describe-security-groups --max-results 1  # Should succeed
aws cloudtrail lookup-events --max-results 1  # Should succeed
```

**If any command fails:**
- Check credentials: `aws sts get-caller-identity`
- Check region: `echo $AWS_DEFAULT_REGION`
- Check IAM permissions: Contact AWS admin
- Add missing permissions to IAM policy (see `SYSTEM_ANALYSIS.md`)

---

## 📁 Working Directory & Files

### Required Files Present
- [x] `requirements.txt` - Python dependencies
- [x] `app.py` - Flask web server (251 lines)
- [x] `enumerate_baseline.py` - AWS enumerator (154 lines)
- [x] `compare_baseline.py` - Comparison engine (194 lines)
- [x] `realtime_monitor.py` - Monitor daemon (304 lines)
- [x] `cloudtrail_fetch.py` - CloudTrail client

### Expected Output Files (Generated During Runtime)
- [ ] `Baseline.json` - Reference baseline (created manually)
- [ ] `snapshot_YYYY-MM-DDTHH-MM-SSZ.json` - Snapshots (auto-generated)
- [ ] `realtime_monitor.log` - Monitor logs (auto-generated)

### Storage Requirements
- **Per snapshot:** ~100 KB - 1 MB (depending on AWS resource count)
- **Keep last 10 snapshots:** ~1-10 MB
- **Logs per day:** ~1-10 MB
- **Total storage:** ~100 MB for normal use

**Current Status:** ✅ All source files present, output files will be generated

---

## 🔧 Development Tools

### For Testing
- [x] `curl` or `wget` - HTTP requests (for testing Flask)
- [x] `python3` - Python interpreter
- [x] `pip` - Python package manager
- [x] `jq` (optional) - JSON formatting

### For AWS Interaction
- [ ] `aws` CLI - AWS command line tool
  - Used for manual testing
  - Not required but highly recommended

**Optional installation:**
```bash
# macOS
brew install awscli

# Linux
sudo apt-get install awscli

# All platforms
pip install awscli
```

**Current Status:** ⚠️ AWS CLI recommended but not required

---

## 🧪 Testing Requirements

### For Manual Testing
- [x] Web browser (for testing Flask UI)
- [x] Terminal/shell (for CLI testing)
- [x] AWS console access (for making test changes)

### For Automated Testing
- [ ] `pytest` - Python test framework
- [ ] `boto3-stubs` - Type hints for testing
- [ ] `moto` - AWS mock library
- [ ] Test fixtures with sample data

**Current Status:** ❌ No automated tests present (can be added)

---

## 🚀 Getting Started Checklist

### Phase 1: Verify Setup (5 minutes)
- [ ] Open terminal in project directory
- [ ] Activate virtual environment:
  ```bash
  source .venv/bin/activate
  ```
- [ ] Verify Python packages:
  ```bash
  pip list | grep -E "Flask|boto3"
  ```
- [ ] Verify AWS credentials:
  ```bash
  aws sts get-caller-identity
  ```

**Estimated time:** 5 minutes
**Success criteria:** All commands return without errors

### Phase 2: Create Baseline (5 minutes)
- [ ] Take initial AWS snapshot:
  ```bash
  python enumerate_baseline.py
  ```
- [ ] Verify output file created:
  ```bash
  ls -lh snapshot_*.json
  ```
- [ ] Copy to baseline:
  ```bash
  cp snapshot_*.json Baseline.json
  ```
- [ ] Verify baseline created:
  ```bash
  ls -lh Baseline.json
  ```

**Estimated time:** 5 minutes
**Success criteria:** Baseline.json exists and contains valid JSON

### Phase 3: Test Web Interface (10 minutes)
- [ ] Start Flask server:
  ```bash
  python app.py
  ```
- [ ] Open browser to `http://127.0.0.1:5000`
- [ ] Verify UI displays correctly
- [ ] Click "Take Snapshot" button
- [ ] Verify new snapshot appears in list
- [ ] Click "Compare Latest vs Baseline" button
- [ ] Check drift output (should say "No drift" if no changes)

**Estimated time:** 10 minutes
**Success criteria:** Web UI works, buttons responsive, snapshots created

### Phase 4: Test Drift Detection (15 minutes)
- [ ] In AWS console, make a test change (e.g., create security group)
- [ ] In Flask UI, click "Take Snapshot"
- [ ] Click "Compare Latest vs Baseline"
- [ ] Verify drift is detected and displayed
- [ ] Check that CloudTrail events are listed

**Estimated time:** 15 minutes
**Success criteria:** Drift detected and correlated with CloudTrail events

### Phase 5: Test Monitor Daemon (20 minutes)
- [ ] In terminal, start monitor:
  ```bash
  python realtime_monitor.py
  ```
- [ ] Make a test change in AWS
- [ ] Watch logs update:
  ```bash
  tail -f realtime_monitor.log
  ```
- [ ] Verify drift detected within 40 seconds
- [ ] Stop monitor with Ctrl+C
- [ ] Verify graceful shutdown

**Estimated time:** 20 minutes
**Success criteria:** Monitor detects changes automatically

### Total Setup & Testing Time: ~55 minutes

---

## 📋 What Each Module Needs to Run

### `enumerate_baseline.py`
**Needs:**
- ✅ boto3 library
- ✅ AWS credentials
- ✅ IAM permissions: STS, IAM, S3, EC2
- ✅ Current working directory: writable
- ❌ No external files

**Run:** `python enumerate_baseline.py`

**Output:** `snapshot_2025-11-03T12-34-56Z.json` (~500 KB typically)

---

### `compare_baseline.py`
**Needs:**
- ✅ Two JSON snapshot files
- ✅ Valid JSON format
- ✅ Current working directory

**Run:** `python compare_baseline.py Baseline.json snapshot_2025-11-03T12-34-56Z.json`

**Output:** Human-readable diff to stdout

---

### `app.py` - Flask Web Server
**Needs:**
- ✅ Flask library
- ✅ Python 3.9+
- ✅ Current working directory: writable (for file uploads)
- ✅ Port 5000: available
- ❌ Optionally: enumerate_baseline.py and compare_baseline.py in same directory

**Run:** `python app.py`

**Output:** Web server on `http://127.0.0.1:5000`

**Dependencies:** Calls `enumerate_baseline.py` and `compare_baseline.py` via subprocess

---

### `realtime_monitor.py` - Monitor Daemon
**Needs:**
- ✅ boto3 library
- ✅ AWS credentials
- ✅ Current working directory: writable
- ✅ `Baseline.json` (optional but recommended)
- ✅ `enumerate_baseline.py` in same directory
- ✅ `compare_baseline.py` in same directory
- ✅ `cloudtrail_fetch.py` in same directory (optional but recommended)

**Run:** `python realtime_monitor.py`

**Output:** 
- `snapshot_*.json` files (every 20 seconds)
- `realtime_monitor.log` updates
- Prints to stdout

**Behavior:**
- Runs continuously
- Press Ctrl+C to stop
- Creates/updates snapshots every 20 seconds
- Keeps last 10 snapshots
- Queries CloudTrail for context

---

### `cloudtrail_fetch.py` - CloudTrail Client
**Needs:**
- ✅ boto3 library
- ✅ AWS credentials
- ✅ CloudTrail enabled in AWS account

**Run:** Called by `realtime_monitor.py` (not directly)

**Used by:** `realtime_monitor.py` to correlate drift with CloudTrail events

---

## ⚠️ Common Issues & Quick Fixes

| Problem | Fix |
|---------|-----|
| `NoCredentialsError` | Run `aws configure` or set `AWS_*` env vars |
| `ModuleNotFoundError: boto3` | Run `pip install -r requirements.txt` |
| `Port 5000 in use` | Change app.py port or run `lsof -i :5000 \| kill -9` |
| Enumerate runs but finds no resources | Check IAM permissions, may need to add more |
| Comparison shows no drift | Either no changes made, or use `--debug` flag if available |
| Monitor doesn't detect changes | Wait 20+ seconds, check CloudTrail enabled |
| Web UI won't start | Check Python version >= 3.9, check port availability |

---

## 🎯 Success Criteria

### Minimal Success (System Works)
- ✅ Can take AWS snapshots
- ✅ Can compare snapshots
- ✅ Web UI responds
- ✅ Detects changes when made manually

### Full Success (All Features Working)
- ✅ All above, plus:
- ✅ Monitor daemon runs continuously
- ✅ Automatically detects changes
- ✅ CloudTrail integration works
- ✅ Snapshot rotation working (keeps last 10)
- ✅ Logs to file and console

### Production Ready
- ✅ All above, plus:
- ✅ Error handling and recovery
- ✅ Test coverage > 80%
- ✅ Configuration management
- ✅ Security hardening (authentication, HTTPS)
- ✅ Documentation complete
- ✅ Performance optimized

**Current Status:** Full Success achievable with setup ✅

---

## 📊 Testing Matrix

| Feature | Manual Test | Web UI Test | CLI Test | Monitor Test | Status |
|---------|-------------|------------|----------|--------------|--------|
| Enumerate IAM | `python enumerate_baseline.py` | "Take Snapshot" | Direct call | Every 20s | ✅ Ready |
| Enumerate S3 | Same as above | Same | Same | Same | ✅ Ready |
| Enumerate EC2 | Same | Same | Same | Same | ✅ Ready |
| Compare | `python compare_baseline.py` | "Compare Latest" | Direct call | Every 20s | ✅ Ready |
| Drift Detection | Manual AWS changes | Manual AWS changes | Manual AWS changes | Automatic | ✅ Ready |
| CloudTrail Integration | Via compare script | Via compare button | Via CLI | Automatic | ✅ Ready |
| Snapshot Rotation | Manual monitoring | View list | Check files | Every 20s | ✅ Ready |
| Web UI | N/A | Full test | N/A | Monitor can be started from UI | ✅ Ready |
| File Upload | Manual | Upload button | Not applicable | N/A | ✅ Ready |
| Log Viewing | `cat realtime_monitor.log` | Click link | Direct file | Via button | ✅ Ready |

---

## 🎓 Quick Reference Commands

### Setup & Activation
```bash
cd /Users/angeport/Documents/GitHub/Senior-Project-Drift-Detection/ics496-drift/baseline
source .venv/bin/activate
```

### Testing
```bash
# Single enumeration
python enumerate_baseline.py

# Comparison
python compare_baseline.py Baseline.json snapshot_*.json

# Web interface
python app.py  # Visit http://127.0.0.1:5000

# Monitor daemon
python realtime_monitor.py  # Ctrl+C to stop

# Watch logs (in another terminal)
tail -f realtime_monitor.log
```

### AWS CLI (Optional)
```bash
# Verify credentials
aws sts get-caller-identity

# List IAM users
aws iam list-users

# List S3 buckets
aws s3 ls

# List security groups
aws ec2 describe-security-groups --query 'SecurityGroups[*].GroupId' --output table

# Make test changes
aws iam create-user --user-name test-user
aws ec2 authorize-security-group-ingress --group-id sg-xxx --protocol tcp --port 443 --cidr 0.0.0.0/0
```

### File Management
```bash
# List snapshots
ls -lh snapshot_*.json

# View snapshot (pretty print)
python -m json.tool snapshot_*.json | head -50

# Compare file sizes
du -h snapshot_*.json Baseline.json

# Clean up old snapshots (keep last 5)
ls -t snapshot_*.json | tail -n +6 | xargs rm
```

---

## 📞 Support & Resources

### Documentation
- See `SYSTEM_ANALYSIS.md` for complete system design
- See `TESTING_GUIDE.md` for detailed testing procedures

### AWS Documentation
- [AWS SDK for Python (boto3)](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
- [CloudTrail API Reference](https://docs.aws.amazon.com/awscloudtrail/latest/APIReference/)
- [IAM API Reference](https://docs.aws.amazon.com/IAM/latest/APIReference/)

### Common Errors
- `NoCredentialsError`: Set up AWS credentials (see AWS CLI setup)
- `AccessDenied`: Add IAM permissions (see policy in SYSTEM_ANALYSIS.md)
- `ModuleNotFoundError`: Run `pip install -r requirements.txt`

### Getting Help
1. Check `SYSTEM_ANALYSIS.md` for architecture details
2. Check `TESTING_GUIDE.md` for troubleshooting
3. Review error logs in `realtime_monitor.log`
4. Test AWS connectivity: `aws sts get-caller-identity`

