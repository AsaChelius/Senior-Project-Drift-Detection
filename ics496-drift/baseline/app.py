#!/usr/bin/env python3
import os, sys, json, glob, subprocess, threading, signal, re
from pathlib import Path
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template_string, request, redirect, url_for, send_from_directory, flash

# Try to import cloudtrail_fetch
try:
    from cloudtrail_fetch import find_events_for_keywords
except ImportError:
    find_events_for_keywords = None

UTC = timezone.utc

# --- CONFIG ---
APP_DIR = Path(__file__).parent.resolve()         # this folder (baseline/)
LOGFILE = APP_DIR / "realtime_monitor.log"
BASELINE = APP_DIR / "Baseline.json"
SNAP_GLOB = "baseline_*.json"                     # matches enumerate_baseline.py output
PY = sys.executable                                # current interpreter
MONITOR_POPEN = {"proc": None}                     # track running monitor

app = Flask(__name__)
app.secret_key = "dev-demo-only"                   # for flash(); replace for real use

# --- HTML (simple, no external deps) ---
PAGE = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>AWS Drift Demo</title>
  <style>
    :root {
      --bg-primary: #ffffff;
      --bg-secondary: #f9fafb;
      --bg-tertiary: #f6f8fa;
      --text-primary: #000000;
      --text-secondary: #666666;
      --border-color: #eeeeee;
      --card-bg: #ffffff;
      --table-header-bg: #f0f0f0;
    }
    
    body.dark-mode {
      --bg-primary: #1a1a1a;
      --bg-secondary: #2d2d2d;
      --bg-tertiary: #3a3a3a;
      --text-primary: #e0e0e0;
      --text-secondary: #b0b0b0;
      --border-color: #404040;
      --card-bg: #242424;
      --table-header-bg: #333333;
    }
    
    body{font-family:system-ui,Arial,sans-serif; max-width:1200px; margin:40px auto; line-height:1.4; background:var(--bg-primary); color:var(--text-primary); transition:background 0.3s, color 0.3s}
    header{display:flex; gap:12px; align-items:center; justify-content:space-between}
    .header-right{display:flex; gap:12px; align-items:center}
    .dark-mode-toggle{display:inline-flex; align-items:center; gap:8px; padding:8px 12px; border-radius:8px; border:1px solid var(--border-color); background:var(--card-bg); cursor:pointer; font-size:14px; color:var(--text-primary)}
    .dark-mode-toggle:hover{background:var(--bg-secondary)}
    code,pre{background:var(--bg-tertiary); padding:8px; border-radius:8px; display:block; overflow:auto; color:var(--text-primary); border:1px solid var(--border-color)}
    .row{display:flex; gap:16px; flex-wrap:wrap}
    .card{flex:1 1 320px; border:1px solid var(--border-color); border-radius:12px; padding:16px; background:var(--card-bg)}
    .card-wide{flex:1 1 100%; max-width:100%}
    .good{color:#0a7a2f} .bad{color:#b00020}
    .btn{display:inline-block; padding:8px 12px; border-radius:8px; border:1px solid var(--border-color); background:var(--card-bg); cursor:pointer; color:var(--text-primary); transition:background 0.2s}
    .btn:hover{background:var(--bg-secondary)}
    .btn-primary{background:#0d6efd; color:#fff; border-color:#0d6efd}
    .btn-primary:hover{background:#0b5ed7}
    .btn-danger{background:#b00020; color:#fff; border-color:#b00020}
    .btn-danger:hover{background:#a00020}
    form{display:inline}
    table{width:100%; border-collapse:collapse}
    th, td{border-bottom:1px solid var(--border-color); padding:8px; text-align:left; color:var(--text-primary)}
    .muted{color:var(--text-secondary)}
    .change-section{margin:16px 0; padding:12px; background:var(--bg-secondary); border-left:4px solid #0d6efd; border-radius:4px}
    .change-section h4{margin:0 0 8px 0; color:#0d6efd}
    .change-item{padding:8px; margin:4px 0; background:var(--card-bg); border-radius:4px; border:1px solid var(--border-color)}
    .change-item.added{border-left:3px solid #0a7a2f; color:#0a7a2f}
    .change-item.removed{border-left:3px solid #b00020; color:#b00020}
    .change-item.modified{border-left:3px solid #f59e0b; color:#f59e0b}
    .cloudtrail-table{width:100%; border-collapse:collapse; margin-top:12px}
    .cloudtrail-table th{background:var(--table-header-bg); padding:10px; font-weight:bold; border:1px solid var(--border-color); text-align:left; color:var(--text-primary)}
    .cloudtrail-table td{padding:10px; border:1px solid var(--border-color); max-width:300px; word-break:break-word; color:var(--text-primary)}
    .cloudtrail-table .ip-cell{background:var(--bg-tertiary); border-radius:3px; color:var(--text-primary)}
    body.dark-mode .cloudtrail-table .ip-cell{background:#404040; color:#70d5ff}
    .snapshot-meta{background:#e3f2fd; padding:12px; border-radius:8px; margin-bottom:16px; color:var(--text-primary)}
    .snapshot-meta strong{color:#0d6efd}
    body.dark-mode .snapshot-meta{background:#1e3a5f}
    ul{color:var(--text-primary)}
    li{margin:4px 0}
  </style>
  <script>
    function initDarkMode() {
      const isDark = localStorage.getItem('darkMode') === 'true';
      if (isDark) {
        document.body.classList.add('dark-mode');
        updateToggleLabel();
      }
    }
    
    function toggleDarkMode() {
      const isDark = document.body.classList.toggle('dark-mode');
      localStorage.setItem('darkMode', isDark);
      updateToggleLabel();
    }
    
    function updateToggleLabel() {
      const btn = document.getElementById('darkModeBtn');
      if (btn) {
        const isDark = document.body.classList.contains('dark-mode');
        btn.textContent = isDark ? '☀️ Light' : '🌙 Dark';
      }
    }
    
    // Initialize on page load
    document.addEventListener('DOMContentLoaded', initDarkMode);
  </script>
</head>
<body>
<header>
  <h1>AWS Drift Detection — Demo</h1>
  <div class="header-right">
    <button id="darkModeBtn" class="dark-mode-toggle" onclick="toggleDarkMode()">🌙 Dark</button>
    <div>
      {% if monitor_running %}
        <form method="post" action="{{ url_for('stop_monitor') }}"><button class="btn btn-danger">Stop Monitor</button></form>
      {% else %}
        <form method="post" action="{{ url_for('start_monitor') }}"><button class="btn btn-primary">Start Monitor</button></form>
      {% endif %}
    </div>
  </div>
</header>

{% with messages = get_flashed_messages() %}
  {% if messages %}
    <ul>
    {% for m in messages %}<li>{{ m }}</li>{% endfor %}
    </ul>
  {% endif %}
{% endwith %}

<div class="row">
  <div class="card">
    <h3>Baseline</h3>
    <p class="muted">Canonical file: <code>Baseline.json</code></p>
    <p>Status:
      {% if baseline_exists %}<span class="good">Present</span>{% else %}<span class="bad">Missing</span>{% endif %}
    </p>
    <form method="post" action="{{ url_for('upload_baseline') }}" enctype="multipart/form-data">
      <input type="file" name="file" accept=".json" required>
      <button class="btn">Upload Baseline.json</button>
    </form>
    {% if baseline_exists %}
      <a class="btn" href="{{ url_for('download_file', name='Baseline.json') }}">Download Baseline</a>
    {% endif %}
  </div>

  <div class="card">
    <h3>Snapshots</h3>
    <form method="post" action="{{ url_for('take_snapshot') }}"><button class="btn btn-primary">Take Snapshot</button></form>
    <form method="post" action="{{ url_for('compare_latest') }}"><button class="btn">Compare Latest vs Baseline</button></form>
    <p class="muted">Keeps last 10 snapshots (monitor handles rotation)</p>
    <table>
      <thead><tr><th>File</th><th>Time</th><th>Actions</th></tr></thead>
      <tbody>
      {% for s in snapshots %}
        <tr>
          <td><code>{{ s.name }}</code></td>
          <td class="muted">{{ s.mtime }}</td>
          <td>
            <a class="btn" href="{{ url_for('download_file', name=s.name) }}">Download</a>
            <a class="btn" href="{{ url_for('view_text', name=s.name) }}">View</a>
            <a class="btn" href="{{ url_for('compare_to', name=s.name) }}">Compare→Baseline</a>
          </td>
        </tr>
      {% else %}
        <tr><td colspan="3" class="muted">No snapshots yet.</td></tr>
      {% endfor %}
      </tbody>
    </table>
  </div>

  <div class="card card-wide">
    <div style="display:flex; justify-content:space-between; align-items:center;">
      <h3>Latest Log</h3>
      {% if latest_comparison and latest_comparison.get('warning') %}
        <div style="background:#fff3cd; border:1px solid #ffc107; border-radius:6px; padding:8px 12px; display:flex; align-items:center; gap:8px; color:#856404;">
          <span style="font-size:18px;">⚠️</span>
          <span style="font-size:13px;">{{ latest_comparison['warning'] }}</span>
        </div>
      {% endif %}
    </div>
    <p class="muted">Most recent comparison result</p>
    {% if latest_comparison and latest_comparison.get('snapshot_name') %}
      <div class="snapshot-meta">
        <strong>📅 Snapshot:</strong> {{ latest_comparison['snapshot_name'] }}<br>
        <strong>⏰ Date:</strong> {{ latest_comparison['snapshot_date'] }}
      </div>
      
      <div style="display:flex; gap:20px; min-height:300px;">
        <!-- Left column: Changes -->
        <div style="flex:1; min-width:400px;">
          <h4 style="color:#0d6efd; margin-top:0">Changes</h4>
          {% if latest_comparison.get('changes') %}
            {% for section in latest_comparison['changes'] %}
              <div class="change-section">
                <h5 style="margin:0 0 8px 0; color:#0d6efd; font-size:13px;">{{ section['type'] }}</h5>
                {% if section['items'] %}
                  {% for item in section['items'] %}
                    <div class="change-item {{ item['status'] }}" style="font-size:13px;">
                      {{ item['text'] }}
                    </div>
                  {% endfor %}
                {% else %}
                  <div style="color:var(--text-secondary); font-size:13px; font-style:italic;">No changes</div>
                {% endif %}
              </div>
            {% endfor %}
          {% else %}
            <p class="muted">No changes detected.</p>
          {% endif %}
        </div>
        
        <!-- Right column: CloudTrail Events -->
        <div style="flex:1; min-width:400px;">
          <h4 style="color:#7c3aed; margin-top:0">🔍 CloudTrail Events</h4>
          {% if latest_comparison.get('cloudtrail_events') %}
            <table class="cloudtrail-table" style="font-size:12px;">
              <thead>
                <tr>
                  <th style="padding:8px; font-size:12px;">Event Time</th>
                  <th style="padding:8px; font-size:12px;">Event Name</th>
                  <th style="padding:8px; font-size:12px;">User/Principal</th>
                  <th style="padding:8px; font-size:12px;">Source IP</th>
                </tr>
              </thead>
              <tbody>
                {% for event in latest_comparison['cloudtrail_events'] %}
                  <tr>
                    <td style="padding:6px; font-size:11px;">{{ event['time'] }}</td>
                    <td style="padding:6px; font-size:11px;">{{ event['name'] }}</td>
                    <td style="padding:6px; font-size:11px;">{{ event['user'] }}</td>
                    <td style="padding:6px; font-size:11px; border-radius:3px;" class="ip-cell">{{ event['ip'] }}</td>
                  </tr>
                {% endfor %}
              </tbody>
            </table>
          {% else %}
            <p class="muted">No CloudTrail events found for this comparison.</p>
          {% endif %}
        </div>
      </div>
    {% else %}
      <p class="muted">No comparisons yet.</p>
    {% endif %}
  </div>
</div>

<div class="row">
  <div class="card">
    <h3>Log</h3>
    <p class="muted">Full monitoring and comparison log</p>
    <pre style="max-height:300px; overflow:auto;">{{ drift or "No drift output yet." }}</pre>
    <a class="btn" href="{{ url_for('view_text', name='realtime_monitor.log') }}">Open full log</a>
  </div>

<footer class="muted" style="margin-top:24px">
  <small>Demo-only UI. Do not expose publicly. Uses your existing Python scripts via subprocess.</small>
</footer>
</body>
</html>
"""

def list_snapshots():
    files = []
    for p in sorted(APP_DIR.glob(SNAP_GLOB), key=lambda x: x.stat().st_mtime, reverse=True):
        ts = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        files.append(type("Snap", (), {"name": p.name, "mtime": ts}))
    return files

def get_latest_comparison():
    """Extract the most recent comparison block from the log with structured data."""
    if not LOGFILE.exists():
        return None
    try:
        with open(LOGFILE, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Find the last "[manual compare]" block
        if "[manual compare]" not in content:
            return None
        
        # Split by "[manual compare]" and take the last block
        blocks = content.split("[manual compare]")
        latest_block = blocks[-1].strip()
        
        if not latest_block:
            return None
        
        # Extract snapshot filename from the first line
        first_line = latest_block.split('\n')[0]
        snapshot_name = ""
        snapshot_date = "Unknown"
        
        if "vs" in first_line:
            parts = first_line.split("vs")
            if len(parts) > 1:
                snapshot_name = parts[1].strip()
                snap_path = APP_DIR / snapshot_name
                if snap_path.exists():
                    ts = datetime.fromtimestamp(snap_path.stat().st_mtime)
                    snapshot_date = ts.strftime("%Y-%m-%d %H:%M:%S")
        
        # Parse changes from the comparison output
        changes = []
        lines = latest_block.split('\n')
        current_section = None
        current_items = []
        section_keywords = ['IAM', 'S3', 'EC2', 'WARNING', 'changes']
        warning_text = None
        
        for line in lines:
            stripped = line.strip()
            
            # Detect section headers (contains many =)
            if '==========' in stripped:
                continue
            
            # Check for warning content
            if 'WARNING' in stripped or 'Snapshots are from different' in stripped:
                if not warning_text and 'Snapshots are from different' in stripped:
                    warning_text = stripped.replace('- ', '')
                continue
            
            # Check if this is a section name
            if stripped and not stripped.startswith('-'):
                is_section = any(kw in stripped for kw in section_keywords)
                if is_section and stripped not in ('Done.', 'Baseline.json'):
                    if current_section and current_items:
                        changes.append({"type": current_section, "items": current_items})
                    # Skip WARNING section in changes
                    if 'WARNING' not in stripped:
                        current_section = stripped
                        current_items = []
                    continue
            
            # Parse change items (lines starting with "- ")
            # BUT skip CloudTrail event lines (which have timestamps and " by " and " from ")
            if stripped.startswith('- '):
                item_text = stripped[2:].strip()
                # Skip if this looks like a CloudTrail event
                if ' by ' in item_text and ' from ' in item_text and 'T' in item_text[:20]:
                    # This is a CloudTrail event, skip it
                    continue
                # Otherwise, it's a change item
                # Determine status
                if "added" in item_text.lower():
                    status = "added"
                elif "removed" in item_text.lower():
                    status = "removed"
                else:
                    status = "modified"
                if current_section:  # Only add if we're in a valid section
                    current_items.append({"text": item_text, "status": status})
        
        if current_section and current_items:
            changes.append({"type": current_section, "items": current_items})
        
        # Extract CloudTrail events from the latest block
        cloudtrail_events = []
        try:
            # Look through all lines in the latest block for CloudTrail events
            # They appear after "Found X CloudTrail event(s)" with format: "  - 2025-11-19T00:24:50Z DescribeSecurityGroups by Test from 141.239.161.203"
            in_cloudtrail_section = False
            for line in lines:
                # Check if we're entering the CloudTrail section
                if "Found" in line and "CloudTrail event" in line:
                    in_cloudtrail_section = True
                    continue
                
                # Once in CloudTrail section, parse event lines
                if in_cloudtrail_section:
                    stripped = line.strip()
                    # CloudTrail events start with "- " and have the pattern: "- TIME EVENTNAME by USER from IP"
                    if stripped.startswith('- ') and ' by ' in stripped and ' from ' in stripped:
                        try:
                            event_line = stripped[2:].strip()  # Remove "- "
                            
                            # Format: "2025-11-19T00:24:50Z DescribeSecurityGroups by Test from 141.239.161.203"
                            # Split by " by " first
                            parts = event_line.split(' by ')
                            if len(parts) == 2:
                                time_and_event = parts[0].strip()
                                rest = parts[1]
                                
                                # Split rest by " from "
                                user_and_ip = rest.split(' from ')
                                if len(user_and_ip) == 2:
                                    user = user_and_ip[0].strip()
                                    ip = user_and_ip[1].strip()
                                    
                                    # Split time_and_event to get timestamp and event name
                                    # "2025-11-19T00:24:50Z DescribeSecurityGroups"
                                    event_parts = time_and_event.rsplit(' ', 1)
                                    if len(event_parts) == 2:
                                        event_time = event_parts[0].strip()
                                        event_name = event_parts[1].strip()
                                        
                                        cloudtrail_events.append({
                                            "time": event_time,
                                            "name": event_name,
                                            "user": user,
                                            "ip": ip
                                        })
                        except Exception as e:
                            pass
                    elif not stripped or not stripped.startswith('-'):
                        # End of CloudTrail section when we hit a blank line or non-event line
                        if stripped and not stripped.startswith('-'):
                            pass  # Continue looking
        except Exception as e:
            print(f"Error extracting CloudTrail events: {e}")
        
        # Ensure all three main sections are present (even if empty)
        section_names = {item['type']: item for item in changes}
        final_changes = []
        for section_name in ['IAM users', 'S3 changes', 'EC2 Security Group changes']:
            if section_name in section_names:
                final_changes.append(section_names[section_name])
            else:
                final_changes.append({"type": section_name, "items": []})
        
        # Return as dict-like object
        return {
            "snapshot_name": snapshot_name,
            "snapshot_date": snapshot_date,
            "changes": final_changes,
            "cloudtrail_events": cloudtrail_events,
            "warning": warning_text
        }
    except Exception as e:
        print(f"Error in get_latest_comparison: {e}")
        import traceback
        traceback.print_exc()
    return None

def run_script(args, timeout=300):
    """Run a python script and return (rc, stdout, stderr)."""
    try:
        proc = subprocess.run([PY] + args, cwd=APP_DIR, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Script execution timed out after 5 minutes"
    except Exception as e:
        return 1, "", str(e)

def parse_wrote(stdout: str):
    # enumerate prints: "Wrote <filename>"
    words = stdout.strip().split()
    if len(words) >= 2 and words[0] == "Wrote":
        return words[1]
    return None

def monitor_start():
    if MONITOR_POPEN["proc"] and MONITOR_POPEN["proc"].poll() is None:
        return
    MONITOR_POPEN["proc"] = subprocess.Popen([PY, "realtime_monitor.py"], cwd=APP_DIR)

def monitor_stop():
    p = MONITOR_POPEN["proc"]
    if not p: return
    if p.poll() is None:
        try:
            if os.name == "nt":
                p.send_signal(signal.CTRL_BREAK_EVENT)  # best-effort on Windows
            p.terminate()
        except Exception:
            pass
    MONITOR_POPEN["proc"] = None

@app.route("/", methods=["GET"])
def index():
    drift_tail = ""
    if LOGFILE.exists():
        try:
            with open(LOGFILE, "r", encoding="utf-8") as f:
                # last block is fine for demo
                drift_tail = "".join(f.readlines()[-200:])
        except Exception:
            pass
    return render_template_string(
        PAGE,
        baseline_exists=BASELINE.exists(),
        snapshots=list_snapshots(),
        drift=drift_tail,
        latest_comparison=get_latest_comparison(),
        monitor_running=(MONITOR_POPEN["proc"] and MONITOR_POPEN["proc"].poll() is None),
    )

@app.post("/snapshot")
def take_snapshot():
    rc, out, err = run_script(["enumerate_baseline.py"])
    if rc != 0:
        flash(f"enumerate_baseline.py failed: {err.strip() or rc}")
        return redirect(url_for("index"))
    fname = parse_wrote(out) or "(unknown)"
    flash(f"Snapshot created: {fname}")
    return redirect(url_for("index"))

@app.post("/compare/latest")
def compare_latest():
    snaps = list_snapshots()
    if not snaps:
        flash("No snapshots to compare.")
        return redirect(url_for("index"))
    if not BASELINE.exists():
        flash("Baseline.json not found. Upload a baseline first.")
        return redirect(url_for("index"))
    latest = snaps[0].name
    rc, out, err = run_script(["compare_baseline.py", "Baseline.json", latest])
    if out.strip():
        with open(LOGFILE, "a", encoding="utf-8") as f:
            f.write(f"\n[manual compare] Baseline.json vs {latest}\n")
            f.write(out)
            
            # Try to fetch CloudTrail events
            if find_events_for_keywords:
                try:
                    # Extract keywords from the comparison output
                    keywords = set()
                    for m in re.findall(r"sg-[0-9a-fA-F]+", out):
                        keywords.add(m)
                    for line in out.splitlines():
                        for token in line.split():
                            if 'bucket' in token.lower() or token.startswith('arn:aws:s3'):
                                kw = token.strip('[],()"')
                                keywords.add(kw)
                    for m in re.findall(r"[A-Za-z0-9_\-]+", out):
                        if len(m) > 2 and m.lower() not in ('added','removed','was','now','sg','bucket','s3','iam','ec2','aws'):
                            keywords.add(m)
                    
                    kws = [k for k in keywords if k]
                    if kws:
                        end_t = datetime.now(UTC)
                        start_t = end_t - timedelta(minutes=10)
                        events = find_events_for_keywords(kws[:20], start_t, end_t)
                        if events:
                            f.write(f"\nFound {len(events)} CloudTrail event(s) related to the drift:\n")
                            for ev in events[:10]:
                                u = ev.get('userIdentity') or {}
                                uname = (u.get('userName') or u.get('arn') or str(u))
                                ip = ev.get('sourceIPAddress')
                                en = ev.get('eventName')
                                et = ev.get('eventTime')
                                f.write(f"  - {et} {en} by {uname} from {ip}\n")
                        else:
                            f.write("\nNo matching CloudTrail events found in the recent window\n")
                except Exception as e:
                    f.write(f"\nCloudTrail lookup failed: {e}\n")
    
    flash(f"Compared Baseline.json vs {latest} (see drift panel).")
    return redirect(url_for("index"))

@app.get("/compare/<name>")
def compare_to(name):
    if not BASELINE.exists():
        flash("Baseline.json not found. Upload a baseline first.")
        return redirect(url_for("index"))
    rc, out, err = run_script(["compare_baseline.py", "Baseline.json", name])
    if out.strip():
        with open(LOGFILE, "a", encoding="utf-8") as f:
            f.write(f"\n[manual compare] Baseline.json vs {name}\n")
            f.write(out)
            
            # Try to fetch CloudTrail events
            if find_events_for_keywords:
                try:
                    # Extract keywords from the comparison output
                    keywords = set()
                    for m in re.findall(r"sg-[0-9a-fA-F]+", out):
                        keywords.add(m)
                    for line in out.splitlines():
                        for token in line.split():
                            if 'bucket' in token.lower() or token.startswith('arn:aws:s3'):
                                kw = token.strip('[],()"')
                                keywords.add(kw)
                    for m in re.findall(r"[A-Za-z0-9_\-]+", out):
                        if len(m) > 2 and m.lower() not in ('added','removed','was','now','sg','bucket','s3','iam','ec2','aws'):
                            keywords.add(m)
                    
                    kws = [k for k in keywords if k]
                    if kws:
                        end_t = datetime.now(UTC)
                        start_t = end_t - timedelta(minutes=10)
                        events = find_events_for_keywords(kws[:20], start_t, end_t)
                        if events:
                            f.write(f"\nFound {len(events)} CloudTrail event(s) related to the drift:\n")
                            for ev in events[:10]:
                                u = ev.get('userIdentity') or {}
                                uname = (u.get('userName') or u.get('arn') or str(u))
                                ip = ev.get('sourceIPAddress')
                                en = ev.get('eventName')
                                et = ev.get('eventTime')
                                f.write(f"  - {et} {en} by {uname} from {ip}\n")
                        else:
                            f.write("\nNo matching CloudTrail events found in the recent window\n")
                except Exception as e:
                    f.write(f"\nCloudTrail lookup failed: {e}\n")
    
    flash(f"Compared Baseline.json vs {name} (see drift panel).")
    return redirect(url_for("index"))

@app.post("/baseline/upload")
def upload_baseline():
    file = request.files.get("file")
    if not file:
        flash("No file provided.")
        return redirect(url_for("index"))
    file.save(BASELINE)
    flash("Baseline.json uploaded.")
    return redirect(url_for("index"))

@app.get("/files/<name>")
def download_file(name):
    return send_from_directory(APP_DIR, name, as_attachment=True)

@app.get("/view/<name>")
def view_text(name):
    p = APP_DIR / name
    if not p.exists():
        return "Not found", 404
    try:
        text = p.read_text(encoding="utf-8")
    except Exception as e:
        text = f"(unable to read) {e}"
    return f"<pre>{text.replace('<','&lt;').replace('>','&gt;')}</pre>"

@app.post("/monitor/start")
def start_monitor():
    monitor_start()
    flash("Monitor started.")
    return redirect(url_for("index"))

@app.post("/monitor/stop")
def stop_monitor():
    monitor_stop()
    flash("Monitor stopped.")
    return redirect(url_for("index"))

if __name__ == "__main__":
    os.chdir(APP_DIR)
    app.run(host="127.0.0.1", port=5000, debug=True)
