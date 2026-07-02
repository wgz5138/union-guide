# CLAUDE.md — 臨床快查（search.html）開發記憶

這份文件是給下一個 Claude session 讀的。讀完就知道整個專案狀況，不需要重問使用者。

## 專案基本資訊

- **GitHub Pages 網址**：https://wgz5138.github.io/union-guide/search.html
- **GitHub Repo**：wgz5138/union-guide
- **主要開發分支**：直接推 `main`（GitHub Pages 從 main 部署）
- **主要檔案**：`search.html`、`ebn-common.js`、`sw.js`、`ebn-ver.txt`

## 版本管理機制

每次修改必須同時更新以下四個地方，否則使用者看不到新版：

1. `search.html` 裡的 `const BUILD="YYYYMMDDNN"`（NN 是當天第幾版，從 01 開始）
2. `sw.js` 裡的 `const CACHE = "ebn-YYYYMMDDNN"`（與 BUILD 一致）
3. `ebn-ver.txt` 的內容（與 BUILD 一致，`echo -n "2026XXXXNN" > ebn-ver.txt`）
4. `CHANGELOG` 陣列加一行說明（在 search.html 約第 400 行）

更新後橫幅「有新版本了！」才會出現，使用者按「立即更新」會強制清除所有 Service Worker 快取並重載。

## 共用函式庫：ebn-common.js

所有頁面共用。包含：
- `toast(msg)` — 底部提示
- `copy(text, ok)` / `copyEl(id, ok)` — 複製到剪貼簿
- `cyrb53(s)` — 密碼雜湊
- `verLabel()` / `checkUpdate()` / `initVersionCheck(verFile)` — 版本檢查與更新橫幅
- `PRICE` / `ntd()` / `apiHeaders()` / `apiErr()` — Claude API 工具

**重要**：`ebn-common.js` 被 sw.js 設為「不攔截，永遠走網路」，避免快取卡住。

## Service Worker（sw.js）

- HTML 走「網路優先」
- `ver.txt`、`ebn-ver.txt`、`ebn-common.js`、`laws.json` 完全不攔截
- 每次更新 CACHE 版本號可清除舊快取
- 「立即更新」按鈕會先 `caches.keys()` 全刪、再 `serviceWorker.getRegistrations()` 全 unregister、再 `location.replace()`

## search.html 功能清單（2026-06-27 現況）

### 密碼保護
- 預設密碼：`qqq11111111`（3個q＋8個1）
- 雜湊存在 localStorage，原始碼看不到真密碼
- ACCESS_VERSION 加 1 可踢出所有人重設

### ① 中文描述 → 關鍵字
- 使用者用中文描述臨床問題
- **🎤 語音輸入**：右側麥克風鈕，Web Speech API，`lang="zh-TW"`，說完自動停
- 免費路線：產生提示詞 → 複製貼給 ChatGPT/Claude
- 付費路線：有 API 金鑰 → 直接呼叫 Claude 生成查詢

### ② 搜尋（Europe PMC API）
- API endpoint：`https://www.ebi.ac.uk/europepmc/webservices/rest/search`
- 自動清除 PubMed 欄位標籤 `[tiab]`、URL 編碼、`QUERY1:` 前綴
- 篩選：研究類型（SR/RCT）、年份（近5/10年）、只看 Cochrane
- 0 筆時自動放寬（先拿掉篩選，再砍最後一個 AND 條件）
- 搜尋失敗時顯示 fallback（PubMed / Europe PMC / Cochrane 連結）

### 精準化面板（結果 ≥50 篇自動出現）
- PICO 快速選項 chips（病人、介入、結果、時程）
- 點選後即時預覽補充的英文條件
- 「套用精準條件，重新搜尋」一鍵重搜
- 函式：`window._showRefinePanel(hitCount)` / `window._hideRefinePanel()`

### 搜尋結果卡片
- 標題 + 作者 + 年份 + 期刊
- 研究類型 badge（Cochrane / SR/Meta / RCT）、免費全文 badge
- 展開/收合摘要
- 操作列：出版社全文、PubMed、Google 學術、複製連結、帶去評讀、**🌐 翻譯中文**

### 🌐 翻譯中文（內嵌，不開新視窗）
- 引擎：`translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=zh-TW`
- 中文標題顯示在英文標題正下方（綠色 `.tr-title`）
- 中文摘要顯示在英文摘要正下方（青綠色左邊框 `.tr-abs`）
- 已翻譯過再按切換顯示/隱藏
- 有 API 金鑰時改用 Claude 翻（醫學術語更準）
- 一鍵翻譯全部（上方大按鈕），逐篇翻、進度即時顯示

### 勾選 & 全選
- 勾選後卡片顯示青色邊框（`.res.selected`）
- 全選 / 全取消按鈕 + 「已勾選 N / M 篇」計數

### ③ AI 綜合
- 免費：產生綜合提示詞 → 複製貼給 AI
- 付費：直接呼叫 Claude，結果顯示在頁面，有複製按鈕
- 帶去評讀：寫入 localStorage，評讀工具（evidence.html）開啟自動帶入

### 換裝置接力
- 「📲 換手機／電腦接力」：複製進度 JSON（不含金鑰） → 貼到另一台 → 接力

### 付費 API（選用）
- 金鑰存 `localStorage.ebn_api-key`，與評讀工具共用
- 支援 Sonnet / Haiku / Opus
- 計費顯示（NT$）

### 互動導覽（6步）
1. 中文描述 + 🎤 語音說明
2. 搜尋框操作
3. 一鍵試範例
4. 精準化面板（lazy：搜尋後才顯示）
5. 一鍵翻譯全部（lazy）
6. AI 綜合（lazy）

