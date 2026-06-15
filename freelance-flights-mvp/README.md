# 機票監測爬蟲骨架（MVP）— A2310 練手 / 起點

這是一份**現在就能跑**的爬蟲骨架。它不直接抓機票（目標網站還沒跟客戶確認），
而是先把接案要交付的「**高穩定性結構**」搭好：重試、log、CSV、排程、失敗通知。
等你確認真網站，只要改兩個地方就變正式案子。

---

## 1. 先跑起來（5 分鐘看到成果）

```bash
cd freelance-flights-mvp
python -m venv .venv && source .venv/bin/activate   # Windows：.venv\Scripts\activate
pip install -r requirements.txt
python scraper.py
```

跑完看：
- `data/flights.csv` — 抓到的資料
- `logs/scraper.log` — 每次執行的紀錄（含重試、錯誤）

> 預設 `USE_DEMO = True`，抓的是 `quotes.toscrape.com`（**專門給人練爬蟲的合法沙盒**）。
> 目的是讓你親眼看到「重試 → 抓取 → 解析 → 存 CSV → log」整條會動。

**試試重試機制**：把 `scraper.py` 裡的 `DEMO_URL` 改成一個壞網址，再跑一次，
看 log 怎麼重試、間隔怎麼逐次拉長、最後怎麼報錯——這就是客戶說的「高穩定性」。

---

## 2. 變成真案子要改哪裡

1. **先偵查目標網站**（報價前就要做）：打開網站 → `F12` → Network → XHR/Fetch，
   操作一次搜尋，看資料怎麼來：
   - 有回傳 JSON 的 API → 最好爬，直接打那個網址。
   - 資料在 HTML 裡 → 用 `scraper.py` 的 BeautifulSoup。
   - 資料靠 JS 動態長出來（Google Flights 多半是）→ 用 `scraper_playwright.py`。
2. 把 `scraper.py` 的 `USE_DEMO` 改成 `False`，填 `TARGET_URL`、`ROUTES`。
3. 把 `parse_flights()`（或 Playwright 版的 `extract_flights()`）裡的 `REPLACE_ME`
   換成真實選擇器 / JSON 取值。
4. 失敗通知：`notify_failure()` 裡接上客戶要的管道（Telegram 範例已附）。

---

## 3. 定時排程（「定期、定時抓」就靠這個）

選一種即可。先確認手動 `python scraper.py` 能跑，再排程。

### A) GitHub Actions（免費、不用自己開電腦，輕量監測首選）
在 repo 建 `.github/workflows/scrape.yml`：

```yaml
name: scrape-flights
on:
  schedule:
    - cron: "0 * * * *"   # 每小時整點（UTC 時區，台灣要 -8 換算）
  workflow_dispatch: {}    # 也可手動按按鈕跑
jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r freelance-flights-mvp/requirements.txt
      - run: python freelance-flights-mvp/scraper.py
      # CSV 要保存的話，這裡再加一步 commit 回 repo 或上傳 artifact
```

### B) Linux / Mac：cron
```bash
crontab -e
# 每小時整點跑（路徑換成你的絕對路徑）
0 * * * * cd /path/to/freelance-flights-mvp && /path/to/.venv/bin/python scraper.py
```

### C) Windows：工作排程器
1. 開「工作排程器 / Task Scheduler」→ 建立基本工作
2. 觸發程序：選每天 / 每小時
3. 動作：啟動程式 → 程式填 `python`（或 venv 裡的 python.exe 絕對路徑），
   引數填 `scraper.py`，「開始位置」填這個資料夾的路徑

---

## 4. 檔案說明

| 檔案 | 用途 |
|---|---|
| `travelpayouts_flights.py` | ⭐ **高雄↔東京每日記價 + 降價通知**（用 Travelpayouts/Aviasales 免費資料 API）。自己找便宜機票用這支，註冊與設定步驟寫在檔案開頭 |
| `amadeus_flights.py` | 同功能的 Amadeus 版。⚠️ **Amadeus 免費自助版將於 2026/7/17 關閉**，留作參考，新用戶請改用上面那支 |
| `scraper.py` | 主骨架（requests 版）。要爬靜態網站 / 有 JSON API 用這支 |
| `scraper_playwright.py` | 動態網站版（Google Flights 這類，資料靠 JS 載入） |
| `requirements.txt` | 套件清單 |

> **想自己找便宜機票？** 直接用 `travelpayouts_flights.py`，比爬 Google Flights 輕鬆太多。
> 去 https://www.travelpayouts.com 免費註冊 → Profile → API token 拿 token →
> 設成環境變數 `TRAVELPAYOUTS_TOKEN` → `python travelpayouts_flights.py`。細節看該檔案開頭。

---

## 5. 接案時記得提醒客戶的事（保護自己）

- **目標網站的服務條款（ToS）**：很多網站禁止爬取，Google 系列尤其嚴。先讓客戶知道法律/封號風險，別自己默默扛。
- **頻率 vs 風險**：抓越兇越容易被封。把頻率寫進報價、並設禮貌等待。
- **反爬升級不是免費維修**：網站改版、加驗證碼、封 IP，要不要處理、代理 IP 費用誰出，先講清楚、寫進範圍。
