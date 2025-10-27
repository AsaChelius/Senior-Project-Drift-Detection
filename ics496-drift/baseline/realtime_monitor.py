#!/usr/bin/env python3
"""
Realtime Drift Monitor
- Runs `enumerate_baseline.py` to create snapshots.
- Compares each snapshot to Baseline.json (if present) or the previous snapshot.
- Logs any drift and (optionally) queries CloudTrail for related events.
- Automatically keeps ONLY the last 10 snapshots.

TENTATIVE TO CHANGE - angello 10-26-25
"""
from typing import Optional

import subprocess
import time
import os
import sys
import json
import select
import re
from datetime import datetime, timedelta, timezone
UTC = timezone.utc

try:
    from cloudtrail_fetch import find_events_for_keywords
except Exception:
    find_events_for_keywords = None

# ----------------- CONFIG -----------------
SNAP_PREFIX = "snapshot_"             # new naming
SNAP_GLOB = f"{SNAP_PREFIX}*.json"
FALLBACK_GLOB = "baseline_*.json"     # for transition only
SLEEP_SECONDS = 20
LOGFILE = "realtime_monitor.log"
BASELINE_FILE = "Baseline.json"

# Use the SAME interpreter that launched this script
PY = sys.executable
# ------------------------------------------


def now_ts() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")


def log(msg: str):
    ts = now_ts()
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")
    print(f"[{ts}] {msg}")



def newest_snapshot_name() -> Optional[str]:
    """Return newest snapshot file (prefers snapshot_*.json, falls back to baseline_*.json)."""
    files = sorted(
        [f for f in os.listdir('.') if f.startswith(SNAP_PREFIX) and f.endswith('.json')],
        key=os.path.getmtime
    )
    if files:
        return files[-1]
    # fallback (transition period)
    files = sorted(
        [f for f in os.listdir('.') if f.startswith('baseline_') and f.endswith('.json')],
        key=os.path.getmtime
    )
    return files[-1] if files else None


def run_enumerate():
    """Run enumerate_baseline.py and return (filename, rc, stdout, stderr)."""
    proc = subprocess.run([PY, "enumerate_baseline.py"], capture_output=True, text=True)
    out = proc.stdout.strip()
    fname = None

    # enumerate prints: "Wrote <filename>"
    if out:
        parts = out.split()
        if len(parts) >= 2 and parts[0] == "Wrote":
            fname = parts[1]

    # Fallback: pick newest snapshot_* (then baseline_* for transition)
    if not fname:
        fname = newest_snapshot_name()

    return fname, proc.returncode, proc.stdout, proc.stderr


