"""
批量拉取 前后两时相 Sentinel-2 影像（免登录，STAC + COG 窗口读）
用法: python fetch_s2.py <区域ID> [目标块数]
输出: D:\\cropchg\\out\\<区>\\<区>_###.tif   8波段 float32, nodata=-1
"""
import os, sys, time, json
import numpy as np
import rasterio
from rasterio.warp import transform as wtr
from rasterio.windows import Window
import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ.update({"GDAL_HTTP_MULTIPLEX": "NO", "CPL_VSIL_CURL_USE_HEAD": "NO",
                   "GDAL_HTTP_MAX_RETRY": "5", "GDAL_HTTP_TIMEOUT": "90",
                   "GDAL_HTTP_RETRY_DELAY": "2",
                   "CPL_VSIL_CURL_CHUNK_SIZE": "262144"})

STAC = "https://earth-search.aws.element84.com/v1/search"
UA = {"User-Agent": "Mozilla/5.0"}
OUT = r"D:\cropchg\out"
PX, SCALE = 256, 10
BANDS = ["blue", "green", "red", "nir"]
CLOUD_BAD = {1, 3, 8, 9, 10, 11}
MIN_VALID = 0.70

REGIONS = {
    "HN": dict(name="湖南", w1="2020-07-01T00:00:00Z/2020-09-15T23:59:59Z",
               w2="2024-07-01T00:00:00Z/2024-09-15T23:59:59Z",
               aois=[[111.85, 28.80, 112.20, 29.08], [112.85, 27.75, 113.20, 28.03]]),
    "JX": dict(name="江西", w1="2020-07-01T00:00:00Z/2020-09-15T23:59:59Z",
               w2="2024-07-01T00:00:00Z/2024-09-15T23:59:59Z",
               aois=[[114.85, 26.98, 115.20, 27.26], [115.95, 28.30, 116.30, 28.58]]),
    "JP": dict(name="日本九州", w1="2020-07-01T00:00:00Z/2020-09-15T23:59:59Z",
               w2="2024-07-01T00:00:00Z/2024-09-15T23:59:59Z",
               aois=[[130.38, 33.20, 130.73, 33.48], [130.62, 32.72, 130.97, 33.00]]),
    "KR": dict(name="韩国全罗南道", w1="2020-07-01T00:00:00Z/2020-09-15T23:59:59Z",
               w2="2024-07-01T00:00:00Z/2024-09-15T23:59:59Z",
               aois=[[126.60, 34.88, 126.95, 35.16], [126.48, 34.52, 126.83, 34.80]]),
    "VN": dict(name="越南红河", w1="2020-06-15T00:00:00Z/2020-08-31T23:59:59Z",
               w2="2024-06-15T00:00:00Z/2024-08-31T23:59:59Z",
               aois=[[106.30, 20.25, 106.65, 20.53], [106.20, 20.82, 106.55, 21.10]]),
    "MM": dict(name="缅甸伊洛瓦底", w1="2020-08-01T00:00:00Z/2020-10-15T23:59:59Z",
               w2="2024-08-01T00:00:00Z/2024-10-15T23:59:59Z",
               aois=[[94.68, 16.68, 95.03, 16.96], [95.30, 16.90, 95.65, 17.18]]),
}


def search_items(bbox, dt, tries=4):
    body = {"collections": ["sentinel-2-l2a"], "bbox": bbox, "datetime": dt,
            "limit": 80, "query": {"eo:cloud_cover": {"lt": 25}}}
    for k in range(tries):
        try:
            fs = requests.post(STAC, json=body, headers=UA, timeout=45).json()["features"]
            fs = [f for f in fs if all(b in f["assets"] for b in BANDS + ["scl"])]
            fs.sort(key=lambda f: f["properties"]["eo:cloud_cover"])
            return fs
        except Exception:
            time.sleep(3)
    return []


def grid(rect, step_px):
    x1, y1, x2, y2 = rect
    side = step_px * SCALE
    dlat = side / 111320
    dlon = side / (111320 * np.cos(np.radians((y1 + y2) / 2)))
    nx, ny = int((x2 - x1) / dlon), int((y2 - y1) / dlat)
    return [(x1 + i * dlon + dlon / 2, y1 + j * dlat + dlat / 2)
            for i in range(nx) for j in range(ny)]


def in_bbox(it, lon, lat):
    b = it["bbox"]
    return b[0] <= lon <= b[2] and b[1] <= lat <= b[3]


