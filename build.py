"""從資料檔產出兩個自足單檔 HTML。

  單檔版  -> H:\\我的雲端硬碟\\index_mobile.html      (本機直接開，不掛 manifest)
  發布版  -> build/public_plain.html                (加密後成為 docs/index.html)

兩份內容完全一樣，差別只有掛不掛 manifest 與加不加密。
個資兩份都不寫，跑同一套遮蔽與同一套掃描；任何一份掃不過就中止不寫檔。
改資料只改 json，不手改 html。

這一檔只是入口：載入 -> 產生 -> 遮蔽 -> 掃描 -> 寫檔。實作在 sitegen/ 底下。

  python build.py                                預設讀 repo 根目錄(Sendai 現況)
  python build.py --trip trips/hokkaido-2027       讀另一個行程資料夾
  python build.py --out /tmp/preview --no-drive    輸出到別的資料夾，不寫雲端硬碟單檔版

--trip / --out / --no-drive 的路徑一定要在 import sitegen.data 之前算好 —
那些模組是在被 import 的當下讀 sitegen.config 的值，所以這一檔刻意把
argparse 與 sitegen.config.configure() 放在所有 sitegen 子模組 import 之前。
"""

from __future__ import annotations

import argparse
import re


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    p.add_argument("--trip", default=None,
                   help="行程資料夾路徑(內含 trip_data.json 等)；不給就讀 repo 根目錄")
    p.add_argument("--out", default=None,
                   help="public_plain.html / manifest.webmanifest / sw.js 的輸出資料夾；"
                        "不給就是 build/ 與 docs/")
    p.add_argument("--no-drive", action="store_true", dest="no_drive",
                   help="不寫雲端硬碟單檔版(預設 H:\\我的雲端硬碟\\index_mobile.html)")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    from sitegen import config
    config.configure(trip=args.trip, out=args.out, no_drive=args.no_drive)

    # 一定要等 configure() 跑完才 import 這幾個 — 它們在 import 當下就會讀
    # sitegen.config 的路徑(trip_data.json 在哪、private/redactions.json 在哪)。
    from sitegen import data, deploy, redact
    from sitegen.render.page import build_html

    config.DOCS.mkdir(parents=True, exist_ok=True)
    config.BUILD.mkdir(parents=True, exist_ok=True)

    # 把 places / guide 掛到行程站點上。掛完 render 只做字典查表，不做模糊比對。
    data.attach()

    # 兩份跑同一組禁用字。單檔版先掃過才寫，掃不過連本機那份都不產。
    full = build_html(standalone=True)
    redact.scan(full, "單檔版")
    if config.DRIVE_OUT is not None:
        config.DRIVE_OUT.parent.mkdir(parents=True, exist_ok=True)
        config.DRIVE_OUT.write_text(full, encoding="utf-8")

    pub = build_html(standalone=False)
    redact.scan(pub, "發布版")
    # 明文公開版寫到 build/(已 gitignore)，當作加密工具的輸入。
    # 絕對不直接寫 docs/index.html — 那是加密後的成品，重跑 build 會把它蓋成明文。
    (config.BUILD / "public_plain.html").write_text(pub, encoding="utf-8")

    deploy.write_manifest()
    deploy.write_sw(pub)

    st = data.stats()
    n_routes = len(re.findall(r'class="rbtn', full))
    n_pid = len(re.findall(r"place_id=", full))
    if config.DRIVE_OUT is not None:
        print(f"單檔版   -> {config.DRIVE_OUT}  ({len(full.encode()) // 1024} KB)  個資掃描通過")
    else:
        print(f"單檔版   -> (--no-drive，未寫檔)  ({len(full.encode()) // 1024} KB)  個資掃描通過")
    print(f"待加密版 -> {config.BUILD / 'public_plain.html'}  ({len(pub.encode()) // 1024} KB)  個資掃描通過")
    print(f"路線按鈕 {n_routes} 顆；步行群組 {st['clusters']} 組；帶 place_id 的連結參數 {n_pid} 個")
    print(f"地點 {st['places']} 筆(其中 {st['place_id']} 筆有 place_id)；逐點說明 {st['guide']} 條")
    print()
    print(f"{config.DOCS} 底下的 index.html 沒有被動到。要更新公開版，用 tools/encrypt.html 加密")
    print(f"{config.BUILD / 'public_plain.html'} 後另存成 {config.DOCS / 'index.html'}。")
    print("(兩份內容一樣，但發布請一律用待加密版 — 它掛了 manifest)")


if __name__ == "__main__":
    main()
