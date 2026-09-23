# 加密單檔行程表產生器

把多日行程資料產生成手機優先的單檔 HTML，內容以密碼加密後才發布。
`docs/index.html` 沒有密碼就只是密文，看原始碼也拿不到內容。

## 這個 repo 裡有什麼

```
build.py              產生器：資料 -> 自足單檔 HTML(--trip 選行程、--out/--no-drive 控輸出)
new_trip.py            新行程骨架產生器：trips/<name>/
extract.py            一次性抽取工具：舊版 HTML -> 結構化資料
tools/encrypt.html    加密工具，瀏覽器內執行
docs/                 GitHub Pages 目錄(加密後的 index.html / sw.js / manifest)
tests/                pytest，全部用合成假資料，不碰真實行程
```

行程資料本身**不在這個 repo 裡**，全部由 `.gitignore` 排除：

| 排除項目 | 內容 |
|---|---|
| `trip_data.json` | 行程原貌 |
| `clusters.json` | 各站順序與備註 |
| `private/` | 遮蔽對照 |
| `assets/`、`build/` | 建置素材與待加密的明文 |
| `trips/` | 每一趟行程各自的資料夾(見下方「新增一趟旅遊」) |

`build.py` 讀不到 `private/redactions.json` 會直接中止，不會產出未遮蔽的版本。

## 產出

```bash
python build.py
```

不加參數就是現況：讀 repo 根目錄的行程資料，產生兩份**內容完全一樣**的檔案 —
本機直接開的單檔版，以及待加密的明文版（在 `build/public_plain.html`，已排除）。
差別只有掛不掛 manifest。個資兩份都不寫，跑同一套遮蔽與同一套掃描，
任何一份掃不過就中止不寫檔。

**不會動到 `docs/index.html`** — 那是加密後的成品，避免重跑時被蓋成明文。

可選參數：

| 參數 | 作用 |
|---|---|
| `--trip <資料夾>` | 讀哪個行程的資料；不給就是 repo 根目錄(現況) |
| `--out <資料夾>` | `public_plain.html`／`manifest.webmanifest`／`sw.js` 輸出到別的地方；不給就是 `build/` 與 `docs/`(現況) |
| `--no-drive` | 不寫雲端硬碟單檔版(預設 `H:\我的雲端硬碟\index_mobile.html`) |

先試跑不想動到任何既有檔案時，`--out` 配 `--no-drive` 一起下。

## 加密後才發布

1. 瀏覽器開 `tools/encrypt.html`
2. 選 **`build/public_plain.html`**，設密碼
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

## 新增一趟旅遊

這一份產生器是共用的，行程資料不是。新行程走這條路，Sendai 那份不會被動到：

1. **搭骨架**

   ```bash
   python new_trip.py hokkaido-2027
   ```

   會在 `trips/hokkaido-2027/` 底下建好 `trip_data.json`、`clusters.json`、
   `places.json`、`guide.json`、`shopping.json`、對應的 `_overrides.json`、
   `private/redactions.json`、`assets/`，還有一份 `trip.json` 範例 —
   全部是空骨架，**不含任何真實資料**。`trips/` 整個資料夾已被 `.gitignore`
   排除，跟根目錄那份行程資料同理，不會進公開 repo。

2. **填資料**

   把行程內容填進 `trips/hokkaido-2027/` 底下那幾個 json。如果來源是一份舊版
   自足 HTML，可以先用 `extract.py` 抽：

   ```bash
   python extract.py <來源.html> --out-dir trips/hokkaido-2027
   ```

   `private/redactions.json` 一定要填 — 沒有這一檔 `build.py` 會直接中止，
   不會產出未遮蔽的版本。`trip.json` 是選用的，留著預設值也能跑，
   內容可以覆蓋：

   ```json
   {
     "drive_out": "H:\\我的雲端硬碟\\hokkaido_mobile.html",
     "manifest_name": "北海道行程",
     "cache_prefix": "hokkaido-trip"
   }
   ```

   不填 `trip.json` 的話，這三項就照 Sendai 現況的值跑(`行程` / `sendai-trip` /
   `H:\我的雲端硬碟\index_mobile.html`) — 這樣會跟 Sendai 那份撞名，
   所以新行程建議一定要填。

3. **試跑，不動到任何既有檔案**

   ```bash
   python build.py --trip trips/hokkaido-2027 --no-drive --out /tmp/preview
   ```

   確認 `/tmp/preview/public_plain.html` 打開沒問題，再跑正式的：

   ```bash
   python build.py --trip trips/hokkaido-2027
   ```

   這樣才會真的寫本機單檔版（用 `trip.json` 裡的 `drive_out`，沒填就還是
   Sendai 那個檔案位置，所以務必先填）、`build/public_plain.html`、
   `docs/manifest.webmanifest`、`docs/sw.js`。

4. **加密後發布**

   跟現況一樣，開 `tools/encrypt.html` 加密 `build/public_plain.html`。

   **但發布地點要另外處理**：這個 repo 的 `docs/` 是 Sendai 那個 GitHub Pages
   網站專用的，兩趟行程共用同一個 `docs/` 會互相蓋掉。新行程要嘛另開一個
   GitHub repo 各自掛自己的 Pages，要嘛用別的靜態網站託管 — 哪一種由 Max
   決定，這個 repo 本身沒有幫你自動切分。

## 修改

改資料檔後重跑 `python build.py`（或帶 `--trip` 指定行程），再重新加密。
不要直接改產出的 HTML，下次 build 會被蓋掉。

## 測試

```bash
python -m pytest tests/
```

全部用臨時目錄裡現造的合成假資料，不會讀寫任何真實行程資料。
