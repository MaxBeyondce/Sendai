# -*- coding: utf-8 -*-
"""站點卡片與每日區塊。這一檔不含任何地名、日期或時段。"""
from __future__ import annotations

from urllib.parse import unquote

from ..data import PLACES, children_of, cluster_for
from ..maps import search_url
from .detail import detail_html, goal_html, names_html, parking_buttons, tags_html
from .plans import candidates, picks_html
from .routes import route_block, day_routes
from .shopping import stores_by_day
from .text import E

# verified 的顯示對照。空字串代表不顯示警示 — 只有查不到位置的才需要提醒。
VER_LABEL = {"address": "", "route": "", "place_id": "", "coords": "",
             "review": "", "inferred": "位置待確認"}


def stop_html(day_id: str, idx: int, s: dict, want_parking: bool) -> str:
    sid = f"{day_id}-{idx}"
    place = s.get("place") or {}
    entries = s.get("guide") or []
    picks, _ = candidates(s)
    # 有候選的站，說明歸各候選自己，不重複放在卡片層
    own = [] if picks else entries

    tg, optional = tags_html(own)
    out = [f'<li class="stop{" optional" if optional else ""}" id="s{sid}">']
    out.append(f'<input type="checkbox" class="tick" id="t{sid}" aria-label="標記已完成">')
    out.append(f'<label class="tickbox" for="t{sid}"></label>')
    out.append('<div class="sbody">')
    out.append(f'<div class="stime">{E(s["time"])}</div>')
    out.append(names_html(place if not picks else None, s["name"]))
    out.append(tg)
    out.append(goal_html(own))
    if s.get("memo"):
        out.append(f'<p class="smemo">{E(s["memo"])}</p>')
    # 父條目底下的子項要一起收進詳細。只有 kind=group 的父條目其子項會變成
    # 候選手風琴；父條目是一個實際地點時，子項是它裡面的小點，
    # 不能當成「挑一家」，但也不能就這樣消失。
    kids = [k for e in own for k in children_of(e)]
    out.append(detail_html(own, kids))

    if s.get("parking"):
        out.append('<div class="parks">')
        for p in s["parking"]:
            note = f'<span>{E(p["note"])}</span>' if p.get("note") else ""
            link = (f'<a class="pbtn" href="{E(search_url(unquote(p["query"]), p.get("place")))}" '
                    f'target="_blank" rel="noopener">停車場導航</a>') if p.get("query") else ""
            out.append(f'<div class="park"><strong>🅿 {E(p["name"])}</strong>{note}{link}</div>')
        out.append("</div>")

    cl = cluster_for(day_id, s["time"])
    if cl:
        out.append('<div class="cluster">')
        out.append(f'<div class="clhead">{"重排過的順序" if cl["reordered"] else "順序未變"}</div>')
        out.append('<ol class="chips">')
        for c in cl["stops"]:
            tag = VER_LABEL.get(c.get("verified", ""), "")
            memo = f'<span class="cmemo">{E(c["memo"])}</span>' if c.get("memo") else ""
            warn = f'<span class="cwarn">{tag}</span>' if tag else ""
            out.append(f'<li><a href="{E(search_url(c["query"], c.get("place")))}" target="_blank" rel="noopener">'
                       f'{E(c["name"])}{warn}</a>{memo}')
            # 群組成員也是站點，它們的逐點說明一樣要出得來。
            # data.attach() 已經把說明掛上去了，這裡少讀就等於整批不見。
            ce = c.get("guide") or []
            if ce:
                ct, _ = tags_html(ce)
                out.append(ct)
                out.append(detail_html(ce, [k for e in ce for k in children_of(e)]))
            out.append("</li>")
        out.append("</ol>")
        out.append(route_block(cl["stops"], cl["mode"], cl["label"], cl.get("note", "")))
        out.append("</div>")

    out.append(picks_html(s, want_parking, PLACES))

    if s.get("query") and not picks:
        out.append('<div class="actions">')
        out.append(f'<a class="gbtn" href="{E(search_url(unquote(s["query"]), place))}" '
                   f'target="_blank" rel="noopener">導航到這裡</a>')
        out.append(parking_buttons(place))
        out.append("</div>")
    out.append("</div></li>")
    return "".join(out)


def shop_hint(day_id: str) -> str:
    """今天會經過哪些購物清單上的店。點一下切到購物分頁並篩選到那一家。"""
    stores = stores_by_day().get(day_id) or []
    if not stores:
        return ""
    links = "、".join(
        f'<a href="#store-{E(s["id"])}" data-shopjump="{E(s["id"])}">{E(s.get("short") or s["name"])}</a>'
        for s in stores)
    return f'<p class="stay">🛒 今天會經過｜{links}</p>'


def day_section(d: dict) -> str:
    # 沒有車的日子不給停車按鈕 — 那天的移動是走路與大眾運輸
    want_parking = d.get("drive", True)
    p = [f'<section class="day" id="{d["id"]}" data-date="{E(d["date"])}">']
    p.append(f'<div class="dhead"><div class="dtop"><span class="badge">{d["id"]}</span>'
             f'<span class="date">{E(d["date"])}</span></div>')
    p.append(f'<h2>{E(d["title"])}</h2>')
    if d.get("anchor"):
        p.append(f'<p class="anchor">{E(d["anchor"])}</p>')
    if d.get("stay") and d["stay"] != "—":
        p.append(f'<p class="stay">住宿｜<b>{E(d["stay"])}</b></p>')
    p.append(shop_hint(d["id"]))
    p.append('<div class="prog"><span class="bar"><i></i></span><span class="ptxt"></span></div>')
    p.append("</div>")

    rb = day_routes(d)
    if rb:
        p.append(f'<div class="droutes">{rb}</div>')

    p.append('<ol class="stops">')
    for i, s in enumerate(d["stops"]):
        p.append(stop_html(d["id"], i, s, want_parking))
    p.append("</ol>")

    if d.get("notes"):
        p.append('<div class="notes"><b>當日提醒</b><ul>'
                 + "".join(f"<li>{E(n)}</li>" for n in d["notes"]) + "</ul></div>")
    p.append("</section>")
    return "".join(p)
