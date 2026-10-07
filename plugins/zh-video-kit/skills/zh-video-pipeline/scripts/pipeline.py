#!/usr/bin/env python3
"""口播影片一條龍：把三個子流程串成四個階段，每階段之間留給 Claude／使用者審核。

  prepare   轉錄 + 分析贅詞停頓      -> 產出 cut_plan.json、sentences.txt（停下來審核）
  cut       套用剪輯計畫             -> cut.mp4、transcript.cut.json、segments.json（停下來翻譯）
  finish    合併雙語、燒錄           -> final.mp4（需要 translations.json）
  status    顯示專案目前進度與下一步

專案資料夾結構：
  <project>/input.mp4（或用 --video 指定）  work/...  final.mp4
"""
import argparse, json, os, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAP = ROOT / "zh-bilingual-captions" / "scripts"
CUT = ROOT / "zh-clean-cut" / "scripts"


def run(*cmd):
    print("$", " ".join(str(c) for c in cmd))
    r = subprocess.run([str(c) for c in cmd])
    if r.returncode != 0:
        sys.exit(f"失敗（結束碼 {r.returncode}）：{cmd[1] if len(cmd) > 1 else cmd[0]}")


def duration(video):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


def load_profile(a):
    """讀個人檔案（~/.zh-video-kit/profile.json，或 ZH_VIDEO_KIT_HOME）。沒有或指定 --no-profile 就回傳空字典。"""
    if getattr(a, "no_profile", False):
        return {}
    home = Path(os.environ.get("ZH_VIDEO_KIT_HOME") or Path.home() / ".zh-video-kit")
    p = home / "profile.json"
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        print(f"使用個人檔案：{p}（加 --no-profile 可忽略）")
        return data
    except (json.JSONDecodeError, OSError) as e:
        print(f"提醒：個人檔案讀取失敗，已忽略（{e}）", file=sys.stderr)
        return {}


