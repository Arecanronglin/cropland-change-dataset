"""在耕云智巡 deck 插入一页「数据底座」成果页"""
import io, os, re, shutil, sys
from copy import deepcopy
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SRC = r"D:\耕云智巡\耕云智巡 .pptx"
OUT = r"D:\耕云智巡\耕云智巡_v2.pptx"
BAK = r"D:\耕云智巡\耕云智巡 .pptx.bak"
ASSETS = r"D:\耕云智巡\素材_变化检测"
GOLD = RGBColor(0xE3, 0xA5, 0x1C)
YELLOW = RGBColor(0xFF, 0xC8, 0x45)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
MINT = RGBColor(0xE6, 0xEF, 0xE8)
DARK = RGBColor(0x06, 0x24, 0x19)
FONT = "微软雅黑"
FONT_NUM = "优设标题黑"

prs = Presentation(SRC)
W, H = prs.slide_width, prs.slide_height
print("页数 %d  尺寸 %.2f x %.2f in" % (len(prs.slides), W / 914400, H / 914400))

# ---------- 1. 找出模板页（产品页 index 5）的背景图 ----------
tpl = prs.slides[5]
bg_shape = None
for sh in tpl.shapes:
    if sh.shape_type == 13 and sh.left is not None and sh.width > W * 0.9:
        bg_shape = sh
        break
print("模板背景图:", bg_shape.name if bg_shape else None,
      "大小 %.1f MB" % (len(bg_shape.image.blob) / 1e6) if bg_shape else "")

# ---------- 2. 新建幻灯片并移到第 6 位 ----------
blank = prs.slide_layouts[6]
s = prs.slides.add_slide(blank)
lst = prs.slides._sldIdLst
el = list(lst)[-1]
lst.remove(el)
lst.insert(5, el)

# 背景
if bg_shape is not None and len(bg_shape.image.blob) < 6e6:
    s.shapes.add_picture(io.BytesIO(bg_shape.image.blob), 0, 0, W, H)
else:
    r = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, W, H)
    r.fill.solid(); r.fill.fore_color.rgb = DARK
    r.line.fill.background()

# 压暗层：背景是亮色麦田照，白字会糊，加一层半透明深色
from pptx.oxml.ns import qn
from lxml import etree

scrim = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, W, H)
scrim.fill.solid()
scrim.fill.fore_color.rgb = RGBColor(0x04, 0x16, 0x0E)
scrim.line.fill.background()
_sf = scrim.fill._xPr.find(qn("a:solidFill"))
_srgb = _sf.find(qn("a:srgbClr"))
_alpha = etree.SubElement(_srgb, qn("a:alpha"))
_alpha.set("val", "66000")


def tb(x, y, w, h, text, size, color, bold=False, font=FONT, align=None):
    box = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = 0
    tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]
    if align is not None:
        p.alignment = align
    r = p.add_run(); r.text = text
    r.font.size = Pt(size); r.font.bold = bold
    r.font.name = font; r.font.color.rgb = color
    return box


# ---------- 3. 页头（与其它页一致） ----------
tb(0.72, 0.40, 11.89, 0.18, "06  ·  数据", 10.5, YELLOW, True)
tb(0.72, 0.72, 11.89, 0.88, "六区实测，样本已在手", 52, WHITE, True)
tb(0.72, 1.60, 11.89, 0.25,
   "不是设想，是已经跑通的样本库：前后双时相影像，逐像元变化掩膜", 13.5, MINT)
rule = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.72), Inches(1.99),
                          Inches(1.10), Inches(0.06))
rule.fill.solid(); rule.fill.fore_color.rgb = GOLD; rule.line.fill.background()

# ---------- 4. 主图：六区前后对照 ----------
IMG_W = 8.50
img_path = os.path.join(ASSETS, "六区前后对照.png")
pic = s.shapes.add_picture(img_path, Inches(0.72), Inches(2.24), width=Inches(IMG_W))
IMG_H = pic.height / 914400
print("主图高 %.2f in" % IMG_H)

