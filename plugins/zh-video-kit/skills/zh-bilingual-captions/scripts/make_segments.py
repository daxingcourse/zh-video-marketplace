#!/usr/bin/env python3
"""把逐字稿斷成字幕句：transcript.json -> segments.json + zh.srt

斷句規則（台灣字幕習慣）：
  1. 遇到句末標點（。？！）一定斷
  2. 遇到逗號類標點，且目前已累積 >= soft 字時斷
  3. 詞與詞之間停頓 > gap 秒時斷
  4. 一行超過 max 字強制斷
  5. 顯示時去掉標點（？！保留）

用法：python make_segments.py work/transcript.json -o work/ [--max 16] [--soft 3] [--gap 0.6]
"""
import argparse, json, re
from pathlib import Path

END_PUNCT = "。？！?!…"
SOFT_PUNCT = "，、；,;：:"
KEEP_PUNCT = "？！?!"


def join_tokens(tokens):
    """tokens 可為字串或 {text, sp}。中文直接相連；英數字詞界優先看 Whisper 的 sp 標記，
    沒有標記時才用長度推測（單字元 token 視為字母碎片，不補空白）。"""
    out, prev = "", ""
    for t in tokens:
        text, sp = (t["text"], t.get("sp")) if isinstance(t, dict) else (t, None)
        if (
            prev
            and re.match(r"[A-Za-z0-9]", text[:1])
            and re.match(r"[A-Za-z0-9]", prev[-1:])
        ):
            if sp is True or (sp is None and (len(prev) > 1 or len(text) > 1)):
                out += " "
        out += text
        prev = text
    return out


def width(text):
    """顯示寬度：全形字 1，半形英數 0.5。"""
    return sum(1 if ord(c) > 0x2E80 else 0.5 for c in text)


def clean_display(text):
    text = re.sub(r"[，、；,;：:。…]", " ", text)
    text = re.sub(r"[「」『』（）()《》]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    # 中文字之間的空白是標點留下的，移除；英數字之間保留
    text = re.sub(r"(?<=[一-鿿]) (?=[一-鿿])", "", text)
    # 台灣排版：中文與英數字之間留一個半形空白
    text = re.sub(r"(?<=[一-鿿])(?=[A-Za-z0-9])|(?<=[A-Za-z0-9])(?=[一-鿿])", " ", text)
    return text


def segment(words, max_chars, soft, gap, soft_gap=0.25):
    segs, buf = [], []

    def flush(n=None):
        """送出 buf 前 n 個詞（預設全部），其餘留在 buf。"""
        n = len(buf) if n is None else n
        if not n:
            return
        part = buf[:n]
        disp = clean_display(join_tokens(part))
        if disp:
            segs.append({"start": part[0]["start"], "end": part[-1]["end"], "zh": disp})
        del buf[:n]

    for i, w in enumerate(words):
        if buf and w["start"] - buf[-1]["end"] > gap:
            flush()
        buf.append(w)
        cur = join_tokens(buf)
        plain_len = width(clean_display(cur))
        last = w["text"].rstrip()[-1:] if w["text"].strip() else ""
        if last and last in END_PUNCT:
            flush()
        elif last and last in SOFT_PUNCT and plain_len >= soft and (
            plain_len >= 6 or i + 1 >= len(words) or words[i + 1]["start"] - w["end"] >= soft_gap
        ):
            flush()  # 逗號後沒有真的停頓（例如口吃剪掉後殘留的逗號）且句子還短，就不斷
        elif plain_len >= max_chars:
            # 太長：優先退回最近的逗號處斷開，沒有逗號才硬切
            for k in range(len(buf) - 2, -1, -1):
                if buf[k]["text"].strip()[-1:] in SOFT_PUNCT and width(clean_display(join_tokens(buf[: k + 1]))) >= soft:
                    flush(k + 1)
                    break
            else:
                flush()
    flush()

    # 太短的尾巴（<=2 字）併回前一句，避免孤字
    merged = []
    for s in segs:
        if merged and len(s["zh"]) <= 2 and s["start"] - merged[-1]["end"] < gap:
            merged[-1]["zh"] += s["zh"]
            merged[-1]["end"] = s["end"]
        else:
            merged.append(s)
    for n, s in enumerate(merged, 1):
        s["id"] = n
    return merged


def ts(sec):
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("transcript")
    ap.add_argument("-o", "--out", default="work")
    ap.add_argument("--max", type=int, default=16)
    ap.add_argument("--soft", type=int, default=3)
    ap.add_argument("--gap", type=float, default=0.6)
    ap.add_argument("--glossary", help="校正表 JSON：{\"口物\":\"口誤\"}，斷句後自動替換已知誤辨")
    ap.add_argument("--soft-gap", type=float, default=0.25, help="逗號後至少停頓幾秒才斷句（句子已夠長時不受限）")
    a = ap.parse_args()

    words = json.loads(Path(a.transcript).read_text(encoding="utf-8"))
    segs = segment(words, a.max, a.soft, a.gap, a.soft_gap)
    if a.glossary:
        gl = json.loads(Path(a.glossary).read_text(encoding="utf-8"))
        n = 0
        for sg in segs:
            for wrong, right in gl.items():
                if wrong in sg["zh"]:
                    sg["zh"] = sg["zh"].replace(wrong, right); n += 1
        print(f"校正表：套用 {n} 處替換")

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "segments.json").write_text(json.dumps(segs, ensure_ascii=False, indent=1), encoding="utf-8")
    srt = "\n".join(f"{s['id']}\n{ts(s['start'])} --> {ts(s['end'])}\n{s['zh']}\n" for s in segs)
    (out / "zh.srt").write_text(srt, encoding="utf-8")
    print(f"完成：{len(segs)} 句 -> {out / 'segments.json'}、{out / 'zh.srt'}")


if __name__ == "__main__":
    main()
