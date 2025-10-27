#!/usr/bin/env python3
import os, sys, json, glob, subprocess, threading, signal
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, send_from_directory, flash

# --- CONFIG ---
APP_DIR = Path(__file__).parent.resolve()         # this folder (baseline/)
LOGFILE = APP_DIR / "realtime_monitor.log"
BASELINE = APP_DIR / "Baseline.json"
SNAP_GLOB = "snapshot_*.json"                     # your new naming
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
    body{font-family:system-ui,Arial,sans-serif; max-width:1000px; margin:40px auto; line-height:1.4}
    header{display:flex; gap:12px; align-items:center; justify-content:space-between}
    code,pre{background:#f6f8fa; padding:8px; border-radius:8px; display:block; overflow:auto}
    .row{display:flex; gap:16px; flex-wrap:wrap}
    .card{flex:1 1 320px; border:1px solid #eee; border-radius:12px; padding:16px}
    .good{color:#0a7a2f} .bad{color:#b00020}
    .btn{display:inline-block; padding:8px 12px; border-radius:8px; border:1px solid #ddd; background:#fff; cursor:pointer}
    .btn-primary{background:#0d6efd; color:#fff; border-color:#0d6efd}
    .btn-danger{background:#b00020; color:#fff; border-color:#b00020}
    form{display:inline}
    table{width:100%; border-collapse:collapse}
    th, td{border-bottom:1px solid #eee; padding:6px 8px; text-align:left}
    .muted{color:#666}
  </style>
</head>
<body>
<header>
  <h1>AWS Drift Detection — Demo</h1>
  <div>
    {% if monitor_running %}
      <form method="post" action="{{ url_for('stop_monitor') }}"><button class="btn btn-danger">Stop Monitor</button></form>
    {% else %}
      <form method="post" action="{{ url_for('start_monitor') }}"><button class="btn btn-primary">Start Monitor</button></form>
    {% endif %}
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

  <div class="card">
    <h3>Latest Drift Output</h3>
    <pre>{{ drift or "No drift output yet." }}</pre>
    <a class="btn" href="{{ url_for('view_text', name='realtime_monitor.log') }}">Open full log</a>
  </div>
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

def run_script(args, timeout=120):
    """Run a python script and return (rc, stdout, stderr)."""
    proc = subprocess.run([PY] + args, cwd=APP_DIR, capture_output=True, text=True, timeout=timeout)
    return proc.returncode, proc.stdout, proc.stderr

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
