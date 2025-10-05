import boto3
import json
from botocore.exceptions import ClientError
from typing import List, Dict


def find_events_for_keywords(keywords: List[str], start_time, end_time, event_names: List[str] = None, max_results: int = 200) -> List[Dict]:
    """Lookup CloudTrail events in the given time window and return events that contain any of the keywords.

    - keywords: list of strings to search for in the CloudTrailEvent JSON payload
    - start_time, end_time: datetime objects (UTC)
    - event_names: optional list of event names to restrict LookupEvents
    """
    ct = boto3.client('cloudtrail')
    matches = []
    lookup_attrs = []
    # If event names are provided, lookup by EventName to reduce results
    if event_names:
        # Note: LookupEvents accepts only a single AttributeKey/EventName per call; we'll call repeatedly
        attrs_list = [{'AttributeKey': 'EventName', 'AttributeValue': en} for en in event_names]
    else:
        attrs_list = [None]

    try:
        for attr in attrs_list:
            kwargs = {'StartTime': start_time, 'EndTime': end_time, 'MaxResults': 50}
            if attr:
                kwargs['LookupAttributes'] = [attr]

            resp = ct.lookup_events(**kwargs)
            events = resp.get('Events', [])
            # handle pagination
            while True:
                for ev in events:
                    try:
                        ev_json = json.loads(ev.get('CloudTrailEvent', '{}'))
                    except Exception:
                        ev_json = {}
                    s = json.dumps(ev_json)
                    for kw in keywords:
                        if kw and kw in s:
                            # enrich with top-level metadata
                            matches.append({
                                'eventTime': ev_json.get('eventTime'),
                                'eventName': ev_json.get('eventName'),
                                'userIdentity': ev_json.get('userIdentity'),
                                'sourceIPAddress': ev_json.get('sourceIPAddress'),
                                'userAgent': ev_json.get('userAgent'),
                                'raw': ev_json,
                            })
                            break

                # pagination
                token = resp.get('NextToken')
                if token:
                    resp = ct.lookup_events(NextToken=token)
                    events = resp.get('Events', [])
                else:
                    break

    except ClientError as e:
        raise

    # Deduplicate by eventTime+eventName+sourceIPAddress
    seen = set()
    out = []
    for m in matches:
        key = (m.get('eventTime'), m.get('eventName'), m.get('sourceIPAddress'))
        if key in seen:
            continue
        seen.add(key)
        out.append(m)

    return out
