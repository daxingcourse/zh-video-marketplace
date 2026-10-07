#!/usr/bin/env python3
"""個人檔案（profile.json）讀寫工具。檔案存在使用者自己的電腦，不上傳。

位置：~/.zh-video-kit/profile.json（可用環境變數 ZH_VIDEO_KIT_HOME 改位置）

用法：
  python profile_tool.py path                      顯示檔案位置
  python profile_tool.py init                      建立預設檔（已存在則不覆蓋）
  python profile_tool.py show                      顯示全部內容
  python profile_tool.py get cut.gap               讀一個欄位
  python profile_tool.py set cut.gap 0.35          寫一個欄位（值用 JSON 格式）
  python profile_tool.py set hotwords '["Claude Code","HeyGen"]'
  python profile_tool.py add hotwords "地中海飲食"   對清單欄位追加一項（不重複）
  python profile_tool.py add glossary 口物=口誤      對字典欄位追加 key=value

每次修改前會把舊檔備份成 profile.json.bak，方便還原。
"""
import json, os, shutil, sys
from datetime import date
from pathlib import Path

DEFAULT = {
    "version": 1,
    "created": "",
    "role": "",
    "audience": "",
    "tone": "",
    "languages": {"source": "zh", "target": "en", "bilingual": True},
    "fillers_extra": [],
    "hotwords": [],
    "glossary": {},
    "cut": {"gap": 0.5, "keep": 0.15, "style": "自然"},
    "output": {"platform": "reels", "size": "1080x1920", "max_chars": 16},
    "level": "新手",
    "positioning": {},
    "consent": {"share_anonymous_feedback": False},
}


def home():
    return Path(os.environ.get("ZH_VIDEO_KIT_HOME") or Path.home() / ".zh-video-kit")


def path():
    return home() / "profile.json"


def load():
    p = path()
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def save(data):
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        shutil.copy2(p, p.with_suffix(".json.bak"))
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_in(d, dotted):
    for k in dotted.split("."):
        d = d[k]
    return d


def set_in(d, dotted, value):
    keys = dotted.split(".")
    for k in keys[:-1]:
        d = d.setdefault(k, {})
    d[keys[-1]] = value


def parse(v):
    try:
        return json.loads(v)
    except json.JSONDecodeError:
        return v


def main(argv):
    if not argv:
        sys.exit(__doc__)
    cmd = argv[0]
    if cmd == "path":
        print(path()); return
    if cmd == "init":
        if path().exists():
            print(f"已存在，未覆蓋：{path()}"); return
        d = json.loads(json.dumps(DEFAULT)); d["created"] = date.today().isoformat()
        save(d); print(f"已建立：{path()}"); return
    data = load()
    if data is None:
        sys.exit("尚未建立個人檔案，請先執行：python profile_tool.py init")
    if cmd == "show":
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif cmd == "get" and len(argv) == 2:
        try:
            print(json.dumps(get_in(data, argv[1]), ensure_ascii=False))
        except KeyError:
            sys.exit(f"沒有這個欄位：{argv[1]}")
    elif cmd == "set" and len(argv) == 3:
        set_in(data, argv[1], parse(argv[2])); save(data); print(f"已設定 {argv[1]}")
    elif cmd == "add" and len(argv) == 3:
        try:
            cur = get_in(data, argv[1])
        except KeyError:
            sys.exit(f"沒有這個欄位：{argv[1]}")
        if isinstance(cur, list):
            if argv[2] not in cur:
                cur.append(argv[2])
        elif isinstance(cur, dict) and "=" in argv[2]:
            k, v = argv[2].split("=", 1); cur[k] = v
        else:
            sys.exit("add 只能用在清單或字典欄位（字典請用 key=value）")
        save(data); print(f"已追加到 {argv[1]}")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
