"""
整理数据集：扫描 out/<区>/*.tif，切分 train/val/test，出 manifest.csv
用法: python make_dataset.py [--neg-ratio 0.5]
"""
import os, sys, glob, csv, json
import numpy as np
import rasterio

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OUT = r"D:\cropchg\out"
POS_THR = 0.02
NEG_THR = 0.005


def main():
    rows = []
    for res in sorted(os.listdir(OUT)):
        d = os.path.join(OUT, res)
        if not os.path.isdir(d):
            continue
        for f in sorted(glob.glob(os.path.join(d, "*.tif"))):
            with rasterio.open(f) as ds:
                if ds.count < 9:
                    continue
                lab = np.round(ds.read(9)).astype(np.int16)
            inv = lab == 255
            va = (lab != 255).sum()
            if va == 0:
                continue
            valid = 1 - inv.mean()
            ratio = float((lab > 0).sum() - inv.sum()) / va
            tag = "pos" if ratio >= POS_THR else ("neg" if ratio < NEG_THR else "mid")
            rows.append(dict(path=f, region=res, ratio=round(ratio, 5),
                             valid=round(float(valid), 4), cls=tag))

    # 按区、按类别分层切分
    by = {}
    for r in rows:
        by.setdefault((r["region"], r["cls"]), []).append(r)
    for k in by:
        by[k].sort(key=lambda x: x["path"])
        n = len(by[k])
        for i, r in enumerate(by[k]):
            r["split"] = "train" if i < int(n * 0.7) else (
                "val" if i < int(n * 0.85) else "test")

    os.makedirs(os.path.join(OUT, "..", "dataset"), exist_ok=True)
    man = r"D:\cropchg\dataset\manifest.csv"
    os.makedirs(os.path.dirname(man), exist_ok=True)
    with open(man, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["path", "region", "ratio", "valid", "cls", "split"])
        w.writeheader()
        w.writerows(rows)

    print("%-6s %-6s %5s %5s %5s %5s" % ("区", "类别", "train", "val", "test", "合计"))
    print("-" * 42)
    agg = {}
    for r in rows:
        a = agg.setdefault((r["region"], r["cls"]), {"train": 0, "val": 0, "test": 0})
        a[r["split"]] += 1
    for (rg, cl), a in sorted(agg.items()):
        print("%-6s %-6s %5d %5d %5d %5d" % (rg, cl, a["train"], a["val"], a["test"],
                                             sum(a.values())))
    tot = {s: sum(1 for r in rows if r["split"] == s) for s in ("train", "val", "test")}
    print("-" * 42)
    print("总计 %d ｜ train %d / val %d / test %d" %
          (len(rows), tot["train"], tot["val"], tot["test"]))
    print("有变化 %d ｜ 无变化 %d ｜ 灰区 %d" % (
        sum(1 for r in rows if r["cls"] == "pos"),
        sum(1 for r in rows if r["cls"] == "neg"),
        sum(1 for r in rows if r["cls"] == "mid")))
    print("清单 →", man)


if __name__ == "__main__":
    main()
