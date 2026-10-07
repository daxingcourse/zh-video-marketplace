#!/usr/bin/env python3
"""輪播圖產生器：slides.json -> 一頁一張 PNG。純文字排版，不使用任何第三方圖片或 AI 生圖。

用法：
  python carousel_render.py init calendar.json 2026-10-09 -o slides.json
      由日曆項目建立草稿（內容欄位會是【待補】，要由使用者與 Claude 填完）
  python carousel_render.py render slides.json -o out/ [--theme ink|paper|sage] [--size 1080x1350]
                                  [--font 字型檔] [--bold 粗體字型檔] [--allow-todo]
      排版並輸出 PNG。仍有【待補】會拒絕輸出（--allow-todo 只供預覽）

slides.json 格式：
{
  "meta":  {"handle": "@帳號", "footer_note": "一般性資訊，非個人建議", "eyebrow": "迷思破解"},
  "slides": [
    {"type": "cover", "title": "...", "subtitle": "..."},
    {"type": "point", "heading": "...", "body": "..."},
    {"type": "list",  "heading": "...", "bullets": ["...", "..."]},
    {"type": "cta",   "text": "...", "keyword": "外食", "note": "留言後會收到自動回覆的連結（自動訊息）"}
  ]
}
"""
import argparse, json, platform, re, sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "content-calendar" / "scripts"))

TODO = "【待補】"
NO_START = set("，。、；：？！）」』》〕】…,.;:?!)]}%")
NO_END = set("（「『《〔【([{")

THEMES = {
    # 墨：深藍底、字幕黃重點
    "ink":   {"bg": "#14213a", "fg": "#f3f5f8", "sub": "#a9b6cc", "accent": "#f2c230", "accent_fg": "#14213a", "rule": "#2c3b5c"},
    # 紙：冷灰白底、深墨字、青綠重點
    "paper": {"bg": "#eef1f4", "fg": "#142033", "sub": "#4a586b", "accent": "#1d7a78", "accent_fg": "#ffffff", "rule": "#cfd6df"},
    # 鼠尾草：灰綠底、深色字、深綠重點
    "sage":  {"bg": "#e3e9e1", "fg": "#1e2b24", "sub": "#4c5c52", "accent": "#2f6b4f", "accent_fg": "#ffffff", "rule": "#c3cdc1"},
}


def mkfont(spec, size):
    """載入字型。spec 可寫成「路徑」或「路徑|字重名稱」（可變字型需要，例如 NotoSansTC-VF.ttf|Bold）。
    Noto Sans TC 是可變字型，預設字重是最細的 Thin，不指定字重會變成很細的字。"""
    path, _, var = spec.partition("|")
    f = ImageFont.truetype(path, size)
    if var:
        try:
            f.set_variation_by_name(var)
        except Exception:
            pass
    return f


FONT_DIR = Path(__file__).resolve().parents[2] / "zh-bilingual-captions" / "fonts"


def find_fonts():
    """預設只使用隨套件附的開源字型（Noto Sans TC，SIL OFL）。不再自動使用系統字型，
    因為商用的圖片裡會直接含有字形，授權要明確。要用別的字型請以 --font 指定。"""
    reg, bold = FONT_DIR / "NotoSansTC-Regular.ttf", FONT_DIR / "NotoSansTC-Bold.ttf"
    if reg.exists() and bold.exists():
        return str(reg), str(bold)
    return None, None


def tokens(text):
    """英數字連續視為一個單位，其餘一字一單位。"""
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9'’\-.]*|\s|.", text)


def wrap(text, font, max_w):
    lines = []
    for para in text.split("\n"):
        cur = ""
        for t in tokens(para):
            if t.isspace() and not cur:
                continue
            if font.getlength(cur + t) <= max_w or not cur:
                cur += t
                continue
            # 行首禁則：標點不可落在行首，讓它留在上一行（允許略微超出）
            if t[0] in NO_START:
                cur += t
                continue
            # 行尾禁則：開括號不可落在行尾，移到下一行
            if cur[-1] in NO_END:
                lines.append(cur[:-1]); cur = cur[-1] + t
            else:
                lines.append(cur); cur = t
        lines.append(cur)
    return [l.rstrip() for l in lines]


