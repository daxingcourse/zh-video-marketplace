#!/usr/bin/env python3
"""在你自己的電腦上產生練習用口播影片 practice.mp4（使用系統內建中文語音，不含任何第三方錄音）。

  Windows：需要已安裝「Microsoft Hanhan」台灣中文語音（Windows 10/11 多數內建）
  macOS：使用 say -v Meijia（台灣中文語音；此路徑尚未實測）

用法：python make_practice.py
輸出：在你「目前所在的資料夾」產生 practice.mp4（直式 1080x1920，約 40 秒）與 script.txt
"""
import platform, shutil, subprocess, sys, tempfile
from pathlib import Path

OUT_DIR = Path.cwd()  # 寫到「目前所在資料夾」，不寫進套件本身（裝成外掛後套件資料夾不應被改動）
OUT = OUT_DIR / "practice.mp4"

# (文字, 之後停頓毫秒)。刻意放入：開頭停頓、贅詞、口吃、重錄、長停頓、英文名詞。
LINES = [
    ("大家好，歡迎來到我的頻道。", 1800),
    ("嗯，今天我想我想跟你分享三個剪片的小技巧。", 500),
    ("呃，第一個技巧，就是先把空白剪掉。", 600),
    ("第二個技巧，那個，要把口誤剪掉。", 700),
    ("第三個技巧，我我會用 Claude Code 幫我剪。", 1500),
    ("不對，重來。", 600),
    ("第三個技巧，是讓 Claude Code 幫我自動剪。", 2000),
    ("謝謝大家。", 0),
]


def windows_tts(wav):
    ssml = ['<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="zh-TW">']
    for text, pause in LINES:
        ssml.append(text)
        if pause:
            ssml.append(f'<break time="{pause}ms"/>')
    ssml.append("</speak>")
    ps = f"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {{ $s.SelectVoice('Microsoft Hanhan Desktop') }} catch {{ Write-Error '找不到 Microsoft Hanhan 語音'; exit 3 }}
$s.SetOutputToWaveFile('{wav}')
$s.SpeakSsml(@'
{chr(10).join(ssml)}
'@)
$s.Dispose()
"""
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("產生語音失敗：" + (r.stderr.strip() or "未知錯誤") +
                 "\n請到「設定 → 時間與語言 → 語音」安裝繁體中文（台灣）語音，或改用自己錄的影片。")


def mac_tts(wav):
    text = "".join(t + (f" [[slnc {p}]] " if p else "") for t, p in LINES)
    aiff = Path(wav).with_suffix(".aiff")
    r = subprocess.run(["say", "-v", "Meijia", "-o", str(aiff), text], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("產生語音失敗：" + r.stderr.strip())
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(aiff), str(wav)], check=True)


def main():
    if not shutil.which("ffmpeg"):
        sys.exit("找不到 ffmpeg，請先執行 zh-video-pipeline/scripts/doctor.py")
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "speech.wav"
        {"Windows": windows_tts, "Darwin": mac_tts}.get(platform.system(), lambda w: sys.exit("此系統尚無內建產生方式，請改用自己錄的影片（見 錄影測試腳本.md）"))(wav)
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0x1f2a44:s=1080x1920:r=30",
             "-i", str(wav), "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(OUT)],
            check=True,
        )
    (OUT_DIR / "script.txt").write_text("\n".join(t for t, _ in LINES), encoding="utf-8")
    print(f"完成：{OUT}\n逐字稿原文：{OUT_DIR / 'script.txt'}（轉錄結果應該與它相近，但不會完全相同）")


if __name__ == "__main__":
    main()
