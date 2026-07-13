# CLAUDE.md — union-guide 全專案地圖

> 這份文件是給下一個 Claude session 讀的。讀完就知道整個專案狀況，不需要重問使用者。

---

> 🔴 **鐵律：任何 session 新增或改動任何功能，必須同步更新本檔對應段落。不更新 = 下一個 session 沒上下文，等於白做。**

---

## 專案基本資訊

- **GitHub Pages 網址**：https://wgz5138.github.io/union-guide/
- **GitHub Repo**：wgz5138/union-guide（公開 repo）
- **主要開發分支**：直接推 `main`（GitHub Pages 從 main 部署）
- **整體架構**：純前端 HTML，無後端。所有資料存 localStorage / sessionStorage / IndexedDB（各工具說明）。

---

## 版本管理機制（EBN 工具群共用）

`evidence.html`、`search.html`、`lawyer.html` 三支有版本偵測。每次修改必須同時更新以下四個地方，否則使用者看不到新版：

1. **改到的那支 html** 裡的 `const BUILD="YYYYMMDDNN"`（NN 是當天第幾版，從 01 開始）
2. `sw.js` 裡的 `const CACHE = "ebn-YYYYMMDDNN"`（與 BUILD 一致）
3. `ver.txt` 的內容（與 BUILD 一致）
4. `ebn-ver.txt` 的內容（與 BUILD 一致，`echo -n "2026XXXXNN" > ebn-ver.txt`）
5. 該 html 的 `CHANGELOG` 陣列加一行說明

更新後橫幅「有新版本了！」才會出現，使用者按「立即更新」會強制清除所有 Service Worker 快取並重載。

工會工具群（finance/roster/meeting/…）沒有 BUILD 機制，改完直接推即生效。

---

## 基礎設施

### ebn-common.js（共用函式庫）

`evidence.html`、`search.html`、`lawyer.html` 共用，`<script src="ebn-common.js">` 在各頁自己的 `<script>` 之前。

包含：
- `toast(msg)` — 底部提示
- `copy(text, ok)` / `copyEl(id, ok)` — 複製到剪貼簿（含 in-app webview 降級）
- `cyrb53(s)` — 密碼雜湊（純數學，無外部依賴）
- `verLabel()` / `checkUpdate(manual, verFile)` / `initVersionCheck(verFile)` — 版本檢查與更新橫幅
- `PRICE` / `ntd()` / `apiHeaders()` / `apiErr()` — Claude API 工具
- Service Worker 自動註冊（`sw.js`）

**重要**：`ebn-common.js` 被 sw.js 設為「不攔截，永遠走網路」，避免快取卡住。

### sw.js（Service Worker）

- HTML 走「網路優先」
- `ver.txt`、`ebn-ver.txt`、`ebn-common.js`、`laws.json` 完全不攔截（永遠拿最新）
- 每次更新 CACHE 版本號可清除舊快取
- 「立即更新」按鈕會先 `caches.keys()` 全刪、再 `serviceWorker.getRegistrations()` 全 unregister、再 `location.replace()`

### laws.json（法規庫）

- 由 `.github/workflows/update-laws.yml`（GitHub Action）從全國法規資料庫官方 API 每週自動抓取並 commit
- 腳本：`tools/update-laws.py`
- sw.js 不攔截此檔，永遠走網路
- `lawyer.html` 開頁時以 12 小時節流策略決定是否重抓（見 lawyer.html 說明）

---

## EBN 工具一：臨床快查（search.html）

**網址**：https://wgz5138.github.io/union-guide/search.html
**主要檔案**：`search.html`、`ebn-common.js`、`sw.js`、`ver.txt`、`ebn-ver.txt`
**版本機制**：有 BUILD（在 `initVersionCheck("ver.txt")` 偵測下運作）
**狀態**：完整上線

### 密碼保護
- 預設密碼：`qqq11111111`（3個q＋8個1）
- 雜湊存在 localStorage，原始碼看不到真密碼
- `ACCESS_VERSION` 加 1 可踢出所有人重設

### 互連
- 搜尋結果「帶去評讀」→ 寫入 localStorage（`ebn_f-title/f-author/f-journal/f-text`）→ 跳轉 `evidence.html`
- API 金鑰共用（`ebn_api-key`/`ebn_api-model`），與 evidence.html / lawyer.html 共用同一個