labels = ["湖南", "江西", "日本九州", "韩国·全罗南道", "越南·红河"]
n = len(labels)
cw = IMG_W / n
for i, name in enumerate(labels):
    tb(0.72 + i * cw, 2.24 + IMG_H + 0.06, cw, 0.20, name, 9, YELLOW, True,
       align=PP_ALIGN.CENTER)
tb(0.72, 2.24 + IMG_H + 0.28, IMG_W, 0.18,
   "上排 2020 年 7—8 月　下排 2024 年 7—8 月　同一地块、同一物候窗", 8.5, MINT)

# ---------- 5. 右侧三张指标卡 ----------
cards = [
    ("六区采样", "湘赣稻作、九州与全罗南道水田、红河与伊洛瓦底三角洲"),
    ("276 对样本", "每对 256×256 像元，前后时相各 4 波段"),
    ("F1 0.34", "U-Net 基线实测，正负样本 102 比 121 已平衡"),
]
x, y0, cw2, ch = 9.45, 2.24, 3.16, 1.02
for i, (k, v) in enumerate(cards):
    y = y0 + i * (ch + 0.16)
    card = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y),
                              Inches(cw2), Inches(ch))
    card.fill.solid(); card.fill.fore_color.rgb = WHITE; card.line.fill.background()
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y),
                             Inches(0.05), Inches(ch))
    bar.fill.solid(); bar.fill.fore_color.rgb = GOLD; bar.line.fill.background()
    tb(x + 0.22, y + 0.14, cw2 - 0.36, 0.34, k, 17, DARK, True, FONT_NUM)
    tb(x + 0.22, y + 0.56, cw2 - 0.36, 0.40, v, 8.5, RGBColor(0x22, 0x22, 0x22))

# ---------- 6. 底部说明 ----------
note_y = 2.24 + IMG_H + 0.56
tb(0.72, note_y, 11.89, 0.16,
   "影像｜Sentinel-2 L2A，10 m，免注册公开库直取，云区逐像元剔除", 8.5, MINT)
tb(0.72, note_y + 0.20, 11.89, 0.16,
   "标签｜CLCD 30 m 年度土地覆被差分，仅保留 ≥1 公顷成片变化，压掉年度分类抖动", 8.5, MINT)

# ---------- 7. 页脚 ----------
tb(0.72, 6.98, 6.00, 0.16, "耕云智巡 ｜ 湖南科技大学 地球科学与空间信息工程学院",
   9.5, MINT, True)
tb(12.01, 6.98, 0.60, 0.28, "06", 10, GOLD, True)

# ---------- 8. 全 deck 重编号 ----------
def renumber():
    """页码 = 第 i 页；页眉小节号 = 页码 - 1（全 deck 原本就是这个规律）"""
    for i, sl in enumerate(prs.slides, start=1):
        done_page = done_eye = False
        for sh in sl.shapes:
            if done_page and done_eye:
                break
            if not sh.has_text_frame:
                continue
            t = sh.text_frame.text.strip()
            top = sh.top / 914400 if sh.top is not None else -9

            # 页码：右下角两位数字
            if not done_page and re.fullmatch(r"\d{2}", t) and top > 6.7:
                for p in sh.text_frame.paragraphs:
                    for r in p.runs:
                        r.text = "%02d" % i
                done_page = True
                continue

            # 页眉小节号：形如 "05  ·  产品"
            if not done_eye and re.match(r"^\d{2}(\s*·\s*)", t) and abs(top - 0.40) < 0.12:
                new = "%02d" % (i - 1)
                for p in sh.text_frame.paragraphs:
                    for r in p.runs:
                        if re.match(r"^\d{2}", r.text):
                            r.text = re.sub(r"^\d{2}", new, r.text, count=1)
                            break
                    break
                done_eye = True

renumber()

if not os.path.exists(BAK):
    shutil.copy(SRC, BAK)
    print("已备份 →", BAK)
prs.save(OUT)
print("已保存 →", OUT, " 页数", len(prs.slides),
      "大小 %.1f MB" % (os.path.getsize(OUT) / 1e6))
