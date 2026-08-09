# -*- coding: utf-8 -*-
"""三行名稱、常駐標籤、可收合的逐點說明。這一檔不含任何地名、日期或時段。"""
from __future__ import annotations

from ..maps import search_url
from .text import E, display_name, same_name

# 一直可見的欄位。操作性資料不進收合 — 到現場要看的東西不該再點一下才出現。
ALWAYS = {"類型": "kind", "時間提示": "when", "狀態": "state"}
GOAL = "明確目標"
# 停車相關的欄位在按鈕區處理，不重複塞進詳細
PARK_FIELDS = {"停車", "停車二選一"}


def names_html(place: dict | None, fallback: str) -> str:
    """日文原名為主標，中文與英文發音為次行。

    次行與主標正規化後相同就不輸出 — 拉丁字母店名三行都一樣，
    整排重複的字只會把卡片撐高。
    """
    n = (place or {}).get("name") or {}
    jp = display_name(n.get("jp") or "") or fallback
    alt = []
    zh = (n.get("zh") or "").strip()
    en = (n.get("en") or "").strip()
    if zh and not same_name(zh, jp):
        alt.append(f"{E(zh)}")
    if en and not same_name(en, jp) and not same_name(en, zh):
        alt.append(f'<span class="en">{E(en)}</span>')
    out = f'<h3 class="sname">{E(jp)}</h3>'
    if alt:
        out += f'<p class="salt">{"　".join(alt)}</p>'
    return out


def tags_html(entries: list[dict]) -> tuple[str, bool]:
    """常駐標籤。回傳 (html, 是不是備選)。"""
    tags, optional = [], False
    seen = set()
    for e in entries:
        for f in e.get("flags") or []:
            raw = f["raw"] if isinstance(f, dict) else f
            if raw in seen:
                continue
            seen.add(raw)
            optional = True
            tags.append(f'<span class="tag flag">{E(raw)}</span>')
        for fd in e.get("fields") or []:
            cls = ALWAYS.get(fd["k"])
            if not cls:
                continue
            v = fd["v"].strip().rstrip("。")
            if v in seen:
                continue
            seen.add(v)
            tags.append(f'<span class="tag {cls}">{E(v)}</span>')
    return (f'<div class="tags">{"".join(tags)}</div>' if tags else ""), optional


def goal_html(entries: list[dict]) -> str:
    for e in entries:
        for fd in e.get("fields") or []:
            if fd["k"] == GOAL:
                return f'<div class="goal">◎ {E(fd["v"])}</div>'
    return ""


def _body(e: dict) -> list[str]:
    out = []
    for fd in e.get("fields") or []:
        if fd["k"] in ALWAYS or fd["k"] == GOAL or fd["k"] in PARK_FIELDS:
            continue
        v = (fd["v"] or "").strip()
        if not v:
            continue  # 來源有欄位是空的，留著只會多一條空行
        # 只印內容不印欄位名。「角色」「定位」這些是來源 md 的結構標籤，
        # 不是給人讀的字，而值本身已經是完整句子。
        out.append(f'<p class="fld">{E(v)}</p>')
    bl = e.get("bullets") or []
    if bl:
        out.append("<ul>" + "".join(f"<li>{E(b)}</li>" for b in bl) + "</ul>")
    for b in e.get("blocks") or []:
        # 有標題的小清單(例如停車的優先順序)。順序有意義，用 ol 保留。
        tag = "ol" if b.get("type") == "ordered" else "ul"
        out.append(f'<p class="sub">{E(b.get("label", ""))}</p>'
                   f'<{tag}>' + "".join(f"<li>{E(x)}</li>" for x in b.get("items") or [])
                   + f"</{tag}>")
    return out


def detail_html(entries: list[dict], children: list[dict] | None = None) -> str:
    """收合的說明。沒有內容就不長這顆鈕 — 空的收合鈕比沒有更煩。

    鈕上的數字是藏起來的項目數，讓人知道值不值得點。
    """
    parts, n = [], 0
    for e in entries:
        b = _body(e)
        if not b:
            continue
        n += len([x for x in b if x.startswith('<p class="fld"')])
        n += sum(x.count("<li>") for x in b)
        n += len([x for x in b if x.startswith('<p class="sub"')])
        parts.extend(b)
    for c in children or []:
        b = _body(c)
        if not b:
            continue
        # 子條目自成一個小區塊。不能用 .fld 的標籤欄 — 那一欄是 flex:0 0 auto，
        # 設計給「角色」這種兩三個字的欄位名，長店名會把整個容器撐出畫面。
        parts.append(f'<div class="kid"><b>{E(c["title"])}</b>{"".join(b)}</div>')
        n += 1
    if not parts:
        return ""
    return (f'<details class="detail"><summary>詳細 ·{n}</summary>'
            f'<div class="dbody">{"".join(parts)}</div></details>')


def parking_buttons(place: dict | None) -> str:
    """停車按鈕。逐家實查的結果分兩類，顯示方式不同。

    lot     查到確定可停的場 -> 直接導航過去，標距離
    search  周邊只有月租或需事前預約的 -> 給以店家座標為中心的即時搜尋。
            把月租場當成可停的地方推出去，比沒有按鈕更糟。
    """
    pk = (place or {}).get("parking_hint")
    if not pk:
        return ""
    if pk.get("kind") == "lot":
        url = search_url(pk["name"], {"place_id": pk.get("pid")} if pk.get("pid") else None)
        dist = f'（{pk["m"]} m）' if pk.get("m") else ""
        out = [f'<a class="pbtn" href="{E(url)}" target="_blank" rel="noopener">'
               f'停車導航{E(dist)}</a>']
    else:
        c = (place or {}).get("coords") or {}
        if not c:
            return ""
        url = f'https://www.google.com/maps/search/%E9%A7%90%E8%BB%8A%E5%A0%B4/@{c["lat"]},{c["lng"]},17z'
        out = [f'<a class="pbtn hint" href="{E(url)}" target="_blank" rel="noopener">附近停車場</a>']
    if pk.get("note"):
        out.append(f'<p class="phint">🅿 {E(pk["note"])}</p>')
    return "".join(out)