### 功能清單
① **中文描述 → 關鍵字**：語音輸入（Web Speech API `lang="zh-TW"`）/ 免費複製貼 / 付費直接呼叫 Claude

② **搜尋（Europe PMC API）**：`https://www.ebi.ac.uk/europepmc/webservices/rest/search`
- 自動清除 PubMed 欄位標籤 `[tiab]`、URL 編碼、`QUERY1:` 前綴
- 篩選：研究類型（SR/RCT）、年份（近5/10年）、只看 Cochrane
- 0 筆時自動放寬（先拿掉篩選，再砍最後一個 AND 條件）
- 搜尋失敗時顯示 fallback（PubMed / Europe PMC / Cochrane 連結）

**精準化面板**（結果 ≥50 篇自動出現）：PICO 快速 chips，一鍵重搜

**搜尋結果卡片**：標題+摘要+badge（Cochrane / SR/Meta / RCT / 免費全文）
操作列：出版社全文、PubMed、Google 學術、複製連結、帶去評讀、🌐 翻譯中文

**🌐 翻譯中文（內嵌）**：
- 引擎：`translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=zh-TW`
- 有 API 金鑰時改用 Claude 翻（醫學術語更準）
- 一鍵翻譯全部，逐篇進度顯示

③ **AI 綜合**：免費複製提示詞 / 付費直接呼叫 Claude

**換裝置接力**：複製進度 JSON（不含金鑰）→ 另一台貼上接力
**付費 API**：金鑰存 `localStorage.ebn_api-key`，計費顯示 NT$
**互動導覽（6步）**：說明免費/付費路、範例搜尋、精準化、翻譯、AI 綜合
**PWA**：加到主畫面、離線可開、Service Worker 快取外殼

---

## EBN 工具二：文獻評讀（evidence.html）

**網址**：https://wgz5138.github.io/union-guide/evidence.html
**主要檔案**：`evidence.html`、`evidence-data.js`（CASP 題庫）、`evidence-engine.js`（評讀邏輯）、`ebn-common.js`
**版本機制**：有 BUILD（在 `initVersionCheck("ver.txt")` 偵測下運作）
**狀態**：完整上線

### 密碼保護
- 進場密碼：`ebn2026`（雜湊存 localStorage）
- 改密碼需先輸管理密碼 `qqq11111111`（= search.html 密碼），防止拿到進場密碼的人亂改
- `ACCESS_VERSION` 加 1 可踢出所有人重設

### 核心功能
- CASP 2024 檢核表（RCT 11 題、SR/Meta 10 題）
- 研究類型：RCT / SR/Meta / 🤖 AI 判斷（UNK）
- 答案必為「是/否/無法判斷」＋理由＋原文引用（quote）
- **⚠ 待查自我標記**：AI 沒把握的論點標 `.vflag`
- **判斷題/適用題（apply:true）**：AI 給是非答案 + 提醒對照臨床情況
- **成本效益題（costben:true）**：攤開算帳（效果/傷害/金錢），前提成立才下結論
- 結果題（results:true）：逐項列數據（OR/RR/HR/MD、CI、p、I²）

### 匯出
- PDF（@media print 白底黑字低調版）
- PPTX（PptxGenJS，深色版型，備忘稿含演講稿）
- Word（HTML-as-.doc，可編輯）
- 預覽（modal，白底「像 PDF」）

### 組員模式 / 主講者模式
- 組員：選分到的題 → 產提示詞 → 「匯出我的部分」（純文字）
- 主講者：匯入多位組員 → 與正確版比對 → 標紅不一致 → 產報告＋演講稿

### 互連
- 接收 search.html「帶去評讀」寫入的 localStorage 四個欄位
- API 金鑰共用 `ebn_api-key`
- 推薦「對照官網看有沒有新版 CASP」連結＋「複製更新指令給 AI」

---

## EBN 工具三：AI 律師（lawyer.html）

**網址**：https://wgz5138.github.io/union-guide/lawyer.html
**主要檔案**：`lawyer.html`、`ebn-common.js`、`laws.json`、`lawyer.webmanifest`、`icon-lawyer.png`
**版本機制**：有 BUILD（在 `initVersionCheck("ver.txt")` 偵測下運作）
**狀態**：完整上線

