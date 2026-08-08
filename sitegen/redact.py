# -*- coding: utf-8 -*-
"""遮蔽與掃描。中止邏輯全部集中在這一檔。

遮蔽對照本身就含個資，不能寫在原始碼裡(這個套件會進公開 repo)。
private/ 已被 .gitignore 排除；讀不到就不產出 — 寧可 build 失敗也不要漏出去。

只有一組替換、一組禁用字，兩個產出跑同一套。原本分成「完整版」與「公開版」
兩套門檻，那個分岔本身就是漏出去的來源，所以合併掉。
"""
from __future__ import annotations

import html
import json
import sys

from .config import ROOT

PRIVATE = ROOT / "private" / "redactions.json"
if not PRIVATE.exists():
    sys.exit(f"找不到 {PRIVATE}；沒有遮蔽對照就不產出，已中止。")
_priv = json.loads(PRIVATE.read_text(encoding="utf-8"))

# 順序有意義：前面套過的會影響後面比對
REPLACE = [tuple(x) for x in _priv["replace"]]
FORBIDDEN = _priv["forbidden"]


def apply(body: str) -> str:
    """跑替換。HTML 逸出前後兩種寫法都換 — 同一個字串在文字節點與屬性裡長得不一樣。"""
    for a, b in REPLACE:
        body = body.replace(html.escape(a), html.escape(b)).replace(a, b)
    return body


def scan(text: str, label: str) -> None:
    """掃不過就中止。這是 fail-closed 的那一道，不要改成只印警告。"""
    bad = [w for w in FORBIDDEN if w in text]
    if bad:
        sys.exit(f"{label}個資掃描未通過：{bad}；已中止")