### PWA 功能
- 可加到主畫面變 App
- 離線可開（Service Worker 快取外殼）
- 更新自動偵測（比對 ebn-ver.txt vs BUILD）

## 其他頁面（同 repo）

| 檔案 | 功能 |
|---|---|
| `evidence.html` | 文獻評讀工具（CASP 檢核表） |
| `lawyer.html` | AI 律師（勞動法） |
| `finance.html` | 工會財務 |
| `roster.html` | 排班 |
| `meeting.html` | 會議記錄 |
| `plan.html` | 計畫書 |
| `gongwen.html` | 公文 |
| `jianshi.html` | 監事 |
| `activity.html` | 活動 |

---

## 透析印藥水 LINE 小幫手

### 系統架構

| 元件 | 位置 |
|---|---|
| GAS 後端程式碼（備份） | `/home/user/union-guide/藥水小幫手_完整版.gs`（branch: `claude/line-webhook-permission-wc9dwc`） |
| Streamlit 排班 App | repo: `wgz5138/union-guide`，branch: `claude/dialysate-scheduling-rl20mk`，路徑: `透析排班/webapp/app.py` |
| Google Sheet | `https://docs.google.com/spreadsheets/d/1UF-DjDcrIPDbp016vkIyV9zsLF6Qz5EBo6Bq-z6t-Js` |
| GAS Web App URL（現役）| `https://script.google.com/macros/s/AKfycbxU0UM3gRmt_I69tWY3whwypJso1O7nhh44igdua3G_Lbi_WQ_hwGNBqkTERim5U3HR/exec` |
| LINE Bot | 印藥水小幫手(new)，在 LINE Developers Console → Provider → wgz5138 |

### GAS 程式（藥水小幫手_完整版.gs）

- **版本**：v2.3
- **觸發**：`sendReminders` 每天早上 7 點（時間觸發器，GAS 觸發條件手動設定）
- **Webhook**：`doPost` 接收 LINE 事件，只記錄 userId 到試算表「userid」分頁，不自動回覆
- **LINE_TOKEN**：在 GAS 程式碼第 19 行
- **WRITE_SECRET**：`yaoshui2026`
- **SS_ID**：`1UF-DjDcrIPDbp016vkIyV9zsLF6Qz5EBo6Bq-z6t-Js`

### GAS 部署重要說明

- 執行身分：**我（wgz5138@gmail.com）**
- 誰可以存取：**所有人**（不是「所有 Google 帳戶的使用者」）
- LINE Verify 永遠顯示 302 是 GAS 先天限制，**不影響實際運作**，忽略即可
- 實際運作驗證：到 GAS「執行記錄」看有無 doPost 紀錄；到 Sheet「userid」分頁看有無新資料

### Streamlit 排班 App（透析藥水排班 v3.11）

- **功能**：上傳/抓取雲端班表 → 排印藥水名單 → 定案送雲端 → LINE 自動提醒
- **修改方式**：直接編輯 repo `wgz5138/union-guide` 的 `claude/dialysate-scheduling-rl20mk` branch，push 後 Streamlit 自動重新部署
- **git 操作**：用 `git worktree add /tmp/xxx origin/claude/dialysate-scheduling-rl20mk` 建立工作區再修改
- **班表來源**：Gmail 標籤「班表」→ 新信件要先在 Gmail 手動加上「班表」標籤才能被抓到
- **跨區借人標記**：🔺 顯示在表格名字後面，定案時自動去除

### 每月 LINE 發送量估算

- 每日提醒（今天+明天各1則）× 2人/天 × ~26天/月 ≈ **100 則**
- 稽核通知（每月一次）≈ **5-10 則**
- **合計約 105-110 則/月**，免費方案上限 200 則，安全 ✓
- 五個禮拜的月份約 120 則，仍在上限內 ✓

### 常見問題

**Q：Gmail 班表抓到舊的**
A：新信件要在 Gmail 手動加「班表」標籤，再按「抓取雲端最新班表」。建議設篩選器自動貼標（寄件人 wcjung 或主旨含班表）。

**Q：週次預設選到錯的週**
A：已修正，使用台灣時區（UTC+8）判斷最近週次，不受 Streamlit 伺服器 UTC 時差影響。

**Q：LINE Verify 顯示 302**
A：GAS 先天限制，忽略。確認 doPost 執行記錄有出現即代表正常。

## 使用者偏好與背景

- 職業：醫療/護理相關，會使用臨床文獻工具
- 裝置：主要用 Chrome，多台電腦輪流使用
- 操作習慣：偏好「一鍵完成」，不喜歡切換視窗或多步驟操作
- 語言：繁體中文介面
- 不喜歡：需要右鍵操作、跳出新視窗、切換分頁、API 爆額度

## 常見問題與解法

**Q：使用者看到舊版 / 「立即更新」沒反應**
A：`ebn-common.js` 的 `initVersionCheck` 裡「立即更新」按鈕已改為先清 cache + unregister SW 再 reload。若還是卡，請使用者 Ctrl+Shift+R 強制刷新。

**Q：翻譯失敗**
A：`translate.googleapis.com` 有時被防火牆擋。可改用 Claude API（有金鑰時自動切換）。

**Q：搜尋被擋**
A：Europe PMC API 有時在特定網路環境被擋，fallback 會自動顯示 PubMed/Europe PMC/Cochrane 連結。

**Q：新增功能後使用者看不到**
A：一定要同時更新 BUILD、sw.js CACHE 版本號、ebn-ver.txt，三個要一致。