### 密碼保護
- 進場密碼：`qqq11111111`（與臨床快查 search.html 統一，`PW_HASH="2716985802763051"`）
- `ACCESS_VERSION="3"`（升版會踢出所有舊 session）
- 使用者可在右上角自行改密碼（不需管理碼）

### 法規庫設計
- 內建 `LAW_SEED`（快照，標 `seed:true`，顯示「📌 快照」徽章）
- 開頁自動 fetch `laws.json`（官方版，GitHub Action 每週更新）
  - **12小時節流**：本機快取（`LAW_CACHE_KEY` in localStorage）存在且距上次成功抓取 < 12 小時，不重抓
  - 時間戳：`law_fetch_ts` in localStorage
  - 節流只作用在靜默背景刷新；「🔄 重新抓官方法規」按鈕可隨時強制重抓
- 使用者可從 AI 更新指令匯入自訂法條（`law_db` in localStorage），優先於官方版

### 核心功能
- **多輪對話**（`CHAT[]`、`askLawyer()`）：帶 system + history 呼叫 Claude
- **引經據典**：系統提示詞注入當前相關法條原文（`lawContext()`），只引用已知條文
- **判斷對方說法**：逐點分析、給反駁語句
- **羅列證據**（`parseEvidence()`）：打勾清單，三組（核心/加分/程序），localStorage 記憶進度
- **🔎 查相關判決**：AI 建議關鍵字 → 一鍵到司法院裁判書系統
- **⚠ 待查護欄**：引用法規庫外條號必須標 `⚠ 待查`
- **範例**：加班費補發爭議（`🧪` 帶入）
- **📖 記憶訓練**（第 6 區）：40 張法條情境卡（含醫療法§99/§83 醫療糾紛調解、刑法§309/§304/§305 職場霸凌刑告），每張含白話說明、典型情境、記憶口訣；🔊 單張朗讀（Google TTS 真實音訊，iOS 鎖屏繼續）；📻 連續播放（Radio 模式）；🔎 查判決（直連司法院）；法律領域**不含智財**（智財法條仍在法規庫可手動查）

### 互連
- API 金鑰共用 `ebn_api-key`
- 換裝置接力（帶案件設定＋對話＋證據，不含金鑰）
- 🗑 一鍵清除換下一案

### 法規庫 localStorage 配額說明
- `LAW_CACHE_KEY` 約佔 github.io/union-guide 的 localStorage 配額 ~16%（~5MB 共用）
- 已選擇方案(a)：保留 localStorage 快取 + 12 小時節流（最省事，16% 換「開頁即時＋少下載」）
- 若日後配額吃緊，可改(b)：SW Cache API 快取 laws.json（配額獨立）

---

## 工會工具群

工會工具採「溫暖風格」（綠色/金色/襯線字）與 EBN 工具的冷感科技風相反。
密碼模型：統一使用 `PW_HASH="1621267407177439"`（= cyrb53("gaorong2026")）、`UNLOCK_KEY="union_panel_unlocked"`。部分工具設 `const LOCK=false`（目前解鎖狀態）。
版本機制：無 BUILD，改完 push 即生效。

### union.html — 幹部功能表（導覽樞紐）

**功能**：工會幹部的主頁，列出所有工具的入口連結。
**密碼**：有（`LOCK=false` 目前關閉），通行碼 `gaorong2026`
**狀態**：完整上線

### finance.html — 工會透明帳本

**功能**：工會財務記帳，依工會財務處理準則（工會法 §30）設計。每項功能標明條號。
**主要檔案**：`finance.html`、`finance-law.js`（財務法規說明）、`finance.webmanifest`
**資料儲存**：localStorage（只存本機，不上傳）
**連結**：幹部買東西 → 用 `receipt.html` 拍照 → 「匯出給帳本」→ 傳給帳房，在 finance.html 記錄
**風格**：綠色系（#1A7A4A），Noto Serif TC
**密碼**：有，通行碼 `gaorong2026`
**狀態**：完整上線

### receipt.html — 單據快拍

**功能**：幹部用手機拍收據/發票（原始憑證），存電子底稿，可「匯出給帳本」傳財務幹部。
**主要檔案**：`receipt.html`、`receipt.webmanifest`
**資料儲存**：IndexedDB（照片）；資料只在本機手機，不上傳
**法源**：工會財務處理準則 §9、§10、§27（保存 5 年）
**互連**：「匯出給帳本」→ 傳給 finance.html
**密碼**：無（使用 LINE 傳送機制本身已有存取控制）
**狀態**：完整上線

