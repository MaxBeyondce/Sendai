"""One-time extractor: 原始 index.html -> trip_data.json + assets/

原始檔是機器產生的規則標記，用 regex 解析即可，不引入額外套件。
執行後產出的 trip_data.json 需要人工核對。
產出物都在 .gitignore 內，不進公開 repo。
"""

from __future__ import annotations

import base64
import html
import json
import re
from pathlib import Path

SRC = Path(r"H:\我的雲端硬碟\index.html")
ROOT = Path(__file__).parent
OUT_JSON = ROOT / "trip_data.json"
ASSETS = ROOT / "assets"

B64_RE = re.compile(r"data:image/(?P<ext>[a-z]+);base64,(?P<data>[A-Za-z0-9+/=]+)")
TAG_RE = re.compile(r"<[^>]+>")


def text_of(fragment: str) -> str:
    """標記轉純文字，保留可讀空白。"""
    fragment = re.sub(r"<br\s*/?>", " ", fragment)
    return html.unescape(TAG_RE.sub("", fragment)).strip()


def query_of(href: str) -> str | None:
    """取出 maps 連結裡已編碼的 query 值，原樣沿用不重新編碼。"""
    m = re.search(r"[?&]query=([^&\"']+)", html.unescape(href))
    return m.group(1) if m else None


def first_query(fragment: str) -> str | None:
    m = re.search(r'href="([^"]*maps[^"]*)"', fragment)
    return query_of(m.group(1)) if m else None


def parse_parking(cell: str) -> list[dict]:
    items = []
    for block in re.findall(r'<div class="parking-item">(.*?)</div>\s*(?=<div class="parking-item">|$)',
                            cell + "", re.S):
        name = re.search(r"<strong>(.*?)</strong>", block, re.S)
        note = re.search(r"<span>(.*?)</span>", block, re.S)
        items.append({
            "name": text_of(name.group(1)) if name else "",
            "note": text_of(note.group(1)) if note else "",
            "query": first_query(block),
        })
    return [i for i in items if i["name"]]


def parse_multi_map(cell: str) -> list[dict]:
    """既有的 multi-map-list 拆成子站。"""
    block = re.search(r'<div class="multi-map-list">(.*?)</div>', cell, re.S)
    if not block:
        return []
    subs = []
    for href, label in re.findall(r'<a href="([^"]+)"[^>]*>(.*?)</a>', block.group(1), re.S):
        subs.append({
            "name": text_of(label).replace("｜Google Maps", "").strip(),
            "query": query_of(href),
        })
    return subs


