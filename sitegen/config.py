# -*- coding: utf-8 -*-
"""路徑與常數。這一檔不含任何地名、店名或日期。"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
DOCS = ROOT / "docs"
BUILD = ROOT / "build"
WEB = Path(__file__).resolve().parent / "web"

# 本機單檔版的落點。放在雲端硬碟資料夾，手機端靠同步取得。
DRIVE_OUT = Path(r"H:\我的雲端硬碟\index_mobile.html")

# 手機瀏覽器最多 3 個中繼點，所以每段最多 5 站(起點＋3 中繼＋終點)
MAX_PER_LEG = 5
# Google Maps 其他平台上限 9 個中繼點 -> 單一連結最多 11 站
MAX_SINGLE = 11