### roster.html — 會員名冊

**功能**：工會會員名冊管理、入會申請審查、會費狀態管理。
**主要檔案**：`roster.html`、`roster.webmanifest`
**資料儲存**：localStorage
**密碼**：有（LOCK=false 目前關閉），通行碼 `gaorong2026`
**狀態**：完整上線

### meeting.html — 會議文件

**功能**：工會會議記錄，含出席人數與法定人數檢查，產出正式會議紀錄格式。
**主要檔案**：`meeting.html`、`meeting.webmanifest`
**資料儲存**：localStorage
**密碼**：有（LOCK=false 目前關閉），通行碼 `gaorong2026`
**狀態**：完整上線

### jianshi.html — 監事秘書

**功能**：監事會 AI 秘書，含年度監察行事曆、監察意見書範本、稽核查核表。
**主要檔案**：`jianshi.html`、`jianshi.webmanifest`
**密碼**：有，`PW_HASH="1621267407177439"`（通行碼 `gaorong2026`），`LOCK=true`（目前鎖定）
**狀態**：完整上線

### plan.html — 年度計畫與預算

**功能**：工會年度工作計畫與經費收支預算表，供會員大會審議。
**主要檔案**：`plan.html`、`plan.webmanifest`
**密碼**：有（LOCK=false 目前關閉），通行碼 `gaorong2026`
**狀態**：完整上線

### gongwen.html — 對外公文／函稿

**功能**：產生工會對外公文、函稿格式。
**主要檔案**：`gongwen.html`、`gongwen.webmanifest`
**密碼**：有（LOCK=false 目前關閉），通行碼 `gaorong2026`
**狀態**：完整上線

### activity.html — 活動報名

**功能**：工會福利活動與教育訓練報名統計、繳費與簽到管理。
**主要檔案**：`activity.html`、`activity.webmanifest`
**密碼**：有（LOCK=false 目前關閉），通行碼 `gaorong2026`
**狀態**：完整上線

---

## 其他獨立頁面

### index.html — 加班費申請說明

**功能**：靜態說明頁，介紹高雄榮總護理工會加班費補發申請流程與法律依據（§38 等）。
**密碼**：無（公開頁面）
**狀態**：靜態已上線，內容可能需定期更新

### gaorong.html — 高榮企業工會主頁

**功能**：工會對外公開主頁（籌備中），有低調模式（`LOW_PROFILE` 開關控制是否顯示密碼頁）。
**密碼**：有 `LOW_PROFILE` 模式，預設視情況開啟
**狀態**：籌備中

### share.html — 掃碼分享看板

**功能**：顯示所有工具的 QR Code（供投影/列印貼桌上）。含 evidence/search/lawyer 三工具＋回饋問卷。
**主要檔案**：`share.html`（使用 qrcodejs CDN 前端生成 QR）
**密碼**：無
**狀態**：完整上線

### lottery.html — 威力彩包牌選號產生器

**功能**：威力彩選號工具，明確說明「歷史冷熱號無法預測中獎機率」，誠實揭露娛樂性質。
**主要檔案**：`lottery.html`、`lottery-freq.json`（開獎頻率資料）
**資料**：`lottery-freq.json` 是靜態資料檔，需定期更新
**密碼**：無
**狀態**：完整上線
**相關子專案**：`taiwan-superlotto-analysis/`（統計分析，見該 README）

### id-mark.html — 證件影本加註記 A4 整理列印

**功能**：幫照片型證件影本加上「僅供 XX 用途」等浮水印/加註記，整理成 A4 格式列印。
**密碼**：無
**狀態**：完整上線

### privacy.html — 個人資料保護政策

**功能**：工會隱私政策靜態頁面。
**密碼**：無
**狀態**：靜態已上線

### demo-*.html / style-demo.html

**功能**：風格樣板頁（深色/淺色/企業風/科技風），供選色用，已完成任務。
**密碼**：無
**狀態**：可保留參考，不再主動維護

---

## 子專案（各有獨立 README）

### freelance-flights-mvp/

**功能**：機票價格監測工具，降價即推送 Telegram 通知，支援雲端自動跑。
**詳情**：見 `freelance-flights-mvp/README.md`
**狀態**：獨立子專案

