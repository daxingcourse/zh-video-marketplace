#!/usr/bin/env python3
"""分析逐字稿，產生剪輯計畫 cut_plan.json 與供人／Claude 閱讀的 sentences.txt。

偵測四類候選：
  silence  詞與詞之間停頓過長（保留左右各 keep 秒，只剪中間）；頭尾靜音一併修短
  filler   贅詞。hard 自動剪；soft 只列入審核（auto=false）
  stutter  口吃／重複。2 字以上片段連續重複 -> 自動剪前面的；單字重複 -> 審核
  retake   不在此偵測，由 Claude 讀 sentences.txt 判斷後手動加入 cut_plan.json

用法：python analyze.py transcript.json --duration 95.3 -o work/
      [--gap 0.5] [--keep 0.15] [--fillers fillers.json]
"""
import argparse, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import audio_utils  # noqa: E402


PUNCT = set("，。、；：？！,.;:?!…「」『』（）()《》 　")
SUSPECT_AUTO = {"恩"}  # 「嗯」常被聽成這些字：單獨成詞時才視為贅詞
SUSPECT_REVIEW = {"二", "額", "餓", "阿", "啊"}


def build_text(words):
    """把 token 攤平成字元序列，保留每個字元屬於哪個 token。"""
    chars, owner = [], []
    for i, w in enumerate(words):
        for ch in w["text"].strip():
            if ch in PUNCT:
                continue  # 標點不參與比對，避免「我想我，想」這種被逗號隔開的口吃漏掉
            chars.append(ch)
            owner.append(i)
    return "".join(chars), owner


def span_times(words, owner, a, b):
    """字元區間 [a,b) 對應的時間範圍（以涵蓋到的 token 為準）。"""
    i, j = owner[a], owner[b - 1]
    return words[i]["start"], words[j]["end"], i, j


def detect_silence(words, duration, gap, keep):
    cuts = []
    if words:
        lead = words[0]["start"]
        if lead > keep + 0.1:
            cuts.append(dict(start=0.0, end=round(lead - keep, 3), kind="silence", auto=True, text="", reason="開頭靜音"))
        tail = duration - words[-1]["end"]
        if tail > keep + 0.1:
            cuts.append(dict(start=round(words[-1]["end"] + keep, 3), end=round(duration, 3), kind="silence", auto=True, text="", reason="結尾靜音"))
    for a, b in zip(words, words[1:]):
        g = b["start"] - a["end"]
        if g > gap:
            s, e = a["end"] + keep, b["start"] - keep
            if e - s > 0.05:
                cuts.append(dict(start=round(s, 3), end=round(e, 3), kind="silence", auto=True, text="", reason=f"停頓 {g:.2f}s"))
    return cuts


def detect_silence_audio(sils, duration, gap, keep):
    """由音訊波形偵測停頓（比詞時間戳準）。頭尾靜音一併修短。"""
    cuts = []
    for s, e in sils:
        if e - s < gap:
            continue
        head = s <= 0.02
        tail = e >= duration - 0.05
        a = 0.0 if head else s + keep
        b = duration if tail else e - keep
        if b - a > 0.05:
            why = "開頭靜音" if head else "結尾靜音" if tail else f"停頓 {e - s:.2f}s"
            cuts.append(dict(start=round(a, 3), end=round(b, 3), kind="silence", auto=True, text="", reason=why + "（波形）"))
    return cuts


def detect_fillers(words, text, owner, cfg):
    cuts = []
    for level, auto in (("hard", True), ("soft", False)):
        items = sorted(cfg[level], key=len, reverse=True)
        if not items:
            continue
        pat = re.compile("|".join(re.escape(x) for x in items))
        for m in pat.finditer(text):
            a, b = m.start(), m.end()
            s, e, i, j = span_times(words, owner, a, b)
            # token 比贅詞長（例如「那個人」被切成同一個 token）時風險高，降為審核
            covered = "".join(c for w in words[i : j + 1] for c in w["text"].strip() if c not in PUNCT)
            ok = auto and covered == m.group()
            ctx = text[max(0, a - 4) : min(len(text), b + 4)]
            cuts.append(dict(start=round(s, 3), end=round(e, 3), kind="filler", auto=ok, text=m.group(), reason=f"{level}｜前後文：{ctx}"))
    return cuts


def detect_suspect_fillers(words):
    """單獨成詞（前後有標點或停頓）的疑似語助詞。「二」「額」可能是正文，只列入審核。"""
    cuts = []
    for i, w in enumerate(words):
        raw = w["text"].strip()
        core = "".join(c for c in raw if c not in PUNCT)
        if len(core) != 1 or (core not in SUSPECT_AUTO and core not in SUSPECT_REVIEW):
            continue
        has_punct = raw != core
        prev_gap = w["start"] - words[i - 1]["end"] if i else 9
        prev_ends = i == 0 or words[i - 1]["text"].strip()[-1:] in PUNCT
        if not (has_punct or prev_gap > 0.2) or not prev_ends and prev_gap <= 0.2:
            continue
        ctx = "".join(x["text"].strip() for x in words[max(0, i - 3) : i + 4])
        cuts.append(dict(start=round(w["start"], 3), end=round(w["end"], 3), kind="filler",
                         auto=core in SUSPECT_AUTO, text=core,
                         reason=f"疑似語助詞被誤辨為「{core}」｜前後文：{ctx}"))
    return cuts


