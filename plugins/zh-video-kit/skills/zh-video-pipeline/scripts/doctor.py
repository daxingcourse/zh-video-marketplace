#!/usr/bin/env python3
"""環境檢查（可選自動修復）。用法：python doctor.py [--fix] [--model small]

檢查：Python、ffmpeg、faster-whisper、opencc、Whisper 模型是否已下載、中文字型、GPU 狀態。
--fix 只會執行 pip install；不會安裝系統軟體，缺 ffmpeg 時給出安裝指令。
"""
import argparse, importlib.util, platform, shutil, subprocess, sys
from pathlib import Path

OK, WARN, BAD = "✅", "⚠️ ", "❌"


def has_module(name):
    return importlib.util.find_spec(name) is not None


def find_cjk_font():
    """字幕與輪播預設只用隨套件附的開源字型（Noto Sans TC），不退回系統字型。"""
    bundled = Path(__file__).resolve().parents[2] / "zh-bilingual-captions" / "fonts"
    reg, bold = bundled / "NotoSansTC-Regular.ttf", bundled / "NotoSansTC-Bold.ttf"
    return (str(bundled) + "（內附開源字型 Noto Sans TC）") if reg.exists() and bold.exists() else None


def model_cached(model):
    root = Path.home() / ".cache" / "huggingface" / "hub"
    return any(root.glob(f"models--*faster-whisper-{model}*")) if root.exists() else False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--model", default="small")
    a = ap.parse_args()

    problems, fixable = [], []

    v = sys.version_info
    if v >= (3, 9):
        print(f"{OK} Python {v.major}.{v.minor}.{v.micro}")
    else:
        print(f"{BAD} Python {v.major}.{v.minor}，需要 3.9 以上"); problems.append("python")

    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool):
            print(f"{OK} {tool}")
        else:
            print(f"{BAD} 找不到 {tool}")
            hint = {"Windows": "winget install Gyan.FFmpeg", "Darwin": "brew install ffmpeg"}.get(platform.system(), "sudo apt install ffmpeg")
            print(f"     安裝指令：{hint}")
            problems.append(tool)

    for mod, pip_name in (("faster_whisper", "faster-whisper"), ("opencc", "opencc-python-reimplemented")):
        if has_module(mod):
            print(f"{OK} {pip_name}")
        else:
            print(f"{BAD} 缺少 {pip_name}"); fixable.append(pip_name); problems.append(pip_name)

    if has_module("faster_whisper"):
        if model_cached(a.model):
            print(f"{OK} Whisper 模型 {a.model} 已下載")
        else:
            print(f"{WARN} Whisper 模型 {a.model} 尚未下載，第一次轉錄會自動下載（small 約 460MB，需要網路）")

    if has_module("PIL"):
        print(f"{OK} Pillow（輪播圖需要）")
    else:
        print(f"{WARN} 缺少 Pillow（只有「輪播圖產生器」需要）。需要時執行：pip install pillow")

    font = find_cjk_font()
    if font:
        print(f"{OK} 中文字型：{font}")
    else:
        print(f"{WARN} 找不到內附的開源字型（zh-bilingual-captions/fonts/ 內的 NotoSansTC-Regular.ttf 與 NotoSansTC-Bold.ttf）。請補回，或自備你有授權的字型並用 --font 指定")

    if has_module("ctranslate2"):
        try:
            import ctranslate2
            n = ctranslate2.get_cuda_device_count()
            if not n:
                print(f"{WARN} GPU：無 CUDA，使用 CPU（較慢，但可用）")
            else:
                import ctypes
                lib = "cublas64_12.dll" if platform.system() == "Windows" else "libcublas.so.12"
                try:
                    ctypes.CDLL(lib)
                    print(f"{OK} GPU：CUDA 可用")
                except OSError:
                    print(f"{WARN} GPU：偵測到顯示卡，但缺 CUDA 函式庫（{lib}），將自動使用 CPU（可用，只是較慢）")
        except Exception as e:  # noqa: BLE001
            print(f"{WARN} GPU 檢查失敗：{e}")

    if fixable and a.fix:
        print(f"\n執行：pip install {' '.join(fixable)}")
        r = subprocess.run([sys.executable, "-m", "pip", "install", *fixable])
        if r.returncode == 0:
            problems = [p for p in problems if p not in fixable]
        print("安裝完成，請重新執行 doctor.py 確認。")
    elif fixable:
        print(f"\n可自動修復：python doctor.py --fix（會執行 pip install {' '.join(fixable)}）")

    print("\n" + ("環境完整，可以開始。" if not problems else f"尚有 {len(problems)} 項未解決：{', '.join(problems)}"))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
