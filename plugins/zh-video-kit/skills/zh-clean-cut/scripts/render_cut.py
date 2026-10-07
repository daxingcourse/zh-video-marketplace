#!/usr/bin/env python3
"""依 cut_plan.json 剪片，輸出剪後影片，並產出時間軸重新對齊的逐字稿。

只套用 auto=true 的項目。輸出：
  <out>.mp4                 剪後影片
  transcript.cut.json       剪後時間軸的逐字稿（可直接餵給 zh-bilingual-captions）

用法：python render_cut.py input.mp4 work/cut_plan.json work/transcript.json -o output.mp4
      [--min-seg 0.12] [--fade 0.01] [--crf 18] [--dry-run]
"""
import argparse, json, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import audio_utils  # noqa: E402


def merge(intervals):
    out = []
    for s, e in sorted(intervals):
        if out and s <= out[-1][1] + 1e-6:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out


def keep_segments(duration, cuts, min_seg):
    removed = merge([(c["start"], c["end"]) for c in cuts if c.get("auto")])
    keep, pos = [], 0.0
    for s, e in removed:
        s, e = max(0.0, s), min(duration, e)
        if s > pos:
            keep.append([pos, s])
        pos = max(pos, e)
    if pos < duration:
        keep.append([pos, duration])
    return [k for k in keep if k[1] - k[0] >= min_seg], removed


def remap(words, removed):
    """舊時間 -> 新時間：減去該時間點之前被剪掉的總長。"""
    def shift(t):
        d = 0.0
        for s, e in removed:
            if e <= t:
                d += e - s
            elif s < t:
                d += t - s
        return round(t - d, 3)

    out = []
    for w in words:
        mid = (w["start"] + w["end"]) / 2
        if any(s <= mid < e for s, e in removed):
            continue  # 這個詞被剪掉了
        out.append({**w, "start": shift(w["start"]), "end": shift(w["end"])})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("plan")
    ap.add_argument("transcript")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--min-seg", type=float, default=0.12)
    ap.add_argument("--fade", type=float, default=0.01, help="每段音訊淡入淡出秒數，避免接點爆音")
    ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--audio", help="audio.wav：提供時，所有剪點先貼齊到真實靜音處（強烈建議）")
    ap.add_argument("--no-snap", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    plan = json.loads(Path(a.plan).read_text(encoding="utf-8"))
    if a.audio and not a.no_snap:
        rms = audio_utils.load_rms(a.audio)
        sils = audio_utils.silences(rms, audio_utils.threshold(rms))
        moved = 0
        for c in plan["cuts"]:
            if not c.get("auto"):
                continue
            for k in ("start", "end"):
                new, how = audio_utils.snap(c[k], rms, sils)
                if abs(new - c[k]) > 0.02:
                    moved += 1
                    print(f"  貼齊 {c.get('kind')} {k}: {c[k]:.2f} -> {new:.2f}（{how}）")
                c[k] = round(new, 3)
        print(f"剪點校正：{moved} 個邊界依波形調整")
    elif not a.audio:
        print("提醒：未提供 --audio，剪點直接使用詞時間戳，可能吃字或剪不乾淨")
    keep, removed = keep_segments(plan["duration"], plan["cuts"], a.min_seg)
    if not keep:
        sys.exit("錯誤：所有內容都被剪掉了，請檢查 cut_plan.json。")
    new_len = sum(e - s for s, e in keep)
    print(f"保留 {len(keep)} 段，{plan['duration']:.1f}s -> {new_len:.1f}s（剪掉 {plan['duration']-new_len:.1f}s）")

    words = json.loads(Path(a.transcript).read_text(encoding="utf-8"))
    out_t = Path(a.out).with_name("transcript.cut.json")
    out_t.write_text(json.dumps(remap(words, removed), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> {out_t}")
    if a.dry_run:
        return

    parts, labels = [], []
    for i, (s, e) in enumerate(keep):
        f = min(a.fade, (e - s) / 3)
        parts.append(f"[0:v]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS[v{i}]")
        parts.append(
            f"[0:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:d={f:.3f},afade=t=out:st={e-s-f:.3f}:d={f:.3f}[a{i}]"
        )
        labels.append(f"[v{i}][a{i}]")
    parts.append("".join(labels) + f"concat=n={len(keep)}:v=1:a=1[v][a]")

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(";\n".join(parts))
        script = f.name
    base = ["ffmpeg", "-y", "-loglevel", "error", "-i", a.video]
    tail = ["-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", str(a.crf), "-preset", "medium",
            "-c:a", "aac", "-b:a", "192k", a.out]
    try:
        # 新版 ffmpeg 用 -/filter_complex 讀檔；舊版用 -filter_complex_script
        r = subprocess.run(base + ["-/filter_complex", script] + tail, capture_output=True, text=True)
        if r.returncode != 0:
            r = subprocess.run(base + ["-filter_complex_script", script] + tail, capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit("ffmpeg 失敗：\n" + r.stderr[-1500:])
    finally:
        Path(script).unlink(missing_ok=True)
    print(f"完成：{a.out}")


if __name__ == "__main__":
    main()
