# ✈️ 機票價格監測小幫手 / Flight Price Monitor

> 自動監測指定航線的便宜機票，**降價就主動推到手機 Telegram**；
> 支援雲端每天自動跑（電腦關著也行）、桌面一鍵查、以及在 Telegram 直接打字查詢。

這是一個從零打造的小型自動化專案：把「定時抓資料 → 整理 → 通知」整條流程做成
**穩定、免顧、跨裝置**的服務。也是一份示範「資料擷取 + 排程 + 通知」如何串起來的範例。

---

## 🎯 解決什麼問題

人工一條一條去比價、還要天天回去看「降了沒」很煩。這個工具把它自動化：

- 你只要設定「想盯哪些航線、低於多少價想被通知」
- 它每天自動查、**只在變便宜時**通知你（不洗版）
- 通知附**繁體中文訂票連結**，點開直接看 / 訂

---

## ✨ 功能

| 功能 | 說明 |
|---|---|
| 🔎 多航線批次查價 | 一次查多條航線，單程 / 來回都支援 |
| 🌏 中文地名 | 直接輸入「高雄」「日本」「首爾」，自動轉成機場/國家代碼 |
| 🏙️ 整國搜尋 + 多城市選項 | 查「高雄→日本」會列出各城市的直飛選項讓你挑 |
| 📉 降價偵測 | 記住上次價格，**只有變便宜才通知**，避免洗版 |
| 📱 Telegram 推播 | 撿到便宜票直接推到手機，附中文 Skyscanner 連結 |
| 💬 雙向聊天 bot | 在 Telegram 打「查 高雄 東京 2026-09」即時回你 |
| ☁️ 雲端每天自動跑 | GitHub Actions 排程，電腦關機也照跑照推 |
| 🖱️ 桌面一鍵 / 開機自動 | Windows `.bat` 雙擊即用，可設開機背景待命 |
| 🔁 高穩定性 | 自動重試（間隔逐次拉長）、逾時、log、失敗不中斷 |

---

## 🧱 用到的技術

- **Python**（標準庫 + `requests`）
- **Travelpayouts / Aviasales Data API**（免費機票價格資料）
- **Telegram Bot API**（單向推播 + 雙向長輪詢查詢）
- **GitHub Actions**（雲端排程 + 把價格記憶提交回 repo）
- **Windows 工作排程器 / 批次檔**（本機自動化與一鍵啟動）
- 設計重點：重試/退避、log 輪替、設定與密鑰分離（環境變數）、相對路徑寫檔

---

## 🗺️ 架構（三種使用方式，同一套核心）

```
            ┌─────────────────────────────┐
            │  travelpayouts_flights.py   │  ← 核心：查價 / 降價偵測 / 通知
            └──────────────┬──────────────┘
                           │
   ┌───────────────┬───────┴────────┬────────────────────┐
   │               │                │                    │
☁️ 雲端排程     🖱️ 桌面一鍵       💬 雙向 bot          📉 降價記憶
GitHub Actions  每日查價.bat     telegram_bot.py     price_state.json
(電腦關著也跑)  查機票.bat        (手機打字即查)       (只在變便宜才推)
                           │
                           ▼
                  📱 Telegram 推播（附繁中 Skyscanner 連結）
```

---

## 🚀 快速開始

```bash
cd freelance-flights-mvp
pip install -r requirements.txt

# 設定金鑰（環境變數，不寫進程式碼）
#   Windows(PowerShell)： $env:TRAVELPAYOUTS_TOKEN="..."  $env:TG_TOKEN="..."  $env:TG_CHAT="..."
#   Mac/Linux：           export TRAVELPAYOUTS_TOKEN=...   等

python travelpayouts_flights.py        # 批次查設定好的航線
python telegram_bot.py                  # 啟動雙向聊天 bot
```

- Travelpayouts token：到 https://www.travelpayouts.com 免費註冊 → Profile → API token
- Telegram：用 @BotFather 建 bot 拿 token；`tg_setup.py` 幫你找出 chat id

**雲端每天自動跑**：把 token 設成 GitHub repo 的 Secrets（`TRAVELPAYOUTS_TOKEN` / `TG_TOKEN` / `TG_CHAT`），
`.github/workflows/flight-prices.yml` 會每天自動執行並推 Telegram。

---

## 📁 檔案

| 檔案 | 用途 |
|---|---|
| `travelpayouts_flights.py` | ⭐ 核心：多航線查價、降價偵測、推播 |
| `telegram_bot.py` | 雙向聊天 bot（在 Telegram 打字即查） |
| `tg_setup.py` | 找出你的 Telegram chat id |
| `查機票.bat` / `每日查價.bat` | 桌面一鍵：互動查 / 批次查 |
| `背景啟動機器人.bat` / `停止機器人.bat` / `開機背景啟動.bat` | bot 背景執行 / 停止 / 開機自動 |
| `設定每天自動跑.bat` / `取消每天自動跑.bat` | 本機每日排程（Windows 工作排程器） |
| `../.github/workflows/flight-prices.yml` | 雲端每日排程 |
| `scraper.py` / `scraper_playwright.py` | 通用爬蟲骨架（requests / 動態網站版），可改去爬其他網站 |
| `amadeus_flights.py` | Amadeus 版（其免費自助版 2026/7/17 關閉，留作參考） |

---

## ⚖️ 誠實的限制

- 免費的 Travelpayouts 資料 API 給的是「**其他使用者近期搜尋過、被快取的價格**」，
  所以**冷門航線 / 太遠的日期可能查無資料**——這不是 bug，是免費資料的天性。
- 適合「**監測熱門航線的降價**」；若要「任何航線都保證即時報價」，需付費的即時搜尋 API。
- 想盯「我一定要飛的那幾條」最穩的免費做法：搭配 **Google Flights 內建的「追蹤價格」**。
- 雙向 bot 跑在本機，**電腦關著時不會回應**；要 24 小時即時聊天需自備雲端主機。

---

## 🛠️ 也可當「資料擷取接案」起點

`scraper.py` / `scraper_playwright.py` 是通用骨架，已把接案要交付的「高穩定性結構」
（重試、log、CSV、排程、失敗通知）搭好。要改去爬別的網站，只需替換解析那一小塊。
接案前提醒：先確認目標網站服務條款、抓取頻率、反爬處理範圍，寫進報價保護自己。
