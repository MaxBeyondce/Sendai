# -*- coding: utf-8 -*-
"""載入所有資料檔並把它們接在一起。這一檔不含任何地名。

四份來源、四種生命週期，所以分四個檔，在這裡疊起來：

  trip_data.json  extract.py 機器抽出來的行程原貌
  clusters.json   步行／大眾運輸群組
  places.json     地點名稱／座標／place_id 的單一來源
  guide.json      逐點說明；靠 match.target 掛回行程站點
  shopping.json   購物清單

產生的檔案一律不手改，手改的部分在相鄰的 *_overrides.json，載入時疊上去。
選用的檔案缺席不會中止 — 覆蓋率是漸進的，缺說明或缺購物清單就少一塊，不會壞。
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from .config import ROOT


def _load(name: str, key: str | None = None, required: bool = True):
    p = ROOT / name
    if not p.exists():
        if required:
            raise SystemExit(f"找不到 {p}；已中止。")
        return None
    doc = json.loads(p.read_text(encoding="utf-8"))
    return doc[key] if key else doc


DATA = _load("trip_data.json")
CLUSTERS = _load("clusters.json", "clusters")
PLACES = (_load("places.json", "places", required=False) or {})
GUIDE = (_load("guide.json", required=False) or {}).get("entries", [])
SHOPPING = _load("shopping.json", required=False)


def norm(s: str) -> str:
    """比對用的正規化：全半形統一、去掉空白與標點。"""
    s = unicodedata.normalize("NFKC", s or "")
    return re.sub(r"[\s・･\-–—〜~,、。．.]+", "", s).casefold()


def _place_index() -> dict[str, str]:
    """名稱／查詢字串 -> place key。同一個 key 可能有好幾種寫法指得到。"""
    idx: dict[str, str] = {}
    for k, v in PLACES.items():
        cand = [v["name"].get("jp"), v["name"].get("zh"), v["name"].get("en"), v.get("query")]
        cand += v.get("aliases") or []
        for c in cand:
            if c and norm(c) not in idx:
                idx[norm(c)] = k
    return idx


def _guide_by_target() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for e in GUIDE:
        m = e.get("match") or {}
        if m.get("status") == "matched" and m.get("target"):
            out.setdefault(m["target"], []).append(e)
    return out


PLACE_INDEX = _place_index()
GUIDE_BY_TARGET = _guide_by_target()


def place_for(*names: str) -> dict | None:
    """依名稱或查詢字串找 places 條目。第一個對得到的贏。"""
    for n in names:
        if not n:
            continue
        k = PLACE_INDEX.get(norm(n))
        if k:
            return PLACES[k]
    return None


def attach() -> None:
    """把 places 與 guide 掛到行程站點上，讓 render 只做字典查表，不做模糊比對。

    掛得到就有 place_id，路線網址跟著升級；掛不到就維持原本的文字查詢，不會壞。
    """
    for d in DATA["days"]:
        for i, s in enumerate(d["stops"]):
            entries = GUIDE_BY_TARGET.get(f"{d['id']}/stop/{i}", [])
            pl = None
            if entries:
                pl = PLACES.get(entries[0].get("id"))
                s["guide"] = entries
            if pl is None:
                pl = place_for(s.get("name"), s.get("query"))
            if pl:
                s["place"] = pl
            for p in s.get("parking") or []:
                pp = place_for(p.get("name"), p.get("query"))
                if pp:
                    p["place"] = pp

    for c in CLUSTERS:
        for i, cs in enumerate(c["stops"]):
            entries = GUIDE_BY_TARGET.get(f"{c['day']}/cluster/{c['stop_time']}/{i}", [])
            pl = PLACES.get(entries[0].get("id")) if entries else None
            if entries:
                cs["guide"] = entries
            if pl is None:
                pl = place_for(cs.get("name"), cs.get("query"))
            if pl:
                cs["place"] = pl


def cluster_for(day_id: str, time: str) -> dict | None:
    for c in CLUSTERS:
        if c["day"] == day_id and c["stop_time"] == time:
            return c
    return None


def day_map() -> dict:
    """{'YYYY-M-D': 'D1', ...}，供「跳到今天」使用。

    全部從行程資料推導，原始碼不含任何日期 — 這一檔會進公開 repo。
    """
    year = (re.search(r"(20\d\d)", DATA.get("hero_sub", ""))
            or re.search(r"(20\d\d)", DATA.get("title", "")))
    if not year:
        return {}
    out = {}
    for d in DATA["days"]:
        md = re.match(r"\s*(\d+)/(\d+)", d["date"])
        if md:
            out[f"{year.group(1)}-{int(md.group(1))}-{int(md.group(2))}"] = d["id"]
    return out


def stats() -> dict:
    """給 build 收尾時列印用。"""
    n_pid = sum(1 for v in PLACES.values() if v.get("place_id"))
    return {"places": len(PLACES), "place_id": n_pid, "guide": len(GUIDE),
            "clusters": len(CLUSTERS),
            "shopping": len((SHOPPING or {}).get("items", []))}
