import time

from playwright.sync_api import sync_playwright

t0 = time.monotonic()
pw = sync_playwright().start()
b = pw.chromium.connect_over_cdp("ws://127.0.0.1:9222", timeout=8000)
c = b.new_context()
p = c.new_page()
try:
    p.goto("https://www.xiaohongshu.com/explore", wait_until="commit", timeout=8000)
except Exception as exc:  # noqa: BLE001
    print("commit_timeout", round((time.monotonic() - t0) * 1000), type(exc).__name__)
for _ in range(40):
    try:
        title = p.title()
    except Exception:  # noqa: BLE001
        title = ""
    if title and not title.lower().startswith("loading"):
        break
    time.sleep(0.3)
print("title", title, "url", p.url)
try:
    links = p.eval_on_selector_all("a", "els => els.map(e => e.href)")
except Exception as exc:  # noqa: BLE001
    links = []
    print("links_err", type(exc).__name__)
hits = [link for link in links if "/explore/" in link and "xsec_token" in link]
print("total_links", len(links), "token_links", len(hits))
for link in hits[:5]:
    print(link)
c.close()
pw.stop()
