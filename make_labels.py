"""
用 CLCD 年度土地覆被（30m）生成变化掩膜，作为样本第 9 波段
只保留「成片变化」：3×3 开运算去散点 + 去掉面积 < 1 公顷的连通块
（不切方块，保留真实田块形状）
  label: 0=无变化  1=耕地->非耕地  2=非耕地->耕地  255=无效
用法: python make_labels.py HN JX
"""
import os, sys, glob, time
import numpy as np
import rasterio
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = r"D:\cropchg\out"
CLCD = r"D:\cropchg\data\clcd"
PROV = {"HN": "hunan", "JX": "jiangxi"}
CROP_CLASS = 1
MIN_AREA = 100          # 10m 像元 → 100 像元 = 1 公顷


def warp_crop(path, crs, tr, w, h):
    with rasterio.open(path) as s:
        with WarpedVRT(s, crs=crs, transform=tr, width=w, height=h,
                       resampling=Resampling.nearest, nodata=0) as v:
            return v.read(1)


def opening(m, it=1):
    for _ in range(it):
        p = np.pad(m, 1, constant_values=False)
        m = p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:]
    for _ in range(it):
        p = np.pad(m, 1, constant_values=False)
        m = p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
    return m


def area_filter(mask, min_area):
    """去掉面积小于 min_area 的 4 连通块（数组级 BFS）"""
    h, w = mask.shape
    lab = np.zeros((h, w), np.int16)
    out = np.zeros_like(mask)
    cur = 0
    ys, xs = np.nonzero(mask)
    for y0, x0 in zip(ys.tolist(), xs.tolist()):
        if lab[y0, x0]:
            continue
        cur += 1
        stack = [(y0, x0)]
        lab[y0, x0] = cur
        pix = []
        while stack:
            y, x = stack.pop()
            pix.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not lab[ny, nx]:
                    lab[ny, nx] = cur
                    stack.append((ny, nx))
        if len(pix) >= min_area:
            for y, x in pix:
                out[y, x] = True
    return out


def main():
    for rid in sys.argv[1:] or ["HN"]:
        files = sorted(glob.glob(os.path.join(OUT, rid, "%s_*.tif" % rid)))
        print("[%s] %d 个样本" % (rid, len(files)), flush=True)
        npos = nneg = nmid = 0
        t0 = time.time()
        for f in files:
            with rasterio.open(f) as ds:
                cube = ds.read()
                tr, crs, w, h = ds.transform, ds.crs, ds.width, ds.height
                prof = ds.profile
            c20 = warp_crop(os.path.join(CLCD, "2020_%s.tif" % PROV[rid]), crs, tr, w, h) == CROP_CLASS
            c24 = warp_crop(os.path.join(CLCD, "2024_%s.tif" % PROV[rid]), crs, tr, w, h) == CROP_CLASS
            lost = area_filter(opening(c20 & ~c24), MIN_AREA)
            gain = area_filter(opening(~c20 & c24), MIN_AREA)
            lab = np.zeros((h, w), np.uint8)
            lab[lost] = 1
            lab[gain] = 2
            lab[cube[0] <= 0] = 255
            va = int((lab != 255).sum())
            r = float((lab > 0).sum() - (lab == 255).sum()) / max(va, 1)
            if r >= 0.02:
                npos += 1
            elif r < 0.002:
                nneg += 1
            else:
                nmid += 1
            prof.update(count=9, dtype="float32", nodata=-1.0)
            tmp = f + ".tmp"
            with rasterio.open(tmp, "w", **prof) as o:
                o.write(np.concatenate([cube[:8], lab[None].astype(np.float32)], 0))
                for i, nm in enumerate(["t1_blue", "t1_green", "t1_red", "t1_nir",
                                        "t2_blue", "t2_green", "t2_red", "t2_nir",
                                        "change"]):
                    o.set_band_description(i + 1, nm)
            os.replace(tmp, f)
        print("[%s] 完成 有变化 %d ｜ 无变化 %d ｜ 灰区 %d  (%.0fs)" % (
            rid, npos, nneg, nmid, time.time() - t0), flush=True)


if __name__ == "__main__":
    main()
