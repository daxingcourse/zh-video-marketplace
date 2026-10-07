#!/usr/bin/env python3
"""把 bilingual.ass 燒進影片。跨平台（Windows／macOS／Linux），不需要 bash。

用法：python burn.py input.mp4 work/bilingual.ass output.mp4 [字型資料夾]

- 沒指定字型資料夾時，使用隨套件附的開源字型（Noto Sans TC，SIL OFL，見 ../fonts）。
- 在字幕檔所在資料夾內執行 ffmpeg，避開 Windows 路徑中冒號與反斜線的跳脫問題。
"""
import os, subprocess, sys
from pathlib import Path


def fonts_arg(fonts_dir, cwd):
    """產生 ass 濾鏡的 fontsdir 值。優先相對路徑；不同磁碟無法相對時，改用絕對路徑並跳脫冒號。"""
    try:
        rel = os.path.relpath(fonts_dir, cwd)
        if not os.path.isabs(rel):
            return rel.replace("\\", "/")
    except ValueError:
        pass  # Windows 上跨磁碟
    return str(fonts_dir).replace("\\", "/").replace(":", "\\:")


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    src, ass, out = (Path(p).resolve() for p in sys.argv[1:4])
    fonts = Path(sys.argv[4]).resolve() if len(sys.argv) > 4 and sys.argv[4] else Path(__file__).resolve().parent.parent / "fonts"
    if not ass.exists():
        sys.exit(f"找不到字幕檔：{ass}")
    if not src.exists():
        sys.exit(f"找不到影片：{src}")
    out.parent.mkdir(parents=True, exist_ok=True)

    vf = f"ass={ass.name}"
    if fonts.is_dir():
        vf += f":fontsdir={fonts_arg(fonts, ass.parent)}"
    else:
        print(f"提醒：找不到字型資料夾 {fonts}，將使用系統預設字型。", file=sys.stderr)

    r = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vf", vf, "-c:v", "libx264", "-crf", "18",
         "-preset", "medium", "-c:a", "copy", str(out)],
        cwd=str(ass.parent), capture_output=True, text=True,
    )
    if r.returncode != 0:
        sys.exit("ffmpeg 失敗：\n" + r.stderr[-800:])
    print(f"完成：{out}")


if __name__ == "__main__":
    main()
