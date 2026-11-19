"""
双时相变化检测 训练脚本（U-Net baseline）
数据: 9 波段 GeoTIFF（t1_blue/green/red/nir, t2_*, change）
用法: python train_unet.py [--epochs 40] [--bs 8] [--lr 1e-3]
"""
import argparse, csv, os, sys, time
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
import rasterio

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAN = r"D:\cropchg\dataset\manifest.csv"
CKPT = r"D:\cropchg\dataset\best.pt"


class CDDataset(Dataset):
    def __init__(self, rows):
        self.rows = rows

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        with rasterio.open(self.rows[i]["path"]) as ds:
            a = ds.read().astype(np.float32)
        x = np.concatenate([a[:4], a[4:8]], 0)
        x = np.where(x < 0, 0.0, x)                     # 云/无效 → 0
        y = a[8]
        valid = (y != 255).astype(np.float32)
        y = np.where(y == 255, 0.0, y)
        y = (y > 0).astype(np.float32)                  # 二值：变/没变
        return torch.from_numpy(x), torch.from_numpy(y)[None], torch.from_numpy(valid)[None]


def conv(i, o):
    return nn.Sequential(nn.Conv2d(i, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU(True),
                         nn.Conv2d(o, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU(True))


class UNet(nn.Module):
    def __init__(self, cin=8, base=32):
        super().__init__()
        b = base
        self.e1, self.e2, self.e3, self.e4 = conv(cin, b), conv(b, b * 2), conv(b * 2, b * 4), conv(b * 4, b * 8)
        self.pool = nn.MaxPool2d(2)
        self.u3 = nn.ConvTranspose2d(b * 8, b * 4, 2, 2); self.d3 = conv(b * 8, b * 4)
        self.u2 = nn.ConvTranspose2d(b * 4, b * 2, 2, 2); self.d2 = conv(b * 4, b * 2)
        self.u1 = nn.ConvTranspose2d(b * 2, b, 2, 2);     self.d1 = conv(b * 2, b)
        self.out = nn.Conv2d(b, 1, 1)

    def forward(self, x):
        e1 = self.e1(x); e2 = self.e2(self.pool(e1))
        e3 = self.e3(self.pool(e2)); e4 = self.e4(self.pool(e3))
        d3 = self.d3(torch.cat([self.u3(e4), e3], 1))
        d2 = self.d2(torch.cat([self.u2(d3), e2], 1))
        d1 = self.d1(torch.cat([self.u1(d2), e1], 1))
        return self.out(d1)


def loss_fn(pred, y, valid):
    bce = F.binary_cross_entropy_with_logits(pred, y, reduction="none")
    bce = (bce * valid).sum() / valid.sum().clamp(min=1)
    p = torch.sigmoid(pred) * valid
    inter = (p * y).sum()
    dice = 1 - (2 * inter + 1) / (p.sum() + y.sum() + 1)
    return bce + dice


@torch.no_grad()
def evaluate(model, dl, dev):
    model.eval()
    tp = fp = fn = tn = 0
    for x, y, v in dl:
        x, y, v = x.to(dev), y.to(dev), v.to(dev)
        p = (torch.sigmoid(model(x)) > 0.5).float() * v
        tp += ((p == 1) & (y == 1)).sum().item()
        fp += ((p == 1) & (y == 0)).sum().item()
        fn += ((p == 0) & (y == 1)).sum().item()
        tn += ((p == 0) & (y == 0)).sum().item()
    iou = tp / max(tp + fp + fn, 1)
    f1 = 2 * tp / max(2 * tp + fp + fn, 1)
    return iou, f1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--bs", type=int, default=8)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--base", type=int, default=32)
    a = ap.parse_args()

    rows = list(csv.DictReader(open(MAN, encoding="utf-8")))
    tr = [r for r in rows if r["split"] == "train"]
    va = [r for r in rows if r["split"] in ("val", "test")]
    print("train %d / val %d" % (len(tr), len(va)), flush=True)
    if not tr:
        sys.exit("没有训练样本")

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    print("设备:", dev, torch.cuda.get_device_name(0) if dev == "cuda" else "", flush=True)

    dl_tr = DataLoader(CDDataset(tr), batch_size=a.bs, shuffle=True, num_workers=0, drop_last=True)
    dl_va = DataLoader(CDDataset(va), batch_size=a.bs, shuffle=False, num_workers=0)

    model = UNet(8, a.base).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=1e-4)
    sch = torch.optim.lr_scheduler.CosineAnnealingLR(opt, a.epochs)

    best = -1
    for ep in range(1, a.epochs + 1):
        model.train()
        t0, tot = time.time(), 0.0
        for x, y, v in dl_tr:
            x, y, v = x.to(dev), y.to(dev), v.to(dev)
            opt.zero_grad()
            loss = loss_fn(model(x), y, v)
            loss.backward(); opt.step()
            tot += loss.item()
        sch.step()
        iou, f1 = evaluate(model, dl_va, dev) if va else (0, 0)
        print("ep %02d  loss %.4f  val IoU %.4f  F1 %.4f  (%.0fs)" % (
            ep, tot / max(len(dl_tr), 1), iou, f1, time.time() - t0), flush=True)
        if f1 > best:
            best = f1
            torch.save({"model": model.state_dict(), "iou": iou, "f1": f1,
                        "args": vars(a)}, CKPT)
    print("最优 F1 %.4f  模型 → %s" % (best, CKPT), flush=True)


if __name__ == "__main__":
    main()
