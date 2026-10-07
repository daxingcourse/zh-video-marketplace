#!/usr/bin/env python3
"""動態圖卡：在口播影片上疊加標題卡、重點卡、數字卡、引言卡與下三分之一字卡，帶淡入與滑入動畫。

純本機處理，只用 ffmpeg 與 Pillow，字型使用內附的開源字型。**不使用任何第三方圖片或素材。**
時間軸是「剪後影片」的時間（與字幕相同）。圖卡先疊上去，字幕最後才燒錄，所以字幕會在圖卡之上。

用法：
  python cards_overlay.py init -o cards.json [--size 1080x1920]
  python cards_overlay.py check cards.json --video work/cut.mp4 [--segments work/segments.json]
  python cards_overlay.py preview cards.json --video work/cut.mp4 -o preview/
  python cards_overlay.py render cards.json --video work/cut.mp4 -o work/cut_cards.mp4 [--segments work/segments.json]

cards.json：
{
  "meta": {"theme": "ink"},
  "cards": [
    {"type": "point", "start": 3.2, "end": 7.0, "label": "重點", "text": "先看一整天的總量", "position": "lower"},
    {"type": "title", "start": 0.4, "end": 3.0, "text": "晚餐真的會讓人變胖嗎？"},
    {"type": "stat",  "start": 8.0, "end": 11.0, "number": "三件事", "text": "挑便當固定看這三件"},
    {"type": "quote", "start": 12.0, "end": 16.0, "text": "我都會先問他今天吃了什麼", "by": "（使用者自己的話）"},
    {"type": "lower", "start": 0.3, "end": 3.3, "name": "名稱", "title": "一句話身分"}
  ]
}
"""
import argparse, json, re, subprocess, sys, tempfile
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "carousel-maker" / "scripts"))
sys.path.insert(0, str(HERE.parents[1] / "content-calendar" / "scripts"))
from carousel_render import THEMES, FONT_DIR, fit, mkfont  # noqa: E402

TYPES = {"title", "point", "stat", "quote", "lower"}
POSITIONS = {"lower", "top", "center"}
FADE_IN, FADE_OUT, SLIDE = 0.30, 0.25, 0.022  # 秒、秒、滑動距離（相對於高度）
NUM = re.compile(r"[0-9]+(?:\.[0-9]+)?\s*(?:%|％|公斤|kg|KG|斤|週|周|天|倍|萬|元|個月|次|分鐘|小時|歲|年)?|[一二兩三四五六七八九十百千]+\s*(?:公斤|斤|週|周|天|倍|萬|元|個月|分鐘|小時|歲|年)")


def hex_rgba(h, a):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (a,)


def fonts():
    reg, bold = FONT_DIR / "NotoSansTC-Regular.ttf", FONT_DIR / "NotoSansTC-Bold.ttf"
    if not (reg.exists() and bold.exists()):
        sys.exit("找不到內附的開源字型（zh-bilingual-captions/fonts/）。請補回，或自行修改程式指定字型")
    return str(reg), str(bold)


def probe(video):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate",
                          "-show_entries", "format=duration", "-of", "json", str(video)], capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    s = d["streams"][0]
    num, den = (int(x) for x in s["r_frame_rate"].split("/"))
    return int(s["width"]), int(s["height"]), num / den, float(d["format"]["duration"])


def zones(W, H):
    """回傳圖卡底邊的上限（避開雙語字幕）與各位置的基準。字幕預設在下方，見 merge_bilingual.py。"""
    vertical = H > W
    sub_top = 0.72 if vertical else 0.79     # 字幕大約從這個高度比例開始（依預設設定估算）
    return {"limit": sub_top - 0.02, "vertical": vertical}


