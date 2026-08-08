# -*- coding: utf-8 -*-
"""把購物清單原檔抽成 shopping.json ＋ 重新壓縮過的圖片。

原檔是一份自足單檔 HTML，99.8% 的位元組是內嵌的 base64 JPEG。
做法是**先把圖片抽掉再解析**：28.6MB 的檔案會變成 43KB 的骨架，
後面所有比對都在骨架上做，快而且不會被巨大的屬性字串拖垮。

因為輸出是從 JSON 重新產生的，原檔那些標記瑕疵(沒關的 grid div、
巢狀位置不對的 extra 區塊)不需要去修，它們不會被帶過來。

  python tools/extract_shopping.py --report   只檢查並輸出報告，不寫檔
  python tools/extract_shopping.py --write    產出 shopping.json 與圖片

這一檔會進公開 repo，所以裡面不能出現任何店名、品名或地名 —
來源路徑用萬用字元找，不寫死檔名。
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html as _html
import io
import json
import re
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    sys.exit("需要 Pillow：uv pip install --python .venv/Scripts/python.exe pillow")

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "private" / "raw"
OUT_JSON = ROOT / "shopping.json"
OUT_IMG = ROOT / "assets" / "shop"
OVERRIDES = ROOT / "shopping_overrides.json"
BUILD = ROOT / "build"

# 商品照：原檔 CSS 本來就是 aspect-ratio:1/1 + object-fit:cover，
# 瀏覽器反正要裁，在這裡先裁掉才省得到位元組。
#
# 480px 的依據：手機 2 欄格線在 375px 視窗下每張約 170 CSS px，
# 3 倍螢幕要 510 實體像素，480 幾乎剛好；再往上只是浪費位元組。
# q76 的依據（實測 90 張合計）：
#   400px  q60 1.40MB  q72 1.59MB  q76 1.70MB  q80 1.95MB
#   480px  q60 1.78MB  q72 2.03MB  q76 2.17MB  q80 2.49MB
# q76 到 q80 只多 8 個品質點卻多 320KB，收益不成比例。
PHOTO_PX, PHOTO_Q = 480, 76
# 文字類的圖(優惠券、截圖)縮到 480 會讓字糊掉，另走一組參數。
TEXT_PX, TEXT_Q = 960, 82

# 疑似文字圖的線索，交給人確認，不自動判定。
# 只比對品名，不比對說明 — 說明裡「照片…」是描述商品照的常用寫法，
# 拿去比對會把絕大多數一般商品照都標成疑似，等於沒有篩選作用。
TEXT_HINTS = ("截圖", "優惠券", "折價", "クーポン", "coupon", "スクリーン")

U = _html.unescape


def find_source() -> Path:
    cands = sorted(RAW.glob("*.html"))
    if not cands:
        sys.exit(f"在 {RAW} 找不到來源 HTML；來源檔應該放在 private/raw/ 之下。")
    if len(cands) > 1:
        sys.exit(f"{RAW} 有多個 HTML，無法判斷用哪一個：{[c.name for c in cands]}")
    return cands[0]


def strip_images(raw: str) -> tuple[str, list[bytes]]:
    """把每一個 data URI 換成 __IMG_n__ 佔位符，回傳骨架與解碼後的位元組。"""
    imgs: list[bytes] = []

    def grab(m: re.Match) -> str:
        imgs.append(base64.b64decode(m.group(2)))
        return f"__IMG_{len(imgs) - 1}__"

    sk = re.sub(r"data:image/(\w+);base64,([A-Za-z0-9+/=]+)", grab, raw)
    return sk, imgs


def slugify(name: str, fallback: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower()
    s = re.sub(r"-{2,}", "-", s)
    return s if len(s) >= 3 else fallback


CHIP = re.compile(r'<a class="navchip" href="#(shop-\d+)">(.*?)</a>')
SEC_SPLIT = re.compile(r'<section class="shop-section" id="(shop-\d+)">')
H2 = re.compile(r"<h2>(.*?)</h2>", re.S)
CARD = re.compile(r'<article class="card"(?P<attrs>[^>]*)>(?P<body>.*?)</article>', re.S)
EXTRA = re.compile(r'<section class="extra"(?P<attrs>[^>]*)>(?P<body>.*?)</section>', re.S)


def attr(s: str, name: str) -> str | None:
    m = re.search(rf'{name}="([^"]*)"', s)
    return U(m.group(1)) if m else None


def parse(sk: str) -> tuple[list[dict], list[dict], list[dict], list[str]]:
    """回傳 (stores, items, extras, anomalies)。"""
    anomalies: list[str] = []

    # 導覽列順序 = 作者的意圖。DOM 順序與編號順序都是產生過程的殘留，不採用。
    nav_order = [(sid, U(nm)) for sid, nm in CHIP.findall(sk)]

    # 依 section 切開。用 split 而不是貪婪比對，避免被 extra 區塊的巢狀問題影響。
    parts = SEC_SPLIT.split(sk)
    dom_order: list[tuple[str, str]] = []
    body_by_id: dict[str, str] = {}
    for i in range(1, len(parts), 2):
        sid, body = parts[i], parts[i + 1]
        h2 = H2.search(body)
        name = U(h2.group(1)).strip() if h2 else sid
        dom_order.append((sid, name))
        body_by_id[sid] = body

    nav_ids = [s for s, _ in nav_order]
    dom_ids = [s for s, _ in dom_order]
    if nav_ids != dom_ids:
        anomalies.append(
            f"導覽列順序與 DOM 順序不一致(以導覽列為準)\n"
            f"      導覽列: {' '.join(nav_ids)}\n"
            f"      DOM   : {' '.join(dom_ids)}"
        )
    if set(nav_ids) != set(dom_ids):
        anomalies.append(f"導覽列與 DOM 的分類集合不同：只在導覽列 {set(nav_ids)-set(dom_ids)}；"
                         f"只在 DOM {set(dom_ids)-set(nav_ids)}")

    name_by_id = dict(dom_order)
    stores, items, extras = [], [], []
    used_slugs: set[str] = set()

    for order, sid in enumerate(nav_ids, 1):
        name = name_by_id.get(sid, sid)
        sl = slugify(name, sid)
        if sl in used_slugs:
            sl = sid
        used_slugs.add(sl)
        stores.append({"id": sl, "section": sid, "order": order, "name": name,
                       "short": name, "days": []})

        body = body_by_id.get(sid, "")
        for m in CARD.finditer(body):
            a, b = m.group("attrs"), m.group("body")
            iid = attr(b, "data-id")
            img = re.search(r'src="__IMG_(\d+)__"', b)
            h3 = re.search(r"<h3>(.*?)</h3>", b, re.S)
            p = re.search(r"<p>(.*?)</p>", b, re.S)
            shop = re.search(r'<div class="shop">(.*?)</div>', b, re.S)
            if not (iid and h3):
                anomalies.append(f"{sid} 有一張卡缺 data-id 或品名，已跳過")
                continue
            items.append({
                "id": iid,
                "store": sl,
                "name": U(h3.group(1)).strip(),
                "desc": U(p.group(1)).strip() if p else "",
                "img_idx": int(img.group(1)) if img else None,
                "alt": attr(b, "alt") or "",
                "cat": attr(a, "data-cat") or "",
                "search": attr(a, "data-search"),
                "shop_label": U(shop.group(1)).strip() if shop else "",
            })

        for n, m in enumerate(EXTRA.finditer(body), 1):
            a, b = m.group("attrs"), m.group("body")
            h2e = re.search(r"<h2>(.*?)</h2>", b, re.S)
            img = re.search(r'src="__IMG_(\d+)__"', b)
            extras.append({
                "id": f"extra-{len(extras) + 1}",
                "store": sl,
                "title": U(h2e.group(1)).strip() if h2e else "",
                "img_idx": int(img.group(1)) if img else None,
                "table": parse_table(b),
                "html_note": strip_tags(re.sub(r"<table.*?</table>", "", b, flags=re.S)),
            })

    return stores, items, extras, anomalies


def parse_table(b: str) -> dict | None:
    t = re.search(r"<table.*?</table>", b, re.S)
    if not t:
        return None
    rows = []
    for tr in re.findall(r"<tr>(.*?)</tr>", t.group(0), re.S):
        cells = [strip_tags(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S)]
        status = re.findall(r'class="status (\w+)"', tr)
        if cells:
            rows.append({"cells": cells, "status": status[0] if status else None})
    if not rows:
        return None
    return {"head": rows[0]["cells"], "rows": [r for r in rows[1:]]}


def strip_tags(s: str) -> str:
    return re.sub(r"\s+", " ", U(re.sub(r"<[^>]+>", " ", s))).strip()


def square(im: Image.Image, px: int, anchor="center") -> Image.Image:
    """裁成方形。

    anchor 可以是 "top" / "center" / "bottom"，或 0.0–1.0 的數字
    (方形上緣落在可移動範圍的哪個位置，0=貼齊頂端、1=貼齊底端)。

    為什麼要能逐張指定：來源多半是手機截圖，由上而下是
    狀態列 / 帳號與貼文文字 / 商品照 / 互動數 / 留言，
    而別人的帳號名與大頭照上下都有。試過三種自動判斷都不可靠 —
    固定裁上會露出貼文作者、固定裁下會露出留言者，
    用「非白色 = 照片」去找照片段則會誤殺白底商品照。
    最後採目視逐張確認 + 需要微調的才寫進 shopping_overrides.json 的 crops。
    """
    w, h = im.size
    s = min(w, h)
    l = (w - s) // 2
    span = h - s
    if isinstance(anchor, (int, float)):
        t = round(span * max(0.0, min(1.0, float(anchor))))
    else:
        t = {"top": 0, "bottom": span}.get(anchor, span // 2)
    return im.crop((l, t, l + s, t + s)).resize((px, px), Image.LANCZOS)


def fit(im: Image.Image, px: int) -> Image.Image:
    w, h = im.size
    if max(w, h) <= px:
        return im
    r = px / max(w, h)
    return im.resize((round(w * r), round(h * r)), Image.LANCZOS)


def encode(data: bytes, profile: str, anchor="center") -> tuple[bytes, int, int]:
    im = Image.open(io.BytesIO(data))
    im = im.convert("RGB")
    if profile == "text":
        im = fit(im, TEXT_PX)
        q = TEXT_Q
    else:
        im = square(im, PHOTO_PX, anchor)
        q = PHOTO_Q
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=q, method=6)
    return buf.getvalue(), im.width, im.height


def load_overrides() -> dict:
    if not OVERRIDES.exists():
        return {}
    return json.loads(OVERRIDES.read_text(encoding="utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--report", action="store_true", help="只檢查並輸出報告")
    g.add_argument("--write", action="store_true", help="產出 shopping.json 與圖片")
    args = ap.parse_args()

    src = find_source()
    raw = src.read_text(encoding="utf-8")
    sk, imgs = strip_images(raw)
    stores, items, extras, anomalies = parse(sk)
    ov = load_overrides()
    ov_img = ov.get("images", {})
    ov_store = ov.get("stores", {})

    L: list[str] = []
    add = L.append
    add(f"# 購物清單抽取報告\n")
    add(f"| 項目 | 數值 |")
    add(f"|---|---|")
    add(f"| 來源 | `private/raw/{src.name}` |")
    add(f"| 原始大小 | {len(raw.encode()):,} B |")
    add(f"| 抽掉圖片後的骨架 | {len(sk.encode()):,} B |")
    add(f"| 內嵌圖片 | {len(imgs)} 張，解碼後共 {sum(len(i) for i in imgs):,} B |")
    add(f"| 分類 | {len(stores)} |")
    add(f"| 品項 | {len(items)} |")
    add(f"| 附加區塊 | {len(extras)} |")
    add("")

    # --- 完整性檢查 ---
    add("## 完整性")
    ids = [it["id"] for it in items]
    dup = {i for i in ids if ids.count(i) > 1}
    nums = sorted(int(i.split("-")[1]) for i in ids)
    gaps = [n for n in range(1, max(nums) + 1) if n not in nums] if nums else []
    used_idx = {it["img_idx"] for it in items} | {e["img_idx"] for e in extras}
    orphan = [i for i in range(len(imgs)) if i not in used_idx]
    noimg = [it["id"] for it in items if it["img_idx"] is None]

    for label, val, ok in [
        ("重複的品項編號", sorted(dup) or "無", not dup),
        ("編號缺號", gaps or "無", not gaps),
        ("沒有對應卡片的圖片", orphan or "無", not orphan),
        ("沒有圖片的品項", noimg or "無", not noimg),
    ]:
        add(f"- {'OK  ' if ok else '注意'} {label}：{val}")
    add("")

    # --- 分類 ---
    add("## 分類（順序以導覽列為準）")
    add("| # | id | section | 名稱 | 品項數 |")
    add("|---|---|---|---|---|")
    for s in stores:
        n = sum(1 for it in items if it["store"] == s["id"])
        add(f"| {s['order']} | `{s['id']}` | {s['section']} | {s['name']} | {n} |")
    add("")

    # --- data-search 重現驗證 ---
    add("## data-search 重現驗證")
    have = [it for it in items if it["search"] is not None]
    missing = [it for it in items if it["search"] is None]
    bad = []
    for it in have:
        regen = f"{it['cat']} {it['name']} {it['desc']}".lower()
        if regen != it["search"]:
            bad.append((it["id"], it["search"], regen))
    add(f"- 有 data-search：{len(have)} 張；缺：{len(missing)} 張")
    add(f"- 規則 `f\"{{分類}} {{品名}} {{說明}}\".lower()` 重現不符：**{len(bad)}** 張")
    if bad:
        for iid, was, now in bad[:10]:
            add(f"  - `{iid}`\n    - 原檔：`{was}`\n    - 重現：`{now}`")
    else:
        add("  - 規則成立，所以 shopping.json 不存這個欄位，搜尋時在瀏覽器端現算。")
    if missing:
        add(f"- 缺 data-search 的品項（改為現算，不需補回原檔）：{', '.join(i['id'] for i in missing)}")
    add("")

    # --- 疑似文字圖 ---
    add("## 疑似文字圖（需要人工確認，預設全部當商品照處理）")
    cands = [it for it in items
             if any(h in it["name"].lower() for h in TEXT_HINTS)]
    if cands or extras:
        add("| id | 目前設定 | 依據 |")
        add("|---|---|---|")
        for it in cands:
            add(f"| `{it['id']}` | {ov_img.get(it['id'], 'photo')} | 文字線索：{it['name'][:34]} |")
        for e in extras:
            add(f"| `{e['id']}` | {ov_img.get(e['id'], 'photo')} | 附加區塊的圖，通常是截圖 |")
        add("")
        add("要改的話寫進 `shopping_overrides.json`：`{\"images\": {\"item-91\": \"text\"}}`")
    else:
        add("- 無")
    add("")

    # --- 圖片尺寸抽樣 ---
    add("## 圖片來源尺寸")
    dims = []
    for i, b in enumerate(imgs):
        try:
            im = Image.open(io.BytesIO(b))
            dims.append((i, im.width, im.height, len(b)))
        except Exception as e:
            anomalies.append(f"第 {i} 張圖無法解碼：{e}")
    if dims:
        ws = sorted(d[1] for d in dims)
        hs = sorted(d[2] for d in dims)
        bs = sorted(d[3] for d in dims)
        add(f"- 寬 {ws[0]}–{ws[-1]}，高 {hs[0]}–{hs[-1]}")
        add(f"- 單張 {bs[0]:,}–{bs[-1]:,} B，中位數 {bs[len(bs)//2]:,} B")
    add("")

    if anomalies:
        add("## 原檔異常（輸出從 JSON 重建，不需要回頭修原檔）")
        for a in anomalies:
            add(f"- {a}")
        add("")

    if ov:
        add("## 已套用的 overrides")
        add(f"- 分類設定 {len(ov_store)} 筆、圖片設定 {len(ov_img)} 筆")
        add("")

    report = "\n".join(L)
    BUILD.mkdir(exist_ok=True)
    (BUILD / "shopping_report.md").write_text(report, encoding="utf-8")
    print(report)
    print(f"\n報告已寫到 {BUILD / 'shopping_report.md'}")

    if args.report:
        print("\n(--report 模式，沒有寫出 shopping.json 或圖片)")
        return

    # --- 寫出 ---
    OUT_IMG.mkdir(parents=True, exist_ok=True)
    ov_crop = ov.get("crops", {})
    total_in = total_out = 0
    dropped = []
    for rec in items + extras:
        idx = rec.get("img_idx")
        profile = ov_img.get(rec["id"], "photo")
        if idx is None or profile == "drop":
            rec["img"] = None
            if profile == "drop":
                dropped.append(rec["id"])
                (OUT_IMG / f"{rec['id']}.webp").unlink(missing_ok=True)
            continue
        data, w, h = encode(imgs[idx], profile, ov_crop.get(rec["id"], "center"))
        path = OUT_IMG / f"{rec['id']}.webp"
        path.write_bytes(data)
        total_in += len(imgs[idx])
        total_out += len(data)
        rec["img"] = f"shop/{path.name}"
        rec["w"], rec["h"] = w, h
        rec["src_sha256"] = hashlib.sha256(imgs[idx]).hexdigest()[:16]

    for s in stores:
        o = ov_store.get(s["id"], {})
        s["days"] = o.get("days", [])
        s["short"] = o.get("short", s["name"])
        s["kind"] = o.get("kind", "physical" if o.get("days") else "any")

    out = {
        "version": 2,
        "source": f"private/raw/{src.name}",
        "stores": stores,
        "items": [{k: v for k, v in it.items()
                   if k not in ("img_idx", "search", "cat", "alt", "shop_label")}
                  for it in items],
        "extras": [{k: v for k, v in e.items() if k not in ("img_idx",)} for e in extras],
    }
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    n_img = len(items) + len(extras) - len(dropped)
    if dropped:
        print(f"\n刻意不輸出的圖：{', '.join(dropped)}")
    print(f"\n圖片  {n_img} 張  {total_in:,} B -> {total_out:,} B "
          f"(縮到 {total_out / total_in * 100:.1f}%，平均 {total_out // max(1, n_img):,} B)")
    print(f"寫出  {OUT_JSON}  ({len(OUT_JSON.read_bytes()):,} B)")
    print(f"      {OUT_IMG}")


if __name__ == "__main__":
    main()
