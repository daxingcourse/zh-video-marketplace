#!/usr/bin/env python3
"""把長錄音的逐字稿切成帶時間碼的段落（B01、B02…），供 Claude 萃取觀點、拆題，
並讓每個內容項目都能回頭引用「錄音的哪一段」。

輸入：transcript_zh 產生的 transcript.json（flat word array: text/start/end）
輸出：outline.md（給人與 Claude 讀）、outline.json（給程式用）

用法：python outline_transcript.py work/transcript.json -o work/ [--target 75] [--min-gap 0.5]
  --target  每段目標秒數（在最近的停頓處切開）
  --min-gap 視為可切的最小停頓秒數
"""
import argparse, json, re
from pathlib import Path

SENT_END = "。？！?!"


def mmss(t):
    t = int(t)
    return f"{t // 60:02d}:{t % 60:02d}"


def join(tokens):
    out, prev = "", ""
    for t in tokens:
        text, sp = t["text"], t.get("sp")
        if prev and re.match(r"[A-Za-z0-9]", text[:1]) and re.match(r"[A-Za-z0-9]", prev[-1:]):
            if sp is True or (sp is None and (len(prev) > 1 or len(text) > 1)):
                out += " "
        out += text
        prev = text
    return out


def build(words, target, min_gap):
    blocks, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        if nxt is None:
            break
        dur = w["end"] - cur[0]["start"]
        gap = nxt["start"] - w["end"]
        ends_sentence = w["text"].strip()[-1:] in SENT_END
        if dur >= target and (gap >= min_gap or ends_sentence):
            blocks.append(cur); cur = []
    if cur:
        blocks.append(cur)
    # 太短的尾段併回前一段
    if len(blocks) > 1 and blocks[-1][-1]["end"] - blocks[-1][0]["start"] < target * 0.3:
        blocks[-2].extend(blocks.pop())
    return blocks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("transcript")
    ap.add_argument("-o", "--out", default="work")
    ap.add_argument("--target", type=float, default=75)
    ap.add_argument("--min-gap", type=float, default=0.5)
    a = ap.parse_args()

    words = [w for w in json.loads(Path(a.transcript).read_text(encoding="utf-8")) if w["text"].strip()]
    if not words:
        raise SystemExit("逐字稿是空的")
    blocks = build(words, a.target, a.min_gap)
    items = []
    for n, b in enumerate(blocks, 1):
        items.append({"id": f"B{n:02d}", "start": round(b[0]["start"], 2), "end": round(b[-1]["end"], 2), "text": join(b)})

    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    (out / "outline.json").write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    total = words[-1]["end"]
    lines = [f"# 錄音段落（共 {len(items)} 段，總長 {mmss(total)}）", ""]
    for it in items:
        lines += [f"## {it['id']}  {mmss(it['start'])}–{mmss(it['end'])}", it["text"], ""]
    (out / "outline.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"完成：{len(items)} 段 -> {out / 'outline.md'}、{out / 'outline.json'}")


if __name__ == "__main__":
    main()
