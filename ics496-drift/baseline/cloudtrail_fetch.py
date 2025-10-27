import boto3
import json
from botocore.exceptions import ClientError
from typing import List, Dict

def find_events_for_keywords(
    keywords: List[str],
    start_time,
    end_time,
    event_names: List[str] = None,
    max_results: int = 200,
    region_name: str = None,
) -> List[Dict]:
    """
    Lookup CloudTrail events in the given time window and return events that contain any of the keywords.
    - keywords: list of strings to search for (case-insensitive) within the CloudTrailEvent JSON
    - start_time, end_time: timezone-aware datetimes (UTC)
    - event_names: optional list of event names to restrict LookupEvents (e.g., ["PutUserPolicy"])
    - max_results: soft cap on returned matches
    - region_name: optional AWS region override (e.g., "us-east-2")
    """
    ct = boto3.client("cloudtrail", region_name=region_name)
    matches: List[Dict] = []

    # Normalize keywords (case-insensitive match)
    kwords = [k for k in (keywords or []) if k]
    kwords_lower = [k.lower() for k in kwords]

    # Build attribute batches; CloudTrail accepts only one LookupAttribute per call
    attr_batches = (
        [{"AttributeKey": "EventName", "AttributeValue": en} for en in (event_names or [])]
        or [None]
    )

    try:
        for attr in attr_batches:
            # Use paginator so we don't manually juggle NextToken
            paginator = ct.get_paginator("lookup_events")
            page_iter = paginator.paginate(
                StartTime=start_time,
                EndTime=end_time,
                **({"LookupAttributes": [attr]} if attr else {}),
                PaginationConfig={"PageSize": 50},
            )

            for page in page_iter:
                for ev in page.get("Events", []):
                    raw = ev.get("CloudTrailEvent", "{}")
                    try:
                        ev_json = json.loads(raw)
                    except Exception:
                        ev_json = {}

                    # Case-insensitive contains
                    blob = raw.lower()
                    if any(kw in blob for kw in kwords_lower):
                        matches.append({
                            "eventTime": ev_json.get("eventTime") or ev.get("EventTime"),
                            "eventName": ev_json.get("eventName") or ev.get("EventName"),
                            "userIdentity": ev_json.get("userIdentity"),
                            "sourceIPAddress": ev_json.get("sourceIPAddress"),
                            "userAgent": ev_json.get("userAgent"),
                            "resources": ev_json.get("resources") or ev.get("Resources"),
                            "raw": ev_json or raw,  # keep parsed if possible
                        })
                        if len(matches) >= max_results:
                            return _dedupe_matches(matches)

    except ClientError as e:
        # Re-raise so caller can log/handle
        raise

    return _dedupe_matches(matches)


def _dedupe_matches(matches: List[Dict]) -> List[Dict]:
    """Deduplicate by (eventTime, eventName, sourceIPAddress)."""
    seen = set()
    out = []
    for m in matches:
        key = (m.get("eventTime"), m.get("eventName"), m.get("sourceIPAddress"))
        if key in seen:
            continue
        seen.add(key)
        out.append(m)
    return out
