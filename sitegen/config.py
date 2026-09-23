# -*- coding: utf-8 -*-
"""路徑與常數。這一檔不含任何地名、店名或日期。

單一入口是 configure()：依 --trip / --out / --no-drive 算出這次執行要用的路徑，
寫回這裡的模組全域。其他模組一律在被 import 的當下讀這些全域(例如
`from .config import ROOT`)，所以呼叫順序要固定：build.py 一定要先呼叫
configure()，才能第一次 import sitegen.data / redact / deploy / render.page
— 那些模組的模組層級敘述就是在讀這裡當下的值，之後才 import 不會補讀到。

沒呼叫 configure() 時，下面這組模組層級預設值就是 Sendai 現況(讀 repo 根目錄)，
保證只 `import sitegen.config` 而不呼叫 configure() 的舊行為不變。
"""
from __future__ import annotations

import json
from pathlib import Path

# repo 根目錄，固定不隨 --trip 改變(--out 的預設落點、extract.py 的預設輸出都靠它)。
PKG_ROOT = Path(__file__).resolve().parent.parent
# 樣板 CSS/JS，是套件本體不是行程資料，永遠跟著程式碼走。
WEB = Path(__file__).resolve().parent / "web"

# 手機瀏覽器最多 3 個中繼點，所以每段最多 5 站(起點＋3 中繼＋終點)
MAX_PER_LEG = 5
# Google Maps 其他平台上限 9 個中繼點 -> 單一連結最多 11 站
MAX_SINGLE = 11

_DEFAULT_DRIVE_OUT = Path(r"H:\我的雲端硬碟\index_mobile.html")
_DEFAULT_MANIFEST_NAME = "行程"
_DEFAULT_CACHE_PREFIX = "sendai-trip"

# 這次執行要用的路徑；configure() 沒被呼叫過就是 Sendai 現況。
ROOT = PKG_ROOT
ASSETS = ROOT / "assets"
DOCS = PKG_ROOT / "docs"
BUILD = PKG_ROOT / "build"
DRIVE_OUT: Path | None = _DEFAULT_DRIVE_OUT
MANIFEST_NAME = _DEFAULT_MANIFEST_NAME
CACHE_PREFIX = _DEFAULT_CACHE_PREFIX


def configure(trip: str | None = None, out: str | None = None, no_drive: bool = False) -> None:
    """依 CLI 參數算好這次執行要用的路徑，寫回模組全域。

    trip      行程資料夾；沒給就是 repo 根目錄(Sendai 現況，資料不搬家)。
    out       public_plain.html / manifest / sw.js 的輸出資料夾；
              沒給就是 repo 根目錄下的 build/ 與 docs/(現況)。
    no_drive  True 時 DRIVE_OUT 設成 None，呼叫端看到 None 就跳過那次寫檔 —
              不猜路徑、不試著寫，from 根本不算出一個會被誤用的路徑。

    trip 資料夾裡有 trip.json 就讀它覆蓋預設值(雲端硬碟落點、manifest 名稱、
    service worker 快取字首)；沒有這個檔就完全照 Sendai 現況的寫死值跑。
    """
    global ROOT, ASSETS, DOCS, BUILD, DRIVE_OUT, MANIFEST_NAME, CACHE_PREFIX

    ROOT = Path(trip).resolve() if trip else PKG_ROOT
    ASSETS = ROOT / "assets"

    settings: dict = {}
    trip_json = ROOT / "trip.json"
    if trip_json.exists():
        settings = json.loads(trip_json.read_text(encoding="utf-8"))

    if out:
        out_dir = Path(out).resolve()
        DOCS = out_dir
        BUILD = out_dir
    else:
        DOCS = PKG_ROOT / "docs"
        BUILD = PKG_ROOT / "build"

    if no_drive:
        DRIVE_OUT = None
    else:
        drive = settings.get("drive_out")
        DRIVE_OUT = Path(drive) if drive else _DEFAULT_DRIVE_OUT

    MANIFEST_NAME = settings.get("manifest_name", _DEFAULT_MANIFEST_NAME)
    CACHE_PREFIX = settings.get("cache_prefix", _DEFAULT_CACHE_PREFIX)
