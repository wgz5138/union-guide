# 台灣威力彩開獎分析

一個**獨立**的小專案：從台灣彩券公司官方 API 爬取威力彩（SuperLotto638）
**每一期的真實開獎號碼**，做統計分析，並誠實說明「該買幾個號碼才能提高中獎機率」。

> 這個專案與本 repo 內其他內容（法律小幫手、機票等）完全無關，獨立運作。

## 原則（很重要）

- **只用官方真實資料**。爬蟲只負責「抓取 + 整理」，程式**不會**自行產生、
  推測或填補任何開獎號碼。抓不到的月份會明確標記，不用假資料補。
- **不販賣明牌**。樂透每一期都是獨立隨機事件，歷史冷熱**無法**預測下一期，
  也無法提高你單注命中的機率。本專案如實呈現這個數學事實。

## 檔案

| 檔案 | 用途 |
|---|---|
| `scraper.py` | 從官方 API 逐月抓取全部歷史開獎資料 → `data/superlotto638.{json,csv}` |
| `ingest_csv.py` | 讀取官方下載的 CSV（每年一檔）→ `data/superlotto638.{json,csv}` |
| `analyze.py` | 讀取資料做統計分析 → `report/analysis_report.md` + `report/stats.json` |
| `wheel.py` | 包牌選號產生器（包牌全餐 / 依預算試算 / 隨機選號） |
| `data/` | 官方真實開獎資料 |
| `report/` | 分析報告 |

## 包牌選號產生器 `wheel.py`

```bash
# 包牌全餐：第一區挑一組號碼，產生所有 C(k,6) 組合注單（第二區可多選，省略=全包1~8）
python3 wheel.py wheel --pool "3 14 24 38 7 22 16" --second "2 5" --out tickets.csv

# 依預算試算：有多少錢、第二區選幾個，最多能包幾個號碼、機率多少
python3 wheel.py budget --budget 20000 --second-count 1

# 快速隨機選號（--avoid-birthday 偏好 >31 的號碼，降低與生日選號族群均分的機率）
python3 wheel.py random --count 5 --avoid-birthday
```

> ⚠ 包牌只是等比例放大注數→等比例放大機率，成本同步放大，**期望值仍為負**。
> 樂透每期獨立隨機，沒有任何選號法能保證或長期獲利。請當娛樂、量力而為。

## 使用方式

```bash
pip install -r requirements.txt

# 1) 抓取官方真實資料（2008-01 首期 ~ 本月）
python3 scraper.py

# 想先核對官方回傳欄位，可只抓某月並印出原始 JSON：
python3 scraper.py --dump-raw 2024-01

# 2) 產生統計分析報告
python3 analyze.py
```

## 資料來源

台灣彩券公司官方 API：
`https://api.taiwanlottery.com/TLCAPIWeB/Lottery/SuperLotto638Result`

> ⚠ 若在受限的雲端/沙箱環境執行，需先把 `api.taiwanlottery.com`
> 加入網路出口（egress）允許清單，否則會被擋（HTTP 403 / not in allowlist）。

## 威力彩規則速記

- 第一區：1~38 選 6 個
- 第二區：1~8 選 1 個
- 頭獎：第一區 6 個全中 + 第二區中 → 機率 = 1 / (C(38,6)×8) = **1 / 22,085,448**
- 每注 NT$50

## 分析會告訴你什麼

1. 第一區 1~38 / 第二區 1~8 各號碼的歷史出現次數、頻率、遺漏值
2. 冷熱號（全期 + 近 100 期）
3. 號碼結構：奇偶比、大小比、總和分布、連號比例
4. **機率真相**：單注中獎機率、包牌（買 k 個號碼）對應的注數/花費/機率對照表、
   期望值，以及為什麼長期一定虧
5. 實務建議（如何在預算內提高機率、如何降低中獎後被均分的風險）
