#!/usr/bin/env python3
import json
import boto3
import datetime
from datetime import UTC
from botocore.exceptions import ClientError

def ts() -> str:
    # UTC, ISO-like, matches your monitor format: 2025-10-10T23-18-38Z
    return datetime.datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")

def get_account():
    sts = boto3.client("sts")
    ident = sts.get_caller_identity()
    return {
        "account_id": ident["Account"],
        "arn": ident["Arn"],
        "user_id": ident["UserId"],
    }

def get_iam():
    iam = boto3.client("iam")
    users = []
    paginator = iam.get_paginator("list_users")
    for page in paginator.paginate():
        for u in page["Users"]:
            uname = u["UserName"]
            user = {
                "UserName": uname,
                "CreateDate": u["CreateDate"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                "Arn": u["Arn"],
                "Groups": [],
                "AttachedPolicies": [],
                "InlinePolicies": [],
            }
            # groups
            for g in iam.list_groups_for_user(UserName=uname)["Groups"]:
                user["Groups"].append(g["GroupName"])
            # attached policies
            for p in iam.list_attached_user_policies(UserName=uname)["AttachedPolicies"]:
                user["AttachedPolicies"].append(p["PolicyArn"])
            # inline policies (names only)
            for pn in iam.list_user_policies(UserName=uname)["PolicyNames"]:
                user["InlinePolicies"].append(pn)
            users.append(user)
    return {"Users": users}

def safe_call(fn, default=None):
    try:
        return fn()
    except ClientError:
        return default

def get_s3():
    s3 = boto3.client("s3")
    out = {"Buckets": []}
    buckets = s3.list_buckets().get("Buckets", [])
    for b in buckets:
        name = b["Name"]
        binfo = {"Name": name}
        # location (None means us-east-1)
        loc = safe_call(lambda: s3.get_bucket_location(Bucket=name))
        binfo["Location"] = (loc or {}).get("LocationConstraint")
        # encryption
        enc = safe_call(lambda: s3.get_bucket_encryption(Bucket=name))
        if enc and "ServerSideEncryptionConfiguration" in enc:
            binfo["Encryption"] = enc["ServerSideEncryptionConfiguration"]
        else:
            binfo["Encryption"] = None
        # policy
        pol = safe_call(lambda: s3.get_bucket_policy(Bucket=name))
        if pol and "Policy" in pol:
            binfo["Policy"] = json.loads(pol["Policy"])
        else:
            binfo["Policy"] = None
        # public access block
        pab = safe_call(lambda: s3.get_public_access_block(Bucket=name))
        binfo["PublicAccessBlock"] = (pab or {}).get("PublicAccessBlockConfiguration")
        # versioning
        ver = safe_call(lambda: s3.get_bucket_versioning(Bucket=name))
        binfo["Versioning"] = ver or {}
        out["Buckets"].append(binfo)
    return out

def get_ec2_security_groups():
    ec2 = boto3.client("ec2")
    resp = ec2.describe_security_groups()
    sgs = []

    def fmt_perms(perms):
        rules = []
        for p in perms:
            proto = p.get("IpProtocol")
            fromp = p.get("FromPort")
            top = p.get("ToPort")
            # IPv4 ranges
            for r in p.get("IpRanges", []):
                rules.append({
                    "Protocol": proto,
                    "FromPort": fromp,
                    "ToPort": top,
                    "CidrIp": r.get("CidrIp"),
                    "Desc": r.get("Description"),
                })
            # IPv6 ranges
            for r in p.get("Ipv6Ranges", []):
                rules.append({
                    "Protocol": proto,
                    "FromPort": fromp,
                    "ToPort": top,
                    "CidrIpv6": r.get("CidrIpv6"),
                    "Desc": r.get("Description"),
                })
            # referenced SGs
            for r in p.get("UserIdGroupPairs", []):
                rules.append({
                    "Protocol": proto,
                    "FromPort": fromp,
                    "ToPort": top,
                    "SourceGroupId": r.get("GroupId"),
                    "Desc": r.get("Description"),
                })
        return rules

    for sg in resp.get("SecurityGroups", []):
        sgs.append({
            "GroupId": sg.get("GroupId"),
            "GroupName": sg.get("GroupName"),
            "Description": sg.get("Description"),
            "VpcId": sg.get("VpcId"),
            "InboundRules": fmt_perms(sg.get("IpPermissions", [])),
            "OutboundRules": fmt_perms(sg.get("IpPermissionsEgress", [])),
            "Tags": {t["Key"]: t["Value"] for t in sg.get("Tags", [])} if sg.get("Tags") else {},
        })
    return {"SecurityGroups": sgs}

def main():
    snapshot = {
        "meta": {
            "captured_at_utc": ts(),
            "service_versions": {
                "boto3": boto3.__version__,
            }
        },
        "identity": get_account(),
        "iam": get_iam(),
        "s3": get_s3(),
        "ec2": get_ec2_security_groups(),
    }
    fname = f"snapshot_{ts()}.json"  # <-- new prefix
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, sort_keys=True)
    print(f"Wrote {fname}")

if __name__ == "__main__":
    main()
