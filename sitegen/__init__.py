# -*- coding: utf-8 -*-
"""行程 app 產生器。

分層：
  config   路徑與常數
  data     載入 json、疊 overrides、把 places/guide 掛到行程站點上
  maps     Google Maps 網址組裝(place_id 優先)
  redact   遮蔽與掃描，中止邏輯集中在這裡
  assets   圖片內嵌、讀 web/ 底下的 CSS 與 JS
  render/  產生標記
  deploy   manifest 與 service worker

套件裡每一檔都不含任何地名、店名、日期或時段 — 這些只存在於被 .gitignore
排除的資料檔與加密後的產出裡。
"""
