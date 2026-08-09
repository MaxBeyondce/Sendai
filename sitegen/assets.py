# -*- coding: utf-8 -*-
"""圖片內嵌。單檔自足的要求代表所有圖都得變成 data URI。這一檔不含任何檔名。"""
from __future__ import annotations

import base64
from pathlib import Path

from .config import ASSETS

MIME = {".webp": "image/webp", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".svg": "image/svg+xml"}


def data_uri(rel: str | None) -> str:
    """assets/ 底下的檔案轉成 data URI；檔案不在就回空字串，由呼叫端決定要不要留位。

    同名的 .webp 存在時優先用它。資料檔是機器抽出來的原貌，不手改 —
    改壓縮格式不該去動資料，在這裡挑就好。
    """
    if not rel:
        return ""
    p = ASSETS / rel
    webp = p.with_suffix(".webp")
    if webp.exists():
        p = webp
    if not p.exists():
        return ""
    mime = MIME.get(p.suffix.lower(), "application/octet-stream")
    return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"


def read_web(name: str) -> str:
    """讀 sitegen/web/ 底下的 CSS 或 JS。build 時內嵌，成品仍是單檔。"""
    from .config import WEB
    return (WEB / name).read_text(encoding="utf-8")


def size_of(rel: str) -> int:
    p: Path = ASSETS / rel
    return p.stat().st_size if p.exists() else 0
