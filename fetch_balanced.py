"""
反向采样：先用 CLCD 算出哪些块零变化，再只下这些块 → 补负样本
用法: python fetch_balanced.py HN 40 60     # 区 要负样本数 要正样本数
"""
import os, sys, time
import numpy as np
import rasterio
from rasterio.warp import transform as wtr
import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"D:\cropchg")
import fetch_s2 as F

CLCD = r"D:\cropchg\data\clcd"
PROV = {"HN": "hunan", "JX": "jiangxi"}


def clcd_paths(rid):
    p = PROV[rid]
    return {y: os.path.join(CLCD, "%d_%s.tif" % (y, p)) for y in (2020, 2024)}


def ratio_at(ds20, ds24, lon, lat):
    """在 lon/lat 处取 90x90（≈2.7km@30m）窗口，算「成片变化」占比
    杂点在 8x8 小块里占比不到 25%，直接压掉"""
    vals = []
    for ds in (ds20, ds24):
        xs, ys = wtr("EPSG:4326", ds.crs, [lon], [lat])
        r, c = ds.index(xs[0], ys[0])
        w = rasterio.windows.Window(c - 45, r - 45, 90, 90).intersection(
            rasterio.windows.Window(0, 0, ds.width, ds.height))
        if w.width < 80 or w.height < 80:
            return None
        vals.append(ds.read(1, window=w) == 1)
    d = (vals[0] ^ vals[1]).astype(np.float32)
    h, w2 = d.shape
    nb = min(h, w2) // 8 * 8
    blk = d[:nb, :nb].reshape(nb // 8, 8, nb // 8, 8).mean((1, 3))
    return float((blk >= 0.25).mean())


def main():
    rid = sys.argv[1]
    need_neg = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    need_pos = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    reg = F.REGIONS[rid]
    outdir = os.path.join(F.OUT, rid)
    os.makedirs(outdir, exist_ok=True)

    cp = clcd_paths(rid)
    d20 = rasterio.open(cp[2020]); d24 = rasterio.open(cp[2024])

    centers = []
    for aoi in reg["aois"]:
        centers += F.grid(aoi, F.PX)
    print("[%s] 候选 %d 块，先算 CLCD 变化率" % (rid, len(centers)), flush=True)

    t0 = time.time()
    scored = []
    for lon, lat in centers:
        try:
            r = ratio_at(d20, d24, lon, lat)
        except Exception:
            r = None
        if r is not None:
            scored.append((lon, lat, r))
    negs = [s for s in scored if s[2] < 0.002]
    poss = sorted([s for s in scored if s[2] >= 0.02], key=lambda s: -s[2])
    print("  有效 %d 块 ｜ 零变化 %d ｜ 高变化 %d  (%.0fs)" % (
        len(scored), len(negs), len(poss), time.time() - t0), flush=True)

    # 已有的块中心，避免重复下同一位置
    picked = negs[:need_neg] + poss[:need_pos]
    print("  选中 负%d + 正%d = %d 块" % (
        len(negs[:need_neg]), len(poss[:need_pos]), len(picked)), flush=True)
    if not picked:
        sys.exit("没选出块")

    allbox = [min(a[0] for a in reg["aois"]), min(a[1] for a in reg["aois"]),
              max(a[2] for a in reg["aois"]), max(a[3] for a in reg["aois"])]
    c1 = F.search_items(allbox, reg["w1"])
    c2 = F.search_items(allbox, reg["w2"])
    print("  候选景 T1 %d / T2 %d" % (len(c1), len(c2)), flush=True)

    scenes, ok = {}, 0
    existing = len([f for f in os.listdir(outdir) if f.endswith(".tif")])
    for lon, lat, r in picked:
        cands = [it for it in c1 if F.in_bbox(it, lon, lat)]
        cands2 = [it for it in c2 if F.in_bbox(it, lon, lat)]
        got = None
        for a in cands[:3]:
            for b in cands2[:3]:
                try:
                    sa = scenes.setdefault(a["id"], F.Scene(a))
                    sb = scenes.setdefault(b["id"], F.Scene(b))
                    x1, tr, crs = sa.read(lon, lat)
                    if x1 is None:
                        continue
                    x2, _, _ = sb.read(lon, lat)
                    if x2 is None:
                        continue
                    got = (x1, x2, tr, crs); break
                except Exception:
                    continue
            if got:
                break
        if not got:
            continue
        x1, x2, tr, crs = got
        stack = np.concatenate([x1, x2], 0)
        if float((stack[0] > 0).mean()) < F.MIN_VALID:
            continue
        ok += 1
        prof = dict(driver="GTiff", height=F.PX, width=F.PX, count=8, dtype="float32",
                    nodata=-1.0, compress="deflate", tiled=True,
                    blockxsize=128, blockysize=128, crs=crs, transform=tr)
        tag = "N" if r < 0.002 else "P"
        fn = os.path.join(outdir, "%s_b%03d_%s.tif" % (rid, existing + ok, tag))
        with rasterio.open(fn, "w", **prof) as o:
            o.write(stack)
            for i, nm in enumerate(["t1_blue", "t1_green", "t1_red", "t1_nir",
                                    "t2_blue", "t2_green", "t2_red", "t2_nir"]):
                o.set_band_description(i + 1, nm)
        if ok % 10 == 0:
            print("  %d/%d (%.0fs)" % (ok, len(picked), time.time() - t0), flush=True)

    print("[%s] DONE 补入 %d 块" % (rid, ok), flush=True)


if __name__ == "__main__":
    main()
