#!/usr/bin/env python3
"""素材卡工具：把使用者說過的話整理成一張張卡，並追蹤用在哪一天。

資料存成 materials.json（陣列）。素材只能取自使用者本人說過的內容，工具不會替你補內容。

用法：
  python material_tools.py add materials.json --type 常見疑問 --line "一句話" [--quote 原話片段]
                                              [--blocks B03,B04] [--pillar 支柱] [--check "待確認的事"]
  python material_tools.py list materials.json [--unused] [--type 類型]
  python material_tools.py use materials.json M03 2026-10-09
  python material_tools.py stats materials.json [--calendar calendar.json]
"""
import argparse, json, re, shutil, sys
from collections import Counter
from pathlib import Path

TYPES = ["常見疑問", "迷思澄清", "做法", "經驗故事", "觀點轉變", "清單", "情境", "其他"]
RISK_PATTERNS = [
    # 阿拉伯數字或中文數字，後面接單位（公斤、週、天、倍、萬、元…）
    r"[0-9一二兩三四五六七八九十百千]+\s*(公斤|kg|KG|斤|%|％|週|周|天|倍|萬|元|個月)",
    r"保證|一定會|百分之百|根治|治癒|治療|療效|穩賺|保本",
]


def load(p):
    path = Path(p)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def save(p, data):
    path = Path(p)
    if path.exists():
        shutil.copy2(path, str(path) + ".bak")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def new_id(cards):
    n = max([int(c["id"][1:]) for c in cards] + [0]) + 1
    return f"M{n:02d}"


def cmd_add(a):
    if a.type not in TYPES:
        sys.exit(f"type 必須是 {TYPES} 之一")
    line = a.line.strip()
    if not line:
        sys.exit("line 不可為空")
    if len(line) > 60:
        print(f"提醒：這句有 {len(line)} 字，建議 40 字內。一張卡一個重點，太長請拆成兩張。")
    blocks = [b.strip() for b in (a.blocks or "").split(",") if b.strip()]
    bad = [b for b in blocks if not re.fullmatch(r"B\d{2,3}", b)]
    if bad:
        sys.exit(f"blocks 格式要像 B03：{bad}")
    cards = load(a.file)
    check = a.check or ""
    text = f"{line} {a.quote or ''}"
    hits = [p for p in RISK_PATTERNS if re.search(p, text)]
    if hits and not check:
        check = "含具體數字或肯定性用語，請使用者確認出處與用詞"
        print(f"提醒：已自動標記待確認 —— {check}")
    card = {"id": new_id(cards), "type": a.type, "line": line, "quote": a.quote or "", "blocks": blocks,
            "pillar": a.pillar or "", "check": check, "used_on": []}
    cards.append(card)
    save(a.file, cards)
    print(f"已新增 {card['id']}（{card['type']}）")


def cmd_list(a):
    cards = [c for c in load(a.file) if (not a.unused or not c["used_on"]) and (not a.type or c["type"] == a.type)]
    if not cards:
        print("（沒有符合的素材卡）"); return
    for c in cards:
        used = "已用：" + "、".join(c["used_on"]) if c["used_on"] else "未用"
        flag = "  ⚠待確認" if c.get("check") else ""
        print(f"{c['id']} [{c['type']}] {c['line']}  （{used}）{flag}")


def cmd_use(a):
    cards = load(a.file)
    hit = next((c for c in cards if c["id"] == a.id), None)
    if not hit:
        sys.exit(f"找不到 {a.id}")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", a.date):
        sys.exit("日期格式要 YYYY-MM-DD")
    if a.date not in hit["used_on"]:
        hit["used_on"].append(a.date); hit["used_on"].sort()
    save(a.file, cards)
    extra = ""
    if len(hit["used_on"]) > 1:
        extra = "。提醒：同一張卡用在多天時，請換角度或換格式，不要原句重複發"
    print(f"{a.id} 已標記用於 {a.date}{extra}")


def cmd_stats(a):
    cards = load(a.file)
    if not cards:
        print("還沒有素材卡。請先做素材採集。"); return
    by_type = Counter(c["type"] for c in cards)
    unused = [c for c in cards if not c["used_on"]]
    pending = [c for c in cards if c.get("check")]
    print(f"共 {len(cards)} 張｜未用 {len(unused)} 張｜待確認 {len(pending)} 張")
    print("類型：", dict(by_type))
    if a.calendar:
        cal = json.loads(Path(a.calendar).read_text(encoding="utf-8"))
        print(f"日曆共 {len(cal)} 天；沒有標記素材來源的有 {len([i for i in cal if not i.get('source')])} 天")
    # 誠實估計：一張未用的卡大約可支撐 1 天內容；這是粗略的經驗規則，不是保證
    print(f"\n粗估：目前未用的素材約可支撐 {len(unused)} 天內容（一張卡約一天，這是粗略估計）。")
    if len(unused) < 7:
        print("素材偏少。建議再做一輪素材採集，或接受日曆只排素材夠的天數，不要用空泛內容湊數。")
    missing = [t for t in TYPES[:-1] if by_type[t] == 0]
    if missing:
        print(f"還沒有這些類型：{missing}（可依支柱補採）")
    for c in pending:
        print(f"  ⚠ {c['id']} 待確認：{c['check']}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("add"); s.add_argument("file"); s.add_argument("--type", required=True); s.add_argument("--line", required=True)
    s.add_argument("--quote"); s.add_argument("--blocks"); s.add_argument("--pillar"); s.add_argument("--check"); s.set_defaults(f=cmd_add)
    s = sub.add_parser("list"); s.add_argument("file"); s.add_argument("--unused", action="store_true"); s.add_argument("--type"); s.set_defaults(f=cmd_list)
    s = sub.add_parser("use"); s.add_argument("file"); s.add_argument("id"); s.add_argument("date"); s.set_defaults(f=cmd_use)
    s = sub.add_parser("stats"); s.add_argument("file"); s.add_argument("--calendar"); s.set_defaults(f=cmd_stats)
    a = ap.parse_args(); a.f(a)


if __name__ == "__main__":
    main()
