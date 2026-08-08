# -*- coding: utf-8 -*-
"""把逐點說明 md 解析成 guide.json，並比對回既有的行程資料。

  python tools/parse_guide.py --report   只檢查並輸出報告，不寫檔
  python tools/parse_guide.py --write    產出 guide.json 與 places.json 種子

設計重點：

1. **模糊比對只留在這一支工具裡**。build 時只做字典查表，不做相似度計算 —
   產出才會穩定可重現。

2. **沒有東西可以靜默消失**。比對不到或比對到多個的條目會讓 build 中止，
   除非在 guide_overrides.json 的 drop 裡寫明理由。跟「讀不到遮蔽對照就中止」
   同一套邏輯。

3. **個資在這一步就丟掉**，不進 guide.json，不靠後面的字串替換擋。
   丟掉哪幾行會列在報告裡。

這一檔會進公開 repo，所以不能出現任何地名、店名或日期 —
來源路徑用萬用字元找，比對規則寫成通則。
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "private" / "raw"
OUT = ROOT / "guide.json"
PLACES = ROOT / "places.json"
OVERRIDES = ROOT / "guide_overrides.json"
BUILD = ROOT / "build"

AUTO = 0.90       # 這個分數以上自動配
SUGGEST = 0.75    # 這個分數以上列為建議，但不自動套用

# 中日漢字對折：同一個字的不同寫法。竈/釜 這種「不同字」不在這裡，要寫 alias。
FOLD = str.maketrans({
    "峽": "峡", "藏": "蔵", "國": "国", "廣": "広", "嚴": "厳", "巖": "巌",
    "澤": "沢", "瀧": "滝", "邊": "辺", "實": "実", "營": "営", "觀": "観",
    "寶": "宝", "會": "会", "區": "区", "產": "産", "縣": "県", "櫻": "桜",
    "驛": "駅", "號": "号", "壽": "寿", "團": "団", "圓": "円", "溫": "温",
    "藝": "芸", "醫": "医", "戀": "恋", "櫃": "柜", "點": "点", "齋": "斎",
})

FIELD = re.compile(r"^\*\*([^*]{1,10})\*\*：\s*(.*)$")
BULLET = re.compile(r"^-\s+(.*)$")
OLI = re.compile(r"^(\d+)\.\s+(.*)$")
LINK = re.compile(r"\[([^\]]*)\]\((https://www\.google\.com/maps/[^)]+)\)")
FLAG = re.compile(r"【([^】]+)】")
ORD = re.compile(r"^(?:(?P<br>[AB])?(?P<n>\d{1,2})(?:-(?P<sub>\d{1,2}))?)\.\s")
HEAD = re.compile(r"^(#{1,6})\s+(.*)$")

PARK_WORDS = ("駐車", "パーク", "停車", "Parking", "parking")

FLAG_STATUS = {
    "備選": "alt",
    "保留／視時間": "time",
    "視時間": "time",
    "晚餐前視時間": "time",
    "視天氣／時間": "weather",
    "不納入 D5 主線": "off-route",
}

# 個資：整條丟掉的標記，與人數的寫法。
PII_LABEL = re.compile(r"(預約號碼|訂位號碼|預約者|訂位代號|確認號碼)")
PII_COUNT = re.compile(r"\d+\s*位成人|\d+\s*位(?![^，。；\s])|\d+\s*成人")


def find_source() -> Path:
    c = sorted(RAW.glob("*.md"))
    if not c:
        sys.exit(f"在 {RAW} 找不到來源 md。")
    if len(c) > 1:
        sys.exit(f"{RAW} 有多個 md：{[x.name for x in c]}")
    return c[0]


# ---------------------------------------------------------------- 個資

def scrub(text: str, log: list[str], where: str) -> str | None:
    """回傳清理後的字串；整條該丟掉就回 None。丟掉什麼都會記進 log。

    **一定要先 strip_md 再進來。** 人數的判斷是「數字＋位」後面必須接標點或結尾，
    直接掃原始 markdown 時人數後面接的是 `*` 而不是標點，判斷會失效而漏掉。
    """
    if PII_LABEL.search(text):
        log.append(f"{where}｜整條丟棄（含訂位代號類標籤）")
        return None
    if PII_COUNT.fullmatch(text.strip("。．. ")):
        log.append(f"{where}｜整條丟棄（只有人數）")
        return None
    new = PII_COUNT.sub("", text)
    new = re.sub(r"[，、]\s*(?=[。．]?$)", "", new)
    new = re.sub(r"[，、]{2,}", "，", new)
    if new != text:
        log.append(f"{where}｜移除人數")
    new = new.strip()
    return new or None


def strip_md(s: str) -> str:
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"\*\*([^*]*)\*\*", r"\1", s)
    return s.replace("**", "").strip()


# ---------------------------------------------------------------- 名稱

def split_names(title: str) -> dict:
    """把 `中文（Romaji／日文）` 這種標題拆成三個名字。

    出現過的四種寫法都要吃：
      中文（Romaji／日文）  中文（日文）  純日文  純拉丁
    """
    t = FLAG.sub("", title).strip()
    t = ORD.sub("", t).strip()
    m = re.match(r"^(.*?)（(.*?)）\s*$", t)
    if not m:
        return {"jp": t if has_cjk(t) else "", "zh": t if has_cjk(t) else "",
                "en": t if not has_cjk(t) else ""}
    head, inner = m.group(1).strip(), m.group(2).strip()
    parts = [p.strip() for p in re.split(r"[／/]", inner) if p.strip()]
    en = jp = ""
    for p in parts:
        if has_cjk(p):
            jp = jp or p
        else:
            en = en or p
    return {"jp": jp or (head if has_cjk(head) else ""),
            "zh": head if has_cjk(head) else "",
            "en": en or ("" if has_cjk(head) else head)}


def has_cjk(s: str) -> bool:
    return bool(re.search(r"[぀-ヿ㐀-鿿]", s))


def norm(s: str, is_md_heading: bool = False) -> str:
    """正規化後再比對。

    序號前綴只在 md 這一側去掉，資料那一側絕不去 —
    否則名稱本身就以數字開頭的店家(資料端沒有序號)會被削掉開頭，
    跟 md 端(有序號)對不起來。
    """
    s = unicodedata.normalize("NFKC", s)
    s = FLAG.sub("", s)
    if is_md_heading:
        s = ORD.sub("", s)
    s = s.translate(FOLD)
    s = re.sub(r"[（(].*?[)）]", " ", s)
    s = re.sub(r"[\s・·､、,，.。／/\-–—_'\"’”“」「【】]+", "", s)
    return s.casefold()


SEP = re.compile(r"[＋+／/｜|、,]|→|・{2,}")


def variants(title: str, is_md: bool = False) -> set[str]:
    out = {norm(title, is_md)}
    n = split_names(title)
    for v in (n["jp"], n["zh"], n["en"]):
        if v:
            out.add(norm(v))
    m = re.match(r"^(.*?)（", FLAG.sub("", ORD.sub("", title) if is_md else title))
    if m and m.group(1).strip():
        out.add(norm(m.group(1)))
    # 行程資料有把兩三個地點用分隔符併成一列的寫法，拆開才對得到 md 的個別條目。
    base = FLAG.sub("", ORD.sub("", title) if is_md else title)
    parts = [p.strip() for p in SEP.split(base) if len(p.strip()) > 1]
    if len(parts) > 1:
        for p in parts:
            out.add(norm(p))
            out |= {norm(x) for x in split_names(p).values() if x}
    return {v for v in out if v}


# ---------------------------------------------------------------- 解析

def classify(level: int, text: str, has_link: bool, n_field: int, n_bullet: int,
             open_group: bool) -> str:
    """標題分類。判別關鍵是「空不空」，不是「有沒有序號」。

    候選清單那種標題有序號但底下完全沒有內容 -> 群組；
    有序號而且有欄位或項目符號 -> 地點。
    """
    if level == 1:
        return "section"
    if not has_link and n_field == 0 and n_bullet == 0:
        return "group"
    if ORD.match(text):
        return "place"
    return "place" if open_group else "note"


def parse(md: str, pii_log: list[str]) -> tuple[list[dict], list[dict]]:
    lines = md.split("\n")
    # 先切成 (標題, 內文行) 的區塊
    blocks: list[tuple[int, int, str, list[str]]] = []
    cur = None
    for i, ln in enumerate(lines, 1):
        h = HEAD.match(ln)
        if h:
            if cur:
                blocks.append(cur)
            cur = (i, len(h.group(1)), h.group(2).strip(), [])
        elif cur:
            cur[3].append(ln)
    if cur:
        blocks.append(cur)

    entries: list[dict] = []
    notes: list[dict] = []
    day = None
    branch = None
    section = "preamble"
    group = None
    group_level = 0

    for line_no, level, title, body in blocks:
        fields, bullets, olists, links, raw_bullets = [], [], [], [], []
        cur_ol = None
        for b in body:
            s = b.rstrip()
            for lm in LINK.finditer(s):
                label = lm.group(1)
                url = lm.group(2)
                q = re.search(r"[?&]query=([^&]*)", url)
                if not q:
                    continue
                from urllib.parse import unquote
                links.append({
                    "label": label,
                    "query": unquote(q.group(1)),
                    "role": "parking" if any(w in label for w in PARK_WORDS) else "place",
                })
            if LINK.search(s):
                continue
            fm = FIELD.match(s)
            if fm:
                cur_ol = None
                fields.append((fm.group(1), fm.group(2).strip()))
                continue
            om = OLI.match(s)
            if om:
                if cur_ol is None:
                    cur_ol = {"type": "ordered",
                              "label": fields[-1][0] if fields and not fields[-1][1] else "",
                              "items": []}
                    olists.append(cur_ol)
                cur_ol["items"].append(strip_md(om.group(2)))
                continue
            bm = BULLET.match(s)
            if bm:
                cur_ol = None
                raw_bullets.append(bm.group(1).strip())
                continue
            if s.strip():
                cur_ol = None

        kind = classify(level, title, bool(links), len(fields), len(raw_bullets),
                        group is not None)

        if level == 1:
            group = None
            dm = re.match(r"^D(\d)", title)
            if not dm:
                day, branch, section = None, None, "appendix"
                notes.append({"line": line_no, "title": title, "kind": "appendix"})
                continue
            day = f"D{dm.group(1)}"
            rest = title[dm.end():]
            if "已取消" in rest:
                section, branch = "cancelled", None
            else:
                section = "main"
                a, b = "Plan A" in rest, "Plan B" in rest
                branch = "A" if a and not b else "B" if b and not a else None
            continue

        # 群組標題與條目標題必須用同一套清理，否則子項對不回父群組
        # (群組若存了含序號的版本，條目的 title 已去序號，兩邊會對不起來)
        clean_title = strip_md(FLAG.sub("", ORD.sub("", title)).strip())
        is_group = kind == "group"
        if is_group:
            group = clean_title
            group_level = level
        elif group is not None and level <= group_level:
            group = None

        # 內文清理（個資）
        where = f"L{line_no} {strip_md(title)[:20]}"
        clean_fields = []
        for k, v in fields:
            v2 = scrub(strip_md(v), pii_log, f"{where}｜{k}") if v else v
            if v and v2 is None:
                continue
            clean_fields.append({"k": k, "v": v2 or ""})
        clean_bullets = []
        for rb in raw_bullets:
            v2 = scrub(strip_md(rb), pii_log, where)
            if v2:
                clean_bullets.append(v2)

        om = ORD.match(title)
        flags = [{"raw": f, "status": FLAG_STATUS.get(f, "unknown")}
                 for f in FLAG.findall(title)]

        rec = {
            "src": {"line": line_no, "heading": title},
            "kind": "group" if is_group else "place",
            "day": day, "branch": (om.group("br") if om and om.group("br") else branch),
            "section": section, "group": None if is_group else group,
            "ord": {"raw": om.group(0).strip() if om else None,
                    "n": int(om.group("n")) if om else None,
                    "sub": int(om.group("sub")) if om and om.group("sub") else None},
            "title": clean_title,
            "names": split_names(title),
            "flags": flags,
            "fields": clean_fields,
            "bullets": clean_bullets,
            "blocks": olists,
            "links": links,
        }
        if kind == "note":
            rec["kind"] = "note"
            notes.append(rec)
        else:
            entries.append(rec)

    link_parents(entries)
    return entries, notes


def link_parents(entries: list[dict]) -> None:
    """在 md 內部解出父子關係。

    md 比行程資料細 2.3 倍，多數條目不該去對「站」，而是掛在某一站底下：

      群組成員   候選清單底下的各家店 -> 掛在該群組
      子序號     2-1 -> 掛在 2.      A1-1 -> 掛在 A1.      13-1 -> 掛在 13.

    只有沒有父的條目才需要對應到行程資料的站。
    """
    by_group = {(e["day"], e["title"]): e for e in entries if e["kind"] == "group"}
    by_ord = {(e["day"], e["branch"], e["ord"]["n"]): e
              for e in entries if e["ord"]["n"] and not e["ord"]["sub"]}
    for e in entries:
        p = None
        if e["ord"]["sub"]:
            p = by_ord.get((e["day"], e["branch"], e["ord"]["n"]))
        elif e["group"]:
            p = by_group.get((e["day"], e["group"]))
        e["parent"] = p["src"]["line"] if p and p is not e else None


# ---------------------------------------------------------------- 比對

def load_targets() -> list[dict]:
    from urllib.parse import unquote
    trip = json.loads((ROOT / "trip_data.json").read_text(encoding="utf-8"))
    clus = json.loads((ROOT / "clusters.json").read_text(encoding="utf-8"))["clusters"]
    out = []
    for d in trip["days"]:
        for i, s in enumerate(d["stops"]):
            out.append({"key": f"{d['id']}/stop/{i}", "day": d["id"], "name": s["name"],
                        "query": unquote(s.get("query", "")), "kind": "stop"})
            for p in s.get("parking", []):
                out.append({"key": f"{d['id']}/stop/{i}/p", "day": d["id"],
                            "name": p["name"], "query": unquote(p.get("query", "")),
                            "kind": "parking"})
    for c in clus:
        for j, s in enumerate(c["stops"]):
            out.append({"key": f"{c['day']}/cluster/{c['stop_time']}/{j}", "day": c["day"],
                        "name": s["name"], "query": s.get("query", ""), "kind": "cluster"})
    return out


def score(a: set[str], b: set[str]) -> float:
    best = 0.0
    for x in a:
        for y in b:
            if x == y:
                return 1.0
            r = difflib.SequenceMatcher(None, x, y).ratio()
            if len(x) > 1 and len(y) > 1:
                gx = {x[i:i + 2] for i in range(len(x) - 1)}
                gy = {y[i:i + 2] for i in range(len(y) - 1)}
                r = max(r, len(gx & gy) / max(1, len(gx | gy)))
            best = max(best, r)
    return best


def prio(kind: str, want_parking: bool) -> int:
    """明確程度。群組細項最明確，其次是站，停車場最不明確。
    條目本身只有停車場連結時反過來，優先對停車場。"""
    if want_parking:
        return {"parking": 3, "cluster": 2, "stop": 1}[kind]
    return {"cluster": 3, "stop": 2, "parking": 1}[kind]


def match_all(entries: list[dict], targets: list[dict], alias: dict) -> None:
    tv = []
    for t in targets:
        v = variants(t["name"])
        v |= {norm(x) for x in alias.get(t["name"], [])}
        if t["query"]:
            v.add(norm(t["query"]))
        tv.append(v)

    for e in entries:
        if e.get("parent"):
            # 有父的條目掛在父底下，不必自己去對站
            e["match"] = {"status": "child", "target": None}
            continue
        ev = variants(e["src"]["heading"], is_md=True)
        for L in e["links"]:
            if L["role"] == "place":
                ev.add(norm(L["query"]))
        ev |= {norm(x) for x in alias.get(e["title"], [])}

        want_park = bool(e["links"]) and not any(l["role"] == "place" for l in e["links"])
        cand = []
        for t, v in zip(targets, tv):
            if e["day"] and t["day"] and e["day"] != t["day"]:
                continue
            s = score(ev, v)
            if s >= SUGGEST:
                cand.append((round(s, 3), prio(t["kind"], want_park), t["key"], t["name"]))
        # 先比分數再比明確程度。同一個地點常同時命中「群組細項」「站」「該站的停車場」，
        # 因為停車場那筆的 query 沿用店家的 query，會拿到滿分。
        # 這不是真的模糊，取最明確的那一個就對了。
        cand.sort(key=lambda c: (-c[0], -c[1]))
        top = [c for c in cand if c[0] >= AUTO]
        if not top:
            e["match"] = {"status": "unmatched",
                          "candidates": [{"target": k, "name": n, "score": s}
                                         for s, _, k, n in cand[:3]]}
            continue
        best = top[0]
        tie = [c for c in top if c[0] == best[0] and c[1] == best[1]]
        if len(tie) > 1 and len({c[3] for c in tie}) > 1:
            e["match"] = {"status": "ambiguous",
                          "candidates": [{"target": k, "name": n, "score": s}
                                         for s, _, k, n in tie[:4]]}
        else:
            e["match"] = {"status": "matched", "target": best[2],
                          "name": best[3], "score": best[0]}


# ---------------------------------------------------------------- 主流程

def slug(e: dict, used: set[str]) -> str:
    base = re.sub(r"[^A-Za-z0-9]+", "-", e["names"].get("en") or "").strip("-").lower()
    if len(base) < 3:
        base = f"{(e['day'] or 'x').lower()}-{e['ord']['raw'] or 'n'}".replace(".", "")
    s, i = base, 2
    while s in used:
        s, i = f"{base}-{i}", i + 1
    used.add(s)
    return s


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--report", action="store_true")
    g.add_argument("--write", action="store_true")
    args = ap.parse_args()

    src = find_source()
    ov = json.loads(OVERRIDES.read_text(encoding="utf-8")) if OVERRIDES.exists() else {}
    drops = {d["src_line"]: d.get("reason", "") for d in ov.get("drop", [])}
    fixes = {int(k): v for k, v in ov.get("match", {}).items()}
    alias = ov.get("alias", {})

    pii_log: list[str] = []
    entries, notes = parse(src.read_text(encoding="utf-8"), pii_log)
    entries = [e for e in entries if e["src"]["line"] not in drops]
    targets = load_targets()
    match_all(entries, targets, alias)
    for e in entries:
        f = fixes.get(e["src"]["line"])
        if f:
            e["match"] = {"status": "matched", "target": f, "name": "(overrides 指定)",
                          "score": 1.0}

    used: set[str] = set()
    for e in entries:
        e["id"] = slug(e, used)

    L: list[str] = []
    add = L.append
    st = {"matched": 0, "ambiguous": 0, "unmatched": 0, "child": 0}
    for e in entries:
        st[e["match"]["status"]] += 1

    add("# 逐點說明解析報告\n")
    add("| 項目 | 數值 |")
    add("|---|---|")
    add(f"| 來源 | `private/raw/{src.name}` |")
    add(f"| 條目 | {len(entries)} |")
    add(f"| 註記（不是地點，掛在當日） | {len(notes)} |")
    add(f"| 依 overrides 明確排除 | {len(drops)} |")
    add(f"| 比對成功（對應到一站） | {st['matched']} |")
    add(f"| 掛在別的條目底下（不必對站） | {st['child']} |")
    add(f"| 比對到多個（會讓 build 中止） | {st['ambiguous']} |")
    add(f"| 比對不到（會讓 build 中止） | {st['unmatched']} |")
    add("")

    add("## 個資清理")
    if pii_log:
        add(f"- 共處理 {len(pii_log)} 處：")
        for x in pii_log:
            add(f"  - {x}")
    else:
        add("- 沒有偵測到需要清理的內容 <-- 可疑，來源應該含訂位資料，請確認規則")
    add("")

    add("## 每日條目數")
    add("| 日 | 分支 | 條目 | 比對成功 |")
    add("|---|---|---|---|")
    seen = {}
    for e in entries:
        k = (e["day"], e["branch"])
        seen.setdefault(k, [0, 0])
        seen[k][0] += 1
        seen[k][1] += e["match"]["status"] == "matched"
    for (d, b), (n, m) in sorted(seen.items(), key=lambda x: (str(x[0][0]), str(x[0][1]))):
        add(f"| {d} | {b or '—'} | {n} | {m} |")
    add("")

    for label, status in [("比對不到", "unmatched"), ("比對到多個", "ambiguous")]:
        bad = [e for e in entries if e["match"]["status"] == status]
        add(f"## {label}（{len(bad)}）")
        if not bad:
            add("- 無")
        for e in bad:
            add(f"- L{e['src']['line']} `{e['title']}`（{e['day']}）")
            for c in e["match"].get("candidates", []) or e["match"].get("candidates", []):
                add(f"    - {c['score']} {c['name']} → `{c['target']}`")
            if not e["match"].get("candidates"):
                add("    - 沒有任何候選")
        add("")

    add("## 標記與欄位標籤")
    fl = {}
    for e in entries:
        for f in e["flags"]:
            fl.setdefault(f["raw"], [f["status"], 0])[1] += 1
    add("| 標記 | 判定 | 次數 |")
    add("|---|---|---|")
    for k, (s, n) in sorted(fl.items()):
        add(f"| 【{k}】 | {s}{' <-- 未知，請補進 FLAG_STATUS' if s == 'unknown' else ''} | {n} |")
    add("")
    keys = {}
    for e in entries:
        for f in e["fields"]:
            keys[f["k"]] = keys.get(f["k"], 0) + 1
    add(f"- 欄位標籤共 {len(keys)} 種：" + "、".join(f"{k}({v})" for k, v in
                                                sorted(keys.items(), key=lambda x: -x[1])))
    add("")

    add("## 連結角色")
    np_ = sum(1 for e in entries for l in e["links"] if l["role"] == "parking")
    ne = [e for e in entries if e["links"] and not any(l["role"] == "place" for l in e["links"])]
    add(f"- 停車場連結 {np_} 個")
    add(f"- 只有停車場連結、沒有地點連結的條目 {len(ne)} 個"
        f"（導航鈕會標成「停車場導航」）：")
    for e in ne:
        add(f"  - L{e['src']['line']} {e['title']}")
    add("")

    add("## 註記（掛在當日，不是地點）")
    for n in notes:
        add(f"- L{n['line'] if 'line' in n else n['src']['line']} "
            f"{n.get('title') or n['title']}")
    add("")

    report = "\n".join(L)
    BUILD.mkdir(exist_ok=True)
    (BUILD / "guide_report.md").write_text(report, encoding="utf-8")
    print(report)
    print(f"\n報告已寫到 {BUILD / 'guide_report.md'}")

    if args.report:
        print("\n(--report 模式，沒有寫出 guide.json)")
        return

    if st["unmatched"] or st["ambiguous"]:
        sys.exit(f"\n還有 {st['unmatched']} 個比對不到、{st['ambiguous']} 個比對到多個；"
                 f"請先在 guide_overrides.json 處理完再 --write。")

    OUT.write_text(json.dumps({"version": 1, "source": f"private/raw/{src.name}",
                               "entries": entries, "notes": notes},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    seed = {"_readme": ["parse_guide.py 產生的種子；日文原名與座標由 resolve_places.py 回填。"],
            "places": {e["id"]: {"name": e["names"],
                                 "query": next((l["query"] for l in e["links"]
                                                if l["role"] == "place"), ""),
                                 "verified": "inferred"} for e in entries}}
    if not PLACES.exists():
        PLACES.write_text(json.dumps(seed, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"寫出 {PLACES}（種子）")
    else:
        print(f"{PLACES} 已存在，沒有覆蓋。")
    print(f"寫出 {OUT}  ({len(OUT.read_bytes()):,} B)")


if __name__ == "__main__":
    main()
