"""生成 PPT 用素材：六区前后对照图、单区三联图"""
import os, sys, glob
import numpy as np, rasterio
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OUT = r"D:\cropchg\out"
ASSETS = r"D:\耕云智巡\素材_变化检测"
os.makedirs(ASSETS, exist_ok=True)
REGIONS = ["HN", "JX", "JP", "KR", "VN", "MM"]
TILE = 512


def rgb(a):
    a = np.clip(a, 0, 0.35) / 0.35
    return (np.transpose(a[:3][::-1], (1, 2, 0)) ** 0.7 * 255).astype(np.uint8)


def load(f):
    with rasterio.open(f) as ds:
        return ds.read().astype(np.float32)


def best_file(rid, want_change=True):
    """挑尽可能无云、变化明显的样本；逐级放宽阈值保证每区都有一张"""
    fs = sorted(glob.glob(os.path.join(OUT, rid, "%s_*.tif" % rid)))
    for thr in (0.985, 0.95, 0.90):
        best, bestv = None, -1
        for f in fs:
            try:
                a = load(f)
            except Exception:
                continue
            v = float((a[0] > 0).mean())
            v2 = float((a[4] > 0).mean())
            if min(v, v2) < thr:
                continue
            if a.shape[0] >= 9:
                lab = np.round(a[8])
                ch = float(((lab > 0) & (lab != 255)).sum() / max((lab != 255).sum(), 1))
            else:
                ch = float(np.abs(a[:3].mean(0) - a[4:7].mean(0)).mean())
            score = (ch if want_change else -ch)
            if score > bestv:
                bestv, best = score, f
        if best:
            return best
    return None


pairs = []
for rid in REGIONS:
    f = best_file(rid)
    if not f:
        print("[%s] 无可用样本" % rid, flush=True)
        continue
    a = load(f)
    p1 = np.asarray(Image.fromarray(rgb(a[:4])).resize((TILE, TILE), Image.LANCZOS))
    p2 = np.asarray(Image.fromarray(rgb(a[4:8])).resize((TILE, TILE), Image.LANCZOS))
    pairs.append((rid, p1, p2))
    print("[%s] %s" % (rid, os.path.basename(f)), flush=True)

# 一、六区前后对照（上排 2020，下排 2024）
if pairs:
    w = TILE * len(pairs)
    canvas = Image.new("RGB", (w, TILE * 2), (0, 0, 0))
    for i, (rid, p1, p2) in enumerate(pairs):
        canvas.paste(Image.fromarray(p1), (i * TILE, 0))
        canvas.paste(Image.fromarray(p2), (i * TILE, TILE))
    p = os.path.join(ASSETS, "六区前后对照.png")
    canvas.save(p)
    print("→", p, canvas.size, flush=True)

# 二、单区三联（前后 + 变化掩膜）
for rid in ("HN", "JX"):
    fs = sorted(glob.glob(os.path.join(OUT, rid, "%s_*.tif" % rid)))
    picked = []
    for f in fs:
        a = load(f)
        if a.shape[0] < 9:
            continue
        lab = np.round(a[8])
        ch = float(((lab > 0) & (lab != 255)).sum() / max((lab != 255).sum(), 1))
        if ch > 0.03 and (a[0] > 0).mean() > 0.9:
            picked.append((ch, f, a, lab))
            if len(picked) >= 3:
                break
    if not picked:
        continue
    rows = []
    for ch, f, a, lab in picked:
        im = np.full((*lab.shape, 3), 40, np.uint8)
        im[lab == 0] = (205, 205, 205)
        im[lab == 1] = (230, 45, 45)
        im[lab == 2] = (40, 195, 90)
        im[lab == 255] = (0, 0, 0)
        rows.append(np.concatenate([rgb(a[:4]), rgb(a[4:8]), im], 1))
    img = np.concatenate(rows, 0)
    p = os.path.join(ASSETS, "%s_前后与掩膜.png" % ("湖南" if rid == "HN" else "江西"))
    Image.fromarray(img).save(p)
    print("→", p, img.shape, flush=True)

# 三、模型预测对照
src = r"D:\cropchg\dataset\pred_vs_label.png"
if os.path.exists(src):
    import shutil
    shutil.copy(src, os.path.join(ASSETS, "模型预测对照.png"))
    print("→ 模型预测对照.png", flush=True)

print("素材目录:", ASSETS)
