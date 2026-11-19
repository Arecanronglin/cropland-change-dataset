import sys, csv
import numpy as np, torch, rasterio
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"D:\cropchg")
from train_unet import UNet

MAN = r"D:\cropchg\dataset\manifest.csv"
CKPT = r"D:\cropchg\dataset\best.pt"


def rgb(a):
    a = np.clip(a, 0, 0.35) / 0.35
    return (np.transpose(a[:3][::-1], (1, 2, 0)) ** 0.7 * 255).astype(np.uint8)


def heat(m):
    im = np.full((*m.shape, 3), 40, np.uint8)
    im[m] = (235, 45, 45)
    return im


rows = list(csv.DictReader(open(MAN, encoding="utf-8")))
sel = [r for r in rows if r["split"] == "test" and r["cls"] == "pos"][:3] + \
      [r for r in rows if r["split"] == "test" and r["cls"] == "neg"][:3]
ck = torch.load(CKPT, map_location="cpu")
m = UNet(8, ck["args"]["base"])
m.load_state_dict(ck["model"]); m.eval()
dev = "cuda" if torch.cuda.is_available() else "cpu"
m.to(dev)

out = []
with torch.no_grad():
    for r in sel:
        with rasterio.open(r["path"]) as ds:
            a = ds.read().astype(np.float32)
        x = np.where(np.concatenate([a[:4], a[4:8]], 0) < 0, 0.0,
                     np.concatenate([a[:4], a[4:8]], 0))
        lab = a[8]
        valid = lab != 255
        gt = (np.where(lab == 255, 0, lab) > 0) & valid
        p = (torch.sigmoid(m(torch.from_numpy(x)[None].to(dev)))[0, 0].cpu().numpy() > 0.5) & valid
        out.append(np.concatenate([rgb(a[:4]), rgb(a[4:8]), heat(gt), heat(p)], 1))
        print("%-40s 真值%.1f%% 预测%.1f%%" % (
            r["path"].split("\\")[-1], gt.mean() * 100, p.mean() * 100), flush=True)

img = np.concatenate(out, 0)
p = CKPT.replace("best.pt", "pred_vs_label.png")
Image.fromarray(img).save(p)
print("图 →", p, img.shape, flush=True)
