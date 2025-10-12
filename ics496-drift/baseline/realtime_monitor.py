#!/usr/bin/env python3
"""
Realtime Monitor (with snapshot naming)
---------------------------------------
- Periodically runs `enumerate_baseline.py` to create new AWS snapshots.
- Compares each new snapshot against Baseline.json (if present) or the previous one.
- Logs any drift output from compare_baseline.py into `realtime_monitor.log` with timestamps.

File naming:
  snapshot_YYYY-MM-DDTHH-MM-SSZ.json

Works on both Windows and macOS/Linux.
Make sure:
  - boto3 is installed
  - AWS credentials are configured
  - enumerate_baseline.py and compare_baseline.py are in the same folder
"""

import subprocess
import time
import os
import sys
from datetime import datetime, UTC
from pathlib import Path

# Constants
SNAP_GLOB = "snapshot_*.json"
SLEEP_SECONDS = 20
LOGFILE = "realtime_monitor.log"

# Always run from the same directory as this script
os.chdir(Path(__file__).parent)

# Use the exact Python interpreter running this script
PY = sys.executable


def now_ts():
    """Return UTC timestamp (ISO format)."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")


def run_enumerate():
    """Run enumerate_baseline.py and return (filename, rc, stdout, stderr)."""
    proc = subprocess.run([PY, "enumerate_baseline.py"], capture_output=True, text=True)
    out = proc.stdout.strip()
    fname = None

    # enumerate_baseline.py prints: "Wrote <filename>"
    if out:
        parts = out.split()
        if len(parts) >= 2 and parts[0] == "Wrote":
            fname = parts[1]

    # Fallback: get newest snapshot_*.json
    if not fname:
        files = sorted(
            [f for f in os.listdir('.') if f.startswith('snapshot_') and f.endswith('.json')],
            key=os.path.getmtime
        )
        if files:
            fname = files[-1]

    return fname, proc.returncode, proc.stdout, proc.stderr


def run_compare(old, new):
    """Run compare_baseline.py and return (rc, stdout, stderr)."""
    proc = subprocess.run([PY, "compare_baseline.py", old, new], capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def log(msg):
    """Append a log line with timestamp."""
    ts = now_ts()
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")
    print(f"[{ts}] {msg}")


def main():
    log(f"Starting realtime monitor (every {SLEEP_SECONDS}s)")

    prev = None
    # Use newest snapshot as previous
    files = sorted(
        [f for f in os.listdir('.') if f.startswith('snapshot_') and f.endswith('.json')],
        key=os.path.getmtime
    )
    if files:
        prev = files[-1]
        log(f"Using existing snapshot as previous: {prev}")

    # Prefer Baseline.json as canonical baseline
    baseline_file = 'Baseline.json'
    if os.path.exists(baseline_file):
        log(f"Found canonical baseline: {baseline_file}")

    try:
        while True:
            fname, rc, sout, serr = run_enumerate()
            if rc != 0:
                log(f"enumerate_baseline.py failed (rc={rc}). stderr: {serr.strip()}")
                time.sleep(SLEEP_SECONDS)
                continue

            if not fname:
                log("Could not determine new snapshot filename; skipping compare")
                time.sleep(SLEEP_SECONDS)
                continue

            log(f"Captured snapshot: {fname}")

            # Choose compare target
            compare_target = baseline_file if os.path.exists(baseline_file) else prev
            if compare_target:
                rc2, sout2, serr2 = run_compare(compare_target, fname)
                if rc2 != 0:
                    log(f"compare_baseline.py returned rc={rc2}. stderr: {serr2.strip()}")

                # Log drift output
                if sout2 and sout2.strip():
                    log(f"Drift detected between {compare_target} and {fname}:")
                    log("--- compare stdout begin ---")
                    for line in sout2.splitlines():
                        log("  " + line)
                    log("--- compare stdout end ---")
                    if serr2 and serr2.strip():
                        log("--- compare stderr begin ---")
                        for line in serr2.splitlines():
                            log("  " + line)
                        log("--- compare stderr end ---")
                else:
                    log(f"No drift detected between {compare_target} and {fname}")

            # Keep only last 10 snapshots
            prev = fname
            snapshots = sorted(
                [f for f in os.listdir('.') if f.startswith('snapshot_') and f.endswith('.json')],
                key=os.path.getmtime
            )
            while len(snapshots) > 10:
                rm = snapshots.pop(0)
                try:
                    os.remove(rm)
                    log(f"Removed old snapshot: {rm}")
                except Exception as e:
                    log(f"Failed to remove {rm}: {e}")

            time.sleep(SLEEP_SECONDS)

    except KeyboardInterrupt:
        log("Realtime monitor stopped by user")


if __name__ == "__main__":
    main()
