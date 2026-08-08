# -*- coding: utf-8 -*-
"""整頁組裝。這一檔不含任何地名、日期或時段。"""
from __future__ import annotations

import json
from urllib.parse import unquote

from ..assets import data_uri, read_web
from ..data import DATA, day_map
from ..maps import search_url
from .. import redact
from .itinerary import day_section
from .text import E


def overview() -> str:
    p = ['<section id="overview" class="ovsec"><div class="cards">']
    for c in DATA["cards"]:
        p.append(f'<article class="card"><span class="kicker">{E(c["kicker"])}</span><h2>{E(c["title"])}</h2>')
        if c["rows"]:
            p.append('<div class="rows">' + "".join(
                f'<div><b>{E(r["label"])}</b><span>{E(r["value"])}</span></div>' for r in c["rows"]) + "</div>")
        if c["bullets"]:
            p.append("<ul>" + "".join(f"<li>{E(b)}</li>" for b in c["bullets"]) + "</ul>")
        p.append("</article>")
    p.append("</div>")

    f = DATA.get("feature")
    if f:
        img = data_uri(DATA.get("image"))
        p.append(f'<details class="feature"><summary><span class="kicker">{E(f["kicker"])}</span>'
                 f'<strong>{E(f["title"])}</strong><span class="tap">點一下展開</span></summary>')
        p.append(f'<p>{E(f["note"])}</p>')
        p.append(f'<a class="gbtn" href="{E(search_url(unquote(f["query"])))}" '
                 f'target="_blank" rel="noopener">導航到這裡</a>')
        if img:
            p.append(f'<img alt="{E(f["title"])}" loading="lazy" decoding="async" src="{img}">')
        p.append("</details>")
    p.append("</section>")
    return "".join(p)


def hero() -> str:
    p = ['<header class="hero"><div class="eyebrow">FINAL ROAD TRIP GUIDE</div>']
    p.append(f'<h1>{E(DATA["hero_title"])}</h1>')
    p.append(f'<p class="sub">{E(DATA["hero_sub"])}</p>')
    p.append('<div class="pills">' + "".join(f'<span class="pill">{E(x)}</span>' for x in DATA["pills"]) + "</div>")
    p.append("</header>")
    return "".join(p)


def daybar() -> str:
    p = ['<nav class="daybar" id="daybar"><div class="dbin">']
    p.append('<button class="dbtn today" data-go="today">今天</button>')
    for d in DATA["days"]:
        p.append(f'<button class="dbtn" data-go="{d["id"]}" data-date="{E(d["date"])}">'
                 f'{d["id"]}<em>{E(d["date"].split("（")[0])}</em></button>')
    p.append('<button class="dbtn" data-go="overview">總覽</button>')
    p.append("</div></nav>")
    return "".join(p)


def build_html(standalone: bool) -> str:
    """standalone=True 為本機單檔版(不掛 manifest)；False 為要加密發布的版本。
    內容不因這個旗標而不同 — 個資兩份都不寫。"""
    p = [hero(), daybar(), "<main>", overview()]
    for d in DATA["days"]:
        p.append(day_section(d))
    p.append(f'<p class="foot">{E(DATA["footer"])}</p>')
    p.append("</main>")
    p.append('<div class="toolbar">'
             '<button id="themeBtn" title="切換高對比">◐</button>'
             '<button id="clearBtn" title="清除全部勾選">↺</button>'
             '<button id="topBtn" title="回頂部">↑</button></div>')

    body = redact.apply("".join(p))

    # manifest 只有 Pages 版用得到，單檔離線版沒有這個外部檔，不掛連結避免 404
    manifest = "" if standalone else '<link rel="manifest" href="manifest.webmanifest">'
    # 日期對照在這裡才注入。日期只會出現在產出的 HTML(會被加密)，
    # 不會留在原始碼裡 — 這個套件會進公開 repo。
    js = read_web("app.js").replace("__DAYMAP__", json.dumps(day_map(), ensure_ascii=False))
    return (f'<!DOCTYPE html><html lang="zh-Hant"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            f'<meta name="theme-color" content="#263c36">'
            f'<title>{E(DATA["title"])}</title>{manifest}'
            f'<style>{read_web("app.css")}</style></head>'
            f'<body>{body}<script>{js}</script></body></html>')
