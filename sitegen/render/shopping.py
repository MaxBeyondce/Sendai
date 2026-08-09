# -*- coding: utf-8 -*-
"""購物分頁。這一檔不含任何店名或品名。

圖片不寫進 <img src>：92 張 480×480 全部解碼是 84MB 點陣圖，
舊機器的分頁會被系統收掉。base64 收在一個 JSON 區塊裡，捲到才填 src。
順帶讓標記量從約 2MB 掉到約 250KB，解鎖當下 0 張圖解碼。

搜尋字串不存進資料：來源有五分之一缺這個標註，但規則就是
店名＋品名＋說明，與其補齊再存，不如在瀏覽器端現算 — 省位元組，
也少一個會跟品名脫節的欄位。
"""
from __future__ import annotations

import json

from ..assets import data_uri
from ..data import SHOPPING
from .text import E


def _stores() -> list[dict]:
    return sorted(SHOPPING["stores"], key=lambda s: s.get("order", 999))


def labels_html() -> str:
    """黏頂列在購物分頁時顯示的標籤：全部＋各店家，em 是採購進度。"""
    if not SHOPPING:
        return ""
    items = SHOPPING["items"]
    out = ['<div class="labelset" data-for="shop" hidden>']
    out.append(f'<button class="dbtn on" data-store="all">全部<em>0/{len(items)}</em></button>')
    for s in _stores():
        n = sum(1 for it in items if it["store"] == s["id"])
        if not n:
            continue
        out.append(f'<button class="dbtn" data-store="{E(s["id"])}">'
                   f'{E(s.get("short") or s["name"])}<em>0/{n}</em></button>')
    out.append("</div>")
    return "".join(out)


def _item(it: dict) -> str:
    tid = f'k{it["id"]}'
    out = [f'<div class="it" data-store="{E(it["store"])}" data-n="{E(it["name"])}" '
           f'data-d="{E(it.get("desc", ""))}">']
    out.append('<div class="ph">')
    out.append(f'<input type="checkbox" class="tick" id="{tid}" aria-label="標記已買">')
    out.append(f'<label class="tickbox" for="{tid}"></label>')
    if it.get("img"):
        out.append(f'<img data-img="{E(it["id"])}" alt="" width="{it.get("w", 480)}" '
                   f'height="{it.get("h", 480)}" decoding="async">')
    out.append("</div>")
    out.append(f'<div class="nm">{E(it["name"])}</div>')
    if it.get("desc"):
        out.append(f'<div class="ds">{E(it["desc"])}</div>')
    out.append("</div>")
    return "".join(out)


def _extra(x: dict) -> str:
    """附註不是品項 — 有自己的表格，不進格線也不算進採購進度。"""
    t = x.get("table") or {}
    out = [f'<div class="extra"><b>{E(x.get("title", ""))}</b><table><thead><tr>']
    out.extend(f"<th>{E(h)}</th>" for h in t.get("head") or [])
    out.append("</tr></thead><tbody>")
    for r in t.get("rows") or []:
        out.append(f'<tr class="st-{E(r.get("status", ""))}">'
                   + "".join(f"<td>{E(c)}</td>" for c in r.get("cells") or []) + "</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def pane_html() -> str:
    if not SHOPPING:
        return '<section class="pane" data-pane="shop" hidden></section>'
    items = SHOPPING["items"]
    extras = SHOPPING.get("extras") or []
    out = ['<section class="pane" data-pane="shop" hidden>']
    out.append('<div class="shoptools"><div class="row">'
               '<input id="shopQ" type="search" placeholder="搜尋品名、說明或店家" autocomplete="off">'
               '<label class="toggle"><input type="checkbox" id="onlyLeft">只看未買</label>'
               '</div>'
               f'<p class="shopsum">顯示 <b id="shopShown">{len(items)}</b> 項；'
               f'已買 <b id="shopDone">0</b> / {len(items)} 項</p></div>')

    for s in _stores():
        rows = [it for it in items if it["store"] == s["id"]]
        if not rows:
            continue
        days = "".join(
            f'<a href="#{d}" data-dayjump="{d}">{d}</a>' for d in (s.get("days") or []))
        dtxt = f'<span class="days">{days} 會經過</span>' if days else \
               '<span class="days">不綁行程</span>'
        out.append(f'<section class="shopstore" id="store-{E(s["id"])}" data-store="{E(s["id"])}">'
                   f'<header><h2>{E(s["name"])}{dtxt}'
                   f'<span class="days stprog">0/{len(rows)}</span></h2></header>'
                   f'<div class="grid">')
        out.extend(_item(it) for it in rows)
        out.append("</div>")
        out.extend(_extra(x) for x in extras if x.get("store") == s["id"])
        out.append("</section>")

    out.append('<p class="empty" id="shopEmpty" hidden>沒有符合的品項。清掉搜尋字或改選其他店家。</p>')

    # 圖片 base64 收在 JSON 區塊。用 script 標籤不是 <img src>，
    # 所以解鎖當下瀏覽器不會去解碼任何一張。
    imgs = {it["id"]: data_uri(it["img"]) for it in items if it.get("img")}
    imgs = {k: v for k, v in imgs.items() if v}
    out.append('<script type="application/json" id="shopimg">'
               + json.dumps(imgs, ensure_ascii=False, separators=(",", ":"))
               + "</script>")
    out.append("</section>")
    return "".join(out)


def stores_by_day() -> dict[str, list[dict]]:
    """哪一天會經過哪些店 — 行程頁用這個標出「今天會經過…」。"""
    out: dict[str, list[dict]] = {}
    for s in (SHOPPING or {}).get("stores", []):
        for d in s.get("days") or []:
            out.setdefault(d, []).append(s)
    return out