def main() -> None:
    raw = SRC.read_text(encoding="utf-8")

    # 1) 抽出內嵌圖片另存，json 只記檔名
    ASSETS.mkdir(exist_ok=True)
    image_file = None
    m = B64_RE.search(raw)
    if m:
        ext = "jpg" if m.group("ext") == "jpeg" else m.group("ext")
        image_file = f"trail_map.{ext}"
        (ASSETS / image_file).write_bytes(base64.b64decode(m.group("data")))
    stripped = B64_RE.sub("__IMG__", raw)

    doc: dict = {"source": str(SRC), "image": image_file}

    # 2) 抬頭
    title = re.search(r"<title>(.*?)</title>", stripped, re.S)
    hero_h1 = re.search(r'<h1>(.*?)</h1>', stripped, re.S)
    hero_p = re.search(r'<h1>.*?</h1>\s*<p>(.*?)</p>', stripped, re.S)
    doc["title"] = text_of(title.group(1)) if title else ""
    doc["hero_title"] = text_of(hero_h1.group(1)) if hero_h1 else ""
    doc["hero_sub"] = text_of(hero_p.group(1)) if hero_p else ""
    doc["pills"] = [text_of(x) for x in re.findall(r'<span class="pill">(.*?)</span>', stripped, re.S)]

    # 3) 上方 4 張資訊卡
    doc["cards"] = []
    for kicker, body in re.findall(r'<span class="kicker">(.*?)</span>\s*<h2>(.*?)(?=</article>)',
                                   stripped, re.S):
        heading = re.match(r"(.*?)</h2>", body, re.S)
        rows = [{"label": text_of(b), "value": text_of(s)}
                for b, s in re.findall(r"<div>\s*<b>(.*?)</b>\s*<span>(.*?)</span>\s*</div>", body, re.S)]
        bullets = [text_of(li) for li in re.findall(r"<li>(.*?)</li>", body, re.S)]
        doc["cards"].append({
            "kicker": text_of(kicker),
            "title": text_of(heading.group(1)) if heading else "",
            "rows": rows,
            "bullets": bullets,
        })

    # 4) 步道圖區塊
    feat = re.search(r'<section class="feature">(.*?)</section>', stripped, re.S)
    if feat:
        f = feat.group(1)
        doc["feature"] = {
            "kicker": text_of(re.search(r'class="kicker">(.*?)</span>', f, re.S).group(1)),
            "title": text_of(re.search(r"<h2>(.*?)</h2>", f, re.S).group(1)),
            "note": text_of(re.search(r"<p>(.*?)</p>", f, re.S).group(1)),
            "query": first_query(f),
        }

    # 5) 每日行程
    doc["days"] = []
    for did, body in re.findall(r'<section class="day" id="(D\d)">(.*?)</section>', stripped, re.S):
        date = re.search(r'<span class="date">(.*?)</span>', body, re.S)
        h2 = re.search(r"<h2>(.*?)</h2>", body, re.S)
        anchor = re.search(r'<div class="anchor">(.*?)</div>', body, re.S)
        stay = re.search(r'<div class="stay">(.*?)</div>', body, re.S)
        notes_block = re.search(r'<div class="notes">(.*?)</div>', body, re.S)

        stops = []
        for row in re.findall(r"<tr>(.*?)</tr>", body, re.S):
            if 'class="time"' not in row:
                continue
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
            if len(cells) < 4:
                continue
            name_cell, park_cell, memo_cell = cells[1], cells[2], cells[3]
            name = re.search(r"<strong>(.*?)</strong>", name_cell, re.S)
            stops.append({
                "time": text_of(cells[0]),
                "name": text_of(name.group(1)) if name else text_of(name_cell),
                "query": first_query(name_cell) or first_query(cells[4] if len(cells) > 4 else ""),
                "parking": parse_parking(park_cell),
                "memo": text_of(re.sub(r'<div class="multi-map-list">.*?</div>', "", memo_cell, flags=re.S)),
                "sub_stops": parse_multi_map(memo_cell),
            })

        doc["days"].append({
            "id": did,
            "date": text_of(date.group(1)) if date else "",
            "title": text_of(h2.group(1)) if h2 else "",
            "anchor": text_of(anchor.group(1)) if anchor else "",
            "stay": text_of(stay.group(1)).replace("住宿｜", "") if stay else "",
            "notes": [text_of(li) for li in re.findall(r"<li>(.*?)</li>", notes_block.group(1), re.S)]
                     if notes_block else [],
            "stops": stops,
        })

    doc["footer"] = text_of(re.search(r'<p style="text-align:center[^"]*">(.*?)</p>', stripped, re.S).group(1))

    OUT_JSON.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

    total = sum(len(d["stops"]) for d in doc["days"])
    subs = sum(len(s["sub_stops"]) for d in doc["days"] for s in d["stops"])
    parks = sum(len(s["parking"]) for d in doc["days"] for s in d["stops"])
    print(f"days={len(doc['days'])} stops={total} sub_stops={subs} parking={parks} cards={len(doc['cards'])}")
    print(f"image -> assets/{image_file} ({(ASSETS / image_file).stat().st_size // 1024} KB)")
    for d in doc["days"]:
        missing = [s["name"] for s in d["stops"] if not s["query"]]
        print(f"  {d['id']} {d['date']:<12} stops={len(d['stops']):<3} 無連結={len(missing)} {missing[:3]}")


if __name__ == "__main__":
    main()
