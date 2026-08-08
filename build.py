"""從資料檔產出兩個自足單檔 HTML。

  單檔版  -> H:\\我的雲端硬碟\\index_mobile.html      (本機直接開，不掛 manifest)
  發布版  -> build/public_plain.html                (加密後成為 docs/index.html)

兩份內容完全一樣，差別只有掛不掛 manifest 與加不加密。
個資兩份都不寫，跑同一套遮蔽與同一套掃描；任何一份掃不過就中止不寫檔。
改資料只改 json，不手改 html。

這一檔只是入口：載入 -> 產生 -> 遮蔽 -> 掃描 -> 寫檔。實作在 sitegen/ 底下。
"""

from __future__ import annotations

import re

from sitegen import data, deploy, redact
from sitegen.config import BUILD, DOCS, DRIVE_OUT
from sitegen.render.page import build_html


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    BUILD.mkdir(exist_ok=True)

    # 把 places / guide 掛到行程站點上。掛完 render 只做字典查表，不做模糊比對。
    data.attach()

    # 兩份跑同一組禁用字。單檔版先掃過才寫，掃不過連本機那份都不產。
    full = build_html(standalone=True)
    redact.scan(full, "單檔版")
    DRIVE_OUT.parent.mkdir(parents=True, exist_ok=True)
    DRIVE_OUT.write_text(full, encoding="utf-8")

    pub = build_html(standalone=False)
    redact.scan(pub, "發布版")
    # 明文公開版寫到 build/(已 gitignore)，當作加密工具的輸入。
    # 絕對不直接寫 docs/index.html — 那是加密後的成品，重跑 build 會把它蓋成明文。
    (BUILD / "public_plain.html").write_text(pub, encoding="utf-8")

    deploy.write_manifest()
    deploy.write_sw(pub)

    st = data.stats()
    n_routes = len(re.findall(r'class="rbtn', full))
    n_pid = len(re.findall(r"place_id=", full))
    print(f"單檔版   -> {DRIVE_OUT}  ({len(full.encode()) // 1024} KB)  個資掃描通過")
    print(f"待加密版 -> {BUILD / 'public_plain.html'}  ({len(pub.encode()) // 1024} KB)  個資掃描通過")
    print(f"路線按鈕 {n_routes} 顆；步行群組 {st['clusters']} 組；帶 place_id 的連結參數 {n_pid} 個")
    print(f"地點 {st['places']} 筆(其中 {st['place_id']} 筆有 place_id)；逐點說明 {st['guide']} 條")
    print()
    print("docs/index.html 沒有被動到。要更新公開版，用 tools/encrypt.html 加密")
    print(f"{BUILD / 'public_plain.html'} 後另存成 docs/index.html。")
    print("(兩份內容一樣，但發布請一律用待加密版 — 它掛了 manifest)")


if __name__ == "__main__":
    main()
