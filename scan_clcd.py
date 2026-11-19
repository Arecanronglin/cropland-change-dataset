import os, sys, time
import numpy as np, rasterio
from rasterio.warp import transform as wtr

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"D:\cropchg")
import fetch_s2 as F

CLCD = r"D:\cropchg\data\clcd"
PROV = {"HN": "hunan", "JX": "jiangxi"}


def block_ratio(diff, bs=10, need=0.25):
    """把变化掩膜切成 bs×bs 小块，只有块内变化≥need 才算「成片变化」"""
    h, w = diff.shape
    h2, w2 = h // bs * bs, w // bs * bs
    d = diff[:h2, :w2].astype(np.float32).reshape(h2 // bs, bs, w2 // bs, bs)
    return float((d.mean((1, 3)) >= need).mean())


def main():
    for rid in (sys.argv[1:] or ["HN", "JX"]):
        p = PROV[rid]
        ds20 = rasterio.open(os.path.join(CLCD, "2020_%s.tif" % p))
        ds24 = rasterio.open(os.path.join(CLCD, "2024_%s.tif" % p))
        centers = []
        for aoi in F.REGIONS[rid]["aois"]:
            centers += F.grid(aoi, F.PX)
        t0 = time.time()
        raw, blk = [], []
        for lon, lat in centers:
            try:
                v = []
                for ds in (ds20, ds24):
                    xs, ys = wtr("EPSG:4326", ds.crs, [lon], [lat])
                    r, c = ds.index(xs[0], ys[0])
                    w = rasterio.windows.Window(c - 45, r - 45, 90, 90).intersection(
                        rasterio.windows.Window(0, 0, ds.width, ds.height))
                    if w.width < 80 or w.height < 80:
                        raise ValueError
                    v.append(ds.read(1, window=w) == 1)
                d = v[0] ^ v[1]
                raw.append(float(d.mean()))
                blk.append(block_ratio(d))
            except Exception:
                continue
        raw, blk = np.array(raw), np.array(blk)
        print("[%s] %d 块 (%.1fs)" % (rid, len(raw), time.time() - t0), flush=True)
        print("  原始像素变化率: min %.4f 中位 %.4f max %.4f" % (
            raw.min(), np.median(raw), raw.max()), flush=True)
        print("  成片块占比:     min %.4f 中位 %.4f max %.4f" % (
            blk.min(), np.median(blk), blk.max()), flush=True)
        for thr in (0.0, 0.002, 0.005, 0.01, 0.02, 0.05):
            print("    成片 < %.3f : %3d 块   ≥ %.3f : %3d 块" % (
                thr, int((blk < thr).sum()), thr, int((blk >= thr).sum())), flush=True)


if __name__ == "__main__":
    main()
