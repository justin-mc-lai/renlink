import os
import time

from playwright.sync_api import sync_playwright

URL = os.environ["PROBE_URL"]
t0 = time.monotonic()


def ts():
    return round((time.monotonic() - t0) * 1000)


BLOCK = set(os.getenv("BLOCK", "image,media,font,stylesheet").split(","))

pw = sync_playwright().start()
b = pw.chromium.connect_over_cdp("ws://127.0.0.1:9222", timeout=8000)
c = b.new_context()
p = c.new_page()


def route_handler(route):
    if route.request.resource_type in BLOCK:
        route.abort()
    else:
        route.continue_()


p.route("**/*", route_handler)
try:
    p.goto(URL, wait_until="commit", timeout=8000)
    print("commit", ts())
except Exception as exc:  # noqa: BLE001
    print("commit_timeout", ts(), type(exc).__name__)
for _ in range(60):
    try:
        title = p.title()
    except Exception:  # noqa: BLE001
        title = ""
    if title and not title.lower().startswith("loading"):
        html = p.content()
        print("ready", ts(), repr(title[:50]), "xsec", "xsec_token" in html, len(html))
        break
    time.sleep(0.15)
else:
    print("not_ready", ts(), repr(title))
c.close()
pw.stop()
