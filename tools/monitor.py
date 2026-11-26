"""Readiness checks with failure exit status; --count 0 runs until interrupted."""

import argparse
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://127.0.0.1:8088/health/ready/")
parser.add_argument("--count", type=int, default=3)
parser.add_argument("--interval", type=float, default=5)
args = parser.parse_args()
failed, count = False, 0
while args.count == 0 or count < args.count:
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(args.url, timeout=5) as response:
            result = json.load(response)
            ok = response.status == 200 and result.get("status") == "ready"
    except (OSError, ValueError, urllib.error.HTTPError):
        ok = False
    print(
        json.dumps(
            {
                "time": datetime.now(timezone.utc).isoformat(),
                "ready": ok,
                "ms": round((time.perf_counter() - started) * 1000, 2),
            }
        ),
        flush=True,
    )
    failed = failed or not ok
    count += 1
    if count != args.count:
        time.sleep(args.interval)
raise SystemExit(1 if failed else 0)
