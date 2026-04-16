#!/usr/bin/env python3
"""
Fetch solubility data for a single compound from Wolfram Alpha.

Usage:
  WOLFRAM_APPID=your_appid python scripts/wa_solubility.py "sodium chloride"

Outputs JSON to stdout.
"""

import json
import os
import sys
from urllib.parse import urlencode
from urllib.request import urlopen


def die(msg: str, code: int = 1):
    print(json.dumps({"error": msg}), file=sys.stderr)
    sys.exit(code)


def fetch_solubility(compound: str, appid: str) -> dict:
    query = f"solubility of {compound}"
    params = {
        "input": query,
        "appid": appid,
        "output": "json",
        "format": "plaintext",
    }
    url = f"https://api.wolframalpha.com/v2/query?{urlencode(params)}"

    with urlopen(url) as resp:
        raw = resp.read().decode("utf-8")

    data = json.loads(raw)
    if not data.get("queryresult", {}).get("success"):
        return {
            "compound": compound,
            "query": query,
            "success": False,
            "pods": [],
            "raw_queryresult": data.get("queryresult", {}),
        }

    pods = data.get("queryresult", {}).get("pods", [])

    # Extract pods likely relevant to solubility
    solubility_pods = []
    for pod in pods:
        title = pod.get("title", "")
        if "solubility" in title.lower():
            subpods = pod.get("subpods", [])
            plaintexts = [sp.get("plaintext", "") for sp in subpods if sp.get("plaintext")]
            solubility_pods.append({
                "title": title,
                "plaintext": plaintexts,
            })

    return {
        "compound": compound,
        "query": query,
        "success": True,
        "solubility_pods": solubility_pods,
        "pods": pods,  # full pod list for debugging/extended parsing
    }


def main():
    if len(sys.argv) < 2:
        die("Usage: WOLFRAM_APPID=... python scripts/wa_solubility.py \"compound\"")

    appid = os.environ.get("WOLFRAM_APPID")
    if not appid:
        die("Missing environment variable: WOLFRAM_APPID")

    compound = " ".join(sys.argv[1:]).strip()
    if not compound:
        die("Compound name is empty")

    result = fetch_solubility(compound, appid)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
