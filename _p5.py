import os, sys, time
import numpy as np, rasterio
from rasterio.warp import transform as wtr
from pystac_client import Client

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ.update({"GDAL_HTTP_MULTIPLEX": "NO", "CPL_VSIL_CURL_USE_HEAD": "NO",
                   "GDAL_HTTP_MAX_RETRY": "3", "GDAL_HTTP_TIMEOUT": "60",
                   "CPL_VSIL_CURL_CHUNK_SIZE": "65536"})

lon, lat = 112.05, 28.88

import requests
H = {"User-Agent": "Mozilla/5.0"}
stac_url = "https://earth-search.aws.element84.com/v1/search"
body = {"collections": ["sentinel-2-l2a"],
        "bbox": [lon - .02, lat - .02, lon + .02, lat + .02],
        "datetime": "2020-07-01T00:00:00Z/2020-09-15T23:59:59Z",
        "limit": 5, "query": {"eo:cloud_cover": {"lt": 20}}}
t0 = time.time()
items = requests.post(stac_url, json=body, headers=H, timeout=40).json()["features"]
items.sort(key=lambda f: f["properties"]["eo:cloud_cover"])
print("STAC %d 景 %.1fs，取 %s" % (len(items), time.time() - t0, items[0]["id"]),
      flush=True)

href = "/vsicurl/" + items[0]["assets"]["red"]["href"]
t0 = time.time()
with rasterio.open(href) as ds:
    print("  打开耗时 %.1fs  crs=%s" % (time.time() - t0, ds.crs), flush=True)
    xs, ys = wtr("EPSG:4326", ds.crs, [lon], [lat])
    r, c = ds.index(xs[0], ys[0])
    print("  row=%d col=%d  影像 %dx%d" % (r, c, ds.width, ds.height), flush=True)
    for sz in (64, 256):
        t0 = time.time()
        try:
            a = ds.read(1, window=rasterio.windows.Window(c - sz // 2, r - sz // 2, sz, sz))
            print("  %3dx%-3d 读取 %.1fs  mean=%.0f" % (sz, sz, time.time() - t0, a.mean()),
                  flush=True)
        except Exception as e:
            print("  %3dx%-3d 失败(%.1fs) %s" % (sz, sz, time.time() - t0, str(e)[:90]), flush=True)
