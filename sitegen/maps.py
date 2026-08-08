# -*- coding: utf-8 -*-
"""Google Maps 網址組裝。這一檔不含任何地名。

路線網址優先用 place_id：地圖上顯示的是店名而不是一串經緯度，路上比較好確認點對了。
順位是 place_id -> 座標 -> 文字查詢。**同一段裡不混用** — waypoint_place_ids 的數量
與順序必須跟 waypoints 完全對得上，只要有一站缺 place_id 就整段退回文字查詢。
混用不會報錯，只會靜默導到別的地方，那比退回文字查詢糟得多。
"""
from __future__ import annotations

from urllib.parse import quote, unquote

from .config import MAX_PER_LEG

BASE_DIR = "https://www.google.com/maps/dir/?api=1"
BASE_SEARCH = "https://www.google.com/maps/search/?api=1"


def q(s: str) -> str:
    """統一成純文字再重新編碼，避免原檔已編碼與新資料混用。"""
    return quote(unquote(s), safe="")


def _pid(stop: dict) -> str:
    """站點身上的 place_id；由 places.json 在載入時疊上去。"""
    return (stop.get("place") or {}).get("place_id") or ""


def route_url(stops: list[dict], mode: str) -> str:
    qs = [q(s["query"]) for s in stops]
    url = f"{BASE_DIR}&origin={qs[0]}&destination={qs[-1]}"
    if len(qs) > 2:
        url += "&waypoints=" + "%7C".join(qs[1:-1])

    pids = [_pid(s) for s in stops]
    if all(pids):
        url += f"&origin_place_id={q(pids[0])}&destination_place_id={q(pids[-1])}"
        if len(pids) > 2:
            url += "&waypoint_place_ids=" + "%7C".join(q(p) for p in pids[1:-1])
    return url + f"&travelmode={mode}"


def search_url(query: str, place: dict | None = None) -> str:
    """單點導航。帶 place_id 時 Google 會直接開那一個地點，不再做一次搜尋。"""
    url = f"{BASE_SEARCH}&query={q(query)}"
    pid = (place or {}).get("place_id")
    return url + f"&query_place_id={q(pid)}" if pid else url


def segment(stops: list[dict]) -> list[list[dict]]:
    """切成每段最多 5 站，前一段終點即下一段起點。"""
    if len(stops) <= MAX_PER_LEG:
        return [stops]
    legs, i = [], 0
    while i < len(stops) - 1:
        legs.append(stops[i:i + MAX_PER_LEG])
        i += MAX_PER_LEG - 1
    return legs
