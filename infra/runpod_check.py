"""Read-only RunPod connectivity/auth check (no pods provisioned, no cost).
Run: python -m extraction.runpod_check
"""
import json
import urllib.error
import urllib.request

PATH = r"C:\Users\hampe\Desktop\Secret keys\Runpod-machiavel key.txt"

try:
    key = open(PATH, encoding="utf-8").read().strip().splitlines()[0].strip()
    print("key found: len", len(key), "prefix", key[:5])
except Exception as e:  # noqa: BLE001
    print("KEY READ ERROR:", e)
    raise SystemExit

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
body = json.dumps({"query": "query { myself { id clientBalance } }"}).encode()
for label, url, hdr in [
    ("query-param", "https://api.runpod.io/graphql?api_key=" + key,
     {"Content-Type": "application/json", "User-Agent": UA}),
    ("bearer-header", "https://api.runpod.io/graphql",
     {"Content-Type": "application/json", "User-Agent": UA, "Authorization": "Bearer " + key}),
]:
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, data=body, headers=hdr), timeout=25)
        print(label, "-> HTTP", r.status, r.read()[:400].decode())
    except urllib.error.HTTPError as e:
        print(label, "-> HTTPError", e.code, e.read()[:200].decode())
    except Exception as e:  # noqa: BLE001
        print(label, "-> CONNECT ERROR:", type(e).__name__, e)
