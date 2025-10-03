#!/usr/bin/env python3
"""
TENTATIVE TO CHANGE - angello 9-21-25
IMPORTANT NOTES OF THIS APPLICAITON.

This script expects to be run from the baseline directory and will call
`enumerate_baseline.py` to produce snapshot files. It will then call
`compare_baseline.py` to compare the previous snapshot with the new one. Any
non-empty output is logged to `realtime_monitor.log` along with a timestamp.

- Make sure `boto3` is installed and AWS credentials are configured.
"""

import subprocess
import time
import os
import sys
import shutil
import json
import select
from datetime import datetime

SNAP_GLOB = "baseline_*.json"
SLEEP_SECONDS = 20
LOGFILE = "realtime_monitor.log"


def now_ts():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def run_enumerate():
    # Run enumerate_baseline.py and return the filename written (or None)
    proc = subprocess.run(["python3", "enumerate_baseline.py"], capture_output=True, text=True)
    out = proc.stdout.strip()
    # enumerate prints: Wrote <filename>
    fname = None
    if out:
        parts = out.split()
        if len(parts) >= 2 and parts[0] == "Wrote":
            fname = parts[1]
    # Fallback: pick newest baseline_*.json
    if not fname:
        files = sorted([f for f in os.listdir('.') if f.startswith('baseline_') and f.endswith('.json')], key=os.path.getmtime)
        if files:
            fname = files[-1]
    return fname, proc.returncode, proc.stdout, proc.stderr


def run_compare(old, new):
    proc = subprocess.run(["python3", "compare_baseline.py", old, new], capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr

""" LOG FILE this is where we can print out the monitoring system  """
def log(msg):
    ts = now_ts()
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")
    print(f"[{ts}] {msg}")


def main():
    log("Starting realtime monitor (every %ds)" % SLEEP_SECONDS)

    prev = None
    # If there is an existing snapshot, use the newest as prev
    files = sorted([f for f in os.listdir('.') if f.startswith('baseline_') and f.endswith('.json')], key=os.path.getmtime)
    if files:
        prev = files[-1]
        log(f"Using existing snapshot as previous: {prev}")

    # If there's a Baseline.json in the directory, prefer that as the canonical baseline
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

            # Choose compare target: prefer Baseline.json when available, otherwise use prev
            compare_target = baseline_file if os.path.exists(baseline_file) else prev
            if compare_target:
                rc2, sout2, serr2 = run_compare(compare_target, fname)
                if rc2 != 0:
                    # compare may return non-zero for usage errors; still capture output
                    log(f"compare_baseline.py returned rc={rc2}. stderr: {serr2.strip()}")

                # If compare printed anything other than trivial messages, log it
                if sout2 and sout2.strip():
                    log(f"Drift detected between {prev} and {fname}:")
                    # Log stdout from compare with a header and line-by-line
                    log("--- compare stdout begin ---")
                    for line in sout2.splitlines():
                        log("  " + line)
                    log("--- compare stdout end ---")
                    # Also log stderr if any
                    if serr2 and serr2.strip():
                        log("--- compare stderr begin ---")
                        for line in serr2.splitlines():
                            log("  " + line)
                        log("--- compare stderr end ---")
                else:
                    log(f"No drift detected between {prev} and {fname}")

            # Do not update the canonical baseline; keep prev as the latest snapshot
            prev = fname

            # Retain all snapshots: do not delete old snapshots automatically.
            # Previously the script trimmed snapshots to the last 10 files.
            # That behavior was removed so all baseline_*.json files are kept.
            snapshots = sorted([f for f in os.listdir('.') if f.startswith('baseline_') and f.endswith('.json')], key=os.path.getmtime)
            log(f"Snapshot count: {len(snapshots)} (retained)")

            # Offer interactive update of the canonical Baseline.json to the new snapshot
            try:
                # Interactive: give the user up to SLEEP_SECONDS to respond; do not sleep additionally
                if sys.stdin.isatty():
                    # Prompt and wait up to SLEEP_SECONDS for input
                    print(f"Update '{baseline_file}' to '{fname}'? [y/N]: ", end='', flush=True)
                    rlist, _, _ = select.select([sys.stdin], [], [], SLEEP_SECONDS)
                    if rlist:
                        resp = sys.stdin.readline().strip().lower()
                        if resp in ("y", "yes"):
                                try:
                                    # Load the new snapshot and the existing baseline (if any)
                                    with open(fname, 'r', encoding='utf-8') as fnew:
                                        new_snap = json.load(fnew)

                                    baseline_exists = os.path.exists(baseline_file)
                                    if baseline_exists:
                                        with open(baseline_file, 'r', encoding='utf-8') as fb:
                                            try:
                                                baseline = json.load(fb)
                                            except Exception:
                                                baseline = {}
                                    else:
                                        baseline = {}

                                    # Present available top-level categories and prompt the user
                                    avail = sorted(list(new_snap.keys()))
                                    print()
                                    print("Available categories in the new snapshot:")
                                    for k in avail:
                                        print(f"  - {k}")
                                    print("Enter a comma-separated list of categories to copy into the baseline, or 'all' to replace the entire baseline.")
                                    print(f"Waiting up to {SLEEP_SECONDS}s for category selection: ", end='', flush=True)
                                    rlist2, _, _ = select.select([sys.stdin], [], [], SLEEP_SECONDS)
                                    if not rlist2:
                                        log(f"No category selection within {SLEEP_SECONDS}s; baseline unchanged")
                                    else:
                                        cats = sys.stdin.readline().strip()
                                        if not cats:
                                            log("Empty category selection; baseline unchanged")
                                        else:
                                            if cats.strip().lower() == 'all':
                                                # Replace entire baseline with new snapshot
                                                with open(baseline_file, 'w', encoding='utf-8') as fbw:
                                                    json.dump(new_snap, fbw, indent=2, sort_keys=True)
                                                log(f"Replaced entire baseline with snapshot: {fname}")
                                            else:
                                                selected = [c.strip() for c in cats.split(',') if c.strip()]
                                                updated = []
                                                for c in selected:
                                                    if c in new_snap:
                                                        baseline[c] = new_snap[c]
                                                        updated.append(c)
                                                    else:
                                                        log(f"Category not found in snapshot: {c}")
                                                if updated:
                                                    with open(baseline_file, 'w', encoding='utf-8') as fbw:
                                                        json.dump(baseline, fbw, indent=2, sort_keys=True)
                                                    log(f"Updated baseline categories: {', '.join(updated)} from {fname}")
                                                else:
                                                    log("No valid categories selected; baseline unchanged")
                                except Exception as e:
                                    log(f"Failed to update baseline: {e}")
                        else:
                            log("Baseline unchanged by user choice")
                    else:
                        log(f"No response within {SLEEP_SECONDS}s; baseline unchanged")
                    # do not call time.sleep() here — the select timeout acts as the interval
                else:
                    log("Non-interactive session: baseline update prompt skipped")
                    # Non-interactive runs should sleep normally between snapshots
                    time.sleep(SLEEP_SECONDS)
            except Exception as e:
                # Protect the monitor loop from unexpected input errors
                log(f"Error during baseline update prompt: {e}")
                # On error, wait a bit before next snapshot to avoid tight loop
                time.sleep(SLEEP_SECONDS)
    except KeyboardInterrupt:
        log("Realtime monitor stopped by user")


if __name__ == "__main__":
    main()
