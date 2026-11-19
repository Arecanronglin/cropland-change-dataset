import os, sys, time
import numpy as np
import rasterio
from rasterio.warp import transform as warp_transform
from pystac_client import Client

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
for k, v in {
    "GDAL_HTTP_MULTIPLEX": "YES", "GDAL_HTTP_VERSION": "2",
    "GDAL_HTTP_MAX_RETRY": "2", "CPL_VSIL_CURL_USE_HEAD": "NO",
    "CPL_VSIL_CURL_CHUNK_SIZE": "262144", "GDAL_HTTP_TIMEOUT": "30",
}.items():
    os.environ.setdefault(k, v)

stac = Client.open("https://earth-search.aws.element84.com/v1")


def best_item(bbox, dt):
    res = stac.search(collections=["sentinel-2-l2a"], bbox=bbox, datetime=dt,
                      query={"eo:cloud_cover": {"lt": 20}})
    its = sorted(res.items(), key=lambda i: i.properties["eo:cloud_cover"])
    return its[0] if its else None


def read_win(item, band, lon, lat, size=256):
    href = "/vsicurl/" + item.assets[band].href
    with rasterio.open(href) as ds:
        xs, ys = warp_transform("EPSG:4326", ds.crs, [lon], [lat])
        r, c = ds.index(xs[0], ys[0])
        win = rasterio.windows.Window(c - size // 2, r - size // 2, size, size)
        win = win.intersection(rasterio.windows.Window(0, 0, ds.width, ds.height))
        return ds.read(1, window=win)


lon, lat = 112.05, 28.88
bbox = [lon - 0.02, lat - 0.02, lon + 0.02, lat + 0.02]

t_all = time.time()
t1 = best_item(bbox, "2020-07-01T00:00:00Z/2020-09-15T23:59:59Z")
t2 = best_item(bbox, "2024-07-01T00:00:00Z/2024-09-15T23:59:59Z")
print("T1", t1.id, "%.1f" % t1.properties["eo:cloud_cover"])
print("T2", t2.id, "%.1f" % t2.properties["eo:cloud_cover"])

for tag, it in (("t1", t1), ("t2", t2)):
    for b in ("green", "red", "nir", "scl"):
        t0 = time.time()
        a = read_win(it, b, lon, lat)
        print("  %s %-5s %-12s %5.1fs mean=%.0f" % (tag, b, str(a.shape),
                                                    time.time() - t0, a.mean() if a.size else -1))
print("合计 %.1fs" % (time.time() - t_all))