### taiwan-superlotto-analysis/

**功能**：從台彩官方 API 爬取威力彩歷史開獎號碼，做統計分析，誠實說明中獎機率。
**詳情**：見 `taiwan-superlotto-analysis/README.md`
**狀態**：獨立子專案

### tools/

**功能**：Claude Code 個人工具（cccswitch 多帳號切換、statusline 設定）。
**詳情**：見 `tools/README.md`
**狀態**：個人工具

---

## 使用者偏好與背景

- 職業：醫療/護理相關（高雄榮總護理師），同時是工會幹部
- 裝置：主要用 Chrome，多台電腦輪流使用，也有手機
- 操作習慣：偏好「一鍵完成」，不喜歡切換視窗或多步驟操作
- 語言：繁體中文介面
- 不喜歡：需要右鍵操作、跳出新視窗、切換分頁、API 爆額度
- **設計理念**：EBN 工具是「冷感科技風」（深色、青藍、JetBrains Mono）；工會工具是「溫暖風格」（綠金、襯線字）——刻意區隔，讓人看不出是同一人做的

---

## 常見問題與解法

**Q：使用者看到舊版 / 「立即更新」沒反應**
A：`ebn-common.js` 的 `initVersionCheck` 裡「立即更新」按鈕已改為先清 cache + unregister SW 再 reload。若還是卡，請使用者 Ctrl+Shift+R 強制刷新。

**Q：翻譯失敗（search.html）**
A：`translate.googleapis.com` 有時被防火牆擋。可改用 Claude API（有金鑰時自動切換）。

**Q：搜尋被擋（search.html）**
A：Europe PMC API 有時在特定網路環境被擋，fallback 會自動顯示 PubMed/Europe PMC/Cochrane 連結。

**Q：lawyer.html 開頁法條是快照不是官方版**
A：laws.json 由 GitHub Action 每週自動抓取。Action 60 天無提交會停用（repo 閒置問題）。到 GitHub Actions 手動 Run workflow 一次即可恢復。

**Q：新增功能後使用者看不到**
A：EBN 工具一定要同時更新 BUILD、sw.js CACHE、ver.txt、ebn-ver.txt，四個要一致。工會工具沒有 BUILD，直接 push 即生效。

**Q：localStorage 快取與配額**
A：lawyer.html 的 laws.json 快取（`law_official_cache`）佔 ~16% 配額（github.io/union-guide 共用 ~5MB）。已加 12 小時節流避免無謂重下載。若日後配額吃緊，可改 SW Cache API 方案。

**Q：使用者「不管怎麼改都進不去」／密碼一直錯**
A：兩個獨立成因，2026071306 版都已處理：
1. **本機壞密碼永久卡死（已修）**：`evidence.html`／`search.html`／`lawyer.html` 的 `pwOk()` 原本只認「本機 localStorage 存的自訂密碼 `||` 預設 `PW_HASH`」，一旦本機曾經（含誤觸）用「🔑 改密碼」存過任何自訂密碼，預設密碼就永久失效、無從復原。已改成 `cyrb53(輸入)===PW_HASH || ===本機自訂密碼`——**文件公告的預設密碼永遠有效**（當備援鑰匙），不會再被本機殘留設定卡死。
2. **裝置卡在舊版畫面（多為此因）**：使用者截圖顯示的登入框（欄位窄到打不下密碼、眼睛圖示飄在框外、密碼提示文字）其實是**已經修掉的舊版 UI**，代表該裝置的瀏覽器/PWA 還在吃舊快取，不是密碼邏輯壞掉。判斷方法：叫使用者用**無痕視窗**開同一網址，若畫面正常就是快取問題。解法：無痕視窗可直接用；一般視窗要請使用者手動清該網站的瀏覽器資料（iOS Safari：設定→Safari→進階→網站資料→找 wgz5138.github.io 刪除；Android Chrome：網址列旁 ⓘ →網站設定→清除儲存空間），或刪除加到主畫面的舊 PWA 圖示重新加。已同步加固 `sw.js` 的 HTML fetch 為 `{cache:"no-store"}`，避免瀏覽器 HTTP 快取蓋掉「網路優先」策略，降低未來再發生機率，但**既有的陳舊快取仍須使用者手動清一次**才會生效。
