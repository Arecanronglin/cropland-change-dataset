import os, sys, time
import numpy as np, rasterio
from rasterio.warp import transform as wtr
from pystac_client import Client

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ.pop("HTTPS_PROXY", None); os.environ.pop("HTTP_PROXY", None)
os.environ.update({
    "GDAL_HTTP_MULTIPLEX": "NO",
    "GDAL_HTTP_VERSION": "1",
    "CPL_VSIL_CURL_USE_HEAD": "NO",
    "GDAL_HTTP_MAX_RETRY": "10",
    "GDAL_HTTP_RETRY_DELAY": "2",
    "CPL_VSIL_CURL_CHUNK_SIZE": "65536",
    "GDAL_HTTP_TIMEOUT": "90",
    "VSI_CACHE": "FALSE",
})

stac = Client.open("https://earth-search.aws.element84.com/v1")
lon, lat = 112.05, 28.88
bb = [lon - .02, lat - .02, lon + .02, lat + .02]


def pick(dt):
    r = stac.search(collections=["sentinel-2-l2a"], bbox=bb, datetime=dt,
                    query={"eo:cloud_cover": {"lt": 20}})
    return sorted(r.items(), key=lambda i: i.properties["eo:cloud_cover"])[0]


def rd(it, b, tries=4):
    last = None
    for k in range(tries):
        try:
            with rasterio.open("/vsicurl/" + it.assets[b].href) as ds:
                xs, ys = wtr("EPSG:4326", ds.crs, [lon], [lat])
                r, c = ds.index(xs[0], ys[0])
                return ds.read(1, window=rasterio.windows.Window(c - 128, r - 128, 256, 256))
        except Exception as e:
            last = e
            time.sleep(3)
    raise last


t1 = pick("2020-07-01T00:00:00Z/2020-09-15T23:59:59Z")
t2 = pick("2024-07-01T00:00:00Z/2024-09-15T23:59:59Z")
print("T1", t1.id, "T2", t2.id)
tot = time.time()
ok = 0
for tag, it in (("t1", t1), ("t2", t2)):
    for b in ("green", "red", "nir", "scl"):
        s = time.time()
        try:
            a = rd(it, b)
            ok += 1
            print("  %s %-5s %s %5.1fs mean=%.0f" % (tag, b, a.shape, time.time() - s, a.mean()))
        except Exception as e:
            print("  %s %-5s 失败 %s" % (tag, b, str(e)[:80]))
print("成功 %d/8，合计 %.1fs" % (ok, time.time() - tot))
