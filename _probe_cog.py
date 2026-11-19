import os, sys, time
import numpy as np
import rasterio
from rasterio.windows import Window
from pystac_client import Client

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("GDAL_HTTP_MULTIPLEX", "YES")
os.environ.setdefault("GDAL_HTTP_VERSION", "2")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "3")
os.environ.setdefault("CPL_VSIL_CURL_USE_HEAD", "NO")

stac = Client.open("https://earth-search.aws.element84.com/v1")
res = stac.search(
    collections=["sentinel-2-l2a"],
    bbox=[112.00, 28.85, 112.35, 29.08],
    datetime="2020-07-01T00:00:00Z/2020-09-15T23:59:59Z",
    query={"eo:cloud_cover": {"lt": 15}},
)
items = sorted(res.items(), key=lambda i: i.properties["eo:cloud_cover"])
best = items[0]
print("用景:", best.id, "cloud=%.1f" % best.properties["eo:cloud_cover"])

lon, lat = 112.05, 28.88
total = 0.0
for band in ("red", "green", "blue", "nir", "scl"):
    href = "/vsicurl/" + best.assets[band].href
    t0 = time.time()
    try:
        with rasterio.open(href) as ds:
            row, col = ds.index(lon, lat)
            win = Window(col - 128, row - 128, 256, 256)
            arr = ds.read(1, window=win)
        dt = time.time() - t0
        total += dt
        print("  %-6s %-12s %5.2fs  mean=%8.1f  min=%d max=%d" % (
            band, str(arr.shape), dt, arr.mean(), arr.min(), arr.max()))
    except Exception as e:
        print("  %-6s 失败 %s: %s" % (band, type(e).__name__, str(e)[:120]))

print("5 个波段合计 %.1fs" % total)
