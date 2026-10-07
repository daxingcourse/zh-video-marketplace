#!/usr/bin/env python3
"""完整稿工具：每一篇稿都要標明「取自哪張素材卡」，並檢查稿裡的數字與用語有沒有憑空出現。

稿的格式（Markdown，開頭是簡單的欄位區）：

---
date: 2026-10-08
format: Threads
topic: 這一篇講什麼
sources: [M01, M03]
---
## 稿
（稿的內容）
## 對照
- 主張：... ｜ 來源：M01
## 待使用者確認
- ...

用法：
  python draft_tools.py new calendar.json 2026-10-08 -o drafts/     由日曆項目建立空稿
  python draft_tools.py check drafts/ --materials materials.json   檢查所有稿（也可指定單一檔案）

檢查是啟發式的：它只能找出「稿裡有、來源卡裡沒有」的數字，與命中的風險用語；
**無法判斷稿的內容是否忠於使用者原意，這一定要使用者自己讀過。**
"""
import argparse, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from calendar_tools import scan_terms  # noqa: E402

TODO = "【待補】"
NUM = re.compile(r"[0-9]+(?:\.[0-9]+)?\s*(?:%|％|公斤|kg|KG|斤|週|周|天|倍|萬|元|個月|次|分鐘|小時|歲|年)?|[一二兩三四五六七八九十百千]+\s*(?:公斤|斤|週|周|天|倍|萬|元|個月|分鐘|小時|歲|年)")


def parse(path):
    text = Path(path).read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    meta, body = {}, text
    if m:
        for line in m.group(1).split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        body = m.group(2)
    sections, cur = {}, None
    for line in body.split("\n"):
        h = re.match(r"^##\s*(.+)$", line)
        if h:
            cur = h.group(1).strip(); sections[cur] = []
        elif cur:
            sections[cur].append(line)
    return meta, {k: "\n".join(v).strip() for k, v in sections.items()}


def ids(s):
    return re.findall(r"M\d+", s or "")


def cmd_new(a):
    cal = json.loads(Path(a.calendar).read_text(encoding="utf-8"))
    it = next((i for i in cal if i["date"] == a.date), None)
    if not it:
        sys.exit(f"日曆裡沒有 {a.date}")
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    f = out / f"{a.date}.md"
    if f.exists():
        sys.exit(f"{f} 已存在，不覆蓋")
    src = ", ".join(i for i in it.get("source", []) if re.fullmatch(r"M\d+", str(i)))
    f.write_text(f"""---
date: {it['date']}
format: {it['format']}
topic: {it['topic']}
sources: [{src}]
---
## 稿
{TODO}

## 對照
- 主張：{TODO} ｜ 來源：{src or TODO}

## 待使用者確認
- {TODO}
""", encoding="utf-8")
    print(f"已建立 {f}。請依素材卡寫稿，每個主張都要在「對照」標明來源，寫完請使用者逐句讀過。")


def card_text(c):
    return f"{c.get('line','')} {c.get('quote','')}"


def check_one(path, mats, cfg):
    meta, sec = parse(path)
    errors, warns = [], []
    srcs = ids(meta.get("sources", ""))
    body = sec.get("稿", "")
    if not srcs:
        errors.append("沒有標示 sources（取自哪些素材卡）")
    missing = [s for s in srcs if s not in mats]
    if missing:
        errors.append(f"sources 的素材卡不存在：{missing}")
    if TODO in body or TODO in sec.get("對照", ""):
        errors.append(f"仍有{TODO}")
    if not sec.get("對照", "").replace(TODO, "").strip():
        warns.append("「對照」是空的：每個主張都應標明來源")
    cited = set(ids(sec.get("對照", "")))
    if srcs and cited and not cited <= set(srcs):
        warns.append(f"「對照」引用了未列在 sources 的卡：{sorted(cited - set(srcs))}")
    # 稿裡的數字，必須出現在來源素材卡（或使用者待確認清單）裡
    src_text = " ".join(card_text(mats[s]) for s in srcs if s in mats) + " " + sec.get("待使用者確認", "")
    norm = lambda t: re.sub(r"\s+", "", t)
    for n in sorted(set(NUM.findall(body))):
        n = n.strip()
        if n and norm(n) not in norm(src_text):
            warns.append(f"稿裡出現「{n}」，來源素材卡沒有這個數字。請確認是使用者說過的，或刪掉")
    for cat, term, note in scan_terms({"topic": body}, cfg):
        warns.append(f"用語提示：命中「{term}」［{cat}］：{note}（只是提示，不是法律判斷）")
    for s in srcs:
        if s in mats and mats[s].get("check"):
            warns.append(f"來源素材卡 {s} 有待確認事項：{mats[s]['check']}")
    return errors, warns


def cmd_check(a):
    mats = {m["id"]: m for m in json.loads(Path(a.materials).read_text(encoding="utf-8"))}
    cfg = json.loads((Path(__file__).with_name("flag_terms.json")).read_text(encoding="utf-8"))
    p = Path(a.path)
    files = sorted(p.glob("*.md")) if p.is_dir() else [p]
    if not files:
        sys.exit("沒有找到稿")
    bad = 0
    for f in files:
        e, w = check_one(f, mats, cfg)
        print(f"{f.name}：{'錯誤 ' + str(len(e)) if e else '無錯誤'}｜警告 {len(w)}")
        for x in e:
            print("  ✗", x)
        for x in w:
            print("  ⚠", x)
        bad += bool(e)
    print("\n提醒：這個檢查只能找出稿裡憑空出現的數字與風險用語，**無法判斷內容是否忠於使用者原意**，請使用者逐句讀過再發布。")
    sys.exit(1 if bad else 0)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new"); n.add_argument("calendar"); n.add_argument("date"); n.add_argument("-o", "--out", default="drafts"); n.set_defaults(f=cmd_new)
    c = sub.add_parser("check"); c.add_argument("path"); c.add_argument("--materials", required=True); c.set_defaults(f=cmd_check)
    a = ap.parse_args(); a.f(a)


if __name__ == "__main__":
    main()
