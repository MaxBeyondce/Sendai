# -*- coding: utf-8 -*-
"""建立新行程的資料夾骨架：trips/<name>/。

  python new_trip.py hokkaido-2027            在 trips/hokkaido-2027/ 建立空骨架
  python new_trip.py hokkaido-2027 --force    資料夾已存在也覆蓋

只寫骨架，內容全部留空，交給使用者自己填 — 這一檔不寫任何真實行程資料。
跟 trips/ 底下所有東西一樣，這個資料夾已被 .gitignore 排除，不會進公開 repo。

骨架的檔案形狀對照 sitegen/data.py 的載入邏輯：
  trip_data.json / clusters.json    build.py 一定要讀到，缺了就中止
  places.json / guide.json          選用，缺席不會中止，只是少一塊
  guide_overrides.json
  shopping.json / shopping_overrides.json
  private/redactions.json           build.py 一定要讀到，缺了就中止(遮蔽對照)
  trip.json                         選用；缺席時 sitegen.config 用 Sendai 現況的預設值
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TRIPS = ROOT / "trips"


def _write(p: Path, obj: dict, force: bool) -> None:
    if p.exists() and not force:
        print(f"已存在，略過：{p}")
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"寫入 {p}")


def scaffold(name: str, force: bool) -> Path:
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        sys.exit(f"行程代稱不合法：{name!r}")

    trip_dir = TRIPS / name
    if trip_dir.exists() and any(trip_dir.iterdir()) and not force:
        sys.exit(f"{trip_dir} 已存在且非空；加 --force 才會覆蓋既有檔案。")

    (trip_dir / "assets").mkdir(parents=True, exist_ok=True)
    (trip_dir / "private").mkdir(parents=True, exist_ok=True)

    _write(trip_dir / "trip_data.json", {
        "source": "", "image": None, "title": "", "hero_title": "", "hero_sub": "",
        "pills": [], "cards": [], "feature": None, "days": [], "footer": "",
    }, force)

    _write(trip_dir / "clusters.json", {
        "_readme": ["步行／大眾運輸群組。留空即可；build.py 需要這個檔存在(可以是空陣列)。"],
        "clusters": [],
    }, force)

    _write(trip_dir / "places.json", {
        "_readme": ["地點名稱／座標／place_id 的單一來源。選用，缺席不會中止 build。"],
        "places": {},
    }, force)

    _write(trip_dir / "guide.json", {
        "version": 1, "source": "", "entries": [], "notes": [],
    }, force)

    _write(trip_dir / "guide_overrides.json", {
        "_readme": ["guide.json 的手改層，載入時疊上去。"],
        "match": {}, "alias": {}, "drop": [], "choice": [],
    }, force)

    _write(trip_dir / "shopping.json", {
        "version": 1, "source": "", "stores": [], "items": [], "extras": [],
    }, force)

    _write(trip_dir / "shopping_overrides.json", {
        "_readme": ["shopping.json 的手改層，載入時疊上去。"],
        "images": {}, "crops": {}, "stores": {},
    }, force)

    _write(trip_dir / "private" / "redactions.json", {
        "_readme": [
            "個資遮蔽對照。build.py 讀不到這一檔就不會產出，直接中止。",
            "replace   = 字串替換對照，順序有意義(前面先套的會影響後面)。",
            "forbidden = 產出後的最終掃描字串，出現任何一個就中止不寫檔。",
        ],
        "replace": [], "forbidden": [],
    }, force)

    _write(trip_dir / "trip.json", {
        "_readme": ["這個檔選用；沒有這個檔就照 Sendai 現況的預設值跑(見 sitegen/config.py)。"],
        "drive_out": rf"H:\我的雲端硬碟\{name}_mobile.html",
        "manifest_name": name,
        "cache_prefix": f"{name}-trip",
    }, force)

    return trip_dir


def main() -> None:
    p = argparse.ArgumentParser(description="建立新行程的資料夾骨架")
    p.add_argument("name", help="行程代稱，會建立在 trips/<name>/ 底下")
    p.add_argument("--force", action="store_true", help="資料夾已存在也覆蓋既有檔案")
    args = p.parse_args()

    trip_dir = scaffold(args.name, args.force)
    print()
    print(f"骨架已建立：{trip_dir}")
    print("接著：")
    print(f"  1. 把行程內容填進 {trip_dir} 底下的 json(可用 extract.py 從舊版 HTML 抽)")
    print(f"  2. 先試跑：python build.py --trip {trip_dir} --no-drive --out <輸出資料夾>")
    print(f"  3. 確認沒問題：python build.py --trip {trip_dir}")
    print("  4. tools/encrypt.html 加密 build/public_plain.html，存成 docs/index.html 再發布")


if __name__ == "__main__":
    main()
