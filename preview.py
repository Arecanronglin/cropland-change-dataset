import os, sys, glob
import numpy as np, rasterio
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OUT = r"D:\cropchg\out\HN"
files = sorted(glob.glob(os.path.join(OUT, "*.tif")))
print("样本", len(files), "个")


def rgb(a):
    a = np.clip(a, 0, 0.35) / 0.35
    return (np.transpose(a[:3][::-1], (1, 2, 0)) ** 0.7 * 255).astype(np.uint8)


rows = []
for f in files[:6]:
    with rasterio.open(f) as ds:
        s = ds.read()
    t1, t2 = s[:4], s[4:8]
    d = np.abs(t1.mean(0) - t2.mean(0))
    heat = np.zeros((*d.shape, 3), np.uint8)
    m = d > np.percentile(d, 98)
    heat[..., 0] = 60
    heat[m] = (255, 40, 40)
    rows.append(np.concatenate([rgb(t1), rgb(t2), heat], 1))

if rows:
    img = np.concatenate(rows, 0)
    p = r"D:\cropchg\out\preview_HN.png"
    Image.fromarray(img).save(p)
    print("预览", p, img.shape)
