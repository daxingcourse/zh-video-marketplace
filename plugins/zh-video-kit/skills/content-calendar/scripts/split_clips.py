#!/usr/bin/env python3
"""把「一次錄多支」的長影片，依你錄影時唸的「第 N 支」標記切成單支。

流程：
  1. suggest  由逐字稿找出「第 N 支」標記，產生切片草稿 clips.json（請人看過再切）
  2. cut      依 clips.json 切成單支影片，邊界貼齊真實靜音處

用法：
  python split_clips.py suggest transcript.json recording_order.json -o clips.json [--audio audio.wav] [--duration 秒]
  python split_clips.py cut video.mp4 clips.json -o clips/ [--audio audio.wav]

規則：
  - 同一個 N 唸了不只一次（例如講砸了重來），以**最後一次**為準；前面的嘗試不會進任何一支。
  - 標記本身（「第 N 支」）不會留在成品裡。
  - 找不到的編號會列出來，請人手動補時間。
"""
import argparse, json, re, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "zh-clean-cut" / "scripts"))
try:
    import audio_utils  # noqa: E402
except ImportError:
    audio_utils = None

PUNCT = set("，。、；：？！,.;:?!…「」『』（）()《》 　")
CN = {"零": 0, "〇": 0, "一": 1, "二": 2, "兩": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
PAT = re.compile(r"第([0-9]{1,3}|[零〇一二兩三四五六七八九十]{1,3})支")


def to_int(s):
    if s.isdigit():
        return int(s)
    if s == "十":
        return 10
    if s.startswith("十"):
        return 10 + CN.get(s[1:], 0)
    if "十" in s:
        a, b = s.split("十", 1)
        return CN.get(a, 0) * 10 + (CN.get(b, 0) if b else 0)
    return CN.get(s)


def find_markers(words):
    chars, owner = [], []
    for i, w in enumerate(words):
        for ch in w["text"].strip():
            if ch in PUNCT:
                continue
            chars.append(ch); owner.append(i)
    text = "".join(chars)
    found = []
    for m in PAT.finditer(text):
        n = to_int(m.group(1))
        if n is None:
            continue
        i, j = owner[m.start()], owner[m.end() - 1]
        found.append({"n": n, "start": words[i]["start"], "end": words[j]["end"]})
    return found


def find_isolated_numbers(words, min_gap=0.6):
    """語音辨識常把「第一支」轉成清單編號「1.」。找出前後都有停頓、單獨成詞的阿拉伯數字當作標記。
    只認阿拉伯數字：單獨的中文數字（例如把「呃」聽成的「二」）太容易誤判。"""
    found = []
    for i, w in enumerate(words):
        core = "".join(c for c in w["text"].strip() if c not in PUNCT)
        if not (core.isdigit() and len(core) <= 3):
            continue
        before = w["start"] - (words[i - 1]["end"] if i else -min_gap)
        after = (words[i + 1]["start"] - w["end"]) if i + 1 < len(words) else min_gap
        if before >= min_gap and after >= min_gap:
            found.append({"n": int(core), "start": w["start"], "end": w["end"], "how": "isolated"})
    return found


def suggest(a):
    words = [w for w in json.loads(Path(a.transcript).read_text(encoding="utf-8")) if w["text"].strip()]
    manifest = {m["n"]: m for m in json.loads(Path(a.order).read_text(encoding="utf-8"))}
    total = a.duration or words[-1]["end"]
    marks = find_markers(words)
    for m in find_isolated_numbers(words):
        if not any(abs(m["start"] - x["start"]) < 1.0 for x in marks):  # 已被「第 N 支」抓到就不重複
            marks.append(m)
    if not marks:
        sys.exit("逐字稿裡找不到任何「第 N 支」標記。請確認錄影時有唸，或改用手動指定時間（見 --help）。")

    rms = sils = None
    if a.audio and audio_utils:
        rms = audio_utils.load_rms(a.audio); sils = audio_utils.silences(rms, audio_utils.threshold(rms))

    def snap(t):
        return round(audio_utils.snap(t, rms, sils)[0], 3) if rms else round(t, 3)

    marks.sort(key=lambda m: m["start"])
    clips, warns = [], []
    last = {}
    for k, m in enumerate(marks):
        last[m["n"]] = k  # 同編號以最後一次為準
    for k, m in enumerate(marks):
        if m["n"] not in manifest:
            warns.append(f"標記「第 {m['n']} 支」不在錄製清單裡（可能是內容中提到，已忽略）"); continue
        if last[m["n"]] != k:
            warns.append(f"第 {m['n']} 支 在 {m['start']:.1f} 秒唸過，後來又唸一次，採用後面那次"); continue
        end = marks[k + 1]["start"] - 0.1 if k + 1 < len(marks) else total
        info = manifest[m["n"]]
        clips.append({"n": m["n"], "date": info["date"], "title": info["topic"],
                      "start": snap(m["end"] + 0.15), "end": snap(end), "marker": [m["start"], m["end"]]})
    clips.sort(key=lambda c: c["n"])
    got = {c["n"] for c in clips}
    for n, info in sorted(manifest.items()):
        if n not in got:
            warns.append(f"找不到「第 {n} 支」（{info['date']}《{info['topic']}》）的標記，請手動補 start／end")
    seq = [m["n"] for m in marks if m["n"] in manifest]
    if seq != sorted(seq):
        warns.append(f"標記出現順序與編號不一致：{seq}。請確認是否按清單順序錄製")
    for c in clips:
        if c["end"] - c["start"] < 3:
            warns.append(f"第 {c['n']} 支只有 {c['end']-c['start']:.1f} 秒，可能切錯了")
    Path(a.out).write_text(json.dumps(clips, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"草稿：{len(clips)} 支 -> {a.out}")
    for c in clips:
        print(f"  第 {c['n']} 支  {c['start']:7.2f}–{c['end']:7.2f}（{c['end']-c['start']:.1f} 秒）  {c['date']} {c['title']}")
    for w in warns:
        print("  ⚠", w)
    print("\n請聽過各支的開頭與結尾，確認沒切到內容，再執行 cut。")


def safe(s):
    return re.sub(r'[\\/:*?"<>|\s]+', "_", s).strip("_")[:30]


def cut(a):
    clips = json.loads(Path(a.clips).read_text(encoding="utf-8"))
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    rms = sils = None
    if a.audio and audio_utils:
        rms = audio_utils.load_rms(a.audio); sils = audio_utils.silences(rms, audio_utils.threshold(rms))
    for c in clips:
        s, e = c["start"], c["end"]
        if rms:
            s, e = audio_utils.snap(s, rms, sils)[0], audio_utils.snap(e, rms, sils)[0]
        if e - s <= 0.5:
            print(f"略過第 {c['n']} 支：長度不合理（{e-s:.2f} 秒）"); continue
        name = out / f"{c['n']:02d}_{c['date']}_{safe(c['title'])}.mp4"
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{s:.3f}", "-to", f"{e:.3f}", "-i", a.video,
                            "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-c:a", "aac", "-b:a", "192k", str(name)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"ffmpeg 失敗：{r.stderr[-400:]}")
        print(f"第 {c['n']} 支 -> {name.name}（{e-s:.1f} 秒）")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("suggest"); s.add_argument("transcript"); s.add_argument("order"); s.add_argument("-o", "--out", default="clips.json")
    s.add_argument("--audio"); s.add_argument("--duration", type=float); s.set_defaults(f=suggest)
    c = sub.add_parser("cut"); c.add_argument("video"); c.add_argument("clips"); c.add_argument("-o", "--out", default="clips")
    c.add_argument("--audio"); c.set_defaults(f=cut)
    a = ap.parse_args(); a.f(a)


if __name__ == "__main__":
    main()