def detect_stutter(words, text, owner, legit):
    cuts = []
    # 2~4 字片段連續重複 >= 2 次：我想我想、我們我們
    for m in re.finditer(r"([一-鿿]{2,4})\1+", text):
        if m.group() in legit or m.group(1) * 2 in legit:
            continue
        unit = len(m.group(1))
        a, b = m.start(), m.end() - unit  # 保留最後一份
        s, e, *_ = span_times(words, owner, a, b)
        cuts.append(dict(start=round(s, 3), end=round(e, 3), kind="stutter", auto=True, text=m.group(), reason="片段重複，保留最後一次"))
    # 單字重複：我我、這這 -> 審核（對對對、看看等可能是正常用法）
    for m in re.finditer(r"([一-鿿])\1+", text):
        if m.group() in legit or any(m.group() in L for L in legit):
            continue
        if any(c["text"] == m.group() for c in cuts):
            continue
        a, b = m.start(), m.end() - 1
        s, e, *_ = span_times(words, owner, a, b)
        cuts.append(dict(start=round(s, 3), end=round(e, 3), kind="stutter", auto=False, text=m.group(), reason="單字重複，需看上下文"))
    return cuts


def sentences(words, gap=0.6):
    out, buf = [], []
    for w in words:
        if buf and w["start"] - buf[-1]["end"] > gap:
            out.append(buf); buf = []
        buf.append(w)
        if w["text"].strip()[-1:] in "。？！?!":
            out.append(buf); buf = []
    if buf:
        out.append(buf)
    return out


def dedupe(cuts):
    """去除互相重疊的候選：同範圍保留 auto 的、再保留先出現的。"""
    cuts = sorted(cuts, key=lambda c: (c["start"], not c["auto"]))
    kept = []
    for c in cuts:
        if kept and c["start"] < kept[-1]["end"] - 1e-6 and c["kind"] != "silence" and kept[-1]["kind"] != "silence":
            continue
        kept.append(c)
    for n, c in enumerate(kept, 1):
        c["id"] = n
    return kept


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("transcript")
    ap.add_argument("--duration", type=float, required=True, help="影片總秒數（ffprobe 取得）")
    ap.add_argument("-o", "--out", default="work")
    ap.add_argument("--gap", type=float, default=0.5, help="超過幾秒的停頓才剪")
    ap.add_argument("--keep", type=float, default=0.15, help="剪停頓時兩側保留秒數")
    ap.add_argument("--audio", help="16kHz 單聲道 wav（work/audio.wav）。提供時，停頓改由波形偵測，較準確")
    ap.add_argument("--thr", type=float, help="靜音能量門檻（預設自動）")
    ap.add_argument("--fillers", default=str(Path(__file__).parent.parent / "fillers.json"))
    a = ap.parse_args()

    words = [w for w in json.loads(Path(a.transcript).read_text(encoding="utf-8")) if w["text"].strip()]
    cfg = json.loads(Path(a.fillers).read_text(encoding="utf-8"))
    text, owner = build_text(words)

    cuts = []
    if a.audio:
        rms = audio_utils.load_rms(a.audio)
        thr = audio_utils.threshold(rms, a.thr)
        audio_sils = audio_utils.silences(rms, thr)
        print(f"波形分析：靜音門檻 {thr:.0f}，共 {len(audio_sils)} 段靜音")
        cuts += detect_silence_audio(audio_sils, a.duration, a.gap, a.keep)
    else:
        print("提醒：未提供 --audio，停頓改用詞時間戳判斷，誤差較大（可能吃字）")
        cuts += detect_silence(words, a.duration, a.gap, a.keep)
    cuts += detect_fillers(words, text, owner, cfg)
    cuts += detect_suspect_fillers(words)
    cuts += detect_stutter(words, text, owner, set(cfg.get("legit_double", [])))
    cuts = dedupe(cuts)

    if a.audio:
        # 邊界落在連續語流（附近沒有真實靜音）的剪點，時間戳誤差可能大於音節間隔，容易吃字：降為待審核
        for c in cuts:
            if c["kind"] == "silence" or not c["auto"]:
                continue
            hows = [audio_utils.snap(c[k], rms, audio_sils)[1] for k in ("start", "end")]
            if any(h != "silence" for h in hows):
                c["auto"] = False
                c["risk"] = "boundary_in_speech"
                c["reason"] += "｜⚠ 邊界在連續語流中，可能吃字，請聽過再決定"

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    plan = {"duration": a.duration, "cuts": cuts}
    (out / "cut_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")

    lines = []
    for n, s in enumerate(sentences(words), 1):
        t = ""
        for w in s:
            x = w["text"].strip()
            # 英文詞界看 Whisper 的 sp 標記；中英交界留一個空白方便閱讀
            if t and x[:1].isascii() and x[:1].isalnum() and (w.get("sp") or not t[-1].isascii()):
                t += " "
            elif t and t[-1].isascii() and t[-1].isalnum() and not x[:1].isascii():
                t += " "
            t += x
        lines.append(f"[{n:03}] {s[0]['start']:7.2f}-{s[-1]['end']:7.2f}  {t.strip()}")
    (out / "sentences.txt").write_text("\n".join(lines), encoding="utf-8")

    by = {}
    for c in cuts:
        k = (c["kind"], c["auto"])
        by[k] = by.get(k, 0) + 1
    removed = sum(c["end"] - c["start"] for c in cuts if c["auto"])
    print(f"候選 {len(cuts)} 個，自動剪約 {removed:.1f}s（原長 {a.duration:.1f}s）")
    for (k, auto), n in sorted(by.items()):
        print(f"  {k:8} {'自動' if auto else '待審核'}: {n}")
    print(f"-> {out/'cut_plan.json'}、{out/'sentences.txt'}")


if __name__ == "__main__":
    main()
