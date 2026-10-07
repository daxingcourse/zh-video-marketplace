#!/usr/bin/env python3
"""內容日曆工具：檢查、提示用語、匯出。

日曆格式 calendar.json：一個陣列，每個項目是一天的內容。
必填欄位：date, pillar, topic, format, route, hook, goal, status
有條件必填：cta_keyword（goal 為 轉換 或 名單 時）
選填：script（文字或檔案路徑）、source（錄音段落 id 清單，如 ["B03"]）、likeness_ok、notes

用法：
  python calendar_tools.py check calendar.json [--allow-short] [--terms flag_terms.json] [--materials materials.json]
  python calendar_tools.py export calendar.json --csv out.csv --md out.md
"""
import argparse, csv, json, re, sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

REQUIRED = ["date", "pillar", "topic", "format", "route", "hook", "goal", "status"]
FORMATS = {"Reel", "輪播", "限動", "貼文", "直播", "長影片", "Threads", "Email", "長文"}
ROUTES = {"自己錄", "AI聲音", "AI數字人", "圖文", "文字"}
GOALS = {"認識", "信任", "轉換", "名單"}
STATUS = {"待辦", "已錄", "已剪", "已排程", "已發布"}
TEXT_FIELDS = ["topic", "hook", "script", "notes"]


