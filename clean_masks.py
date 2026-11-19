"""
掩膜形态学清理：去掉孤立斑点，保留成片变化
  - 开运算（3x3）去噪
  - 去掉面积 < 9 像元的小连通块
用法: python clean_masks.py HN JX
"""
import os, sys, glob
import numpy as np
import rasterio

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OUT = r"D:\cropchg\out"
MIN_AREA = 9


def erode(m):
    p = np.pad(m, 1, constant_values=False)
    return (p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:])


def dilate(m):
    p = np.pad(m, 1, constant_values=False)
    return (p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:])


def components(mask):
    """4 邻域连通块标号（纯 numpy，样本 256x256 够用）"""
    h, w = mask.shape
    lab = np.zeros((h, w), np.int32)
    cur = 1
    ys, xs = np.nonzero(mask)
    for y0, x0 in zip(ys, xs):
        if lab[y0, x0]:
            continue
        stack = [(y0, x0)]
        lab[y0, x0] = cur
        while stack:
            y, x = stack.pop()
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not lab[ny, nx]:
                    lab[ny, nx] = cur
                    stack.append((ny, nx))
        cur += 1
    return lab, cur - 1


def clean(binary):
    b = erode(binary)
    b = dilate(b)
    lab, n = components(b)
    if n == 0:
        return b
    sizes = np.bincount(lab.ravel())
    keep = np.isin(lab, np.nonzero(sizes >= MIN_AREA)[0][1:] if False else
                   [i for i in range(1, n + 1) if sizes[i] >= MIN_AREA])
    return keep


def main():
    for rid in sys.argv[1:] or ["HN"]:
        files = sorted(glob.glob(os.path.join(OUT, rid, "%s_*.tif" % rid)))
        print("[%s] %d 个" % (rid, len(files)), flush=True)
        npos = 0
        for f in files:
            with rasterio.open(f) as ds:
                cube = ds.read()
                prof = ds.profile
            if cube.shape[0] < 9:
                continue
            lab = np.round(cube[8]).astype(np.int16)
            inv = lab == 255
            before = float((lab > 0).sum() - inv.sum()) / max((lab != 255).sum(), 1)
            m1 = clean(lab == 1)
            m2 = clean(lab == 2)
            new = np.zeros_like(lab)
            new[m1] = 1
            new[m2] = 2
            new[inv] = 255
            after = float((new > 0).sum() - inv.sum()) / max((new != 255).sum(), 1)
            if after >= 0.02:
                npos += 1
            cube[8] = new.astype(np.float32)
            tmp = f + ".tmp"
            with rasterio.open(tmp, "w", **prof) as o:
                o.write(cube)
            os.replace(tmp, f)
        print("[%s] 清理完成，有变化样本 %d" % (rid, npos), flush=True)


if __name__ == "__main__":
    main()
