import os
import time

from playwright.sync_api import sync_playwright

URL = os.getenv(
    "PROBE_URL",
    "https://www.xiaohongshu.com/explore/6af04386000000001500d626"
    "?xsec_token=<REPLACE_ME>&xsec_source=app_share",
)
t0 = time.monotonic()


def ts():
    return round((time.monotonic() - t0) * 1000)


pw = sync_playwright().start()
print("driver", ts(), flush=True)
b = pw.chromium.connect_over_cdp("ws://127.0.0.1:9222", timeout=8000)
print("connected", ts(), flush=True)
c = b.new_context()
p = c.new_page()
print("page", ts(), flush=True)
try:
    p.goto(URL, wait_until="commit", timeout=8000)
    print("commit", ts(), flush=True)
except Exception as exc:  # noqa: BLE001
    print("commit_timeout", ts(), type(exc).__name__, flush=True)
for i in range(80):
    try:
        t = p.title()
    except Exception as exc:  # noqa: BLE001
        t = "ERR:" + type(exc).__name__
    print("title", ts(), repr(t[:60]), "url", p.url[:100], flush=True)
    if t and not t.lower().startswith("loading"):
        try:
            html = p.content()
            print("content", ts(), len(html), "xsec", "xsec_token" in html, flush=True)
        except Exception as exc:  # noqa: BLE001
            print("content_err", ts(), type(exc).__name__, flush=True)
        break
    time.sleep(0.2)
c.close()
pw.stop()
print("done", ts(), flush=True)
