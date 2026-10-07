#!/usr/bin/env python3
"""產生可貼給社群求助的支援報告 support_report.txt。

只收集：系統與版本、環境檢查結果、專案進度。**不包含**影片內容、逐字稿、檔名以外的任何內容。
會把使用者資料夾路徑與帳號名稱換成 ~ 。請在貼出前自己再看一遍。

用法：python support_report.py [專案資料夾]
"""
import getpass, platform, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sh(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace")
        return (r.stdout + r.stderr).strip()
    except Exception as e:  # noqa: BLE001
        return f"（執行失敗：{e}）"


def scrub(text):
    home = str(Path.home())
    user = getpass.getuser()
    for h in {home, home.replace("\\", "/")}:
        text = text.replace(h, "~")
    if user:
        text = re.sub(re.escape(user), "<user>", text, flags=re.I)
    return text


def main():
    proj = sys.argv[1] if len(sys.argv) > 1 else None
    parts = [
        ("系統", f"{platform.system()} {platform.release()} / Python {platform.python_version()}"),
        ("ffmpeg", sh(["ffmpeg", "-version"]).splitlines()[0] if sh(["ffmpeg", "-version"]) else "未安裝"),
        ("環境檢查", sh([sys.executable, str(HERE / "doctor.py")])),
    ]
    if proj:
        parts.append(("專案進度", sh([sys.executable, str(HERE / "pipeline.py"), "status", proj])))
        work = Path(proj) / "work"
        if work.exists():
            parts.append(("work 資料夾檔案", "\n".join(sorted(p.name for p in work.iterdir()))))
    body = "\n\n".join(f"## {k}\n{v}" for k, v in parts)
    out = Path("support_report.txt")
    out.write_text(scrub(body), encoding="utf-8")
    print(f"已產生 {out.resolve()}\n請先打開檢查內容，確認沒有不想公開的資訊，再貼到社群。")


if __name__ == "__main__":
    main()
