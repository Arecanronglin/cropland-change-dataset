"""CLCD 标签下载（分省 zip，Zenodo 免注册）"""
import os, sys, time
import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DEST = r"D:\cropchg\data\clcd"
os.makedirs(DEST, exist_ok=True)
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
BASE = "https://zenodo.org/records/18180184/files/"

FILES = ["CLCD_v01_2020_albert_province.zip", "CLCD_v01_2024_albert_province.zip"]

for fn in FILES:
    dst = os.path.join(DEST, fn)
    if os.path.exists(dst) and os.path.getsize(dst) > 700e6:
        print("[skip] %s 已存在 %.0f MB" % (fn, os.path.getsize(dst) / 1e6), flush=True)
        continue
    url = BASE + fn + "?download=1"
    for attempt in range(6):
        have = os.path.getsize(dst) if os.path.exists(dst) else 0
        h = dict(H)
        if have:
            h["Range"] = "bytes=%d-" % have
        try:
            t0 = time.time()
            with requests.get(url, headers=h, stream=True, timeout=60) as r:
                if r.status_code not in (200, 206):
                    print("[%s] HTTP %s" % (fn, r.status_code), flush=True)
                    time.sleep(5); continue
                mode = "ab" if have else "wb"
                got = have
                with open(dst, mode) as f:
                    for chunk in r.iter_content(1024 * 256):
                        if chunk:
                            f.write(chunk); got += len(chunk)
                dt = time.time() - t0
                print("[done] %s %.0f MB  %.2f MB/s" % (
                    fn, got / 1e6, (got - have) / dt / 1e6), flush=True)
                break
        except Exception as e:
            print("[retry %d] %s %s" % (attempt + 1, fn, type(e).__name__), flush=True)
            time.sleep(4)
    else:
        print("[FAIL] %s" % fn, flush=True)

print("ALLDONE", flush=True)
