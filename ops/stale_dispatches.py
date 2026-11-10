#!/usr/bin/env python3
"""Count dispatch receipts sent more than N hours ago with no watch result."""
import glob
import json
import os
import sys
import time

limit_h = float(sys.argv[1]) if len(sys.argv) > 1 else 2
now = time.time()
count = 0
for path in glob.glob(os.path.expanduser("~/.openmausbot/dispatch-receipts/*.json")):
    try:
        if now - os.path.getmtime(path) <= limit_h * 3600:
            continue
        doc = json.load(open(path, encoding="utf-8"))
        if doc.get("watched_at"):
            continue
        # a closed dispatch is not stale even if it was never watched
        draft = os.path.join(os.path.dirname(os.path.dirname(path)), "dispatch-drafts", os.path.basename(path))
        try:
            if json.load(open(draft, encoding="utf-8")).get("status") == "done":
                continue
        except Exception:
            pass
        count += 1
    except Exception:
        continue
print(count)