def run_compare(old_path: str, new_path: str):
    proc = subprocess.run([PY, "compare_baseline.py", old_path, new_path], capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def trim_snapshots_keep_last_10():
    """Delete older snapshots, keeping only the 10 most recent (prefers snapshot_*; also trims legacy baseline_*)."""
    # Primary set
    snaps = sorted(
        [f for f in os.listdir('.') if f.startswith(SNAP_PREFIX) and f.endswith('.json')],
        key=os.path.getmtime
    )
    # Legacy set (only if still present)
    legacy = sorted(
        [f for f in os.listdir('.') if f.startswith('baseline_') and f.endswith('.json')],
        key=os.path.getmtime
    )

    # Trim primary snapshots to last 10
    if len(snaps) > 10:
        old = snaps[:-10]
        for rm in old:
            try:
                os.remove(rm)
                log(f"Removed old snapshot: {rm}")
            except Exception as e:
                log(f"Failed to remove {rm}: {e}")

    # Optionally trim legacy files so they don't pile up (keep last 2)
    if len(legacy) > 2:
        old_leg = legacy[:-2]
        for rm in old_leg:
            try:
                os.remove(rm)
                log(f"Removed old legacy snapshot: {rm}")
            except Exception as e:
                log(f"Failed to remove legacy {rm}: {e}")

    # Count after trimming
    count = len([f for f in os.listdir('.') if (f.startswith(SNAP_PREFIX) or f.startswith('baseline_')) and f.endswith('.json')])
    log(f"Snapshot count (after trim): {count}")


def main():
    log(f"Starting realtime monitor (every {SLEEP_SECONDS}s)")

    prev = newest_snapshot_name()
    if prev:
        log(f"Using existing snapshot as previous: {prev}")

    if os.path.exists(BASELINE_FILE):
        log(f"Found canonical baseline: {BASELINE_FILE}")

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

            # Prefer Baseline.json when available, otherwise previous snapshot
            compare_target = BASELINE_FILE if os.path.exists(BASELINE_FILE) else prev
            if not compare_target:
                log("No baseline or previous snapshot yet; skipping compare.")
                prev = fname
                trim_snapshots_keep_last_10()
                time.sleep(SLEEP_SECONDS)
                continue

            rc2, sout2, serr2 = run_compare(compare_target, fname)
            if rc2 != 0:
                log(f"compare_baseline.py returned rc={rc2}. stderr: {serr2.strip()}")

            if sout2 and sout2.strip():
                log(f"Drift detected between {compare_target} and {fname}:")
                log("--- compare stdout begin ---")

                # Collect candidate keywords for CloudTrail search
                compare_text = sout2
                keywords = set()
                # security group ids
                for m in re.findall(r"sg-[0-9a-fA-F]+", compare_text):
                    keywords.add(m)
                # bucket names / s3 policy hints
                for line in compare_text.splitlines():
                    for token in line.split():
                        if 'bucket' in token.lower() or token.startswith('arn:aws:s3'):
                            kw = token.strip('[],()"')
                            keywords.add(kw)
                # rough usernames / tokens
                for m in re.findall(r"[A-Za-z0-9_\-]+", compare_text):
                    if len(m) > 2 and m.lower() not in ('added','removed','was','now','sg','bucket','s3','iam','ec2','aws'):
                        keywords.add(m)

                for line in sout2.splitlines():
                    log("  " + line)
                log("--- compare stdout end ---")

                if serr2 and serr2.strip():
                    log("--- compare stderr begin ---")
                    for line in serr2.splitlines():
                        log("  " + line)
                    log("--- compare stderr end ---")

                # CloudTrail enrichment (optional)
                if find_events_for_keywords:
                    try:
                        end_t = datetime.now(UTC)
                        start_t = end_t - timedelta(minutes=10)
                        kws = [k for k in keywords if k]
                        if kws:
                            preview = ", ".join(sorted(kws)[:10])
                            log(f"Searching CloudTrail for keywords: {preview}...")
                            events = find_events_for_keywords(kws, start_t, end_t)
                            if events:
                                log(f"Found {len(events)} CloudTrail event(s) related to the drift:")
                                for ev in events[:10]:
                                    u = ev.get('userIdentity') or {}
                                    uname = (u.get('userName') or u.get('arn') or str(u))
                                    ip = ev.get('sourceIPAddress')
                                    en = ev.get('eventName')
                                    et = ev.get('eventTime')
                                    log(f"  - {et} {en} by {uname} from {ip}")
                            else:
                                log("No matching CloudTrail events found in the recent window")
                    except Exception as e:
                        log(f"CloudTrail lookup failed: {e}")
            else:
                log(f"No drift detected between {compare_target} and {fname}")

            # Update previous snapshot pointer
            prev = fname

            # Keep only the last 10 snapshots
            trim_snapshots_keep_last_10()

            # -------- Optional interactive baseline update (unchanged) --------
            try:
                if sys.stdin.isatty():
                    print(f"Update '{BASELINE_FILE}' to '{fname}'? [y/N]: ", end='', flush=True)
                    rlist, _, _ = select.select([sys.stdin], [], [], SLEEP_SECONDS)
                    if rlist:
                        resp = sys.stdin.readline().strip().lower()
                        if resp in ("y", "yes"):
                            try:
                                with open(fname, 'r', encoding='utf-8') as fnew:
                                    new_snap = json.load(fnew)

                                baseline = {}
                                if os.path.exists(BASELINE_FILE):
                                    with open(BASELINE_FILE, 'r', encoding='utf-8') as fb:
                                        try:
                                            baseline = json.load(fb)
                                        except Exception:
                                            baseline = {}

                                avail = sorted(list(new_snap.keys()))
                                print("\nAvailable categories in the new snapshot:")
                                for k in avail:
                                    print(f"  - {k}")
                                print("Enter comma-separated categories to copy, or 'all' to replace the baseline.")
                                print(f"Waiting up to {SLEEP_SECONDS}s for selection: ", end='', flush=True)
                                rlist2, _, _ = select.select([sys.stdin], [], [], SLEEP_SECONDS)
                                if not rlist2:
                                    log(f"No category selection within {SLEEP_SECONDS}s; baseline unchanged")
                                else:
                                    cats = sys.stdin.readline().strip()
                                    if not cats:
                                        log("Empty category selection; baseline unchanged")
                                    else:
                                        if cats.strip().lower() == 'all':
                                            with open(BASELINE_FILE, 'w', encoding='utf-8') as fbw:
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
                                                with open(BASELINE_FILE, 'w', encoding='utf-8') as fbw:
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
                else:
                    # Non-interactive: normal sleep between cycles
                    time.sleep(SLEEP_SECONDS)
            except Exception as e:
                log(f"Error during baseline update prompt: {e}")
                time.sleep(SLEEP_SECONDS)

    except KeyboardInterrupt:
        log("Realtime monitor stopped by user")


if __name__ == "__main__":
    main()
