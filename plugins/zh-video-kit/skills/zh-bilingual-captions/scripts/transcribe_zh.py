#!/usr/bin/env python3
"""中文語音轉錄：影片 -> 逐字稿 transcript.json（flat word array，與 hyperframes 格式相容）。

用法：python transcribe_zh.py input.mp4 -o work/ [--model small] [--lang zh]

注意：不可用 *.en 模型，會把中文翻成英文。
"""
import argparse, json, subprocess, sys, tempfile
from pathlib import Path

TRAD_PROMPT = "以下是繁體中文口語逐字稿，請完整保留口語贅詞與重複，不要修飾：嗯，呃，那個，就是，我我想說，然後然後。"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("-o", "--out", default="work")
    ap.add_argument("--model", default="small", help="tiny/base/small/medium/large-v3，不可帶 .en")
    ap.add_argument("--lang", default="zh")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--hotwords", default="", help="專有名詞提示，空白分隔，例如 \"Claude Code HeyGen\"")
    ap.add_argument("--no-verbatim", action="store_true", help="不要求保留贅詞（純字幕、不剪片時可用）")
    args = ap.parse_args()

    if args.model.endswith(".en"):
        sys.exit("錯誤：.en 模型會把中文翻成英文，請改用 small / medium。")

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit("缺少套件，請先執行：pip install faster-whisper opencc-python-reimplemented")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    wav = out / "audio.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", args.video, "-vn", "-ac", "1", "-ar", "16000", str(wav)],
        check=True,
    )

    def run(device, compute):
        model = WhisperModel(args.model, device=device, compute_type=compute)
        segs, inf = model.transcribe(
            str(wav),
            language=args.lang,
            word_timestamps=True,
            initial_prompt=("以下是繁體中文的句子，請使用台灣習慣用語與標點。" if args.no_verbatim else TRAD_PROMPT),
            hotwords=args.hotwords or None,
            vad_filter=True,
        )
        return list(segs), inf  # 轉成 list 才會真的執行，GPU 問題才會在這裡浮現

    try:
        segments, info = run(args.device, "auto")
    except RuntimeError as e:
        if args.device == "cpu":
            raise
        print(f"提醒：GPU 無法使用（{str(e)[:80]}），改用 CPU，速度會較慢。", file=sys.stderr)
        segments, info = run("cpu", "int8")

    conv = None
    try:
        from opencc import OpenCC
        conv = OpenCC("s2twp")  # 簡體 -> 台灣繁體（含慣用詞）
    except ImportError:
        print("提醒：未安裝 opencc，若辨識結果含簡體字將不會轉換。", file=sys.stderr)

    words = []
    for seg in segments:
        for w in seg.words or []:
            text = w.word.strip()
            if not text:
                continue
            if conv:
                text = conv.convert(text)
            item = {"text": text, "start": round(w.start, 3), "end": round(w.end, 3)}
            item["sp"] = w.word.startswith(" ")  # Whisper 的詞界，英文單字被切成子詞時靠它判斷要不要補空白
            words.append(item)

    (out / "transcript.json").write_text(json.dumps(words, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"完成：{len(words)} 個詞 -> {out / 'transcript.json'}（偵測語言 {info.language}，機率 {info.language_probability:.2f}）")


if __name__ == "__main__":
    main()