def load(p):
    data = json.loads(Path(p).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        sys.exit("日曆必須是陣列（每天一個項目）")
    return data


def scan_terms(item, cfg):
    hits = []
    text = " ".join(str(item.get(f, "")) for f in TEXT_FIELDS)
    for cat, c in cfg["categories"].items():
        for t in c["terms"]:
            if t in text:
                hits.append((cat, t, c["note"]))
    for p in cfg.get("patterns", []):
        m = re.search(p["regex"], text)
        if m:
            hits.append((p["category"], m.group(0), p["note"]))
    return hits


def check(args):
    cal = load(args.calendar)
    cfg_path = Path(args.terms) if args.terms else Path(__file__).with_name("flag_terms.json")
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    errors, warns, flags = [], [], []

    dates = []
    for i, it in enumerate(cal, 1):
        tag = f"第 {i} 項"
        for f in REQUIRED:
            if not str(it.get(f, "")).strip():
                errors.append(f"{tag}：缺少必填欄位 {f}")
        try:
            d = datetime.strptime(it.get("date", ""), "%Y-%m-%d").date(); dates.append(d)
        except ValueError:
            errors.append(f"{tag}：date 格式要 YYYY-MM-DD（目前：{it.get('date')!r}）")
        for field, allowed in (("format", FORMATS), ("route", ROUTES), ("goal", GOALS), ("status", STATUS)):
            v = it.get(field)
            if v and v not in allowed:
                errors.append(f"{tag}：{field} 必須是 {sorted(allowed)} 之一（目前：{v!r}）")
        kw = str(it.get("cta_keyword", "")).strip()
        if it.get("goal") in ("轉換", "名單") and not kw:
            errors.append(f"{tag}：goal 為 {it['goal']}，需要 cta_keyword")
        if kw and (len(kw) > 6 or re.search(r"\s", kw)):
            warns.append(f"{tag}：cta_keyword「{kw}」建議 6 字內、不含空白（留言要好打）")
        if it.get("route") == "AI數字人" and it.get("likeness_ok") is not True:
            warns.append(f"{tag}：路徑是 AI數字人，請確認使用的是本人肖像或已取得同意，並設 likeness_ok: true")
        for cat, term, note in scan_terms(it, cfg):
            flags.append(f"{tag}（{it.get('date')}）命中「{term}」［{cat}］：{note}")

    if args.materials:
        mats = {m["id"]: m for m in json.loads(Path(args.materials).read_text(encoding="utf-8"))}
        for i, it in enumerate(cal, 1):
            for sid in it.get("source", []) or []:
                if re.fullmatch(r"M\d+", str(sid)):
                    if sid not in mats:
                        errors.append(f"第 {i} 項：source 的素材卡 {sid} 不存在於 {args.materials}")
                    elif mats[sid].get("check"):
                        warns.append(f"第 {i} 項：用到的素材卡 {sid} 仍有待確認事項：{mats[sid]['check']}")
        used = {sid for it in cal for sid in (it.get("source") or []) if re.fullmatch(r"M\d+", str(sid))}
        idle = [m for m in mats if m not in used]
        if idle:
            warns.append(f"有 {len(idle)} 張素材卡尚未排進日曆：{', '.join(idle)}")
        nosrc = [i for i, it in enumerate(cal, 1) if not it.get("source")]
        if nosrc and mats:
            warns.append(f"有 {len(nosrc)} 項沒有標示素材來源（第 {', '.join(map(str, nosrc))} 項）。內容應取自使用者說過的話，請補來源，或確認這些是純行動呼籲／互動類內容")

    if len(set(dates)) != len(dates):
        errors.append("有重複的日期")
    if dates and dates != sorted(dates):
        warns.append("日期沒有由早到晚排序")
    if not args.allow_short and len(cal) != 30:
        warns.append(f"共 {len(cal)} 項，30 天日曆預期 30 項（試做可加 --allow-short）")

    pillars = Counter(it.get("pillar") for it in cal if it.get("pillar"))
    total = sum(pillars.values()) or 1
    for p, n in pillars.items():
        if n / total > 0.5:
            warns.append(f"支柱「{p}」佔 {n}/{total}，超過一半，內容會單調")
    if len(pillars) < 3 and len(cal) >= 10:
        warns.append(f"只有 {len(pillars)} 個內容支柱，建議 3 到 5 個")
    run = 1
    for a, b in zip(cal, cal[1:]):
        run = run + 1 if a.get("pillar") == b.get("pillar") else 1
        if run > 3:
            warns.append(f"支柱「{b.get('pillar')}」連續超過 3 天（約 {b.get('date')}）"); break

    goals = Counter(it.get("goal") for it in cal)
    if cal and (goals["轉換"] + goals["名單"]) / len(cal) < 0.15:
        warns.append("導向轉換或名單的內容少於 15%，日曆可能沒有導回你的服務")
    if cal and (goals["轉換"] + goals["名單"]) / len(cal) > 0.5:
        warns.append("導向轉換或名單的內容超過 50%，容易變成一直在推銷")

    print(f"共 {len(cal)} 項｜支柱：{dict(pillars)}｜格式：{dict(Counter(i.get('format') for i in cal))}")
    print(f"製作路徑：{dict(Counter(i.get('route') for i in cal))}｜目標：{dict(goals)}")
    for title, rows in (("錯誤", errors), ("警告", warns), ("用語提示（不是法律判斷，請專業人士確認）", flags)):
        if rows:
            print(f"\n{title}（{len(rows)}）"); [print("  -", r) for r in rows]
    if not (errors or warns or flags):
        print("\n沒有發現問題。")
    sys.exit(1 if errors else 0)


def export(args):
    cal = load(args.calendar)
    cols = ["date", "pillar", "topic", "format", "route", "goal", "cta_keyword", "hook", "script", "source", "status", "notes"]
    head = ["日期", "內容支柱", "主題", "格式", "製作路徑", "目標", "CTA 關鍵字", "開頭鉤子", "腳本", "錄音來源", "狀態", "備註"]
    def cell(it, k):
        v = it.get(k, "")
        return "、".join(v) if isinstance(v, list) else str(v)
    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig：Excel 開啟不會亂碼
            w = csv.writer(f); w.writerow(head)
            for it in cal: w.writerow([cell(it, c) for c in cols])
        print(f"已匯出 {args.csv}")
    if args.md:
        lines = ["| " + " | ".join(head[:7] + ["狀態"]) + " |", "|" + "---|" * 8]
        for it in cal:
            lines.append("| " + " | ".join(cell(it, c).replace("|", "／") for c in cols[:7] + ["status"]) + " |")
        Path(args.md).write_text("\n".join(lines), encoding="utf-8"); print(f"已匯出 {args.md}")
    if not (args.csv or args.md):
        sys.exit("請指定 --csv 或 --md")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check"); c.add_argument("calendar"); c.add_argument("--allow-short", action="store_true"); c.add_argument("--terms"); c.add_argument("--materials")
    c.set_defaults(f=check)
    e = sub.add_parser("export"); e.add_argument("calendar"); e.add_argument("--csv"); e.add_argument("--md")
    e.set_defaults(f=export)
    a = ap.parse_args(); a.f(a)


if __name__ == "__main__":
    main()
