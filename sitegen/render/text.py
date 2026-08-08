# -*- coding: utf-8 -*-
"""共用的文字處理。這一檔不含任何地名。"""
from __future__ import annotations

import html
import re
import unicodedata

E = html.escape


def short(name: str, n: int = 22) -> str:
    """按鈕上只放得下一行；原檔有幾列把整條動線塞進標題，不截會爆版。"""
    name = name.strip()
    return name if len(name) <= n else name[:n - 1] + "…"


_TAIL_PAREN = re.compile(r"[（(]([^（()）]{8,})[)）]\s*$")


def display_name(jp: str) -> str:
    """卡片標題用的日文原名。

    Google Maps 上有些名稱帶一長串括號補述(營運單位、副標)，原樣放進 17px 標題
    會折三行。尾端括號內容夠長、且前面主體還夠長時就收掉 — 完整名稱仍在
    導航連結與詳細裡，不會消失。
    """
    jp = (jp or "").strip()
    m = _TAIL_PAREN.search(jp)
    if m and len(jp[:m.start()].strip()) >= 4:
        return jp[:m.start()].strip()
    return jp


def same_name(a: str, b: str) -> bool:
    """兩個名字正規化後一不一樣 — 一樣就不輸出次行，省掉整排重複的字。"""
    def n(s: str) -> str:
        s = unicodedata.normalize("NFKC", s or "")
        return re.sub(r"[\s'’.,·・\-–—]+", "", s).casefold()
    return bool(a) and n(a) == n(b)
