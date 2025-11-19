import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple

def load(p: str) -> Dict[str, Any]:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def header(t: str):
    print("\n" + "="*80)
    print(t)
    print("="*80)

def bullet(msg: str, level=1):
    print(("  " * level) + f"- {msg}")

def to_tuple_rule(r: Dict[str, Any]) -> Tuple:
    # Normalize SG rules into comparable tuples
    return (
        r.get("Protocol"),
        r.get("FromPort"),
        r.get("ToPort"),
        r.get("CidrIp"),
        r.get("CidrIpv6"),
        r.get("SourceGroupId"),
        r.get("Desc"),
    )

def compare_sets(name: str, a: List[Any], b: List[Any]):
    A, B = set(a), set(b)
    added = sorted(B - A)
    removed = sorted(A - B)
    if added or removed:
        header(f"{name} changes")
        if added:  bullet(f"Added: {added}", level=0)
        if removed: bullet(f"Removed: {removed}", level=0)

def compare_iam(a: dict, b: dict):
    a_users = {u["UserName"]: u for u in a.get("Users", [])}
    b_users = {u["UserName"]: u for u in b.get("Users", [])}

    added_users = sorted(set(b_users) - set(a_users))
    removed_users = sorted(set(a_users) - set(b_users))
    changed_attached = []
    changed_inline = []

    for uname in set(a_users) & set(b_users):
        ap = set(a_users[uname].get("AttachedPolicies", []))
        bp = set(b_users[uname].get("AttachedPolicies", []))
        if ap != bp:
            changed_attached.append((uname, sorted(list(ap)), sorted(list(bp))))

        ai = set(a_users[uname].get("InlinePolicies", []))
        bi = set(b_users[uname].get("InlinePolicies", []))
        if ai != bi:
            changed_inline.append((uname, sorted(list(ai)), sorted(list(bi))))

    if added_users or removed_users or changed_attached or changed_inline:
        header("IAM changes")
        for u in added_users:  bullet(f"User added: {u}")
        for u in removed_users: bullet(f"User removed: {u}")
        for uname, ap, bp in changed_attached:
            bullet(f"Attached policies changed for {uname}:")
            bullet(f"was: {ap}", level=2)
            bullet(f"now: {bp}", level=2)
        for uname, ai, bi in changed_inline:
            bullet(f"Inline policies changed for {uname}:")
            bullet(f"was: {ai}", level=2)
            bullet(f"now: {bi}", level=2)


def compare_s3(a: Dict[str, Any], b: Dict[str, Any]):
    a_buckets = {x["Name"]: x for x in a.get("Buckets", [])}
    b_buckets = {x["Name"]: x for x in b.get("Buckets", [])}

    added = sorted(set(b_buckets) - set(a_buckets))
    removed = sorted(set(a_buckets) - set(b_buckets))
    changed = []

    for name in set(a_buckets) & set(b_buckets):
        A = a_buckets[name]; B = b_buckets[name]

        # Helpers
        a_enc = (A.get("Encryption") or {})
        b_enc = (B.get("Encryption") or {})
        a_pab = (A.get("PublicAccessBlock") or {})
        b_pab = (B.get("PublicAccessBlock") or {})
        a_ver = (A.get("Versioning") or {})
        b_ver = (B.get("Versioning") or {})

        diffs = []

        if a_enc != b_enc:
            diffs.append(("Encryption", a_enc, b_enc))

        if a_pab != b_pab:
            diffs.append(("PublicAccessBlock", a_pab, b_pab))

        # Versioning normalizing (Status may be missing)
        a_status = a_ver.get("Status", None)
        b_status = b_ver.get("Status", None)
        if a_status != b_status:
            diffs.append(("Versioning.Status", a_status, b_status))

        # Bucket policy can be large; compare structurally
        a_pol = A.get("Policy")
        b_pol = B.get("Policy")
        if a_pol != b_pol:
            diffs.append(("BucketPolicy", a_pol, b_pol))

        if diffs:
            changed.append((name, diffs))

    if added or removed or changed:
        header("S3 changes")
        for n in added:  bullet(f"Bucket added: {n}")
        for n in removed: bullet(f"Bucket removed: {n}")
        for name, diffs in changed:
            bullet(f"Bucket modified: {name}")
            for (field, old, new) in diffs:
                bullet(f"{field} changed", level=2)
                bullet(f"was: {old}", level=3)
                bullet(f"now: {new}", level=3)

def compare_ec2_sg(a: Dict[str, Any], b: Dict[str, Any]):
    a_sgs = {x["GroupId"]: x for x in a.get("SecurityGroups", [])}
    b_sgs = {x["GroupId"]: x for x in b.get("SecurityGroups", [])}

    added = sorted(set(b_sgs) - set(a_sgs))
    removed = sorted(set(a_sgs) - set(b_sgs))
    changed = []

    for gid in set(a_sgs) & set(b_sgs):
        A = a_sgs[gid]; B = b_sgs[gid]
        diffs = []

        # Compare inbound
        A_in = set(map(to_tuple_rule, A.get("InboundRules", [])))
        B_in = set(map(to_tuple_rule, B.get("InboundRules", [])))
        if A_in != B_in:
            diffs.append(("InboundRules", sorted(list(A_in)), sorted(list(B_in))))

        # Compare outbound
        A_out = set(map(to_tuple_rule, A.get("OutboundRules", [])))
        B_out = set(map(to_tuple_rule, B.get("OutboundRules", [])))
        if A_out != B_out:
            diffs.append(("OutboundRules", sorted(list(A_out)), sorted(list(B_out))))

        # Name/Desc/VPC changes (rare)
        for key in ("GroupName","Description","VpcId"):
            if A.get(key) != B.get(key):
                diffs.append((key, A.get(key), B.get(key)))

        if diffs:
            changed.append((gid, diffs))

    if added or removed or changed:
        header("EC2 Security Group changes")
        for gid in added:
            sg = b_sgs[gid]
            name = sg.get("GroupName", "N/A")
            desc = sg.get("Description", "N/A")
            bullet(f"SG added: {name} ({gid}) - {desc}")
        for gid in removed:
            sg = a_sgs[gid]
            name = sg.get("GroupName", "N/A")
            desc = sg.get("Description", "N/A")
            bullet(f"SG removed: {name} ({gid}) - {desc}")
        for gid, diffs in changed:
            sg = a_sgs[gid]
            name = sg.get("GroupName", "N/A")
            desc = sg.get("Description", "N/A")
            bullet(f"SG modified: {name} ({gid}) - {desc}")
            for (field, old, new) in diffs:
                bullet(f"{field} changed", level=2)
                bullet(f"was: {old}", level=3)
                bullet(f"now: {new}", level=3)

def main():
    if len(sys.argv) != 3:
        print("Usage: python compare_baseline.py <old_snapshot.json> <new_snapshot.json>")
        sys.exit(1)
    old_path, new_path = sys.argv[1], sys.argv[2]
    if not Path(old_path).exists() or not Path(new_path).exists():
        print("Snapshot file not found.")
        sys.exit(1)

    old = load(old_path)
    new = load(new_path)

    # High-level identity check
    if old.get("identity", {}).get("account_id") != new.get("identity", {}).get("account_id"):
        header("WARNING")
        bullet("Snapshots are from different AWS accounts!")

    compare_iam(old.get("iam", {}), new.get("iam", {}))
    compare_s3(old.get("s3", {}), new.get("s3", {}))
    compare_ec2_sg(old.get("ec2", {}), new.get("ec2", {}))

    print("\nDone.")

if __name__ == "__main__":
    main()