def merged_fillers(extra, work):
    """把個人口頭禪併入贅詞表。個人口頭禪一律放 soft（待審核），不自動剪，避免誤剪正文。"""
    base = json.loads((CUT.parent / "fillers.json").read_text(encoding="utf-8"))
    for w in extra:
        if w not in base["soft"] and w not in base["hard"]:
            base["soft"].append(w)
    out = work / "fillers.merged.json"
    out.write_text(json.dumps(base, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def resolve(a):
    proj = Path(a.project)
    proj.mkdir(parents=True, exist_ok=True)
    video = Path(a.video) if getattr(a, "video", None) else proj / "input.mp4"
    work = proj / "work"
    work.mkdir(exist_ok=True)
    return proj, video, work


def prepare(a):
    proj, video, work = resolve(a)
    if not video.exists():
        sys.exit(f"找不到影片：{video}")
    if video.resolve().parent != proj.resolve():
        shutil.copy2(video, proj / "input.mp4")
        video = proj / "input.mp4"
    P = load_profile(a)
    hotwords = a.hotwords or " ".join(P.get("hotwords", []))
    cmd = [sys.executable, CAP / "transcribe_zh.py", video, "-o", work, "--model", a.model]
    if hotwords:
        cmd += ["--hotwords", hotwords]
    if a.no_cut:
        cmd += ["--no-verbatim"]
    run(*cmd)
    if a.no_cut:
        # 不剪片：直接當作剪後逐字稿使用
        shutil.copy2(work / "transcript.json", work / "transcript.cut.json")
        shutil.copy2(video, work / "cut.mp4")
        print("\n已略過剪片。下一步：python pipeline.py cut", proj, "--skip-render")
        return
    cutcfg = P.get("cut", {})
    gap = a.gap if a.gap is not None else cutcfg.get("gap", 0.5)
    cmd = [sys.executable, CUT / "analyze.py", work / "transcript.json", "--duration", duration(video), "-o", work,
           "--gap", gap, "--keep", cutcfg.get("keep", 0.15), "--audio", work / "audio.wav"]
    if P.get("fillers_extra"):
        cmd += ["--fillers", merged_fillers(P["fillers_extra"], work)]
    run(*cmd)
    print(f"""
── 停下來審核 ──────────────────────────────────────────
1. 讀 {work/'transcript.json'} 抽查是否亂碼或幻聽
2. 審核 {work/'cut_plan.json'}：auto=false 的逐一判斷，改成 true 或保留
3. 讀 {work/'sentences.txt'} 找重錄，補進 cut_plan.json
完成後執行：python pipeline.py cut {proj}
""")


def cut(a):
    proj, video, work = resolve(a)
    if a.skip_render:
        pass
    else:
        if not (work / "cut_plan.json").exists():
            sys.exit("找不到 cut_plan.json，請先執行 prepare")
        run(sys.executable, CUT / "render_cut.py", proj / "input.mp4", work / "cut_plan.json",
            work / "transcript.json", "-o", work / "cut.mp4", "--audio", work / "audio.wav")
    P = load_profile(a)
    cmd = [sys.executable, CAP / "make_segments.py", work / "transcript.cut.json", "-o", work]
    if P.get("output", {}).get("max_chars"):
        cmd += ["--max", P["output"]["max_chars"]]
    if P.get("glossary"):
        g = work / "glossary.json"
        g.write_text(json.dumps(P["glossary"], ensure_ascii=False, indent=1), encoding="utf-8")
        cmd += ["--glossary", g]
    run(*cmd)
    print(f"""
── 停下來翻譯 ──────────────────────────────────────────
1. 讀 {work/'segments.json'}，校對中文（只改 zh，不動 id 與時間）
2. 寫出 {work/'translations.json'}：{{"1":"...","2":"..."}}，每個 id 一句
完成後執行：python pipeline.py finish {proj} --size 1080x1920
""")


def finish(a):
    proj, video, work = resolve(a)
    for f in ("segments.json", "translations.json"):
        if not (work / f).exists():
            sys.exit(f"缺少 {work / f}")
    run(sys.executable, CAP / "merge_bilingual.py", work / "segments.json", work / "translations.json",
        "-o", work, "--size", a.size)
    src = work / "cut_cards.mp4" if (work / "cut_cards.mp4").exists() else work / "cut.mp4"
    if src.name == "cut_cards.mp4":
        print("使用已疊加動態圖卡的影片：", src)
    cmd = [sys.executable, CAP / "burn.py", src, work / "bilingual.ass", proj / "final.mp4"]
    if a.fonts:
        cmd.append(a.fonts)
    run(*cmd)
    print(f"""
── 完成 ────────────────────────────────────────────────
成品：{proj/'final.mp4'}
請在 20%、50%、80% 處各截一張圖檢查字幕，並聽過剪輯接點。
""")


def status(a):
    proj, _, work = resolve(a)
    steps = [
        ("轉錄", work / "transcript.json"),
        ("剪輯計畫", work / "cut_plan.json"),
        ("剪後影片", work / "cut.mp4"),
        ("斷句", work / "segments.json"),
        ("翻譯", work / "translations.json"),
        ("雙語字幕", work / "bilingual.ass"),
        ("成品", proj / "final.mp4"),
    ]
    nxt = None
    for name, f in steps:
        ok = f.exists()
        print(("✅" if ok else "⬜"), name)
        if not ok and not nxt:
            nxt = name
    hints = {"轉錄": "prepare", "剪輯計畫": "prepare", "剪後影片": "cut", "斷句": "cut",
             "翻譯": "（由 Claude 寫 translations.json）", "雙語字幕": "finish", "成品": "finish"}
    print("\n下一步：", hints.get(nxt, "已全部完成") if nxt else "已全部完成")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare"); p.add_argument("project"); p.add_argument("--video")
    p.add_argument("--model", default="small"); p.add_argument("--hotwords", default="")
    p.add_argument("--gap", default=None, help="停頓門檻（秒）；不指定則用個人檔案，再不然 0.5")
    p.add_argument("--no-profile", action="store_true", help="忽略個人檔案")
    p.add_argument("--no-cut", action="store_true", help="只做字幕，不剪片")
    p.set_defaults(f=prepare)
    c = sub.add_parser("cut"); c.add_argument("project"); c.add_argument("--skip-render", action="store_true")
    c.add_argument("--no-profile", action="store_true", help="忽略個人檔案")
    c.set_defaults(f=cut)
    f = sub.add_parser("finish"); f.add_argument("project"); f.add_argument("--size", default="1080x1920")
    f.add_argument("--fonts", default=""); f.set_defaults(f=finish)
    s = sub.add_parser("status"); s.add_argument("project"); s.set_defaults(f=status)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
