# -*- coding: utf-8 -*-
"""把 Google Maps 查到的原名／座標／place_id 併進 places.json，並出一張覆核表。

查詢本身在瀏覽器裡跑（Maps 是純前端渲染，伺服器端抓不到資料），
結果記在 private/resolved_places.json，這一支只負責合併與檢查。

查詢用的網址：
    https://www.google.com/maps/search/?api=1&query=<查詢字串>&hl=ja&gl=jp

**hl=ja 不能省**。不加的話 Google 會依瀏覽器語系把名稱在地化，
拿到的是中文譯名而不是招牌上的日文原名 — 那就違背了「標示 Google Maps 上的
日文原名」這個需求本身。

  python tools/resolve_places.py --report   只出覆核表
  python tools/resolve_places.py --write    寫回 places.json

判定規則：
  direct  前端直接落到單一地點頁 -> 採用，標 verified=place_id 或 coords
  list    回傳搜尋結果清單       -> 採用第一筆但標 verified=review，覆核表列出其他候選
  reject  明確不採用（例如回傳的是行政區而不是店家）-> 維持 inferred，繼續顯示「位置待確認」

這一檔會進公開 repo，所以不含任何地名 — 查詢字串與結果都在 private/ 那一份。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLACES = ROOT / "places.json"
RESOLVED = ROOT / "private" / "resolved_places.json"
BUILD = ROOT / "build"


def norm_q(s: str) -> str:
    return re.sub(r"\s+", "", s).casefold()


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--report", action="store_true")
    g.add_argument("--write", action="store_true")
    args = ap.parse_args()

    if not RESOLVED.exists():
        sys.exit(f"找不到 {RESOLVED}；查詢結果應該放在 private/ 之下。")
    if not PLACES.exists():
        sys.exit(f"找不到 {PLACES}；先跑 tools/parse_guide.py --write 產生種子。")

    res = json.loads(RESOLVED.read_text(encoding="utf-8"))
    doc = json.loads(PLACES.read_text(encoding="utf-8"))
    places = doc["places"]
    by_q = {norm_q(r["q"]): r for r in res["looked_up"]}
    short = res.get("short", {})

    rows, unresolved = [], []
    for pid, p in places.items():
        before = p["name"]["jp"]
        r = short.get(pid)
        if r:
            src, name, coord, gid, alts, rej = "短網址", r["name"], r["coord"], "", [], ""
        else:
            r = by_q.get(norm_q(p.get("query", "")))
            if not r:
                if not before:
                    unresolved.append((pid, p))
                continue
            src = {"direct": "直接命中", "list": "清單第一筆"}.get(r["mode"], r["mode"])
            name, coord, gid = r["name"], r.get("coord", ""), r.get("pid", "")
            alts, rej = r.get("alts", []), r.get("reject", "")

        if rej:
            rows.append((pid, before, name, "不採用", rej, alts))
            continue

        verified = ("place_id" if gid else "coords") if src != "清單第一筆" else "review"
        if src == "短網址":
            verified = "coords"
        rows.append((pid, before, name, src, verified, alts))

        if args.write:
            p["name"]["jp"] = name
            if not p["name"]["zh"]:
                p["name"]["zh"] = name
            if coord:
                la, ln = coord.split(",")
                p["coords"] = {"lat": float(la), "lng": float(ln)}
            if gid:
                p["place_id"] = gid
            p["verified"] = verified

    L = ["# 地點名稱覆核表\n",
         "查法：Google Maps `?api=1&query=…&hl=ja&gl=jp`，等前端改寫網址後讀 h1 與座標。",
         "**hl=ja 必要**：不加會依瀏覽器語系拿到中文譯名，不是招牌上的日文原名。\n",
         "| id | 原本寫法 | Google Maps 日文原名 | 來源 | 判定 |",
         "|---|---|---|---|---|"]
    need = []
    for pid, before, name, src, verified, alts in rows:
        mark = {"place_id": "OK", "coords": "OK", "review": "**要覆核**", "不採用": "**不採用**"}.get(verified, verified)
        L.append(f"| `{pid}` | {before or '—'} | **{name}** | {src} | {mark} |")
        if verified in ("review", "不採用") or alts:
            need.append((pid, name, src, verified, alts))
    L.append("")
    L.append(f"## 需要你判斷的（{len(need)}）")
    L.append("")
    for pid, name, src, verified, alts in need:
        L.append(f"- `{pid}` -> **{name}**（{src}）")
        if alts:
            L.append(f"    其他候選：{'、'.join(alts)}")
        if verified == "不採用":
            L.append(f"    {verified}")
    if unresolved:
        L.append("")
        L.append(f"## 沒有查詢結果、維持「位置待確認」（{len(unresolved)}）")
        for pid, p in unresolved:
            L.append(f"- `{pid}` query=`{p.get('query', '')}`")

    out = "\n".join(L)
    BUILD.mkdir(exist_ok=True)
    (BUILD / "places_report.md").write_text(out, encoding="utf-8")
    print(out)
    print(f"\n報告已寫到 {BUILD / 'places_report.md'}")

    if args.write:
        PLACES.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        n = sum(1 for p in places.values() if p["name"]["jp"])
        print(f"\n寫回 {PLACES}：{n}/{len(places)} 筆有日文原名")
    else:
        print("\n(--report 模式，沒有寫回 places.json)")


if __name__ == "__main__":
    main()
