# -*- coding: utf-8 -*-
"""候選手風琴。這一檔不含任何地名、日期或時段。

**兩個都叫 Plan 的東西在這裡分開**：

  整天分支   資料上的 stop.branch，天氣二選一，會換掉整條開車路線
  單點候選   同一個時段挑一家，不影響當日路線 -> 這一檔處理，叫「候選 A、B、C…」

來源自己的〈使用原則〉寫明只有一天正式設 Plan A／Plan B，所以單點的那種
不跟著叫 Plan — 同一份行程表裡兩個都叫 Plan A，路上會看錯。
"""
from __future__ import annotations

import re

from ..data import CHOICE_STOPS, children_of
from ..maps import search_url
from .detail import detail_html, names_html, parking_buttons, tags_html
from .text import E

LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
CHOICE = re.compile(r"候選|可選|選項|二選")


def candidates(stop: dict) -> tuple[list[dict], bool]:
    """回傳 (候選條目, 是不是二選一)。

    兩種來源：
      群組     一條 kind=group 的說明對到這一站 -> 它的子條目就是候選
      多重對應 好幾條 kind=place 對到同一站 -> 那些就是候選

    「是不是二選一」看群組標題或站名有沒有寫候選／可選 —
    有些站是「這一站包含這幾家」而不是「挑一家」，混在一起會誤導。
    """
    entries = stop.get("guide") or []
    forced = stop.get("key") in CHOICE_STOPS
    groups = [e for e in entries if e.get("kind") == "group"]
    if groups:
        kids = children_of(groups[0])
        if kids:
            title = groups[0].get("title", "") + stop.get("name", "")
            return kids, forced or bool(CHOICE.search(title))
    places = [e for e in entries if e.get("kind") == "place"]
    if len(places) >= 2:
        return places, forced or bool(CHOICE.search(stop.get("name", "")))
    return [], False


def pick_html(idx: int, entry: dict, place: dict | None, want_parking: bool) -> str:
    letter = LETTERS[idx] if idx < len(LETTERS) else str(idx + 1)
    nm = (place or {}).get("name", {}).get("jp") or entry.get("names", {}).get("jp") or entry["title"]
    out = [f'<details class="pick"><summary><span class="ltr">{letter}</span>'
           f'<span class="pn">{E(nm)}</span></summary><div class="pickbody">']
    out.append(names_html(place, entry["title"]))
    tg, _ = tags_html([entry])
    out.append(tg)
    out.append(detail_html([entry]))

    out.append('<div class="actions">')
    q = None
    for lk in entry.get("links") or []:
        if lk.get("role") != "parking":
            q = lk.get("query")
            break
    if q:
        out.append(f'<a class="gbtn" href="{E(search_url(q, place))}" target="_blank" rel="noopener">店家導航</a>')
    if want_parking:
        out.append(parking_buttons(place))
    out.append("</div></div></details>")
    return "".join(out)


def picks_html(stop: dict, want_parking: bool, places_by_id: dict) -> str:
    ents, choice = candidates(stop)
    if len(ents) < 2:
        return ""
    out = [f'<div class="picks{" choice" if choice else ""}">']
    for i, e in enumerate(ents):
        out.append(pick_html(i, e, places_by_id.get(e.get("id")), want_parking))
    out.append("</div>")
    return "".join(out)
