# 耕地变化检测样本工程

## 现状（2026-11-20 00:20）

| 项 | 值 |
|---|---|
| 样本目录 | `D:\cropchg\out\<区>\<区>_###.tif` |
| 标注分级 | 清单 `D:\cropchg\dataset\manifest.csv` |
| 当前可用样本 | 197（湖南 92 / 江西 105） |
| 变化分布 | 有变化 32 ｜ 无变化 121 ｜ 灰区 44 |
| 模型基线 | U-Net，val IoU 0.175 / F1 0.298 |
| 环境 | `D:\cropchg\.venv`（rasterio 1.5.2 / GDAL 3.12.2 / torch 2.11.0+cu128） |

## 样本格式

每张 GeoTIFF 9 波段，float32，nodata = -1：

```
1 t1_blue   2 t1_green   3 t1_red   4 t1_nir     (2020 年，汛期后)
5 t2_blue   6 t2_green   7 t2_red   8 t2_nir     (2024 年，同物候窗)
9 change    0=无变化  1=耕地→非耕地  2=非耕地→耕地  255=无效(云)
```

尺寸 256×256，10m 分辨率（2.56km × 2.56km），带 UTM 投影。

## 脚本

| 脚本 | 作用 |
|---|---|
| `fetch_s2.py <区> <块数>` | 按网格顺序拉双时相影像 |
| `fetch_balanced.py <区> <负> <正>` | 先算 CLCD 变化率再挑块（补负/正样本用） |
| `scan_clcd.py <区>` | 看某区候选块的变化率分布，决定采样阈值 |
| `make_labels.py <区>` | CLCD 差分生成变化掩膜（开运算 + ≥1公顷面积过滤） |
| `make_dataset.py` | 切 train/val/test，出 manifest.csv |
| `train_unet.py` | 训练（BCE+Dice，输出 IoU/F1） |
| `infer_preview.py` | 出「前后影像 / 真值 / 预测」对比图 |
| `preview2.py <区>` | 出样本三联图 |
| `dl_clcd.py` | 下载 CLCD 分省数据（Zenodo 免注册） |

## 关键经验（别重复踩）

1. **工作目录必须是 ASCII 路径**。放在中文路径下，GDAL 报错时按 GBK 解码会抛
   `UnicodeDecodeError`，真实错误完全看不到。
2. **必须走代理**。直连 AWS S3 会截断（读 64×64 都失败），开了 Tyty 全局后正常。
3. **一景只覆盖 AOI 一部分**。要按块选景（`pick_for_tile`），别默认一景包全场。
4. **CLCD 30m 差分有约 4% 噪声底**。不做成片过滤的话，每个块都"有变化"，
   负样本采不出来。
5. **成片过滤用「面积」不要用「分块量化」**。分块会把标签切成 tic-tac-toe 的
   方块，模型学不到真实田块形状，F1 直接被压死。
6. **选样判据和标签判据的物理尺度要一致**。选样用 30m×8 块（240m），
   标签就得用等效的 ≥1 公顷面积过滤，否则选出来的"零变化"块打完标签又变了。

## 还没做

- 日韩越缅四区没有标签源。CLCD 只覆盖中国。需要：
  - 日本九州 → JAXA HRLULC 10m（2020 / 2024 两期，需注册）
  - 韩国全罗南道 → 环境部 세분류 토지피복지도（需注册）
  - 越南红河 → JAXA HRLULC Vietnam 10m（需注册）
  - 缅甸伊洛瓦底 → ADPC/SERVIR 季风稻（需注册）
- 正样本不足，`fetch_balanced.py` 正在补。
