"""從 trip_data.json + clusters.json 產出兩個自足單檔 HTML。

  完整版  -> H:\\我的雲端硬碟\\index_mobile.html      (保留姓名、訂位代號、租車號碼、人數)
  遮蔽版  -> docs/index.html                        (公開 repo 用，個資全部拿掉)

兩版同源，改資料只改 json，不手改 html。
遮蔽版產出後會自動掃描，掃不過就中止不寫檔。
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote, unquote

ROOT = Path(__file__).parent
DATA = json.loads((ROOT / "trip_data.json").read_text(encoding="utf-8"))
CLUSTERS = json.loads((ROOT / "clusters.json").read_text(encoding="utf-8"))["clusters"]
ASSETS = ROOT / "assets"
DOCS = ROOT / "docs"
BUILD = ROOT / "build"
DRIVE_OUT = Path(r"H:\我的雲端硬碟\index_mobile.html")

# 手機瀏覽器最多 3 個中繼點，所以每段最多 5 站(起點+3中繼+終點)
MAX_PER_LEG = 5
# Google Maps 其他平台上限 9 個中繼點 -> 單一連結最多 11 站
MAX_SINGLE = 11

# 這些列不是可導航的地點(候選清單、移動動作、看即時影像)，不進當日路線
ROUTE_SKIP = {
    ("D2", "12:30"), ("D4", "14:20–15:45"), ("D4", "晚間可選"),
    ("D5", "早餐時"), ("D5", "午餐"),
    ("D6", "早餐"), ("D6", "晚餐前"),
    ("D7", "09:40"), ("D7", "11:30"), ("D7", "12:30"), ("D7", "13:00 前後"), ("D7", "16:05"),
}
# D5 有 Plan A / Plan B 兩條分支，不併成一條
D5_PLAN_A = {"Plan A", "10:00", "午餐"}
D5_PLAN_B = {"Plan B"}

# 遮蔽對照本身就含個資，不能寫在這一檔(build.py 會進公開 repo)。
# private/ 被 .gitignore 排除；讀不到就不產遮蔽版，寧可 build 失敗也不要漏出去。
PRIVATE = ROOT / "private" / "redactions.json"
if not PRIVATE.exists():
    sys.exit(f"找不到 {PRIVATE}；沒有遮蔽對照就不產遮蔽版，已中止。")
_priv = json.loads(PRIVATE.read_text(encoding="utf-8"))
ALWAYS = [tuple(x) for x in _priv["always"]]            # 兩版都套用(訂位代號、姓名 — 已外洩)
PUBLIC_ONLY = [tuple(x) for x in _priv["public_only"]]  # 只有公開版套用(人數)
FORBIDDEN = _priv["forbidden"]
FORBIDDEN_ALWAYS = _priv["forbidden_always"]

E = html.escape


def q(s: str) -> str:
    """統一成純文字再重新編碼，避免原檔已編碼與新資料混用。"""
    return quote(unquote(s), safe="")


def route_url(stops: list[dict], mode: str) -> str:
    qs = [q(s["query"]) for s in stops]
    url = f"https://www.google.com/maps/dir/?api=1&origin={qs[0]}&destination={qs[-1]}"
    if len(qs) > 2:
        url += "&waypoints=" + "%7C".join(qs[1:-1])
    return url + f"&travelmode={mode}"


def search_url(query: str) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={q(query)}"


def segment(stops: list[dict]) -> list[list[dict]]:
    """切成每段最多 5 站，前一段終點即下一段起點。"""
    if len(stops) <= MAX_PER_LEG:
        return [stops]
    legs, i = [], 0
    while i < len(stops) - 1:
        legs.append(stops[i:i + MAX_PER_LEG])
        i += MAX_PER_LEG - 1
    return legs


def day_map() -> dict:
    """{'YYYY-M-D': 'D1', ...}，供「跳到今天」使用。全部從行程資料推導，原始碼不含任何日期。"""
    year = re.search(r"(20\d\d)", DATA.get("hero_sub", "")) or re.search(r"(20\d\d)", DATA.get("title", ""))
    if not year:
        return {}
    out = {}
    for d in DATA["days"]:
        md = re.match(r"\s*(\d+)/(\d+)", d["date"])
        if md:
            out[f"{year.group(1)}-{int(md.group(1))}-{int(md.group(2))}"] = d["id"]
    return out


def short(name: str, n: int = 22) -> str:
    """按鈕上只放得下一行；原檔有幾列把整條動線塞進標題(D5 Plan B)，不截會爆版。"""
    name = name.strip()
    return name if len(name) <= n else name[:n - 1] + "…"


def route_block(stops: list[dict], mode: str, label: str, note: str = "") -> str:
    """一組路線按鈕：整段(站數夠少時)＋分段。"""
    stops = [s for s in stops if s.get("query")]
    if len(stops) < 2:
        return ""
    icon = {"driving": "🚗", "walking": "🚶", "transit": "🚌"}.get(mode, "📍")
    out = ['<div class="routegrp">']
    out.append(f'<div class="routelabel">{icon} {E(label)}<span class="cnt">{len(stops)}站</span></div>')
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
    """當日開車路線；D5 分 Plan A / Plan B 兩條。"""
    did = day["id"]
    usable = [s for s in day["stops"]
              if s.get("query") and (did, s["time"]) not in ROUTE_SKIP]
    if did == "D5":
        a = [s for s in usable if s["time"] not in D5_PLAN_B]
        b = [s for s in usable if s["time"] not in D5_PLAN_A]
        # 標籤不寫地名：build.py 會進公開 repo，地名只能存在於加密後的內容裡
        return (route_block(a, "driving", "Plan A｜當日開車路線")
                + route_block(b, "driving", "Plan B｜當日開車路線"))
    if did in ("D6", "D7"):
        return ""  # 這兩天是步行與大眾運輸，路線走群組
    return route_block(usable, "driving", "當日開車路線")


def cluster_for(day_id: str, time: str) -> dict | None:
    for c in CLUSTERS:
        if c["day"] == day_id and c["stop_time"] == time:
            return c
    return None


VER_LABEL = {"address": "", "route": "", "inferred": "位置待確認"}


def stop_html(day_id: str, idx: int, s: dict) -> str:
    sid = f"{day_id}-{idx}"
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
            link = (f'<a class="pbtn" href="{E(search_url(unquote(p["query"])))}" target="_blank" rel="noopener">停車場導航</a>'
                    if p.get("query") else "")
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
            out.append(f'<li><a href="{E(search_url(c["query"]))}" target="_blank" rel="noopener">'
                       f'{E(c["name"])}{warn}</a>{memo}</li>')
        out.append("</ol>")
        out.append(route_block(cl["stops"], cl["mode"], cl["label"], cl.get("note", "")))
        out.append("</div>")

    if s.get("query"):
        out.append(f'<div class="actions"><a class="gbtn" href="{E(search_url(unquote(s["query"])))}" '
                   f'target="_blank" rel="noopener">導航到這裡</a></div>')
    out.append("</div></li>")
    return "".join(out)


def build_html(redact: bool) -> str:
    img = ""
    if DATA.get("image") and (ASSETS / DATA["image"]).exists():
        b64 = base64.b64encode((ASSETS / DATA["image"]).read_bytes()).decode()
        img = f"data:image/jpeg;base64,{b64}"

    p: list[str] = []
    p.append(f'<header class="hero"><div class="eyebrow">FINAL ROAD TRIP GUIDE</div>')
    p.append(f'<h1>{E(DATA["hero_title"])}</h1>')
    p.append(f'<p class="sub">{E(DATA["hero_sub"])}</p>')
    p.append('<div class="pills">' + "".join(f'<span class="pill">{E(x)}</span>' for x in DATA["pills"]) + "</div>")
    p.append("</header>")

    # 黏頂日期列
    p.append('<nav class="daybar" id="daybar"><div class="dbin">')
    p.append('<button class="dbtn today" data-go="today">今天</button>')
    for d in DATA["days"]:
        p.append(f'<button class="dbtn" data-go="{d["id"]}" data-date="{E(d["date"])}">'
                 f'{d["id"]}<em>{E(d["date"].split("（")[0])}</em></button>')
    p.append('<button class="dbtn" data-go="overview">總覽</button>')
    p.append("</div></nav>")

    p.append("<main>")

    # 總覽卡
    p.append('<section id="overview" class="ovsec"><div class="cards">')
    for c in DATA["cards"]:
        p.append(f'<article class="card"><span class="kicker">{E(c["kicker"])}</span><h2>{E(c["title"])}</h2>')
        if c["rows"]:
            p.append('<div class="rows">' + "".join(
                f'<div><b>{E(r["label"])}</b><span>{E(r["value"])}</span></div>' for r in c["rows"]) + "</div>")
        if c["bullets"]:
            p.append("<ul>" + "".join(f"<li>{E(b)}</li>" for b in c["bullets"]) + "</ul>")
        p.append("</article>")
    p.append("</div>")

    if DATA.get("feature"):
        f = DATA["feature"]
        p.append(f'<details class="feature"><summary><span class="kicker">{E(f["kicker"])}</span>'
                 f'<strong>{E(f["title"])}</strong><span class="tap">點一下展開</span></summary>')
        p.append(f'<p>{E(f["note"])}</p>')
        p.append(f'<a class="gbtn" href="{E(search_url(unquote(f["query"])))}" target="_blank" rel="noopener">導航到這裡</a>')
        if img:
            p.append(f'<img alt="{E(f["title"])}" loading="lazy" decoding="async" src="{img}">')
        p.append("</details>")
    p.append("</section>")

    # 每日
    for d in DATA["days"]:
        p.append(f'<section class="day" id="{d["id"]}" data-date="{E(d["date"])}">')
        p.append(f'<div class="dhead"><div class="dtop"><span class="badge">{d["id"]}</span>'
                 f'<span class="date">{E(d["date"])}</span></div>')
        p.append(f'<h2>{E(d["title"])}</h2>')
        if d.get("anchor"):
            p.append(f'<p class="anchor">{E(d["anchor"])}</p>')
        if d.get("stay") and d["stay"] != "—":
            p.append(f'<p class="stay">住宿｜<b>{E(d["stay"])}</b></p>')
        p.append(f'<div class="prog"><span class="bar"><i></i></span><span class="ptxt"></span></div>')
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

    p.append(f'<p class="foot">{E(DATA["footer"])}</p>')
    p.append("</main>")
    p.append('<div class="toolbar">'
             '<button id="themeBtn" title="切換高對比">◐</button>'
             '<button id="clearBtn" title="清除全部勾選">↺</button>'
             '<button id="topBtn" title="回頂部">↑</button></div>')

    body = "".join(p)
    for a, b in ALWAYS:
        body = body.replace(E(a), E(b)).replace(a, b)
    if redact:
        for a, b in PUBLIC_ONLY:
            body = body.replace(E(a), E(b)).replace(a, b)

    # manifest 只有 Pages 版用得到，單檔離線版沒有這個外部檔，不掛連結避免 404
    manifest = '<link rel="manifest" href="manifest.webmanifest">' if redact else ""
    # 「跳到今天」的日期對照表在這裡產生。日期只會出現在產出的 HTML(會被加密)，
    # 不會留在 build.py 這種要進公開 repo 的原始碼裡。
    js = JS.replace("__DAYMAP__", json.dumps(day_map(), ensure_ascii=False))
    return (f'<!DOCTYPE html><html lang="zh-Hant"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            f'<meta name="theme-color" content="#263c36">'
            f'<title>{E(DATA["title"])}</title>{manifest}'
            f"<style>{CSS}</style></head><body>{body}<script>{js}</script></body></html>")


CSS = r"""
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
:root{
 --bg:#f3f0e9;--paper:#fffdfa;--ink:#202421;--muted:#5f645f;--line:#ddd7cd;
 --accent:#8a5d2c;--accent-ink:#fff;--dark:#263c36;--chip:#fbf8f2;--ok:#2f6b4f;
 --shadow:0 6px 18px #3b302310;--r:16px;--tap:46px;
}
:root[data-theme=contrast]{
 --bg:#0d1210;--paper:#161d1a;--ink:#f4f7f4;--muted:#b6c2bb;--line:#33403a;
 --accent:#ffb64d;--accent-ink:#171100;--dark:#0a0f0d;--chip:#1d2622;--ok:#57d59a;
 --shadow:none;
}
@media(prefers-color-scheme:dark){:root:not([data-theme=light]){
 --bg:#0d1210;--paper:#161d1a;--ink:#f4f7f4;--muted:#b6c2bb;--line:#33403a;
 --accent:#ffb64d;--accent-ink:#171100;--dark:#0a0f0d;--chip:#1d2622;--ok:#57d59a;--shadow:none;}}
html{scroll-behavior:smooth;-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);line-height:1.6;
 font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC","PingFang TC",sans-serif;
 padding-bottom:env(safe-area-inset-bottom)}
a{color:inherit}
.hero{padding:26px 16px 20px;background:linear-gradient(135deg,#1f302b,#3b564e);color:#fff}
.eyebrow{font-size:.68rem;letter-spacing:.16em;font-weight:800;color:#d6a86a}
.hero h1{font-size:clamp(1.5rem,6.4vw,2.4rem);line-height:1.15;margin:.3rem 0 .4rem;letter-spacing:-.02em}
.hero .sub{margin:0;color:#dfe7e3;font-size:.88rem}
.pills{display:flex;gap:7px;flex-wrap:wrap;margin-top:12px}
.pill{border:1px solid #ffffff3d;border-radius:999px;padding:5px 10px;background:#ffffff14;font-size:.75rem}

.daybar{position:sticky;top:0;z-index:20;background:color-mix(in srgb,var(--bg) 92%,transparent);
 backdrop-filter:blur(12px);border-bottom:1px solid var(--line)}
.dbin{display:flex;gap:6px;padding:8px 12px;overflow-x:auto;scrollbar-width:none}
.dbin::-webkit-scrollbar{display:none}
.dbtn{flex:0 0 auto;min-height:var(--tap);min-width:58px;display:flex;flex-direction:column;
 align-items:center;justify-content:center;gap:1px;border:1px solid var(--line);background:var(--paper);
 color:var(--ink);border-radius:12px;padding:5px 11px;font-weight:800;font-size:.9rem;cursor:pointer}
.dbtn em{font-style:normal;font-size:.64rem;font-weight:600;color:var(--muted)}
.dbtn.on{background:var(--dark);color:#fff;border-color:var(--dark)}
.dbtn.on em{color:#c7d4ce}
.dbtn.today{background:var(--accent);color:var(--accent-ink);border-color:var(--accent)}

main{max-width:900px;margin:auto;padding:14px 12px 90px}
.cards{display:grid;gap:12px}
.card,.day,.feature{background:var(--paper);border:1px solid var(--line);border-radius:var(--r);box-shadow:var(--shadow)}
.card{padding:16px}
.kicker{font-size:.66rem;letter-spacing:.14em;font-weight:800;color:var(--accent)}
.card h2{margin:.2rem 0 .7rem;font-size:1.08rem}
.rows div{padding:7px 0;border-bottom:1px dashed var(--line)}
.rows div:last-child{border:0}
.rows b{display:block;font-size:.9rem}
.rows span{display:block;color:var(--muted);font-size:.84rem}
.card ul{margin:.3rem 0 0;padding-left:1.15rem;font-size:.88rem}
.card li{margin:.25rem 0}

.feature{margin-top:12px;padding:14px 16px}
.feature summary{display:flex;flex-direction:column;gap:2px;cursor:pointer;min-height:var(--tap);justify-content:center}
.feature summary strong{font-size:1rem}
.feature .tap{font-size:.76rem;color:var(--accent);font-weight:700}
.feature p{color:var(--muted);font-size:.86rem}
.feature img{width:100%;border-radius:12px;border:1px solid var(--line);margin-top:12px}

.day{margin:16px 0;overflow:hidden;scroll-margin-top:74px}
.dhead{padding:16px 16px 12px;border-bottom:1px solid var(--line)}
.dtop{display:flex;align-items:center;gap:9px}
.badge{display:grid;place-items:center;width:38px;height:38px;border-radius:11px;background:var(--dark);color:#fff;font-weight:900;font-size:.9rem}
.date{color:var(--muted);font-weight:800;font-size:.86rem}
.dhead h2{margin:.5rem 0 .25rem;font-size:1.2rem;line-height:1.3}
.anchor{margin:.2rem 0;color:var(--accent);font-weight:800;font-size:.82rem}
.stay{margin:.35rem 0 0;font-size:.85rem;color:var(--muted)}
.prog{display:flex;align-items:center;gap:8px;margin-top:10px}
.prog .bar{flex:1;height:5px;border-radius:99px;background:var(--line);overflow:hidden}
.prog .bar i{display:block;height:100%;width:0;background:var(--ok);transition:width .25s}
.ptxt{font-size:.74rem;color:var(--muted);font-weight:700;min-width:44px;text-align:right}

.droutes{padding:12px 16px;background:var(--chip);border-bottom:1px solid var(--line)}
.routegrp+.routegrp{margin-top:12px}
.routelabel{font-size:.8rem;font-weight:800;display:flex;align-items:center;gap:6px;margin-bottom:7px}
.routelabel .cnt{font-weight:700;color:var(--muted);font-size:.72rem;border:1px solid var(--line);border-radius:99px;padding:1px 7px}
/* minmax(0,1fr) + min-width:0 是必要的：em 用了 nowrap，格線軌道會被撐成 min-content 而超出視窗 */
.routebtns{display:grid;grid-template-columns:minmax(0,1fr);gap:6px}
.rbtn{display:flex;flex-direction:column;justify-content:center;gap:1px;min-height:var(--tap);
 padding:7px 13px;border-radius:12px;background:var(--paper);border:1px solid var(--line);
 text-decoration:none;font-weight:800;font-size:.84rem;min-width:0;overflow:hidden}
.rbtn em{font-style:normal;font-weight:600;font-size:.71rem;color:var(--muted);
 display:block;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.rbtn.whole{background:var(--accent);color:var(--accent-ink);border-color:var(--accent)}
.rbtn.whole em{color:color-mix(in srgb,var(--accent-ink) 75%,transparent)}
.routenote{margin:8px 0 0;font-size:.76rem;color:var(--muted);line-height:1.55}
.routehint{margin:5px 0 0;font-size:.71rem;color:var(--muted);opacity:.85}

.stops{list-style:none;margin:0;padding:0}
.stop{display:flex;gap:10px;padding:13px 16px;border-bottom:1px solid var(--line);position:relative}
.stop:last-child{border-bottom:0}
.tick{position:absolute;opacity:0;pointer-events:none}
/* 可點範圍做滿 44x44，視覺方框用 ::before 縮在中間 26x26 */
.tickbox{flex:0 0 auto;width:44px;height:44px;margin:-5px 0 0 -11px;cursor:pointer;position:relative}
.tickbox::before{content:"";position:absolute;inset:9px;border:2px solid var(--line);
 border-radius:8px;transition:.15s}
.tickbox::after{content:"";position:absolute;left:15px;top:19px;width:12px;height:7px;
 border-left:2.5px solid #fff;border-bottom:2.5px solid #fff;
 transform:rotate(-45deg) scale(.4);opacity:0;transition:.15s}
.tick:checked+.tickbox::before{background:var(--ok);border-color:var(--ok)}
.tick:checked+.tickbox::after{opacity:1;transform:rotate(-45deg) scale(1)}
.tick:focus-visible+.tickbox::before{outline:2px solid var(--accent);outline-offset:2px}
.stop:has(.tick:checked) .sbody{opacity:.5}
.sbody{flex:1;min-width:0}
.stime{font-size:.74rem;font-weight:900;color:var(--accent);letter-spacing:.02em}
.sname{margin:.1rem 0 .3rem;font-size:1rem;line-height:1.35;font-weight:800}
.smemo{margin:.25rem 0;font-size:.84rem;color:var(--muted);line-height:1.6}
.parks{margin:.5rem 0}
.park{background:var(--chip);border:1px solid var(--line);border-radius:11px;padding:9px 11px;margin-bottom:6px}
.park strong{display:block;font-size:.83rem}
.park span{display:block;font-size:.75rem;color:var(--muted);margin:1px 0 5px}
.pbtn,.gbtn{display:inline-flex;align-items:center;justify-content:center;min-height:var(--tap);
 padding:8px 15px;border-radius:11px;text-decoration:none;font-weight:800;font-size:.82rem}
.pbtn{background:var(--paper);border:1px solid var(--accent);color:var(--accent);margin-top:3px}
.gbtn{background:var(--accent);color:var(--accent-ink);width:100%;margin-top:8px}
.actions{margin-top:2px}

.cluster{margin:.6rem 0;border:1px solid var(--line);border-radius:12px;overflow:hidden}
.clhead{padding:7px 11px;background:var(--chip);font-size:.72rem;font-weight:800;color:var(--muted);border-bottom:1px solid var(--line)}
.chips{list-style:none;margin:0;padding:9px 11px;display:grid;gap:5px;counter-reset:c}
.chips li{counter-increment:c;font-size:.8rem;display:flex;flex-wrap:wrap;align-items:baseline;gap:5px}
.chips li::before{content:counter(c);flex:0 0 auto;width:19px;height:19px;border-radius:99px;
 background:var(--dark);color:#fff;font-size:.64rem;font-weight:800;display:grid;place-items:center}
.chips a{font-weight:700;text-decoration:none;border-bottom:1.5px solid var(--accent)}
.cmemo{font-size:.72rem;color:var(--muted);flex:1 1 100%;padding-left:24px}
.cwarn{font-size:.64rem;font-weight:800;color:var(--accent-ink);background:var(--accent);
 border-radius:99px;padding:1px 6px;margin-left:4px;white-space:nowrap}
.cluster .routegrp{padding:9px 11px;border-top:1px solid var(--line);background:var(--chip)}

.notes{padding:13px 16px 16px;background:var(--chip)}
.notes b{font-size:.82rem}
.notes ul{margin:.4rem 0 0;padding-left:1.15rem;font-size:.84rem;color:var(--muted)}
.notes li{margin:.25rem 0}
.foot{text-align:center;color:var(--muted);font-size:.78rem;margin:22px 8px 0;line-height:1.6}

.toolbar{position:fixed;right:12px;bottom:calc(12px + env(safe-area-inset-bottom));display:flex;
 flex-direction:column;gap:8px;z-index:30}
.toolbar button{width:var(--tap);height:var(--tap);border:1px solid var(--line);border-radius:50%;
 background:var(--paper);color:var(--ink);font-size:1.1rem;font-weight:800;cursor:pointer;box-shadow:0 4px 14px #0003}

@media(min-width:760px){
 .hero{padding:44px 26px 34px}
 .cards{grid-template-columns:1fr 1fr}
 main{padding:20px 18px 90px}
 .routebtns{grid-template-columns:1fr 1fr}
 .gbtn{width:auto;min-width:190px}
}
@media print{
 .daybar,.toolbar,.droutes,.tickbox,.prog{display:none!important}
 body{background:#fff}.day{page-break-before:always;box-shadow:none;border:0}
 .card,.feature{box-shadow:none}.stop{break-inside:avoid}
 .feature[open] img{max-height:420px;object-fit:contain}
 a{text-decoration:none}.gbtn,.pbtn{background:none!important;color:#000!important;border:1px solid #999}
}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}*{transition:none!important}}
"""

JS = r"""
(function(){
 var K='sendai2026:';
 var root=document.documentElement;
 var DAYMAP=__DAYMAP__;

 // 高對比切換
 var saved=localStorage.getItem(K+'theme');
 if(saved) root.setAttribute('data-theme',saved);
 document.getElementById('themeBtn').onclick=function(){
  var cur=root.getAttribute('data-theme');
  var dark=window.matchMedia('(prefers-color-scheme:dark)').matches;
  var next=cur? (cur==='contrast'?'light':'contrast') : (dark?'light':'contrast');
  root.setAttribute('data-theme',next);
  localStorage.setItem(K+'theme',next);
 };

 // 勾選記錄
 var ticks=[].slice.call(document.querySelectorAll('.tick'));
 ticks.forEach(function(t){
  if(localStorage.getItem(K+t.id)==='1') t.checked=true;
  t.addEventListener('change',function(){
   localStorage.setItem(K+t.id,t.checked?'1':'0'); prog();
  });
 });
 document.getElementById('clearBtn').onclick=function(){
  if(!confirm('清除全部勾選？')) return;
  ticks.forEach(function(t){t.checked=false;localStorage.removeItem(K+t.id);});
  prog();
 };
 function prog(){
  [].forEach.call(document.querySelectorAll('.day'),function(d){
   var all=d.querySelectorAll('.tick'), done=d.querySelectorAll('.tick:checked');
   var bar=d.querySelector('.prog .bar i'), txt=d.querySelector('.ptxt');
   if(!all.length||!bar) return;
   bar.style.width=(done.length/all.length*100)+'%';
   txt.textContent=done.length+'/'+all.length;
  });
 }
 prog();

 // 日期跳轉
 var bar=document.getElementById('daybar');
 function go(id){
  var el=document.getElementById(id);
  if(el) el.scrollIntoView({behavior:'smooth',block:'start'});
 }
 // 日期對照由 build 時從行程資料產生，不寫死在原始碼裡(原始碼會進公開 repo)
 function todayId(){
  var n=new Date();
  return DAYMAP[n.getFullYear()+'-'+(n.getMonth()+1)+'-'+n.getDate()]||null;
 }
 [].forEach.call(bar.querySelectorAll('.dbtn'),function(b){
  b.onclick=function(){
   var g=b.dataset.go;
   go(g==='today'? (todayId()||'D1') : g);
  };
 });

 // 捲動時標示目前這一天
 var days=[].slice.call(document.querySelectorAll('.day,#overview'));
 var btns={};
 [].forEach.call(bar.querySelectorAll('.dbtn'),function(b){ btns[b.dataset.go]=b; });
 var io=new IntersectionObserver(function(es){
  es.forEach(function(e){
   var b=btns[e.target.id];
   if(!b) return;
   if(e.isIntersecting){
    [].forEach.call(bar.querySelectorAll('.dbtn'),function(x){x.classList.remove('on');});
    b.classList.add('on');
    b.scrollIntoView({inline:'center',block:'nearest',behavior:'smooth'});
   }
  });
 },{rootMargin:'-70px 0px -65% 0px'});
 days.forEach(function(d){io.observe(d);});

 document.getElementById('topBtn').onclick=function(){scrollTo({top:0,behavior:'smooth'});};

 // 開啟時跳到今天(有 hash 就尊重 hash)
 if(!location.hash){
  var t=todayId();
  if(t) setTimeout(function(){go(t);},120);
 }

 // https(GitHub Pages)或 localhost 才註冊離線快取。
 // 不能只判 https：localhost 也是安全來源、要能在本機驗證；
 // 也不能用 isSecureContext：Chrome 把 file:// 也算安全來源，單檔開啟時根本沒有 sw.js，註冊會 404。
 var h=location.hostname;
 if((location.protocol==='https:'||h==='localhost'||h==='127.0.0.1')&&'serviceWorker'in navigator){
  navigator.serviceWorker.register('sw.js').catch(function(){});
 }
})();
"""


def main() -> None:
    DOCS.mkdir(exist_ok=True)

    full = build_html(redact=False)
    bad = [w for w in FORBIDDEN_ALWAYS if w in full]
    if bad:
        sys.exit(f"完整版仍含已外洩的訂位代號／姓名：{bad}；已中止")
    DRIVE_OUT.parent.mkdir(parents=True, exist_ok=True)
    DRIVE_OUT.write_text(full, encoding="utf-8")

    pub = build_html(redact=True)
    bad = [w for w in FORBIDDEN if w in pub]
    if bad:
        sys.exit(f"個資掃描未通過：{bad}；已中止")
    # 明文公開版寫到 build/(已 gitignore)，當作加密工具的輸入。
    # 絕對不直接寫 docs/index.html — 那是加密後的成品，重跑 build 會把它蓋成明文。
    BUILD.mkdir(exist_ok=True)
    (BUILD / "public_plain.html").write_text(pub, encoding="utf-8")

    # manifest 是公開可讀的，名稱不能寫行程內容(會在瀏覽器和 repo 裡直接看到)
    (DOCS / "manifest.webmanifest").write_text(json.dumps({
        "name": "行程", "short_name": "行程", "start_url": "./index.html",
        "display": "standalone", "background_color": "#f3f0e9", "theme_color": "#263c36",
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # 快取名帶內容雜湊：改版重新部署會換名，舊快取在 activate 時清掉。
    # 用固定名稱(v1)的話，cache-first 會讓使用者永遠停在第一次抓到的版本。
    # 注意雜湊算的是明文，加密後每次 salt/iv 不同，用密文會每次都變。
    digest = hashlib.sha1(pub.encode()).hexdigest()[:10]
    (DOCS / "sw.js").write_text(
        f"const C='sendai-trip-{digest}';const A=['./','./index.html','./manifest.webmanifest'];\n"
        "self.addEventListener('install',e=>{self.skipWaiting();"
        "e.waitUntil(caches.open(C).then(c=>c.addAll(A)).catch(()=>{}))});\n"
        "self.addEventListener('activate',e=>{e.waitUntil(caches.keys()"
        ".then(k=>Promise.all(k.filter(x=>x!==C).map(x=>caches.delete(x)))).then(()=>self.clients.claim()))});\n"
        "self.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;"
        "e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request).then(res=>{"
        "const cp=res.clone();caches.open(C).then(c=>c.put(e.request,cp));return res;})"
        ".catch(()=>caches.match('./index.html'))))});\n", encoding="utf-8")

    n_routes = sum(len(re.findall(r'class="rbtn', s)) for s in [full])
    print(f"完整版   -> {DRIVE_OUT}  ({len(full.encode()) // 1024} KB)")
    print(f"待加密版 -> {BUILD / 'public_plain.html'}  ({len(pub.encode()) // 1024} KB)  個資掃描通過")
    print(f"路線按鈕 {n_routes} 顆；步行群組 {len(CLUSTERS)} 組")
    print()
    print("docs/index.html 沒有被動到。要更新公開版，用 tools/encrypt.html 把上面兩份之一")
    print("加密後另存成 docs/index.html。")


if __name__ == "__main__":
    main()