class Scene:
    def __init__(self, item):
        self.item = item
        self.id = item["id"]
        self.ds = {}

    def _open(self, b):
        if b not in self.ds:
            self.ds[b] = rasterio.open("/vsicurl/" + self.item["assets"][b]["href"])
        return self.ds[b]

    def read(self, lon, lat):
        arrs, transform, crs = [], None, None
        for b in BANDS:
            d = self._open(b)
            xs, ys = wtr("EPSG:4326", d.crs, [lon], [lat])
            r, c = d.index(xs[0], ys[0])
            w = Window(c - PX // 2, r - PX // 2, PX, PX).intersection(
                Window(0, 0, d.width, d.height))
            if w.width != PX or w.height != PX:
                return None, None, None
            arrs.append(d.read(1, window=w).astype(np.float32) / 10000.0)
            if transform is None:
                transform, crs = d.window_transform(w), d.crs
        d = self._open("scl")
        xs, ys = wtr("EPSG:4326", d.crs, [lon], [lat])
        r, c = d.index(xs[0], ys[0])
        w = Window(c - PX // 2, r - PX // 2, PX, PX).intersection(
            Window(0, 0, d.width, d.height))
        if w.width != PX or w.height != PX:
            return None, None, None
        out = np.stack(arrs)
        out[:, np.isin(d.read(1, window=w), list(CLOUD_BAD))] = -1.0
        return out, transform, crs


def main():
    rid = sys.argv[1]
    target = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    reg = REGIONS[rid]
    outdir = os.path.join(OUT, rid)
    os.makedirs(outdir, exist_ok=True)
    t0 = time.time()

    # 收集全部候选块
    centers = []
    for aoi in reg["aois"]:
        centers += grid(aoi, PX)
    print("%s %s 候选块 %d，目标 %d" % (rid, reg["name"], len(centers), target), flush=True)

    bbox = reg["aois"][0]
    allbox = [min(a[0] for a in reg["aois"]), min(a[1] for a in reg["aois"]),
              max(a[2] for a in reg["aois"]), max(a[3] for a in reg["aois"])]
    c1 = search_items(allbox, reg["w1"])
    c2 = search_items(allbox, reg["w2"])
    print("候选景 T1 %d / T2 %d (%.0fs)" % (len(c1), len(c2), time.time() - t0), flush=True)
    if not c1 or not c2:
        sys.exit("无候选景")

    scenes = {}
    ok, tried = 0, 0
    for lon, lat in centers:
        if ok >= target:
            break
        tried += 1
        cands = [it for it in c1 if in_bbox(it, lon, lat)]
        cands2 = [it for it in c2 if in_bbox(it, lon, lat)]
        if not cands or not cands2:
            continue
        got = None
        for a in cands[:3]:
            for b in cands2[:3]:
                try:
                    sa = scenes.setdefault(a["id"], Scene(a))
                    sb = scenes.setdefault(b["id"], Scene(b))
                    x1, tr, crs = sa.read(lon, lat)
                    if x1 is None:
                        continue
                    x2, _, _ = sb.read(lon, lat)
                    if x2 is None:
                        continue
                    got = (x1, x2, tr, crs)
                    break
                except Exception as e:
                    print("   #%d %s" % (tried, str(e)[:60]), flush=True)
                    continue
            if got:
                break
        if not got:
            continue
        x1, x2, tr, crs = got
        stack = np.concatenate([x1, x2], 0)
        valid = float((stack[0] > 0).mean())
        if valid < MIN_VALID:
            print("   #%d 有效 %.0f%% 丢弃" % (tried, valid * 100), flush=True)
            continue
        ok += 1
        prof = dict(driver="GTiff", height=PX, width=PX, count=8, dtype="float32",
                    nodata=-1.0, compress="deflate", tiled=True,
                    blockxsize=128, blockysize=128, crs=crs, transform=tr)
        fn = os.path.join(outdir, "%s_%03d.tif" % (rid, ok))
        with rasterio.open(fn, "w", **prof) as o:
            o.write(stack)
            for i, nm in enumerate(["t1_blue", "t1_green", "t1_red", "t1_nir",
                                    "t2_blue", "t2_green", "t2_red", "t2_nir"]):
                o.set_band_description(i + 1, nm)
        if ok % 5 == 0 or ok == 1:
            print("  [%s] %d/%d 有效%.0f%% 已用 %.0fs" % (
                rid, ok, target, valid * 100, time.time() - t0), flush=True)

    print("[%s] DONE %d 个，共试 %d 块，耗时 %.0fs" % (
        rid, ok, tried, time.time() - t0), flush=True)


if __name__ == "__main__":
    main()