def fit(text, path, max_w, max_h, start, minimum, spacing=1.45, index=0):
    """從大到小找出放得下的字級。回傳 (字型, 行, 行高, 是否溢出)。"""
    size = start
    while True:
        font = mkfont(path, size)
        lines = wrap(text, font, max_w)
        lh = int(size * spacing)
        if len(lines) * lh <= max_h:
            return font, lines, lh, False
        if size <= minimum:
            return font, lines, lh, True
        size -= 2


class Renderer:
    def __init__(self, size, theme, font, bold, meta):
        self.W, self.H = size
        self.t = THEMES[theme]
        self.font, self.bold, self.meta = font, bold, meta
        self.M = int(self.W * 0.09)  # 邊界
        self.warns = []

    def canvas(self):
        im = Image.new("RGB", (self.W, self.H), self.t["bg"])
        return im, ImageDraw.Draw(im)

    def text_block(self, d, text, path, x, y, max_w, max_h, start, minimum, color, label, spacing=1.45):
        font, lines, lh, over = fit(text, path, max_w, max_h, start, minimum, spacing)
        if over:
            self.warns.append(f"{label}：文字太長，放不下（已縮到最小字級仍溢出），請縮短")
        for i, ln in enumerate(lines):
            d.text((x, y + i * lh), ln, font=font, fill=color)
        return y + len(lines) * lh

    def chrome(self, d, idx, total):
        """頁尾：分頁進度條（每頁一段，目前頁為重點色）、帳號、備註。"""
        W, H, M = self.W, self.H, self.M
        bar_y, gap = H - int(H * 0.055), 8
        seg = (W - 2 * M - gap * (total - 1)) / total
        for i in range(total):
            x0 = M + i * (seg + gap)
            d.rounded_rectangle([x0, bar_y, x0 + seg, bar_y + 8], radius=4,
                                fill=self.t["accent"] if i == idx else self.t["rule"])
        small = mkfont(self.font, int(W * 0.026))
        y = bar_y - int(W * 0.05)
        note = self.meta.get("footer_note", "")
        if note:
            d.text((M, y), note, font=small, fill=self.t["sub"])
        handle = self.meta.get("handle", "")
        if handle:
            d.text((W - M - small.getlength(handle), y), handle, font=small, fill=self.t["sub"])

    def body_box(self):
        return self.W - 2 * self.M, self.H - 2 * self.M - int(self.H * 0.12)

    def cover(self, s, idx, total):
        im, d = self.canvas(); W, H, M = self.W, self.H, self.M
        bw, bh = self.body_box()
        eyebrow = self.meta.get("eyebrow", "")
        y = M + int(H * 0.17)
        if eyebrow:
            small = mkfont(self.font, int(W * 0.032))
            tw = small.getlength(eyebrow) + 36
            d.rounded_rectangle([M, y, M + tw, y + int(W * 0.062)], radius=int(W * 0.031), fill=self.t["accent"])
            d.text((M + 18, y + int(W * 0.011)), eyebrow, font=small, fill=self.t["accent_fg"])
            y += int(W * 0.062) + int(H * 0.04)
        y = self.text_block(d, s["title"], self.bold, M, y, bw, int(bh * 0.62), int(W * 0.105), int(W * 0.058), self.t["fg"], f"第 {idx+1} 頁標題", 1.28)
        if s.get("subtitle"):
            self.text_block(d, s["subtitle"], self.font, M, y + int(H * 0.03), bw, int(bh * 0.2), int(W * 0.04), int(W * 0.03), self.t["sub"], f"第 {idx+1} 頁副標")
        self.chrome(d, idx, total); return im

    def point(self, s, idx, total):
        im, d = self.canvas(); W, H, M = self.W, self.H, self.M
        bw, bh = self.body_box()
        y = M + int(H * 0.06)
        d.rectangle([M, y, M + int(W * 0.12), y + 8], fill=self.t["accent"])
        y += int(H * 0.04)
        y = self.text_block(d, s["heading"], self.bold, M, y, bw, int(bh * 0.3), int(W * 0.086), int(W * 0.054), self.t["fg"], f"第 {idx+1} 頁標題", 1.3)
        self.text_block(d, s["body"], self.font, M, y + int(H * 0.035), bw, int(bh * 0.55), int(W * 0.06), int(W * 0.038), self.t["fg"], f"第 {idx+1} 頁內文")
        self.chrome(d, idx, total); return im

    def bullets(self, s, idx, total):
        im, d = self.canvas(); W, H, M = self.W, self.H, self.M
        bw, bh = self.body_box()
        y = M + int(H * 0.06)
        d.rectangle([M, y, M + int(W * 0.12), y + 8], fill=self.t["accent"])
        y += int(H * 0.04)
        y = self.text_block(d, s["heading"], self.bold, M, y, bw, int(bh * 0.22), int(W * 0.078), int(W * 0.05), self.t["fg"], f"第 {idx+1} 頁標題", 1.3)
        y += int(H * 0.03)
        n = max(1, len(s["bullets"]))
        room = (self.H - int(H * 0.17)) - y
        per = room / n
        dot = int(W * 0.018)
        for b in s["bullets"]:
            d.ellipse([M, y + int(W * 0.022), M + dot, y + int(W * 0.022) + dot], fill=self.t["accent"])
            self.text_block(d, b, self.font, M + dot + 28, y, bw - dot - 28, per - 12, int(W * 0.056), int(W * 0.034), self.t["fg"], f"第 {idx+1} 頁條列")
            y += per
        self.chrome(d, idx, total); return im

    def cta(self, s, idx, total):
        im, d = self.canvas(); W, H, M = self.W, self.H, self.M
        bw, bh = self.body_box()
        y = M + int(H * 0.14)
        y = self.text_block(d, s["text"], self.bold, M, y, bw, int(bh * 0.4), int(W * 0.082), int(W * 0.05), self.t["fg"], f"第 {idx+1} 頁主文", 1.3)
        y += int(H * 0.04)
        kw = s.get("keyword", "")
        if kw:
            big = mkfont(self.bold, int(W * 0.07))
            label = mkfont(self.font, int(W * 0.036))
            d.text((M, y), "留言輸入", font=label, fill=self.t["sub"])
            y += int(W * 0.06)
            tw = big.getlength(kw) + 70
            d.rounded_rectangle([M, y, M + tw, y + int(W * 0.14)], radius=int(W * 0.03), fill=self.t["accent"])
            d.text((M + 35, y + int(W * 0.026)), kw, font=big, fill=self.t["accent_fg"])
            y += int(W * 0.14) + int(H * 0.035)
        if s.get("note"):
            self.text_block(d, s["note"], self.font, M, y, bw, int(bh * 0.25), int(W * 0.036), int(W * 0.028), self.t["sub"], f"第 {idx+1} 頁備註")
        self.chrome(d, idx, total); return im


