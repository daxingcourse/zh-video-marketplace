#!/usr/bin/env python3
"""合併中文句與翻譯 -> bilingual.srt + bilingual.ass

translations.json 格式：{"1": "English line", "2": "..."}（key 為 segments.json 的 id）

用法：
  python merge_bilingual.py work/segments.json work/translations.json -o work/ \
      [--size 1080x1920] [--font "Noto Sans TC"] [--zh-size 60] [--en-size 38]
"""
import argparse, json, sys, textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from make_segments import ts  # noqa: E402


def ass_ts(sec):
    cs = int(round(sec * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02}:{s:02}.{cs:02}"


def wrap_en(text, width):
    return "\\N".join(textwrap.wrap(text.strip(), width=width)) or ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("segments")
    ap.add_argument("translations")
    ap.add_argument("-o", "--out", default="work")
    ap.add_argument("--size", default="1080x1920", help="影片解析度，直式 1080x1920、橫式 1920x1080")
    ap.add_argument("--font", default="Noto Sans TC")
    ap.add_argument("--zh-size", type=int)
    ap.add_argument("--en-size", type=int)
    ap.add_argument("--en-wrap", type=int, help="英文每行最多字元數")
    ap.add_argument("--margin-v", type=int, help="距離底部像素")
    a = ap.parse_args()

    w, h = (int(x) for x in a.size.lower().split("x"))
    vertical = h > w
    zh_size = a.zh_size or (64 if vertical else 54)
    en_size = a.en_size or (40 if vertical else 34)
    en_wrap = a.en_wrap or (34 if vertical else 60)
    margin_v = a.margin_v or (int(h * 0.18) if vertical else int(h * 0.08))

    segs = json.loads(Path(a.segments).read_text(encoding="utf-8"))
    trans = json.loads(Path(a.translations).read_text(encoding="utf-8"))

    missing = [s["id"] for s in segs if str(s["id"]) not in trans or not trans[str(s["id"])].strip()]
    if missing:
        sys.exit(f"錯誤：缺少翻譯的句子 id：{missing}")
    extra = [k for k in trans if int(k) not in {s["id"] for s in segs}]
    if extra:
        print(f"提醒：translations 內有不存在的 id：{extra}", file=sys.stderr)

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    srt_parts, events = [], []
    for s in segs:
        en = trans[str(s["id"])].strip()
        srt_parts.append(f"{s['id']}\n{ts(s['start'])} --> {ts(s['end'])}\n{s['zh']}\n{en}\n")
        text = (
            f"{{\\fs{zh_size}\\b1\\c&HFFFFFF&}}{s['zh']}"
            f"\\N{{\\fs{en_size}\\b0\\c&HDDDDDD&}}{wrap_en(en, en_wrap)}"
        )
        events.append(f"Dialogue: 0,{ass_ts(s['start'])},{ass_ts(s['end'])},Bi,,0,0,0,,{text}")

    (out / "bilingual.srt").write_text("\n".join(srt_parts), encoding="utf-8")

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Bi,{a.font},{zh_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,2,60,60,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    (out / "bilingual.ass").write_text(header + "\n".join(events) + "\n", encoding="utf-8-sig")
    print(f"完成：{len(segs)} 句 -> {out / 'bilingual.srt'}、{out / 'bilingual.ass'}")


if __name__ == "__main__":
    main()
