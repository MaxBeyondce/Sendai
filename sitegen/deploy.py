# -*- coding: utf-8 -*-
"""manifest 與 service worker。這一檔不含任何地名。"""
from __future__ import annotations

import hashlib
import json

from .config import CACHE_PREFIX, DOCS, MANIFEST_NAME


def write_manifest() -> None:
    """manifest 是公開可讀的，名稱不能寫行程內容(會在瀏覽器和 repo 裡直接看到)。

    名稱預設「行程」；trip.json 有 manifest_name 就用那個(見 config.configure())。
    """
    # start_url 用目錄而不是 ./index.html：service worker 在 install 時
    # 預先快取的是 './'，兩者是不同的網址。寫成 ./index.html 的話，
    # 從主畫面圖示啟動會要求一個沒被快取的網址，離線時整頁打不開 —
    # 而離線正是加到主畫面的主要理由。
    (DOCS / "manifest.webmanifest").write_text(json.dumps({
        "name": MANIFEST_NAME, "short_name": MANIFEST_NAME, "start_url": "./",
        "display": "standalone", "background_color": "#f3f0e9", "theme_color": "#263c36",
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def write_sw(plain: str) -> str:
    """快取名帶內容雜湊：改版重新部署會換名，舊快取在 activate 時清掉。
    用固定名稱的話，cache-first 會讓使用者永遠停在第一次抓到的版本。
    雜湊算的是明文 — 加密後每次 salt/iv 不同，用密文會每次都變。

    快取名字首預設「sendai-trip」；trip.json 有 cache_prefix 就用那個，
    避免多個行程的 service worker 快取互相撞名(見 config.configure())。

    預先快取清單**不含 index.html**：它是整份內容，加上快取名會隨改版而變，
    放進 install 等於每次改版都把同一份大檔下載兩次。讓既有的 fetch handler
    在第一次載入後自己收進去就好。
    """
    digest = hashlib.sha1(plain.encode()).hexdigest()[:10]
    (DOCS / "sw.js").write_text(
        f"const C='{CACHE_PREFIX}-{digest}';const A=['./','./manifest.webmanifest'];\n"
        "self.addEventListener('install',e=>{self.skipWaiting();"
        "e.waitUntil(caches.open(C).then(c=>c.addAll(A)).catch(()=>{}))});\n"
        "self.addEventListener('activate',e=>{e.waitUntil(caches.keys()"
        ".then(k=>Promise.all(k.filter(x=>x!==C).map(x=>caches.delete(x)))).then(()=>self.clients.claim()))});\n"
        "self.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;"
        "e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request).then(res=>{"
        "const cp=res.clone();caches.open(C).then(c=>c.put(e.request,cp));return res;})"
        # 離線的最後退路要指向真的有被預先快取的那個網址，也就是 './'
        ".catch(()=>caches.match('./'))))});\n", encoding="utf-8")
    return digest
