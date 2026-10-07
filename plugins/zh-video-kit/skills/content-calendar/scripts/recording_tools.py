#!/usr/bin/env python3
"""錄影重點卡、批次錄製清單、狀態更新。

原則：給的是「要點」，不是逐字稿。使用者用自己的話講，才像他本人。

用法：
  python recording_tools.py brief calendar.json -o briefs/ [--from 2026-10-08 --to 2026-10-14]
      產生每支影片的重點卡（briefs/*.md）與批次錄製清單（recording_order.md、recording_order.json）
  python recording_tools.py status calendar.json 2026-10-08 已錄
      更新某一天的狀態（會備份成 .bak）

只會替「路徑為自己錄、且格式需要錄影」的項目產生卡片。圖文、輪播、貼文與 AI 路徑會列在清單最後，標明不需錄影。
"""
import argparse, json, re, shutil, sys
from pathlib import Path

NEEDS_VIDEO = {"Reel", "限動", "長影片"}  # 直播是現場進行，不列入批次錄製
# 建議長度（秒）。是一般短影音的常見做法，不是平台規定；使用者可自行調整。
LEN = {"Reel": (30, 60), "限動": (15, 45), "長影片": (300, 600), "直播": (None, None)}
STATUS = ["待辦", "已錄", "已剪", "已排程", "已發布"]


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def points(script):
    """把 script 拆成要點。沒有就回傳空清單，由人與 Claude 補。"""
    if not script or str(script).endswith((".md", ".txt")):
        return []
    parts = [x.strip(" ；;") for x in re.split(r"[。！？\n]", str(script)) if x.strip(" ；;")]
    return parts


def ending(it):
    kw = (it.get("cta_keyword") or "").strip()
    if it.get("goal") in ("名單", "轉換") and kw:
        return (f"請看到的人在留言輸入「{kw}」領取。\n"
                "  - 自動回覆的第一句要說明這是自動訊息（見 references/manychat.md）。\n"
                "  - 只承諾你真的會給的東西。")
    return {"認識": "邀請追蹤，或請觀眾留言說說自己的情況。",
            "信任": "邀請收藏，或請觀眾留言提問，下一支可以回答。"}.get(it.get("goal"), "自然收尾即可。")


def card(it, n, flagged):
    lo, hi = LEN.get(it["format"], (None, None))
    length = f"建議 {lo}–{hi} 秒" if lo else "依現場安排"
    pts = points(it.get("script"))
    pts_md = "\n".join(f"  - {p}" for p in pts) if pts else "  - 【待補】請和 Claude 一起列出 3 個要點（用你自己的話，不用寫逐字稿）"
    src = "、".join(it.get("source", [])) or "（無）"
    warn = ""
    if flagged:
        warn = ("\n## 用語提醒\n" + "\n".join(f"- 「{t}」［{c}］" for c, t in flagged) +
                "\n（只是提示，不是法律判斷。受規範領域請專業人士確認。）\n")
    return f"""# 第 {n} 支｜{it['date']}｜{it['topic']}

- 格式：{it['format']}（{length}）　目標：{it['goal']}　內容支柱：{it['pillar']}
- 錄音來源段落：{src}

## 開始前
開錄後先**清楚唸一句「第 {n} 支」**，停 1 秒再開始。這是之後自動切片用的標記，會在剪輯時一起剪掉。

## 開頭鉤子（這句最重要，念出來）
> {it['hook']}

## 要點（用自己的話講，不用背）
{pts_md}

## 結尾
{ending(it)}
{warn}
## 錄完之後
```bash
python recording_tools.py status calendar.json {it['date']} 已錄
```
"""


def brief(a):
    from calendar_tools import scan_terms  # 重用用語提示
    cal = load(a.calendar)
    cfg = json.loads((Path(__file__).with_name("flag_terms.json")).read_text(encoding="utf-8"))
    sel = [i for i in cal if (not a.from_ or i["date"] >= a.from_) and (not a.to or i["date"] <= a.to)]
    rec = [i for i in sel if i["format"] in NEEDS_VIDEO and i["route"] == "自己錄"]
    skip = [i for i in sel if i not in rec]
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)

    # 錄製順序：同格式放一起，其次同支柱，方便保持同一種狀態與場景
    order = sorted(rec, key=lambda i: (i["format"], i["pillar"], i["date"]))
    manifest = []
    for n, it in enumerate(order, 1):
        flagged = [(c, t) for c, t, _ in scan_terms(it, cfg)]
        fn = out / f"{n:02d}_{it['date']}.md"
        fn.write_text(card(it, n, flagged), encoding="utf-8")
        manifest.append({"n": n, "date": it["date"], "topic": it["topic"], "format": it["format"], "file": fn.name})
    (out / "recording_order.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    est = 0
    lines = ["# 批次錄製清單", "",
             "**每一支開錄前，先清楚唸「第 N 支」，停 1 秒再開始。** 之後可以自動找出標記、切成單支。", "",
             "| 順序 | 標記 | 日期 | 主題 | 格式 | 卡片 |", "|---|---|---|---|---|---|"]
    for m in manifest:
        lines.append(f"| {m['n']} | 第 {m['n']} 支 | {m['date']} | {m['topic']} | {m['format']} | {m['file']} |")
        lo, hi = LEN.get(m["format"], (None, None))
        if lo: est += (lo + hi) / 2
    if manifest:
        lines += ["", f"成品總長約 {est/60:.0f} 分鐘（依建議長度的中間值估算）。",
                  "含重錄與停頓，實際錄製時間通常會是這個數字的數倍，**這只是粗估，請依你自己的習慣調整**。"]
    if skip:
        lines += ["", "## 不需要錄影（或目前無法自動化）", "", "| 日期 | 主題 | 格式 | 路徑 | 說明 |", "|---|---|---|---|---|"]
        for i in skip:
            why = ("直播現場進行，不在批次錄製" if i["format"] == "直播" else "圖文或文字類，不需錄影" if i["format"] not in NEEDS_VIDEO else f"路徑為{i['route']}，目前尚未提供自動化，建議先改為自己錄")
            lines.append(f"| {i['date']} | {i['topic']} | {i['format']} | {i['route']} | {why} |")
    (out / "recording_order.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"完成：{len(manifest)} 張卡片 -> {out}（另有 {len(skip)} 項不需錄影）")


def status(a):
    if a.status not in STATUS:
        sys.exit(f"狀態必須是 {STATUS} 之一")
    cal = load(a.calendar)
    hit = [i for i in cal if i["date"] == a.date]
    if not hit:
        sys.exit(f"日曆裡沒有 {a.date}")
    shutil.copy2(a.calendar, str(a.calendar) + ".bak")
    for i in hit:
        i["status"] = a.status
    Path(a.calendar).write_text(json.dumps(cal, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{a.date} -> {a.status}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("brief"); b.add_argument("calendar"); b.add_argument("-o", "--out", default="briefs")
    b.add_argument("--from", dest="from_"); b.add_argument("--to"); b.set_defaults(f=brief)
    s = sub.add_parser("status"); s.add_argument("calendar"); s.add_argument("date"); s.add_argument("status"); s.set_defaults(f=status)
    a = ap.parse_args(); a.f(a)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    main()