class Painter:
    def __init__(self, W, H, theme):
        self.W, self.H, self.t = W, H, THEMES[theme]
        self.reg, self.bold = fonts()
        self.M = int(W * 0.07)
        self.maxw = W - 2 * self.M
        self.warn = []

    def panel(self, w, h):
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([0, 0, w - 1, h - 1], radius=int(self.W * 0.028), fill=hex_rgba(self.t["bg"], 238))
        return im, d

    def text_lines(self, text, path, max_w, size, minimum, spacing=1.35):
        font, lines, lh, over = fit(text, path, max_w, 10_000, size, minimum, spacing)
        return font, lines, lh

    def point(self, c):
        pad = int(self.W * 0.04); bar = int(self.W * 0.012)
        inner = self.maxw - 2 * pad - bar - 20
        label = c.get("label", "重點")
        lf = mkfont(self.bold, int(self.W * 0.03))
        font, lines, lh = self.text_lines(c["text"], self.bold, inner, int(self.W * 0.058), int(self.W * 0.04))
        lab_h = int(self.W * 0.052)
        h = pad + lab_h + 12 + len(lines) * lh + pad
        im, d = self.panel(self.maxw, h)
        d.rounded_rectangle([0, 0, bar, h - 1], radius=bar // 2, fill=hex_rgba(self.t["accent"], 255))
        x0 = bar + pad
        lw = lf.getlength(label) + 28
        d.rounded_rectangle([x0, pad, x0 + lw, pad + lab_h], radius=lab_h // 2, fill=hex_rgba(self.t["accent"], 255))
        d.text((x0 + 14, pad + int(lab_h * 0.16)), label, font=lf, fill=hex_rgba(self.t["accent_fg"], 255))
        y = pad + lab_h + 12
        for ln in lines:
            d.text((x0, y), ln, font=font, fill=hex_rgba(self.t["fg"], 255)); y += lh
        return im

    def title(self, c):
        pad = int(self.W * 0.05)
        inner = self.maxw - 2 * pad
        font, lines, lh = self.text_lines(c["text"], self.bold, inner, int(self.W * 0.075), int(self.W * 0.045), 1.3)
        h = 2 * pad + len(lines) * lh
        im, d = self.panel(self.maxw, h)
        d.rectangle([pad, pad - int(self.W * 0.018), pad + int(self.W * 0.12), pad - int(self.W * 0.018) + 8], fill=hex_rgba(self.t["accent"], 255))
        y = pad + 6
        for ln in lines:
            d.text((pad, y), ln, font=font, fill=hex_rgba(self.t["fg"], 255)); y += lh
        return im

    def stat(self, c):
        pad = int(self.W * 0.045)
        inner = self.maxw - 2 * pad
        # 大字數字盡量保持一行：從大到小找出一行放得下的字級；太長仍放不下才換行（檢查時會警告）
        size = int(self.W * 0.17)
        while size > int(self.W * 0.06) and mkfont(self.bold, size).getlength(c["number"]) > inner:
            size -= 4
        nf, nl, nlh = self.text_lines(c["number"], self.bold, inner, size, int(self.W * 0.06), 1.1)
        tf, tl, tlh = self.text_lines(c.get("text", ""), self.reg, inner, int(self.W * 0.045), int(self.W * 0.034))
        h = 2 * pad + len(nl) * nlh + (len(tl) * tlh + 8 if c.get("text") else 0)
        im, d = self.panel(self.maxw, h)
        y = pad
        for ln in nl:
            d.text((pad, y), ln, font=nf, fill=hex_rgba(self.t["accent"], 255)); y += nlh
        y += 8
        for ln in (tl if c.get("text") else []):
            d.text((pad, y), ln, font=tf, fill=hex_rgba(self.t["fg"], 255)); y += tlh
        return im

    def quote(self, c):
        pad = int(self.W * 0.05)
        inner = self.maxw - 2 * pad - int(self.W * 0.06)
        font, lines, lh = self.text_lines(c["text"], self.reg, inner, int(self.W * 0.052), int(self.W * 0.036), 1.4)
        by = c.get("by", "")
        bf = mkfont(self.reg, int(self.W * 0.032))
        h = 2 * pad + len(lines) * lh + (int(self.W * 0.06) if by else 0)
        im, d = self.panel(self.maxw, h)
        qf = mkfont(self.bold, int(self.W * 0.16))
        d.text((pad // 2, -int(self.W * 0.02)), "“", font=qf, fill=hex_rgba(self.t["accent"], 255))
        y = pad; x = pad + int(self.W * 0.05)
        for ln in lines:
            d.text((x, y), ln, font=font, fill=hex_rgba(self.t["fg"], 255)); y += lh
        if by:
            d.text((x, y + 6), by, font=bf, fill=hex_rgba(self.t["sub"], 255))
        return im

    def lower(self, c):
        pad = int(self.W * 0.035)
        w = int(self.W * 0.62)
        nf = mkfont(self.bold, int(self.W * 0.052)); tf = mkfont(self.reg, int(self.W * 0.034))
        h = 2 * pad + int(self.W * 0.052 * 1.3) + (int(self.W * 0.034 * 1.4) if c.get("title") else 0)
        im, d = self.panel(w, h)
        bar = int(self.W * 0.01)
        d.rounded_rectangle([0, 0, bar, h - 1], radius=bar // 2, fill=hex_rgba(self.t["accent"], 255))
        d.text((pad + bar, pad), c["name"], font=nf, fill=hex_rgba(self.t["fg"], 255))
        if c.get("title"):
            d.text((pad + bar, pad + int(self.W * 0.052 * 1.3)), c["title"], font=tf, fill=hex_rgba(self.t["sub"], 255))
        return im

    def draw(self, c):
        return {"point": self.point, "title": self.title, "stat": self.stat, "quote": self.quote, "lower": self.lower}[c["type"]](c)


def load(p):
    data = json.loads(Path(p).read_text(encoding="utf-8"))
    return data.get("meta", {}), data["cards"]


def place(c, W, H, ph, zn):
    """決定圖卡左上角 (x, y)。預設在下方（字幕之上）；lower 型靠左。"""
    pos = c.get("position", "lower")
    x = int(W * 0.07) if c["type"] == "lower" else int(W * 0.07)
    if pos == "top":
        y = int(H * 0.07)
    elif pos == "center":
        y = int((H - ph) / 2)
    else:
        y = int(H * zn["limit"]) - ph
    return x, y


def segments_text(p):
    if not p:
        return ""
    return "".join(s.get("zh", "") for s in json.loads(Path(p).read_text(encoding="utf-8")))


def cmd_check(a, quiet=False):
    from calendar_tools import scan_terms
    meta, cards = load(a.cards)
    W, H, fps, dur = probe(a.video)
    zn = zones(W, H)
    P = Painter(W, H, meta.get("theme", "ink"))
    transcript = re.sub(r"\s+", "", segments_text(getattr(a, "segments", None)))
    cfg = json.loads((HERE.parents[1] / "content-calendar" / "scripts" / "flag_terms.json").read_text(encoding="utf-8"))
    errors, warns = [], []
    if len(cards) > 10:
        warns.append(f"共 {len(cards)} 張圖卡。太多會干擾觀看，建議 10 張內，且每張停留至少 2 秒")
    boxes = []
    for i, c in enumerate(cards, 1):
        tag = f"第 {i} 張（{c.get('type')}）"
        if c.get("type") not in TYPES:
            errors.append(f"{tag}：type 必須是 {sorted(TYPES)}"); continue
        if c.get("position", "lower") not in POSITIONS:
            errors.append(f"{tag}：position 必須是 {sorted(POSITIONS)}")
        s, e = c.get("start"), c.get("end")
        if not isinstance(s, (int, float)) or not isinstance(e, (int, float)) or s < 0 or e <= s:
            errors.append(f"{tag}：start／end 必須是秒數，且 end > start"); continue
        if e > dur + 0.05:
            errors.append(f"{tag}：end={e} 超過影片長度 {dur:.1f} 秒")
        if e - s < 1.2:
            warns.append(f"{tag}：只停留 {e - s:.1f} 秒，觀眾可能來不及讀")
        text_all = " ".join(str(c.get(k, "")) for k in ("text", "number", "name", "title", "label", "by"))
        if any("【待補】" in str(v) for v in c.values()):
            errors.append(f"{tag}：仍有【待補】")
            continue
        try:
            im = P.draw(c)
        except KeyError as ex:
            errors.append(f"{tag}：缺少欄位 {ex}"); continue
        x, y = place(c, W, H, im.height, zn)
        boxes.append((i, s, e, y, y + im.height))
        if y < 0:
            warns.append(f"{tag}：圖卡太高，超出畫面上緣，請縮短文字")
        if c.get("position", "lower") == "lower" and y + im.height > H * zn["limit"] + 2:
            warns.append(f"{tag}：圖卡可能壓到字幕區")
        if c.get("position") == "center":
            warns.append(f"{tag}：置中的圖卡很可能遮到講者的臉，請先用 preview 看畫面")
        if c.get("position") == "top":
            warns.append(f"{tag}：置頂的圖卡可能遮到講者的頭，請先用 preview 看畫面")
        if c["type"] == "stat" and len(str(c.get("number", ""))) > 8:
            warns.append(f"{tag}：number「{c['number']}」太長，大字卡建議 8 字內（例如「3 件事」「30 分鐘」），長句請改用 point 或 title")
        if c["type"] == "lower":
            warns.append(f"{tag}：名稱與頭銜由使用者提供，**請確認屬實**，不可編造身分或證照")
        if c["type"] == "quote" and "客人" in text_all:
            warns.append(f"{tag}：引用客人的話，請確認已匿名並取得同意")
        # 圖卡上的數字必須是影片裡說過的
        if transcript:
            for n in sorted(set(NUM.findall(text_all))):
                n = re.sub(r"\s+", "", n)
                if n and n not in transcript:
                    warns.append(f"{tag}：圖卡上的「{n}」沒有出現在影片字幕稿裡。請確認是使用者說過的，或刪掉")
        for cat, term, note in scan_terms({"topic": text_all}, cfg):
            warns.append(f"{tag}：用語提示：命中「{term}」［{cat}］：{note}（只是提示，不是法律判斷）")
    for (i, s1, e1, t1, b1) in boxes:
        for (j, s2, e2, t2, b2) in boxes:
            if j > i and s1 < e2 and s2 < e1 and not (b1 <= t2 or b2 <= t1):
                warns.append(f"第 {i} 與第 {j} 張在同一時間重疊在同一個位置，請錯開時間或位置")
    if quiet:
        return errors, warns
    print(f"影片 {W}x{H}，{dur:.1f} 秒，{fps:.0f} fps｜圖卡 {len(cards)} 張｜字幕安全區：圖卡底邊不超過畫面高度的 {zn['limit']:.0%}")
    for t, rows in (("錯誤", errors), ("警告", warns)):
        if rows:
            print(f"\n{t}（{len(rows)}）"); [print("  -", r) for r in rows]
    if not (errors or warns):
        print("\n沒有發現問題。")
    print("\n提醒：這個檢查看不到畫面。請用 preview 輸出畫面，**自己看過圖卡有沒有擋到講者的臉**。")
    sys.exit(1 if errors else 0)


def build_inputs(a, tmp):
    meta, cards = load(a.cards)
    W, H, fps, dur = probe(a.video)
    zn = zones(W, H)
    P = Painter(W, H, meta.get("theme", "ink"))
    items = []
    for i, c in enumerate(cards):
        im = P.draw(c)
        png = tmp / f"card_{i:02d}.png"
        im.save(png)
        x, y = place(c, W, H, im.height, zn)
        items.append({"png": png, "x": x, "y": y, "s": float(c["start"]), "e": float(c["end"]), "c": c})
    return W, H, fps, dur, items


def cmd_render(a):
    errors, _ = cmd_check(a, quiet=True)
    if errors:
        sys.exit("有錯誤，請先修正（可用 check 查看）：\n  - " + "\n  - ".join(errors))
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        W, H, fps, dur, items = build_inputs(a, tmp)
        if not items:
            sys.exit("沒有圖卡可疊加")
        inputs, parts = [], []
        for i, it in enumerate(items):
            d = it["e"] - it["s"]
            inputs += ["-loop", "1", "-framerate", f"{fps:.3f}", "-t", f"{d:.3f}", "-i", str(it["png"])]
            parts.append(
                f"[{i + 1}:v]format=rgba,fade=t=in:st=0:d={FADE_IN}:alpha=1,fade=t=out:st={max(0, d - FADE_OUT):.3f}:d={FADE_OUT}:alpha=1,"
                f"setpts=PTS+{it['s']:.3f}/TB[c{i}]"
            )
        prev = "0:v"
        for i, it in enumerate(items):
            slide = int(H * SLIDE)
            y = f"{it['y']}+(1-min(1,max(0,(t-{it['s']:.3f})/{FADE_IN})))*{slide}"
            out = f"v{i}"
            parts.append(f"[{prev}][c{i}]overlay=x={it['x']}:y='{y}':enable='between(t,{it['s']:.3f},{it['e']:.3f})':eof_action=pass[{out}]")
            prev = out
        graph = ";\n".join(parts)
        gfile = tmp / "graph.txt"
        gfile.write_text(graph, encoding="utf-8")
        tail = ["-map", f"[{prev}]", "-map", "0:a?", "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-c:a", "copy", str(a.out)]
        base = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(a.video)] + inputs
        r = subprocess.run(base + ["-/filter_complex", str(gfile)] + tail, capture_output=True, text=True)
        if r.returncode != 0:
            r = subprocess.run(base + ["-filter_complex_script", str(gfile)] + tail, capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit("ffmpeg 失敗：\n" + r.stderr[-1200:])
    print(f"完成：{a.out}（{len(items)} 張圖卡）。請自己播放看過，確認圖卡沒有擋到講者。")


def cmd_preview(a):
    with tempfile.TemporaryDirectory() as td:
        W, H, fps, dur, items = build_inputs(a, Path(td))
        out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
        for i, it in enumerate(items, 1):
            t = (it["s"] + it["e"]) / 2
            base = Image.open(extract(a.video, t, Path(td) / f"f{i}.png")).convert("RGBA")
            card = Image.open(it["png"]).convert("RGBA")
            base.alpha_composite(card, (it["x"], it["y"]))
            base.convert("RGB").save(out / f"preview_{i:02d}.png")
        print(f"已輸出 {len(items)} 張預覽到 {out}（在每張圖卡中段的畫面）。請看圖卡有沒有擋住講者的臉。")


def extract(video, t, path):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1", str(path)], check=True)
    return path


def cmd_init(a):
    data = {"meta": {"theme": "ink"}, "cards": [
        {"type": "point", "start": 0.0, "end": 0.0, "label": "重點", "text": "【待補】", "position": "lower"}]}
    Path(a.out).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已建立 {a.out}。請讀字幕稿（segments.json），和使用者一起挑 3 到 6 個值得強調的時刻。")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("init"); i.add_argument("-o", "--out", default="cards.json"); i.add_argument("--size"); i.set_defaults(f=cmd_init)
    for name, fn in (("check", cmd_check), ("preview", cmd_preview), ("render", cmd_render)):
        s = sub.add_parser(name); s.add_argument("cards"); s.add_argument("--video", required=True); s.add_argument("--segments")
        if name != "check":
            s.add_argument("-o", "--out", required=True)
        s.set_defaults(f=fn)
    a = ap.parse_args(); a.f(a)


if __name__ == "__main__":
    main()