def collect_text(slides):
    for s in slides:
        for k, v in s.items():
            if isinstance(v, str):
                yield v
            elif isinstance(v, list):
                yield from (x for x in v if isinstance(x, str))


def cmd_init(a):
    cal = json.loads(Path(a.calendar).read_text(encoding="utf-8"))
    it = next((i for i in cal if i["date"] == a.date), None)
    if not it:
        sys.exit(f"日曆裡沒有 {a.date}")
    if it["format"] not in ("輪播", "貼文"):
        print(f"提醒：{a.date} 的格式是 {it['format']}，不是輪播。仍會建立草稿。")
    pts = [x.strip() for x in re.split(r"[。；\n]", str(it.get("script", ""))) if x.strip()]
    slides = [{"type": "cover", "title": it["topic"], "subtitle": it["hook"]}]
    for p in (pts[:4] or [TODO] * 3):
        slides.append({"type": "point", "heading": TODO, "body": f"{TODO}（參考：{p}）" if p != TODO else TODO})
    if it.get("cta_keyword"):
        slides.append({"type": "cta", "text": TODO, "keyword": it["cta_keyword"], "note": "留言後會收到自動回覆的連結（此為自動訊息）"})
    else:
        slides.append({"type": "cta", "text": "喜歡的話，收藏起來慢慢看", "keyword": "", "note": ""})
    data = {"meta": {"handle": "", "footer_note": "", "eyebrow": it["pillar"]}, "slides": slides}
    Path(a.out).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已建立草稿 {a.out}（{len(slides)} 頁）。請和使用者把【待補】填完，再執行 render。")


