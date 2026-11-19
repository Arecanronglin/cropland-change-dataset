import os, sys, glob
import numpy as np, rasterio
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OUT = r"D:\cropchg\out"


def rgb(a):
    a = np.clip(a, 0, 0.35) / 0.35
    return (np.transpose(a[:3][::-1], (1, 2, 0)) ** 0.7 * 255).astype(np.uint8)


def label_img(lab):
    h, w = lab.shape
    im = np.full((h, w, 3), 40, np.uint8)
    im[lab == 0] = (200, 200, 200)
    im[lab == 1] = (235, 45, 45)
    im[lab == 2] = (40, 200, 90)
    im[lab == 255] = (0, 0, 0)
    return im


for rid in sys.argv[1:] or ["HN"]:
    files = sorted(glob.glob(os.path.join(OUT, rid, "%s_*.tif" % rid)))
    print("[%s] %d 个" % (rid, len(files)), flush=True)
    rows = []
    for f in files[:6]:
        with rasterio.open(f) as ds:
            s = ds.read()
        has_lab = s.shape[0] >= 9
        lab = np.round(s[8]).astype(np.int16) if has_lab else np.zeros(
            s.shape[1:], np.int16)
        rows.append(np.concatenate([rgb(s[:4]), rgb(s[4:8]), label_img(lab)], 1))
    if rows:
        img = np.concatenate(rows, 0)
        p = os.path.join(OUT, "preview_%s.png" % rid)
        Image.fromarray(img).save(p)
        print("  预览", p, img.shape, flush=True)
