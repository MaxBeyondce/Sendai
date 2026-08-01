# 加密單檔行程表產生器

把多日行程資料產生成手機優先的單檔 HTML，內容以密碼加密後才發布。
`docs/index.html` 沒有密碼就只是密文，看原始碼也拿不到內容。

## 這個 repo 裡有什麼

```
build.py              產生器：資料 -> 自足單檔 HTML
extract.py            一次性抽取工具：舊版 HTML -> 結構化資料
tools/encrypt.html    加密工具，瀏覽器內執行
docs/                 GitHub Pages 目錄(加密後的 index.html / sw.js / manifest)
```

行程資料本身**不在這個 repo 裡**，全部由 `.gitignore` 排除：

| 排除項目 | 內容 |
|---|---|
| `trip_data.json` | 行程原貌 |
| `clusters.json` | 各站順序與備註 |
| `private/` | 遮蔽對照 |
| `assets/`、`build/` | 建置素材與待加密的明文 |

`build.py` 讀不到 `private/redactions.json` 會直接中止，不會產出未遮蔽的版本。

## 產出

```bash
python build.py
```

會產生兩份：本機保留的完整版，以及待加密的明文版（在 `build/`，已排除）。
**不會動到 `docs/index.html`** — 那是加密後的成品，避免重跑時被蓋成明文。

## 加密後才發布

1. 瀏覽器開 `tools/encrypt.html`
2. 選要加密的檔案，設密碼
3. 下載到的 `index.html` 覆蓋 `docs/index.html`，然後 push

加密在自己的瀏覽器裡完成，**密碼不會經過任何伺服器，也不寫進任何檔案**。

| 項目 | 規格 |
|---|---|
| 金鑰導出 | PBKDF2-SHA256，310,000 次，16 bytes 隨機 salt |
| 加密 | AES-GCM 256-bit，12 bytes 隨機 IV |
| 實作 | 瀏覽器內建 Web Crypto，無外部套件 |

強度取決於密碼長度，短密碼或純數字擋不住離線暴力破解。密碼沒有救援方式。

「在這台裝置記住」會把導出的金鑰存在瀏覽器本機，之後開啟自動解；清除瀏覽器資料即可取消。

## 產出頁面的功能

卡片式版面(無橫向捲動)、黏頂日期頁籤、觸控區 ≥44px、Google Maps 多點路線、
每站可勾選並記錄進度、深色高對比、service worker 離線快取、可加到主畫面、列印存 PDF。

### Google Maps 多點連結的限制

```
https://www.google.com/maps/dir/?api=1&origin=A&destination=E&waypoints=B%7CC%7CD&travelmode=walking
```

- 手機瀏覽器最多 3個中繼點，其他平台最多 9個 → 單一連結 5站到 11站
- 沒有順序最佳化參數，中繼點依網址列出的順序顯示

所以路線一律拆成每段 5站(起點＋3中繼＋終點)，前一段終點即下一段起點；
站數 ≤11 的另外提供整段連結。順序由資料端決定，不是 Google 算的。

## 修改

改資料檔後重跑 `python build.py`，再重新加密。
不要直接改產出的 HTML，下次 build 會被蓋掉。