def cmd_render(a):
    data = json.loads(Path(a.slides).read_text(encoding="utf-8"))
    meta, slides = data.get("meta", {}), data["slides"]
    w, h = (int(x) for x in a.size.lower().split("x"))
    reg, bold = (a.font, a.bold or a.font) if a.font else find_fonts()
    if not reg:
        sys.exit("找不到內附的開源字型（zh-bilingual-captions/fonts/NotoSansTC-Regular.ttf 與 NotoSansTC-Bold.ttf）。請補回該檔案，或用 --font 指定你有授權的字型檔；可變字型可寫成 路徑|Bold")
    if a.theme not in THEMES:
        sys.exit(f"theme 必須是 {list(THEMES)} 之一")

    problems = []
    todos = [t for t in collect_text(slides) if TODO in t]
    if todos and not a.allow_todo:
        sys.exit(f"仍有 {len(todos)} 處{TODO}，請先和使用者填完（只想預覽排版可加 --allow-todo）")
    if len(slides) < 2:
        problems.append("只有 1 頁，輪播通常至少 2 頁")
    if len(slides) > 10:
        problems.append(f"共 {len(slides)} 頁，建議 10 頁內（這是建議，不是平台上限）")

    r = Renderer((w, h), a.theme, reg, bold, meta)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    fn = {"cover": r.cover, "point": r.point, "list": r.bullets, "cta": r.cta}
    for i, s in enumerate(slides):
        if s["type"] not in fn:
            sys.exit(f"第 {i+1} 頁：未知的 type「{s['type']}」，可用 {list(fn)}")
        fn[s["type"]](s, i, len(slides)).save(out / f"slide_{i+1:02d}.png")

    # 用語提示（重用日曆的詞庫）
    try:
        from calendar_tools import scan_terms
        cfg = json.loads((Path(__file__).resolve().parents[2] / "content-calendar" / "scripts" / "flag_terms.json").read_text(encoding="utf-8"))
        text = "\n".join(collect_text(slides))
        for cat, term, note in scan_terms({"topic": text}, cfg):
            problems.append(f"用語提示：命中「{term}」［{cat}］：{note}（只是提示，不是法律判斷）")
    except Exception:
        problems.append("（找不到用語詞庫，已略過用語提示）")

    problems += r.warns
    print(f"完成：{len(slides)} 頁 -> {out}（{w}x{h}，主題 {a.theme}）")
    for p in problems:
        print("  ⚠", p)
    if not problems:
        print("  沒有發現問題。請自己打開每一頁看過再發布。")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("init"); i.add_argument("calendar"); i.add_argument("date"); i.add_argument("-o", "--out", default="slides.json"); i.set_defaults(f=cmd_init)
    r = sub.add_parser("render"); r.add_argument("slides"); r.add_argument("-o", "--out", default="out")
    r.add_argument("--theme", default="paper"); r.add_argument("--size", default="1080x1350")
    r.add_argument("--font"); r.add_argument("--bold"); r.add_argument("--allow-todo", action="store_true"); r.set_defaults(f=cmd_render)
    a = ap.parse_args(); a.f(a)


if __name__ == "__main__":
    main()
