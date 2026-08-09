# -*- coding: utf-8 -*-
"""路線按鈕。這一檔不含任何地名、日期或時段 — 分支與跳過都由資料上的欄位決定。"""
from __future__ import annotations

from ..config import MAX_PER_LEG, MAX_SINGLE
from ..maps import route_url, segment
from .text import E, short

ICON = {"driving": "🚗", "walking": "🚶", "transit": "🚌"}


def route_block(stops: list[dict], mode: str, label: str, note: str = "") -> str:
    """一組路線按鈕：整段(站數夠少時)＋分段。"""
    stops = [s for s in stops if s.get("query")]
    if len(stops) < 2:
        return ""
    out = ['<div class="routegrp">']
    out.append(f'<div class="routelabel">{ICON.get(mode, "📍")} {E(label)}'
               f'<span class="cnt">{len(stops)}站</span></div>')
    out.append('<div class="routebtns">')
    if len(stops) <= MAX_SINGLE:
        out.append(f'<a class="rbtn whole" href="{E(route_url(stops, mode))}" target="_blank" rel="noopener">'
                   f'整段一次開<em>{E(short(stops[0]["name"]))} → {E(short(stops[-1]["name"]))}</em></a>')
    legs = segment(stops)
    if len(legs) > 1:
        for n, leg in enumerate(legs, 1):
            out.append(f'<a class="rbtn" href="{E(route_url(leg, mode))}" target="_blank" rel="noopener">'
                       f'第{n}段<em>{E(short(leg[0]["name"]))} → {E(short(leg[-1]["name"]))}</em></a>')
    out.append("</div>")
    if note:
        out.append(f'<p class="routenote">{E(note)}</p>')
    if len(stops) > MAX_PER_LEG:
        out.append('<p class="routehint">手機瀏覽器一條路線最多 3 個中繼點，所以拆成每段 5 站；'
                   '在 Google Maps app 裡開「整段一次開」可到 11 站。</p>')
    out.append("</div>")
    return "".join(out)


def day_routes(day: dict) -> str:
    """當日開車路線；有分支的日子分成兩條，不併成一條。"""
    if not day.get("drive", True):
        return ""  # 這一天沒有車，路線走群組(步行／大眾運輸)
    usable = [s for s in day["stops"]
              if s.get("query") and s.get("route", True) is not False]
    if not any(s.get("branch") for s in day["stops"]):
        return route_block(usable, "driving", "當日開車路線")
    a = [s for s in usable if s.get("branch") != "B"]
    b = [s for s in usable if s.get("branch") != "A"]
    # 包成一個有標頭的容器。兩塊並排時看不出是二選一，
    # 而這是整天走哪條路的分歧 — 跟單點的「候選」不是同一件事。
    return ('<div class="branch"><div class="brhead">🌤 整天二選一'
            '<span>兩條路線挑一條走，不是先後順序</span></div>'
            + route_block(a, "driving", "Plan A｜當日開車路線")
            + route_block(b, "driving", "Plan B｜當日開車路線")
            + "</div>")
