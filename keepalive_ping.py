from __future__ import annotations

import os
import sys
import requests


def main() -> int:
    url = (os.getenv("KEEPALIVE_URL") or "").strip()
    if not url:
        print("KEEPALIVE_URL is not set")
        return 2
    try:
        r = requests.get(url, timeout=20)
        print(f"GET {url} -> {r.status_code}")
        return 0 if r.status_code < 500 else 1
    except Exception as e:
        print(f"Ping failed: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
