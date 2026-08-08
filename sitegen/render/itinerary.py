# -*- coding: utf-8 -*-
"""站點卡片與每日區塊。這一檔不含任何地名、日期或時段。"""
from __future__ import annotations

from urllib.parse import unquote

from ..data import cluster_for
from ..maps import search_url
from .routes import route_block, day_routes
from .text import E

# verified 的顯示對照。空字串代表不顯示警示 — 只有查不到位置的才需要提醒。
VER_LABEL = {"address": "", "route": "", "place_id": "", "coords": "",
             "review": "", "inferred": "位置待確認"}


def stop_html(day_id: str, idx: int, s: dict) -> str:
    sid = f"{day_id}-{idx}"
    place = s.get("place") or {}
    out = [f'<li class="stop" id="s{sid}">']
    out.append(f'<input type="checkbox" class="tick" id="t{sid}" aria-label="標記已完成">')
    out.append(f'<label class="tickbox" for="t{sid}"></label>')
    out.append('<div class="sbody">')
    out.append(f'<div class="stime">{E(s["time"])}</div>')
    out.append(f'<h3 class="sname">{E(s["name"])}</h3>')
    if s.get("memo"):
        out.append(f'<p class="smemo">{E(s["memo"])}</p>')

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
                       f'{E(c["name"])}{warn}</a>{memo}</li>')
        out.append("</ol>")
        out.append(route_block(cl["stops"], cl["mode"], cl["label"], cl.get("note", "")))
        out.append("</div>")

    if s.get("query"):
        out.append(f'<div class="actions"><a class="gbtn" href="{E(search_url(unquote(s["query"]), place))}" '
                   f'target="_blank" rel="noopener">導航到這裡</a></div>')
    out.append("</div></li>")
    return "".join(out)


def day_section(d: dict) -> str:
    p = [f'<section class="day" id="{d["id"]}" data-date="{E(d["date"])}">']
    p.append(f'<div class="dhead"><div class="dtop"><span class="badge">{d["id"]}</span>'
             f'<span class="date">{E(d["date"])}</span></div>')
    p.append(f'<h2>{E(d["title"])}</h2>')
    if d.get("anchor"):
        p.append(f'<p class="anchor">{E(d["anchor"])}</p>')
    if d.get("stay") and d["stay"] != "—":
        p.append(f'<p class="stay">住宿｜<b>{E(d["stay"])}</b></p>')
    p.append('<div class="prog"><span class="bar"><i></i></span><span class="ptxt"></span></div>')
    p.append("</div>")

    rb = day_routes(d)
    if rb:
        p.append(f'<div class="droutes">{rb}</div>')

    p.append('<ol class="stops">')
    for i, s in enumerate(d["stops"]):
        p.append(stop_html(d["id"], i, s))
    p.append("</ol>")

    if d.get("notes"):
        p.append('<div class="notes"><b>當日提醒</b><ul>'
                 + "".join(f"<li>{E(n)}</li>" for n in d["notes"]) + "</ul></div>")
    p.append("</section>")
    return "".join(p)
