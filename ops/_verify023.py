import argparse
import json
import time
import urllib.parse
import urllib.request


def probe(base, url, runs):
    out = []
    for i in range(1, runs + 1):
        started = time.monotonic()
        target = base.rstrip("/") + "/render/probe?url=" + urllib.parse.quote(url, safe="")
        try:
            with urllib.request.urlopen(target, timeout=25) as response:
                code = response.status
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            code = exc.code
            try:
                body = json.loads(exc.read().decode("utf-8"))
            except Exception:  # noqa: BLE001
                body = {}
        elapsed = round(time.monotonic() - started, 3)
        out.append({"run": i, "http": code, "client_s": elapsed, "body": body})
        print(json.dumps({"run": i, "http": code, "client_s": elapsed,
                           "title": body.get("title"),
                           "xsec": body.get("has_xsec_token"),
                           "elapsed_ms": body.get("elapsed_ms"),
                           "alive": body.get("obscura_alive")}, ensure_ascii=False))
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:18081")
    parser.add_argument("--url", required=True)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    results = probe(args.base, args.url, args.runs)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump({"url": args.url, "runs": results}, handle, ensure_ascii=False, indent=2)
