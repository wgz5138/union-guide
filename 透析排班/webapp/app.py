# -*- coding: utf-8 -*-
"""透析藥水排班 — 手機網頁版（Streamlit）v3.26
  • v3.53（2026-08-10，v3.52同一天往下查出的兩個連帶問題，使用者要求「不是只查漏洞，
    是要確保玉繡每個月稽核不會出狀況」而主動深挖）：
    ①`extract_notes()` 只排除「【公平累計】」標題那一行，底下逐人明細（例如「林欣儀
    稽11 休 2 本月:休息（夜/一區）」）因為含「休息」二字被誤判成注意事項警告，混進
    畫面「⚠️ 注意事項」清單——這些明細本來就是排出來當下的舊資料，跟旁邊v3.52新增的
    「以這行為準」休息名單同時出現在畫面上，看起來像系統自相矛盾。改成跟
    `extract_fairness()` 一樣用「整個區塊」判斷去跳過，不是只跳過標題那一行。
    ②比①更嚴重：稽核 Stage 2「其他檔案下載」的 Excel（貼護理站公告欄用）、文字檔
    （傳LINE群組用），發的是 稽核.py 子行程當初的原始輸出，**跟玉繡點格子的修改完全
    脫鉤**——如果她改過名字之後去下載這裡的檔案去公告或傳群組，公告欄/群組看到的名單
    會跟系統實際記錄、LINE個別通知的內容兜不起來，這不只是畫面文字沒更新，是真的會把
    錯誤名單傳達出去。改成用玉繡編輯後的 `edited_ak` 現場重建這兩個檔案內容（.csv那顆
    「上傳雲端歷史用」本來就有走 `build_corrected_audit_history()` 修正，維持原樣，
    只補上標籤說明它本身仍是原始版本，不影響雲端同步的正確性）。
    用真實 `ast` 抽出的函式驗證：模擬玉繡把「王乃君」改成「林欣儀」，重建的 txt／xlsx
    （xlsx有做 round-trip 讀回驗證）都正確反映修改；並用「舊版本」（不套用修改的
    DataFrame）當對照組，證實這個問題是真實存在、不是無中生有。extract_notes 也補了
    v3.51「檔案週次不符」與 排班.py 公平累計格式的 regression 測試，確認沒有把真正
    該顯示的警告一起濾掉。
  • v3.52（2026-08-10，玉繡實際回報）：稽核 Stage 2「稽核 AK 名單」畫面點格子把某人
    改成另一個人（例如機器人原排「王乃君」稽核二區/週二四六/第三班，玉繡改成
    「林欣儀」）後，「⚠️ 注意事項」裡的「本月休息」那行沒有跟著更新——因為那行是
    `稽核.py` 產生 `out` 當下（點格子**之前**）印的靜態字串，`extract_notes()` 原封不動
    撿出來顯示，玉繡點格子只改了 `edited_ak`（畫面上的表格），跟這行文字之間完全沒有
    連動。跟印藥水那邊「定案後顯示實際休息人員（依玉繡最終調整，非演算法原始結果）」
    是同一類問題，印藥水那邊早就修過，稽核這邊當初漏掉。
    修法：新增一個依 `edited_ak` 現況即時重算的「😴 本月休息」info框，姓名清洗沿用跟
    `build_corrected_audit_history()`/`send_audit_notices()` 同一條 regex（含全形括號），
    不重寫第三種清洗規則。用模擬的12格稽核名單驗證：改「王乃君→林欣儀」後，新算出的
    休息名單正確把王乃君加回去、林欣儀移出去，舊的靜態字串則確認不會跟著變（對照組），
    另外驗證「(跨區)」括號清洗、格子清空兩種邊界情況都正確。
  • v3.51（2026-08-10真實事件）：0810~0816這週，排班組給的班表檔案「115.08.10~
    115.08.16.xls」，檔名寫這週，但表頭日期實際是兩週前的「2026/07/27~2026/08/02」。
    這種「整份檔案的日期都完整合法可解析、只是根本是別週的」情況，過去完全沒有任何
    自動檢查——排班.py/稽核.py 既有的四層日期備援（v3.45~47）只在表格內容本身壞掉
    （文字/民國年/整排讀不到）時才會被觸發，這次表格內容本身是好的，四層備援完全不會
    介入，全靠玉繡肉眼比對格子內容才發現，屬於僥倖，不是系統設計上真的有防到。
    修法：parse_sheet() 新增第五輪，不管前面哪一層解出日期，只要能解出真實日期、且
    檔名/分頁名也能推出參考週次（既有的 week_hint()），就比對兩者，差距超過3天就在
    「注意事項」跳出醒目警告（⚠🚨 檔案週次不符）。app.py 端另外加硬性攔阻：偵測到這
    則警告時，「✅ 產生定案」／「🚀 送稽核結果到雲端」按鈕會被停用，要勾選「已跟排班組
    核對過」才能繼續，不是只被動顯示警告字（v3.48/v3.49 的教訓——警告訊息容易被忙起來
    的人掃過去，這次改成真的擋住操作）。排班.py／稽核.py 兩邊同步修（同一顆蟲兩份程式碼）。
  • Fix1：公平歷史學玉繡實際決定，而非程式原排
  • Fix2：稽核送出後 LINE 通知每位稽核者責任班次
  • Fix3：自動選最接近今天的班表分頁
  • v3.26：排班 Round3 跨區優先於同區印第二次（病房/ICU/休假限制下盡可能不讓同區人一週兩次）
  • v3.27：本週放假但可印藥水的人可在 UI 手動指定（強制可印.csv），系統視為白班候選人
  • v3.28：強制可印雙效升級 — ①玉繡指定的人優先於公平排序（不再被成本低的人搶掉）②班表空白當天也能被納入候選（從本週其他班別推出所在區域）
  • v3.29：修正 v3.28 補漏邏輯造成印藥水日錯算（把 7/17 的人算成 7/16）；改為只靠優先排序，班表有記錄才納入候選；kind_area 調整讓特休/副值等排除班別也能被玉繡強制指定
  • v3.30：還原 kind_area() — 強制可印只做優先排序，不改資格判斷（放假/大夜/空白 → 一律不能印）
  • v3.30：還原 kind_area() — 強制可印只做優先排序，不改資格判斷（放假/大夜/空白 → 一律不能印）【v3.31 Round1 改動因造成雙印回歸，已撤銷】
  • v3.32：排班 Round1+2 改為全域最佳化配對(scipy)，取代貪心逐格搶人，解決「換處理順序就搶錯人、
    逼別人印第二次」的結構性問題；拿 3 週真實班表驗證：不劣於 v3.30、其中 1 週（本次爭議週）
    從「1人雙印」改善為「0人雙印」，且與玉繡當面確認過的規則(顏凰任 7/16 印 7/18)吻合
  • v3.33：修正「送到雲端」的靜默失敗 — 排班歷史(setScheduleHistory)同步失敗時，先前完全不會
    提示，畫面只顯示「已送到雲端」成功訊息，導致統計管理讀不到那一週卻沒人發現。現在失敗會
    跳出明確錯誤訊息並提示重試。
  • v3.34：v3.33 上線後重送仍不跳錯誤、統計卻還是沒更新 — 因為 GAS 端 setScheduleHistory_()
    不管收到幾筆都一律回 {ok:true}，即使實際送出 0 筆也算「成功」。push_history() 改回傳
    (ok, 實際筆數, 失敗原因)，成功也會顯示送了幾筆，這樣才看得出「回報成功但其實0筆」這種狀況。
  • v3.35：找到 7月資料消失的真正原因 — 不是同步失敗，是「統計管理→印藥水統計」分頁可以
    直接改印次/休次數字、按「存回雲端」，這個功能會呼叫 setAllScheduleHistory（GAS端整份
    clearContents 再重建），把全部人的每週真實明細換成「統計-印01」這種沒有日期的假列，
    26週374筆真實歷史因此消失，只剩總數字。已加防呆：這顆按鈕現在要先勾選「我知道會清空
    每週明細」才能按，並在上方加醒目警告說明用途，避免下次又不小心整份洗掉。
  • v3.36：v3.35上線後第一次真的送出，跳出新錯誤「Out of range float values are not JSON
    compliant: nan」— build_corrected_history()/push_history() 讀 CSV 時沒指定 dtype=str，
    pandas 把「休」狀態那些空白的治療日欄位讀成 float NaN，requests 送 JSON 時嚴格檢查
    NaN 不合法直接拋例外。改成 pd.read_csv(..., dtype=str, keep_default_na=False)，空白
    保留為空字串，不再被轉成 NaN。已用實際資料重現問題、驗證修法有效才上線。
  • v3.38：修掉「統計管理→同步本機CSV→雲端」這顆按鈕的洗資料地雷——2026-07-20凌晨實際
    發生：本機備份CSV還停在舊週次，按下去把雲端剛送出、比CSV新的一週資料整批蓋掉了。
    原本 sync_schedule_history_from_csv()/sync_audit_history_from_csv() 是「本機整批覆蓋
    雲端」；改成「先讀雲端現況，只把本機有、雲端沒有的週次/月份補上去，雲端既有資料原封
    不動」——不是加警告字樣，是讓這顆按鈕在設計上就不可能再覆蓋掉雲端較新的資料。
  • v3.38：同一版加首頁顯眼統計（雲端排班歷史累積筆數／最新一週，大字體 st.metric），
    每次打開網頁都看得到，平常掃一眼就能發現「數字很久沒變/忽然變小」這種異常，不用等
    查統計才發現（這次事件玉繡是三週後才發現）；並主動比對本機git備份CSV是否落後於雲端，
    落後就直接顯示警告，不用等有人誤按同步按鈕才知道備份是舊的。
  • v3.39：修正「傳LINE群組用」文字（_build_line_txt）原本依「治療日」分組輸出，導致不同
    治療日往前推剛好同一天印藥水時（例如白班7/21治療日、小夜7/22治療日，往前推都是
    7/20），會各自變成一行、同一天看起來印了兩批人共四人，容易被誤會排錯（2026-07-19、
    07-20兩週都有人反映看不懂）。改成依「印藥水日」分組合併輸出，同一天的人（不論來自
    哪個治療日）合併成一行，各區用「、」串接多人。
  • v3.40：全面盤點後發現「組員名單」分頁的「📤 從本機CSV同步到雲端」跟排班/稽核歷史
    是同一類地雷——本機 組員名單.csv 落後時按下去一樣整批覆蓋雲端。但組員名單跟排班/
    稽核歷史不同：真的會有人被移除（離職/退組），不能沿用v3.38「只補missing」的合併
    邏輯（會把雲端正確移除的人誤救回來）。改成更嚴格：只有雲端目前是空的（真正的初始化）
    才允許這顆按鈕動作，雲端已有名單一律拒絕並提示改用下方表格編輯＋存回雲端。
  • v3.41：派獨立agent全面稽查出17個bug（5高7中5低），逐一實測資料驗證後修復13個
    （app.py + 排班.py + 稽核.py）：
    【高】LINE群組公告日期每週錯2-3人 — 每欄只取第一區的印藥水日當整欄日期，改成每
    格各自帶自己的印藥水日（實測4週48人次：修正前錯9次→修正後0次）
    【高】雙印時姓名被污染成「XXX雙印」送上雲端，導致收不到提醒/公平歷史算錯/公告
    同時列印與休 — 產生定案 + _build_line_txt 都補上濾除
    【高】稽核統計「存回雲端」沒有防呆，補上跟排班統計一樣的警告勾選框
    【高】稽核第二班白/夜門檻算錯（allow_night_band2 拿 n_night 當基準）— 改成用
    「總白班格數」判斷，實測7月真實資料從1格排不出→0格
    【高】稽核 W135/W246 組別限制形同虛設（cands() 漏帶 g 參數）— 補上 group_ok() 檢查
    ＋排不出時自動放寬並跳警告
    【中】稽核月份key用西元(2026-07)、稽核紀錄.csv卻是民國(115-07)，skip_month永遠對
    不上、公平分數悄悄算錯 — 統一改民國，app.py/稽核.py兩邊都修，連帶修正
    fetch_last_audit_prefill() 抓「上次稽核月」的排序bug
    【中】稽核「第一週」判斷邏輯選錯月份 — 改成看該週落在目標月的天數最多者
    【中】強制可印只認得完整全名，玉繡輸入簡稱查無此人時完全靜默失效 — 改成後綴比對
    ＋比對不到時明確跳警告列出哪幾筆沒生效
    【中】雲端草稿UTC時間字串截前10碼取到錯誤日期（3處同樣手寫 _clean_dt，跨日/跨年
    都會錯）— 統一改共用 gs_date_to_ymd()，已測5組含跨年案例
    【中】排班/稽核歷史讀取失敗時靜默改用本機舊備份算分數，畫面完全無提示 — 3處呼叫
    點補上明確錯誤/警告訊息
    【中】稽核人工改派沒同步回歷史紀錄，下次公平分數對不上玉繡實際決定 — 新增
    build_corrected_audit_history()，仿照排班歷史既有做法
    【中】「產生定案」整週共用同一個猜測年份，跨年那週（如12月最後一週+1月第一週）
    後半段月份年份一定算錯 — 改成從當次產生的雲端貼上CSV建「每格自己的年份」對照表
    （(區,月,日)→年），逐格查表不再整週共用；4週真實資料驗證0筆查表失敗，且跨年模擬
    案例確認1/1、1/2從錯誤的去年改成正確的隔年
    【低】_best_sheet_index 年份修正只做單向（假設分頁一定是未來），跨年後選到半年前
    分頁 — 改雙向修正
    【低】稽核歷史同步會把「草稿」「意見-」開頭的特殊列跟正常月份一起重複疊加 — 同步
    前先過濾掉這兩種
  • v3.42（2026-08-01）休診日單一來源（接續包第二十三節待辦#17，架構決策已由使用者拍板
    「要有同步機制、不是只加交叉檢查」）：過年/連假清單原本有兩份各自維護——
    webapp/休診日.csv（排班.py prev_treat 算「印藥水日」用）與 藥水小幫手.gs 的
    EXTRA_HOLIDAYS 陣列（prevWorkday_ 算「LINE 提醒日」用）。改一邊不會同步到另一邊，
    兩邊對不上就會讓「排出來的印藥水日」跟「LINE 通知的日期」差一天（跟 v5.8 修掉的
    off-by-one 同一類，只是兩份剛好都還是空的所以沒爆）。
    改法：試算表新增「休診日」分頁當唯一來源，.gs 的 isWorkday_ 改讀該分頁（含執行期
    快取＋日期型別正規化），app.py 新增 getHolidays/setHolidays，排班/稽核執行前把雲端
    休診日當 config_override 餵進去（雲端優先、本機 CSV 只當讀不到時的保底且會跳警告），
    並在「📊 統計管理」新增「🗓 休診日」分頁供玉繡直接編輯。
    ⚠ .gs 要手動「部署→管理部署→新版本」到 v6.1 才會生效。
  • v3.49（2026-08-06）那串提醒**根本沒有標題**：v3.48 修好「ℹ/⚠ 被濾掉」之後，使用者
    問「注意事項區在哪???」——查程式碼才發現那些訊息只是 st.write("・"+n) 直接倒在可編輯
    表格下面，沒有任何標題或說明，使用者當然認不出那是什麼、也不知道要看。補上
    「⚠️ 注意事項（產生定案前請看過）」標題與一行說明，並改成沒有訊息時整區不出現。
    印藥水與稽核兩處都補。
  • v3.48（2026-08-06）畫面「注意事項」區漏顯示一整類警告（使用者質疑「警告區會告訴你
    哪幾欄的日期是補回來??」，實測後確認 AI 前一則講錯了——那些警告根本不會顯示）：
    extract_notes() 只挑含「休息 ↳ ※ ❌ 借」的行，但 排班.py 的 warn() 有一整批是
    「ℹ」「⚠」開頭的，全部被濾掉、從來沒顯示過。被埋掉的包括：
      ⚠ 強制可印『X』在組員名單裡找不到 → v3.41 特地為了「不要靜默失效」才加的，
        結果加了等於沒加，玉繡打錯名字依然看不到任何提示（這是本次最嚴重的一個）
      ⚠ 名單有重複 / ⚠「X」卡號變了 / ⚠ 讀取設定檔失敗 / ⚠ 寫檔失敗
      ℹ 視為休診跳過 / ℹ 強制可印人員名單
      ℹ 第N欄日期格被打成純文字已補回年份（v3.46）／⚠ 依檔名推算整週日期（v3.47）
    關鍵字補上「ℹ」「⚠」。已用真的 排班.py 跑重現玉繡那張表的 Excel，把真正的 stdout
    餵給真正的 extract_notes 驗證：3 則日期補回提醒都會出現；舊版規則同一份輸出 26 則
    裡一則都沒有。
  • v3.47（2026-08-06）兩件事：
    ①【首頁補上稽核統計】使用者反映「我的藥水稽核累積筆數咧？我要的東西必須要有啊」——
      首頁只看得到印藥水的累積筆數/最新一週，稽核同樣是每月要送雲端的東西，卻沒有一眼
      可判斷「數字有沒有在增加」的地方。新增「🩺 雲端稽核歷史累積筆數」「🗓 雲端最新稽核
      月份」兩個 metric，與印藥水並列。月份排序用民國→西元換算後比較（115-12 比 2026-07
      晚，直接字串比會錯），草稿/意見-/統計- 等特殊列不計入。排班讀不到但稽核讀得到時，
      稽核仍會顯示，不會整塊消失。
    ②【班表日期完全不依賴排班組怎麼填】使用者明講「那是排班組弄的，我們藥水組管不得，
      想一個辦法繞過去」。v3.46 的修法還需要「表格裡至少有一格日期是正常的」才借得到
      年份，萬一七格全被打上備註就仍然掛掉。新增 week_hint()：從**檔名**
      （115.08.10~115.08.16.xls，民國3碼自動+1911）與**分頁名**（0810~0816，用今天挑
      最接近的年份）取得這一週的起訖日，當第三、四層備援：
        第1層 表格內完整日期 → 第2層 表格內其他日期借年份 → 第3層 檔名/分頁名借年份
        → 第4層（最後手段）整排完全讀不到時，若「檔名天數 == 類別欄數」才依序補連續
          日期，並大聲警告「請務必核對日期再送出」；天數對不上就維持失敗、絕不硬補
      優先序保證表格內容永遠贏過檔名（檔名寫錯也不會把正確資料帶偏，已測）。
      排班.py / 稽核.py 兩支都改。
  • v3.46（2026-08-06）承 v3.45：用新的診斷訊息抓到玉繡那張表的真正原因——日期格被打成
    「8月10日  缺31-33」，有人把備註打進日期格，Excel 就把整格從日期型別變成純文字，而
    「8月10日」沒有年份，舊版讀不到。7 個類別欄有 4 個是正常日期、3 個是文字，偏偏壞掉的
    是第 1 欄，而 monday 取的正是第 1 欄 → 整週排不出來。
    修法：新增 parse_date_parts()，中文「M月D日」與「M/D」也認得，但**只當半成品**；
    年份由 parse_sheet 從同一張表裡已經解析成功的日期借過來（取欄位距離最近的當參考，
    跨年 12月底↔1月初也不會挑錯年），完全沒有任何日期可參考時就照舊失敗、絕不編年份。
    補回來的欄位會在警告區列出「第N欄日期格被打成純文字，已依同表其他日期補回年份」。
    排班.py 與 稽核.py 兩支都改（日期解析原本就是同一份程式碼）。
  • v3.45（2026-08-06）班表日期讀不到：玉繡載入 115.08.10~115.08.16 的班表後按「排印藥水」
    跳「❌ 分頁「0810~0816」抓不到日期，無法決定治療日」，畫面只有這一句、查不下去。
    ①排班.py／稽核.py 的 parse_date() 只認西元（\d{4}），但醫院班表連檔名都是民國格式
    （115.08.10），表頭日期若也用民國就整週讀不到 → 補上民國年（3碼、限民國100~200）
    的解析，只有西元兩個 pattern 都比不中才會走到，不影響原本正常的檔案。
    ②「抓不到日期」改成會講清楚實際狀況：表頭在第幾列、找到幾個『類別』欄、上方那幾格
    到底讀到什麼內容，並點出最常見兩個原因（這週班表還沒填／日期格式不同）。稽核.py
    的「所有檔案都抓不到表頭或日期」同樣補上診斷。
  • v3.44（2026-08-02）修玉繡回報的「暫存失敗」（搭配 .gs v6.3）：按「✅ 產生定案」跳
    「⚠️ 雲端草稿暫存失敗（網路問題？）」、按「💾 備份草稿」跳「暫存失敗」——不是網路問題。
    push_week_draft() 送的是 6 欄（[週次]+[印日期,區,姓名,🔺,治療欄key]），但 GAS 的
    「排班草稿」分頁表頭只有 4 欄，Range.setValues() 欄數不合直接拋例外，每次都失敗。
    連帶的影響是：app.py 讀回草稿時本來就預期有第5欄（治療欄key）才能走「零碰撞」套回
    定案那條路，所以那個功能從加進來就沒真正生效過，小巫也從來看不到草稿。
    修法：.gs 表頭補成 6 欄；這裡把欄數固定補成 5 欄再前綴週次，格式再變動也不會帶歪；
    push_week_draft 改回傳 (ok, 錯誤訊息)，畫面顯示真正的原因，不再寫死「（網路問題？）」
    害人往網路方向查，並註明這只影響給小巫預覽的草稿、不影響 LINE 提醒與統計。
    ⚠️ 同一次在 .gs 挖出更嚴重的地雷並修掉：writeAllRowsFast_ 原本先 clearContents 才
    setValues，寫入一失敗分頁就停在「已清空、資料沒寫進去」＝整份消失（排班草稿就是
    這樣每次被清空的，已實際重現）。該函式同時被 setWeek/setAllScheduleHistory/
    setMembers/writeHistory_ 共用，踩在排班歷史上就是整年資料歸零。詳見 .gs v6.3。
  • v3.43（2026-08-01）搭配 .gs v6.2：GAS 的 sendAuditNotice 現在會檢查 LINE API 回應碼，
    把「真的沒送出去」的人回報在 failed/failedNames。app.py 這端接住並在畫面明確列出
    「這幾位的 LINE 通知實際發送失敗，請改用其他方式告知」——以前 LINE 回 401/403/400
    會被整個吞掉、畫面照樣顯示「已通知 N 人」，那幾個人其實根本沒收到。
    （舊版 GAS 沒有這兩個欄位，取不到就當 0/空，不會壞。）
    接續包第二十三節的 3 項待辦至此全部完成（#14/#16 在 .gs v6.2、#17 在 v3.42/v6.1）。
"""
import os, io, re, csv, json, base64, hashlib, tempfile, shutil, subprocess, sys
from datetime import date, datetime, timedelta
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import requests

HERE = os.path.dirname(os.path.abspath(__file__))

# v3.50（獨立稽查中-9）：detect_shifts_quick()（稽核 Stage1「📊 預覽班型」用）以前是
# app.py 自己另外寫的第三份日期解析器，只認西元 yyyy-mm-dd 完整日期，沒跟上 v3.45~47
# 幫 排班.py／稽核.py 加的民國年／中文「M月D日」／同表借年份／檔名分頁名四層備援。
# 拿引爆整輪連環修的那張真實班表（日期格被打成「8月10日 缺31-33」）測過：每個人
# 全部變 ❓，畫面跟著跳「這些人本月排稽核時會略過」，玉繡會以為班表壞了或工具壞了
# （資料面影響有限，因為稽核.py 自己已經修好，最後仍會排對，但這裡的預覽會誤導人、
# 讓人做白工去人工改一堆本來就對的班型）。
# 改法：不要維護第三份日期解析器，直接匯入 稽核.py 這個模組、共用它已經修好且測過
# 的 parse_sheet()（含全部 4 層備援），讀不到才真的顯示 ❓。
try:
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location("_audit_shared", os.path.join(HERE, "稽核.py"))
    _audit_shared = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_audit_shared)
except Exception:
    _audit_shared = None   # 匯入失敗時 detect_shifts_quick 會整個回空表，不會崩潰

CONFIG = ["組員名單.csv", "床號分區.csv", "不可印班別.csv", "休診日.csv",
          "排班紀錄.csv", "稽核紀錄.csv"]
CELL_RE = re.compile(r'^(.*?)\((\d+)/(\d+)印\)(.*)$')

def _detect_ext(b): return ".xlsx" if b[:4] == b'PK\x03\x04' else ".xls"


# ── 核心工具執行器 ────────────────────────────────────────
def run_tool(script, xls_bytes, extra_args, config_overrides=None):
    work = tempfile.mkdtemp()
    try:
        for fn in CONFIG + [script]:
            src = os.path.join(HERE, fn)
            if os.path.exists(src): shutil.copy(src, work)
        if config_overrides:
            for fn, content in config_overrides.items():
                with open(os.path.join(work, fn), "wb") as f: f.write(content)
        if xls_bytes is not None:        # 一般模式：寫入上傳的班表
            ext  = _detect_ext(xls_bytes)
            xlsp = os.path.join(work, f"上傳班表{ext}")
            with open(xlsp, "wb") as f: f.write(xls_bytes)
            cmd = [sys.executable, script, xlsp] + list(extra_args)
        else:                            # 快速模式：免上傳 Excel
            cmd = [sys.executable, script] + list(extra_args)
        r = subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=180)
        files = {}
        od = os.path.join(work, "輸出")
        if os.path.isdir(od):
            for fn in sorted(os.listdir(od)):
                with open(os.path.join(od, fn), "rb") as fh: files[fn] = fh.read()
        updated_hist = {}
        for hfn in ["排班紀錄.csv", "稽核紀錄.csv"]:
            hp = os.path.join(work, hfn)
            if os.path.exists(hp):
                with open(hp, "rb") as fh: updated_hist[hfn] = fh.read()
        stdout = r.stdout + (("\n" + r.stderr.strip()) if r.stderr.strip() else "")
        return stdout, files, updated_hist
    finally:
        shutil.rmtree(work, ignore_errors=True)


def pick(files, suffix):
    for fn, b in files.items():
        if fn.endswith(suffix): return fn, b
    return None, None

def extract_notes(stdout):
    """把 排班.py/稽核.py 印出來的提醒挑進畫面的「注意事項」區。

    ⚠ v3.48 修正：舊版只挑含「休息 ↳ ※ ❌ 借」的行，但 排班.py 的 warn() 有一整批是
    「ℹ」「⚠」開頭的——這些**全部被濾掉、從來沒顯示過**，包括：
      ⚠ 強制可印『X』在組員名單裡找不到 → v3.41 特地為了「不要靜默失效」才加的，結果
        加了等於沒加，玉繡打錯名字依然看不到任何提示
      ⚠ 名單有重複 / ⚠ 「X」卡號變了 / ⚠ 讀取設定檔失敗 / ⚠ 寫檔失敗
      ℹ 視為休診跳過 / ℹ 強制可印人員名單
      ℹ 第N欄日期格被打成純文字，已補回年份（v3.46 新增）
      ⚠ 這張班表的日期欄完全讀不到，已依檔名推算（v3.47 新增）
    這些正是最需要被看到的東西，補進關鍵字。

    ⚠ v3.53 續修：舊版只排除「【公平累計】」那個標題行本身，底下**逐人**的明細行
    （例如「林欣儀 稽11 休 2  本月:休息（夜/一區）」）完全沒排除。稽核.py 的休息狀態
    寫的是「休息」兩個字（排班.py 寫的是單一個「休」字），剛好命中這裡的關鍵字比對，
    導致每個月「休息」的那幾個人的公平累計明細，全部被誤判成注意事項、混進「⚠️ 注意
    事項」清單裡——這些明細本來就是排出來當下的舊資料，玉繡點格子改稽核者之後不會
    重算，混進注意事項只會讓人以為那是需要處理的警告，也會跟旁邊新增的「以這行為準」
    休息名單互相矛盾看起來像系統講話不一致。改成跟 extract_fairness() 用同一套「整個
    區塊都跳過」邏輯，不是只排除標題那一行。
    """
    lines = stdout.splitlines()
    in_fairness = False
    notes = []
    for ln in lines:
        s = ln.strip()
        if "【公平累計】" in s:
            in_fairness = True
            continue
        if in_fairness:
            if s == "":              # 空行代表公平累計區段結束
                in_fairness = False
            continue                 # 區段內的行(含標題後第一個空行前)一律不進注意事項
        if any(k in s for k in ("休息","↳","※","❌","借","ℹ","⚠")):
            notes.append(s)
    return notes

def extract_fairness(stdout):
    """抽出【公平累計】表格區段（含標題）。"""
    lines = stdout.splitlines()
    in_block = False; block = []
    for ln in lines:
        s = ln.strip()
        if "【公平累計】" in s:
            in_block = True
        if in_block:
            if s == "" and block:    # 空行代表區段結束
                break
            if s:
                block.append(s)
    return block

def parse_grid(df):
    names = df.copy(); dates = df.copy(); marks = df.copy()
    for r in df.index:
        for c in df.columns:
            v = str(df.loc[r,c]); m = CELL_RE.match(v)
            if m:
                names.loc[r,c]=m.group(1); dates.loc[r,c]=f"{int(m.group(2))}/{int(m.group(3))}"; marks.loc[r,c]=m.group(4)
            else:
                names.loc[r,c]=v; dates.loc[r,c]=""; marks.loc[r,c]=""
    return names, dates, marks

def year_from_cloud(files):
    _, b = pick(files, ".csv")
    if b:
        try:
            d = pd.read_csv(io.BytesIO(b), encoding="utf-8-sig")
            return int(str(d["印日期"].iloc[0]).split("-")[0])
        except Exception: pass
    return pd.Timestamp.now().year

def year_map_from_cloud(files):
    """v3.41 修正 #13a：整週不能只用一個年份！
    舊版 year_from_cloud() 只抓 CSV 第一列的年份當「整週共用」，如果這週剛好跨年
    （例如 12月最後一週+1月第一週排在同一張表，或單週橫跨 12/29~1/4），
    後面月份的格子年份一定會算錯（該是明年的被標成今年，或反過來）。
    這支改成「每一格自己查」：排班.py 產生的『雲端貼上_*.csv』本來就有每一列真正的
    印日期(含年)，這裡直接建 (區, 月, 日) → 年 的對照表，之後產生定案時逐格查表，
    不再整週共用單一猜測值。"""
    out = {}
    _, b = pick(files, ".csv")
    if b:
        try:
            d = pd.read_csv(io.BytesIO(b), encoding="utf-8-sig", dtype=str)
            for _, row in d.iterrows():
                ds = str(row.get("印日期", "")).strip()
                m = re.match(r'(\d{4})-(\d{1,2})-(\d{1,2})', ds)
                if not m: continue
                area = str(row.get("區", "")).strip()
                out[(area, int(m.group(2)), int(m.group(3)))] = int(m.group(1))
        except Exception:
            pass
    return out


# ── Fix3：自動選最接近今天的班表分頁 ─────────────────────
def _best_sheet_index(sheets):
    """分頁名稱有日期 → 選最接近今天的；否則選最後一頁。
    支援完整日期（2026-06-16）及 MMDD/MMDD-MMDD 格式（0706、0706-0712）。"""
    from datetime import timezone, timedelta
    today = datetime.now(timezone(timedelta(hours=8))).date()  # 台灣時區
    best_idx = len(sheets) - 1
    best_delta = None
    for i, sn in enumerate(sheets):
        sn_str = str(sn)
        # 完整日期格式：2026-06-16
        m = re.search(r"(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})", sn_str)
        if m:
            try:
                d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                delta = abs((d - today).days)
                if best_delta is None or delta < best_delta:
                    best_delta = delta; best_idx = i
            except Exception: pass
            continue
        # MMDD 或 MMDD-MMDD 格式：0706、0629-0712
        m2 = re.match(r"(\d{2})(\d{2})", sn_str.strip())
        if m2:
            try:
                mo, dy = int(m2.group(1)), int(m2.group(2))
                if 1 <= mo <= 12 and 1 <= dy <= 31:
                    yr = today.year
                    d = date(yr, mo, dy)
                    # 跨年修正要做**雙向**。v3.41：舊版只有「太舊 → 加一年」，
                    # 少了反向的「太新 → 減一年」，導致例如今天是 2027-01-02 時，
                    # 分頁「1228~0103」會被算成 2027-12-28（delta 360）而不是
                    # 2026-12-28（delta 5），預設就選錯分頁。
                    # （_fmt_week 在下方本來就是雙向寫法，兩邊原本不一致。）
                    if (today - d).days > 180:
                        d = date(yr + 1, mo, dy)
                    elif (d - today).days > 180:
                        d = date(yr - 1, mo, dy)
                    delta = abs((d - today).days)
                    if best_delta is None or delta < best_delta:
                        best_delta = delta; best_idx = i
            except Exception: pass
    return best_idx


# ── Fix1：根據玉繡實際定案重建公平歷史 ──────────────────
def _load_roster_names():
    """讀本機備份 組員名單.csv → {姓名: 卡號}（僅供雲端讀不到時保底，見 get_roster_full()）"""
    f = os.path.join(HERE, "組員名單.csv")
    mapping = {}
    if not os.path.exists(f): return mapping
    try:
        with open(f, encoding="utf-8-sig") as fp:
            for row in csv.DictReader(fp):
                card = (row.get("卡號") or "").strip()
                name = (row.get("姓名") or "").strip()
                if name: mapping[name] = card
    except Exception: pass
    return mapping

def _load_roster_full():
    """讀本機備份 組員名單.csv → [{'卡號':.., '姓名':..}]（僅供雲端讀不到時保底，見 get_roster_full()）"""
    f = os.path.join(HERE, "組員名單.csv")
    out = []
    if not os.path.exists(f): return out
    try:
        with open(f, encoding="utf-8-sig") as fp:
            for row in csv.DictReader(fp):
                card = (row.get("卡號") or "").strip()
                name = (row.get("姓名") or "").strip()
                if name: out.append({"卡號": card, "姓名": name})
    except Exception: pass
    return out

# ── 組員名單單一來源（v3.50，接續包獨立稽查高-3）───────────────────
# 排班.py／稽核.py 執行前是用 fetch_members_as_csv() 抓雲端名單當 config_override，
# 但 app.py 自己另外有 5 個地方（LINE公告的休息名單、build_corrected_history、
# build_corrected_audit_history、定案畫面的「😴本週休息」、稽核快速模式的名冊）
# 直接讀本機 repo 裡的 組員名單.csv——這份本機檔跟雲端完全是兩份獨立資料。Tab4
# 「組員名單」的 UI 又明白引導使用者「新增/刪除後存回雲端，之後排班就用新名單」，
# 等於主動製造這個落差。實測：雲端多一位新同仁但只改雲端 → 她照樣被排到印藥水，
# 但 build_corrected_history 寫回的歷史完全沒有她這一列（用的是本機舊名單算的
# 「休」清單），公平輪序永遠看不到她；稽核快速模式的畫面上也不會列出她。
# 改法：這裡統一成單一入口，雲端優先，只有在讀不到雲端時才退回本機備份，並在
# session_state 記下降級旗標，供畫面顯示警告（不要靜默降級）。
def get_roster_full():
    """組員名單單一來源 → [{'卡號':.., '姓名':..}]（依名單順序）。雲端優先、本機保底。"""
    if "_roster_full_v350" not in st.session_state:
        cloud_df = fetch_members_cloud()
        if cloud_df is not None and not cloud_df.empty and "姓名" in cloud_df.columns:
            out = [{"卡號": str(r.get("卡號", "")).strip(), "姓名": str(r.get("姓名", "")).strip()}
                   for _, r in cloud_df.iterrows() if str(r.get("姓名", "")).strip()]
            st.session_state["_roster_full_v350"] = out
            st.session_state["_roster_source_v350"] = "cloud"
        else:
            local = _load_roster_full()
            st.session_state["_roster_full_v350"] = local
            st.session_state["_roster_source_v350"] = "local_fallback"
    return st.session_state["_roster_full_v350"]

def get_roster_names():
    """組員名單單一來源 → {姓名: 卡號}。雲端優先、本機保底。"""
    return {m["姓名"]: m["卡號"] for m in get_roster_full() if m["姓名"]}

def roster_fallback_warning():
    """如果這次 session 是靠本機備份撐著（雲端讀不到），回傳警告文字；正常時回 ""。"""
    if st.session_state.get("_roster_source_v350") == "local_fallback":
        return ("⚠️ 讀不到雲端組員名單，這次是用本機備份頂著——若最近有人入組/退組，"
                "休息名單、公平輪序、稽核名冊都可能不準，請確認網路後重新整理頁面。")
    return ""

def fetch_last_audit_prefill():
    """從雲端稽核歷史抓「最近一個月」的每人班型/區，給快速模式預先帶入。
    回傳 {姓名: (班型, 區)}；班型由班次推回（第三班=小夜，否則白班）。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return {}
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "getAuditHistory", "secret": WRITE_SECRET},
                             timeout=20)
        rows = resp.json().get("rows") or []
        if len(rows) < 2: return {}
        hdr = [str(x).strip() for x in rows[0]]
        iM, iN, iP = hdr.index("月份"), hdr.index("姓名"), hdr.index("位置")
        # 只看正常的月份鍵，跳過草稿/意見那些特殊列。
        # v3.41：舊版寫死 ^\d{4}-\d{2}$（只吃西元4位數），但實際資料全是民國3位數
        # （114-09 ~ 115-07），永遠比不中 → 「快速點選會帶出上個月設定」這功能其實
        # 一直是靜默失效的，玉繡每個月都得從頭點。改成民國/西元都接受。
        months = [str(r[iM]).strip() for r in rows[1:]
                  if re.match(r"^\d{3,4}-\d{2}$", str(r[iM]).strip())]
        if not months: return {}
        # 民國(115-07)與西元(2026-07)若混在一起，直接 max() 會用字串比而排錯
        # （"2">"1" 會讓 2026-07 永遠勝過 115-12），先正規化成西元再取最大
        def _to_ce(k):
            y, m = k.split("-")
            y = int(y)
            return (y + 1911 if y < 1911 else y, int(m))
        last = max(months, key=_to_ce)
        pf = {}
        for r in rows[1:]:
            if str(r[iM]).strip() != last: continue
            name = str(r[iN]).strip(); pos = str(r[iP]).strip()
            if not name or not pos: continue          # 休息者無位置 → 不帶入
            area = pos.split("/")[0].strip()
            typ  = "小夜" if "第三班" in pos else "白班"
            pf[name] = (typ, area)
        return pf
    except Exception:
        return {}

# ── 稽核「草稿暫存」：借用稽核歷史的特殊月份鍵存放，不影響公平輪序 ──
DRAFT_KEY = "草稿"

def fetch_audit_draft():
    """讀雲端草稿（稽核歷史裡 月份=='草稿' 那幾筆）→ {姓名: (班型, 區)}。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return {}
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "getAuditHistory", "secret": WRITE_SECRET},
                             timeout=20)
        rows = resp.json().get("rows") or []
        if len(rows) < 2: return {}
        hdr = [str(x).strip() for x in rows[0]]
        iM, iN, iS, iP = (hdr.index("月份"), hdr.index("姓名"),
                          hdr.index("狀態"), hdr.index("位置"))
        d = {}
        for r in rows[1:]:
            if str(r[iM]).strip() != DRAFT_KEY: continue
            name = str(r[iN]).strip()
            if name: d[name] = (str(r[iS]).strip(), str(r[iP]).strip())  # 狀態=班型, 位置=區
        return d
    except Exception:
        return {}

def push_audit_draft(df):
    """把目前點選存成雲端草稿（借用 setAuditResult，月份=草稿；班型放狀態欄、區放位置欄）。

    回傳 (ok, 錯誤訊息)。v3.50（獨立稽查低-19）：以前只回 True/False，失敗時畫面只能
    講「儲存失敗，請稍後再試」，跟 v3.44 修過的 push_week_draft() 是同一類問題——
    使用者分不出是網路斷線、GAS 端回 ok:false、還是資料格式錯，統一成 (ok, err) 才能
    把真正原因秀出來。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return False, "尚未設定 Apps Script 網址或密鑰"
    try:
        rows = [[DRAFT_KEY, str(r["卡號"]), str(r["姓名"]), str(r["班型"]), str(r["區"])]
                for _, r in df.iterrows()]
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "setAuditResult", "secret": WRITE_SECRET,
                                   "key": DRAFT_KEY, "rows": rows},
                             timeout=20)
        if not resp.ok: return False, f"雲端回應碼異常：HTTP {resp.status_code}"
        d = resp.json()
        if not d.get("ok"): return False, f"雲端回報失敗：{d.get('error') or d}"
        return True, ""
    except Exception as e:
        return False, f"例外：{e}"

def clear_audit_draft():
    """清除雲端草稿（送空 rows，月份=草稿 的紀錄會被移除）。回傳 (ok, 錯誤訊息)。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return False, "尚未設定 Apps Script 網址或密鑰"
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "setAuditResult", "secret": WRITE_SECRET,
                                   "key": DRAFT_KEY, "rows": []},
                             timeout=20)
        if not resp.ok: return False, f"雲端回應碼異常：HTTP {resp.status_code}"
        d = resp.json()
        if not d.get("ok"): return False, f"雲端回報失敗：{d.get('error') or d}"
        return True, ""
    except Exception as e:
        return False, f"例外：{e}"

# ── 印藥水定案雲端草稿（讓小巫雙重確認）───────────────────
def push_week_draft(rows, sheet0):
    """把玉繡的定案存到雲端草稿（排班草稿分頁），讓小巫可以讀取確認。

    回傳 (ok, 錯誤訊息)。v3.44：以前只回 True/False，畫面永遠只能猜「網路問題？」
    ——玉繡實際遇到的「暫存失敗」根本不是網路，是欄數對不上，卻完全看不出來。

    ⚠️ 欄數必須剛好 6 欄，跟 .gs 的 DRAFT_HEADERS（週次/印日期/區/姓名/跨區/治療欄）
    一致。rows 每筆是 [印日期, 區, 姓名, 🔺, 治療欄key]，這裡固定補成 5 欄再前綴週次，
    以後就算 rows 格式再變動也不會把欄數帶歪、害 GAS 端 setValues 爆掉。
    """
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return False, "未設定 APPS_SCRIPT_URL/WRITE_SECRET"
    try:
        cloud_rows = [[str(sheet0)] + [str(v) for v in (list(r) + ["", "", "", "", ""])[:5]]
                      for r in rows]
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "setWeekDraft", "secret": WRITE_SECRET,
                                   "rows": cloud_rows},
                             timeout=20)
        d = resp.json()
        if resp.ok and d.get("ok", False):
            return True, ""
        err = str(d.get("error", f"HTTP {resp.status_code}"))
        if "超過表頭" in err or "does not match" in err:
            err += "（Apps Script 版本太舊，請部署到 v6.3 以上）"
        return False, err
    except Exception as _e:
        return False, str(_e)

def gs_date_to_ymd(s):
    """把 GAS 回傳的日期轉成台北時區的 YYYY-MM-DD 字串。

    ⚠ v3.41 修正的重要 bug：Google Sheets 會把「2026-07-16」這種字串存成**日期型別**，
    `JSON.stringify` 序列化時會轉成 **UTC**：台北 7/16 00:00 → "2026-07-15T16:00:00.000Z"。
    舊版三處 `_clean_dt` 都直接 `re.match(r'(\\d{4}-\\d{2}-\\d{2})')` 截前10碼，於是拿到
    **7/15，整整少一天**。（"T16:00:00Z" 正好是 UTC+8 的午夜，就是它是日期型別的鐵證。）
    後果：載入雲端草稿後，全部12人的印藥水日整批早一天，接著按「送到雲端」就把錯的
    日期寫進本週名單，LINE 提醒也跟著錯——症狀跟 v5.8 修掉的那個一樣，但成因完全不同。

    這裡改成：偵測到帶時間的 ISO 格式就先當 UTC 解析、再轉台北時區取日期；
    純日期字串（沒有時間部分）維持原樣直接取用。
    """
    s = str(s).strip()
    # 帶時間的 ISO 字串（GAS 序列化日期型別會長這樣）→ 必須做時區換算
    m = re.match(r'^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2}):(\d{2})', s)
    if m:
        try:
            dt_utc = datetime.strptime(m.group(0)[:19], "%Y-%m-%dT%H:%M:%S")
            return (dt_utc + timedelta(hours=8)).strftime("%Y-%m-%d")   # UTC → Asia/Taipei
        except Exception:
            return m.group(1)
    m2 = re.match(r'(\d{4}-\d{2}-\d{2})', s)
    return m2.group(1) if m2 else s

def _week_looks_stale(sheet0, today=None):
    """粗略判斷週次字串是不是「已經不像最近這週」，只用來提醒多看一眼，不是精確計算。
    抓不到格式（None）時一律當「看不出來」，不主動警告——沒有把握的東西不亂講。

    v3.50（獨立稽查中-12）：雲端草稿沒有時間戳，`push_week_draft`/GAS 的
    「排班草稿」分頁都只記週次字串，不記存入時間。以前只要玉繡按過一次「產生
    定案」（會自動暫存草稿），下週打開 app 第一件事就是「📬 偵測到玉繡的排班
    草稿（上週那份）」，若不小心按下去又送出，`setWeek` 會拿上週的印藥水日整批
    覆蓋「本週名單」，本週的 LINE 提醒直接失效（而且GAS的dedup會擋住之後的
    補發，因為那些日期「看起來」已經發過提醒了）。這裡加一層粗略的新鮮度判斷，
    當草稿的週次跟今天差超過10天，畫面要多提醒一句、且送出前要多一道確認。
    """
    today = today or date.today()
    m = re.match(r"^(\d{2})(\d{2})", str(sheet0).strip())
    if not m: return None
    mo, dy = int(m.group(1)), int(m.group(2))
    if not (1 <= mo <= 12 and 1 <= dy <= 31): return None
    best = None
    for y in (today.year - 1, today.year, today.year + 1):
        try: cand = date(y, mo, dy)
        except ValueError: continue
        if best is None or abs((cand - today).days) < abs((best - today).days):
            best = cand
    if best is None: return None
    return abs((best - today).days) > 10

def fetch_week_draft():
    """讀取雲端草稿 → (rows, sheet0)；沒有草稿回傳 (None, None)。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return None, None
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "getWeekDraft", "secret": WRITE_SECRET},
                             timeout=20)
        d = resp.json()
        if not d.get("ok") or not d.get("rows"): return None, None
        rows_raw = d["rows"]
        if len(rows_raw) < 2: return None, None
        sheet0 = str(rows_raw[1][0])
        # GAS 回傳日期可能是 "2026-07-05T16:00:00.000Z"（UTC）→ 要轉台北時區才不會少一天
        rows = [[gs_date_to_ymd(r[1])] + [str(x) for x in r[2:]] for r in rows_raw[1:]]
        return rows, sheet0
    except Exception:
        return None, None

def clear_week_draft_cloud():
    """清除雲端草稿。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return False
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "setWeekDraft", "secret": WRITE_SECRET,
                                   "rows": []},
                             timeout=20)
        return resp.ok and resp.json().get("ok", False)
    except Exception:
        return False

def fetch_schedule_stats():
    """從雲端排班歷史彙總每人印/休次數 → DataFrame(有資料) / None(真的沒資料) / 錯誤字串(讀取失敗)。

    v3.50（獨立稽查中-5的同型問題）：舊版把「GAS 明確回 ok:false」跟「真的沒資料」
    都回 None，畫面因此把讀取失敗也顯示成「雲端還沒有排班歷史，請按📤同步本機CSV→雲端」
    ——這句話會主動引導使用者去按那顆同步鈕，而同步鈕已經修過（見
    sync_schedule_history_from_csv）在讀取失敗時會自己中止，所以不會再因此蓋掉資料，
    但這裡的誤導訊息本身還是該修：讀取失敗要老實說失敗，不要說成「還沒有資料」。
    """
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return None
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "getScheduleHistory", "secret": WRITE_SECRET},
                             timeout=30)
        d = resp.json()
        if not (resp.ok and d.get("ok")):
            return str(d.get("error", f"HTTP {resp.status_code}"))
        rows = d.get("rows") or []
        if len(rows) < 2: return None
        df = pd.DataFrame([[str(c) for c in r] for r in rows[1:]], columns=[str(x) for x in rows[0]])
        df["狀態"] = df["狀態"].str.strip()
        # 只統計正常 印/休（排除草稿、修正等特殊週次）
        df = df[df["狀態"].isin(["印","休"])]
        if df.empty: return None
        grp = df.groupby(["卡號","姓名"])["狀態"].value_counts().unstack(fill_value=0)
        grp = grp.reindex(columns=["印","休"], fill_value=0).reset_index()
        grp.columns = ["卡號","姓名","印次","休次"]
        grp["印次"] = pd.to_numeric(grp["印次"], errors="coerce").fillna(0).astype(int)
        grp["休次"] = pd.to_numeric(grp["休次"], errors="coerce").fillna(0).astype(int)
        grp["淨值(印-休)"] = grp["印次"] - grp["休次"]
        grp = grp.sort_values("淨值(印-休)", ascending=False).reset_index(drop=True)
        return grp
    except Exception as _e:
        return str(_e)   # 回傳錯誤字串，UI 可顯示

def save_schedule_stats(df):
    """把統計表重建為歷史 rows 並整批推送到雲端（清空重建）。

    回傳 (ok, 錯誤訊息)。v3.50（獨立稽查低-19）：跟 push_audit_draft 同一類修法，
    以前只回 True/False，「清空所有人的每週明細只留總數字」這種高風險操作失敗時，
    使用者卻只看得到「儲存失敗，請稍後再試」，猜不出到底是網路問題還是 GAS 端拒絕。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return False, "尚未設定 Apps Script 網址或密鑰"
    try:
        rows = []
        for _, r in df.iterrows():
            card = str(r["卡號"]).strip()
            name = str(r["姓名"]).strip()
            n_print = max(0, int(r["印次"]))
            n_rest  = max(0, int(r["休次"]))
            for i in range(n_print):
                rows.append([f"統計-印{i+1:02d}", card, name, "印", ""])
            for i in range(n_rest):
                rows.append([f"統計-休{i+1:02d}", card, name, "休", ""])
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "setAllScheduleHistory", "secret": WRITE_SECRET,
                                   "rows": rows},
                             timeout=30)
        if not resp.ok: return False, f"雲端回應碼異常：HTTP {resp.status_code}"
        d = resp.json()
        if not d.get("ok"): return False, f"雲端回報失敗：{d.get('error') or d}"
        return True, ""
    except Exception as e:
        return False, f"例外：{e}"

def fetch_schedule_history_raw():
    """從雲端排班歷史取得原始明細 → (df, err)。

    v3.50（獨立稽查中-5）：舊版把「GAS 明確回 ok:false」跟「真的沒有資料」都回傳
    同一個 None，`sync_schedule_history_from_csv()` 只擋了 exception 那條路
    （字串），把這個 None 當成「雲端 0 週」，於是 missing=本機全部、
    combined=missing（因為 cloud_df 是 None 不會被合併）→ 整批覆蓋雲端，
    畫面還顯示「已補進雲端」——正是第十六節那場事故的重演路徑，只是這次的
    觸發點是「讀取失敗」而不是「本機落後」。
    改成明確分三態：讀取失敗 → (None, 錯誤字串)；成功但真的沒資料 → (空DataFrame, "")；
    成功有資料 → (DataFrame, "")。呼叫端只要看 df is None 就知道要不要中止。
    """
    if not APPS_SCRIPT_URL or not WRITE_SECRET:
        return None, "未設定 APPS_SCRIPT_URL/WRITE_SECRET"
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "getScheduleHistory", "secret": WRITE_SECRET},
                             timeout=30)
        d = resp.json()
        if not (resp.ok and d.get("ok")):
            return None, str(d.get("error", f"HTTP {resp.status_code}"))
        rows = d.get("rows") or []
        cols = ["週次","卡號","姓名","狀態","治療日"]
        if len(rows) < 2:
            return pd.DataFrame(columns=cols), ""
        df = pd.DataFrame([[str(c) for c in r] for r in rows[1:]], columns=[str(x) for x in rows[0]])
        df["狀態"] = df["狀態"].str.strip()
        return df[df["狀態"].isin(["印","休"])].reset_index(drop=True), ""
    except Exception as _e:
        return None, str(_e)

def fetch_members_cloud():
    """從 GS 雲端讀取組員名單 → DataFrame(卡號/姓名)，或 None。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return None
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "getMembers", "secret": WRITE_SECRET},
                             timeout=20)
        d = resp.json()
        if not d.get("ok") or not d.get("rows"): return None
        rows = d["rows"]
        if len(rows) < 2: return None
        return pd.DataFrame(rows[1:], columns=[str(x) for x in rows[0]])
    except Exception:
        return None

def fetch_members_as_csv():
    """讀雲端組員名單並轉為 CSV bytes（供 config_override 注入排班/稽核.py）。"""
    df = fetch_members_cloud()
    if df is None: return None
    return df.to_csv(index=False).encode("utf-8-sig")

def save_members_cloud(df):
    """把組員名單 DataFrame 存回 GS 雲端。回傳 (ok, 錯誤訊息)（v3.50 獨立稽查低-19）。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return False, "尚未設定 Apps Script 網址或密鑰"
    try:
        rows = [[str(r.get("卡號","")).strip(), str(r.get("姓名","")).strip()]
                for _, r in df.iterrows() if str(r.get("姓名","")).strip()]
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "setMembers", "secret": WRITE_SECRET, "rows": rows},
                             timeout=20)
        if not resp.ok: return False, f"雲端回應碼異常：HTTP {resp.status_code}"
        d = resp.json()
        if not d.get("ok"): return False, f"雲端回報失敗：{d.get('error') or d}"
        return True, ""
    except Exception as e:
        return False, f"例外：{e}"

# ── 休診日：雲端「休診日」分頁是唯一來源（v3.42）────────────────
# 過年/連假這種「沒診、不上班」的日子，本來有兩份各自維護的清單：
#   ① webapp/休診日.csv        → 排班.py 的 prev_treat()，決定「印藥水日」往前推幾天
#   ② 藥水小幫手.gs 的 EXTRA_HOLIDAYS 陣列 → prevWorkday_()，決定「LINE 提醒日」往前推
# 改一邊不會同步到另一邊，兩邊一旦對不上，排班算出來的印藥水日跟 LINE 通知的日期
# 就會差一天——跟 v5.8 修掉的 off-by-one 是同一類災情，只是兩份清單目前剛好都是空的
# 所以還沒爆發。v3.42 起改成雲端「休診日」分頁當唯一來源，兩邊都讀它。
def fetch_holidays_cloud():
    """讀雲端「休診日」分頁 → (DataFrame[日期,說明], 錯誤訊息)。

    (df, "")   成功。⚠ df 可能是空的——「雲端目前沒有登記任何休診日」本身就是有效
               答案，**不可以**當成失敗而改用本機 CSV，否則又變回兩份清單各自為政。
    (None, msg) 真的讀不到（沒設定 URL/Secret、網路失敗、或 Apps Script 還停在
               v6.0 以前、不認得 getHolidays 這個 action）。
    """
    if not APPS_SCRIPT_URL or not WRITE_SECRET:
        return None, "未設定 APPS_SCRIPT_URL / WRITE_SECRET"
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "getHolidays", "secret": WRITE_SECRET},
                             timeout=20)
        d = resp.json()
        if not d.get("ok"):
            err = str(d.get("error", "GAS 回傳失敗"))
            if "unknown action" in err:
                err = ("Apps Script 還沒部署 v6.1（不認得 getHolidays）。"
                       "請把 藥水小幫手_完整版.gs 最新版貼進編輯器後「部署→管理部署→新版本」。")
            return None, err
        rows = d.get("rows") or []
        if len(rows) < 1:
            return pd.DataFrame(columns=["日期", "說明"]), ""
        hdr = [str(x).strip() for x in rows[0]]
        out = []
        for r in rows[1:]:
            # Sheets 會把日期存成日期型別，GAS 序列化成 UTC ISO 字串（見 gs_date_to_ymd
            # 的說明），直接截前 10 碼會少一天，一律走同一支轉換函式。
            ymd = gs_date_to_ymd(r[0]) if len(r) > 0 else ""
            memo = str(r[1]).strip() if len(r) > 1 else ""
            if str(ymd).strip():
                out.append({"日期": str(ymd).strip(), "說明": memo})
        return pd.DataFrame(out, columns=["日期", "說明"]), ""
    except Exception as _e:
        return None, str(_e)

HOLIDAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

def fetch_holidays_as_csv():
    """雲端休診日 → 休診日.csv bytes（給 config_override 注入 排班.py/稽核.py）。

    回傳 (csv_bytes, 錯誤訊息)；讀不到時 csv_bytes 為 None，呼叫端要顯示警告
    （不要靜默改用本機備份，那正是這次要根治的問題）。
    """
    df, err = fetch_holidays_cloud()
    if df is None:
        return None, err
    buf = io.StringIO()
    buf.write("日期,說明\n")
    bad = []
    for _, r in df.iterrows():
        ymd = str(r.get("日期", "")).strip()
        if not ymd: continue
        if not HOLIDAY_RE.match(ymd):
            bad.append(ymd); continue        # 格式不對就不要餵進去，排班.py 也只會警告後略過
        memo = str(r.get("說明", "")).replace(",", "，").replace("\n", " ").strip()
        buf.write(f"{ymd},{memo}\n")
    warn = f"雲端休診日有 {len(bad)} 筆格式不對已略過：{'、'.join(bad)}" if bad else ""
    return buf.getvalue().encode("utf-8-sig"), warn

def save_holidays_cloud(df):
    """把休診日 DataFrame 存回雲端「休診日」分頁 → (ok, 寫入筆數, 錯誤訊息)。

    整批取代（不是「只補不蓋」）——休診日跟組員名單一樣，真的會需要「刪除」
    （例如原本排定的補班日取消），只補不蓋會讓刪掉的日子復活。防呆改成走
    「表格編輯前一定先讀雲端現況」＋「本機 CSV 只有雲端全空時才能上傳」。
    """
    if not APPS_SCRIPT_URL or not WRITE_SECRET:
        return False, 0, "未設定 APPS_SCRIPT_URL / WRITE_SECRET"
    try:
        rows, bad = [], []
        for _, r in df.iterrows():
            ymd = str(r.get("日期", "")).strip()
            if not ymd: continue
            if not HOLIDAY_RE.match(ymd):
                bad.append(ymd); continue
            rows.append([ymd, str(r.get("說明", "")).strip()])
        if bad:
            return False, 0, ("日期格式要像 2026-01-01（西元-月-日，補零）。"
                              f"這幾筆不合格式，沒有存出去：{'、'.join(bad)}")
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "setHolidays", "secret": WRITE_SECRET,
                                   "rows": rows},
                             timeout=20)
        d = resp.json()
        if resp.ok and d.get("ok", False):
            return True, len(rows), ""
        err = str(d.get("error", "GAS 回傳失敗"))
        if "unknown action" in err:
            err = ("Apps Script 還沒部署 v6.1（不認得 setHolidays）。"
                   "請把 藥水小幫手_完整版.gs 最新版貼進編輯器後「部署→管理部署→新版本」。")
        return False, 0, err
    except Exception as _e:
        return False, 0, str(_e)

def fetch_audit_stats():
    """從 GS 稽核歷史彙總每人稽核/休次數 → DataFrame(有資料) / None(真的沒資料) / 錯誤字串(讀取失敗)。

    v3.50：跟 fetch_schedule_stats() 同一類問題，見那邊的說明。
    """
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return None
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "getAuditHistory", "secret": WRITE_SECRET},
                             timeout=20)
        d = resp.json()
        if not (resp.ok and d.get("ok")):
            return str(d.get("error", f"HTTP {resp.status_code}"))
        rows = d.get("rows") or []
        if len(rows) < 2: return None
        df = pd.DataFrame([[str(c) for c in r] for r in rows[1:]], columns=[str(x) for x in rows[0]])
        df["狀態"] = df["狀態"].str.strip()
        # 排除草稿和意見回饋，其餘（正常月份 + 統計重建記錄）都納入計算
        excl = (df["月份"].str.startswith("意見-") | (df["月份"] == "草稿"))
        valid = df[~excl & df["狀態"].isin(["稽核","休"])]
        if valid.empty: return pd.DataFrame(columns=["卡號","姓名","稽核次","休次","淨值(稽核-休)"])
        grp = valid.groupby(["卡號","姓名"])["狀態"].value_counts().unstack(fill_value=0)
        grp = grp.reindex(columns=["稽核","休"], fill_value=0).reset_index()
        grp.columns = ["卡號","姓名","稽核次","休次"]
        grp["稽核次"] = pd.to_numeric(grp["稽核次"], errors="coerce").fillna(0).astype(int)
        grp["休次"]   = pd.to_numeric(grp["休次"],   errors="coerce").fillna(0).astype(int)
        grp["淨值(稽核-休)"] = grp["稽核次"] - grp["休次"]
        return grp.sort_values("淨值(稽核-休)", ascending=False).reset_index(drop=True)
    except Exception as _e:
        return str(_e)

def save_audit_stats(df):
    """把稽核統計表重建為歷史 rows 並整批推送到 GS（清空重建）。
    回傳 (ok, 錯誤訊息)（v3.50 獨立稽查低-19，跟 save_schedule_stats 同一類修法）。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return False, "尚未設定 Apps Script 網址或密鑰"
    try:
        rows = []
        for _, r in df.iterrows():
            card = str(r["卡號"]).strip()
            name = str(r["姓名"]).strip()
            for i in range(max(0, int(r["稽核次"]))):
                rows.append([f"統計-稽{i+1:02d}", card, name, "稽核", ""])
            for i in range(max(0, int(r["休次"]))):
                rows.append([f"統計-休{i+1:02d}", card, name, "休", ""])
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "setAllAuditHistory", "secret": WRITE_SECRET,
                                   "rows": rows},
                             timeout=30)
        if not resp.ok: return False, f"雲端回應碼異常：HTTP {resp.status_code}"
        d = resp.json()
        if not d.get("ok"): return False, f"雲端回報失敗：{d.get('error') or d}"
        return True, ""
    except Exception as e:
        return False, f"例外：{e}"

def fetch_latest_audit_result():
    """從 GS 稽核歷史讀取最新一個月的名單明細（稽核者含位置、休息者列出）。
    回傳 (月份str, DataFrame) 或 (None, None) 或 (None, 錯誤字串)。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return None, None
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "getAuditHistory", "secret": WRITE_SECRET},
                             timeout=30)
        d = resp.json()
        if not d.get("ok") or not d.get("rows"): return None, None
        rows = d["rows"]
        if len(rows) < 2: return None, None
        df = pd.DataFrame([[str(c) for c in r] for r in rows[1:]], columns=[str(x) for x in rows[0]])
        excl = (df["月份"].str.startswith("意見-") |
                df["月份"].str.startswith("統計-") |
                (df["月份"] == "草稿"))
        valid = df[~excl & df["狀態"].isin(["稽核","休"])].copy()
        if valid.empty: return None, None
        # v3.50（獨立稽查低-19）：原本用純字典排序取最新月份，只在同一種年份格式
        # （全部都是民國，或全部都是西元）時才剛好是對的。跟 _home_audit_snapshot()
        # 一樣的陷阱：民國「115-12」跟西元「2026-07」混在一起時，字典排序看第一個
        # 字元 '2' > '1'，會把「2026-07」誤判成比「115-12」還新——但「2026-07」換算
        # 民國其實是 115-07，比 115-12 還早。改成跟 _home_audit_snapshot() 一致的
        # 「民國/西元統一換算成西元年再比大小」。
        def _to_ce(k):
            y, mo = str(k).split("-")
            y = int(y)
            return (y + 1911 if y < 1911 else y, int(mo))
        latest = sorted(valid["月份"].unique(), key=_to_ce)[-1]
        result = valid[valid["月份"] == latest][["姓名","狀態","位置"]].reset_index(drop=True)
        return latest, result
    except Exception as _e:
        return None, str(_e)

def _sync_to_gs(action, rows, timeout=30, retries=2):
    """送資料到 GS，逾時自動重試。回傳 (ok, n, err_msg)。"""
    last_err = ""
    for attempt in range(retries):
        try:
            resp = requests.post(APPS_SCRIPT_URL,
                                 json={"action": action, "secret": WRITE_SECRET, "rows": rows},
                                 timeout=timeout)
            d = resp.json()
            if resp.ok and d.get("ok", False):
                return True, len(rows), ""
            last_err = d.get("error", "GAS 回傳失敗")
            break
        except requests.exceptions.Timeout:
            last_err = f"連線逾時（第{attempt+1}次，共{retries}次）"
        except Exception as e:
            last_err = str(e)
            break
    return False, 0, last_err

def sync_schedule_history_from_csv():
    """把本機排班紀錄.csv 裡「雲端目前沒有的週次」補進雲端排班歷史。

    v3.38 前：整批覆蓋雲端（setAllScheduleHistory 是 clearContents 重建），若本機 CSV
    落後（雲端有、CSV 沒有的新週次），一按就會把雲端較新的資料蓋掉——2026-07-20 凌晨
    實際發生過一次，蓋掉了剛送出的 0720~0726 那 15 筆。
    v3.38 起：先讀雲端現況，只把「本機有、雲端沒有」的週次補上去，雲端既有的週次原封
    不動地保留、一起送回去（GAS 端仍是整批 setAllScheduleHistory，但送出的內容已經是
    「雲端原有 + 本機獨有」的合併結果，不會遺失雲端較新的資料）。
    回傳 (ok, 新補上的筆數, err)。
    """
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return False, 0, "未設定 URL/Secret"
    csv_path = os.path.join(HERE, "排班紀錄.csv")
    if not os.path.exists(csv_path): return False, 0, "找不到排班紀錄.csv"
    try:
        df_local = pd.read_csv(csv_path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
        cloud_df, _err = fetch_schedule_history_raw()
        if cloud_df is None:
            # v3.50：以前這裡只擋「回傳字串」的例外，讀取失敗回 None 沒被擋到，
            # 會被當成「雲端0週」去整批覆蓋（見 fetch_schedule_history_raw 說明）。
            return False, 0, f"讀取雲端現況失敗，為安全起見取消同步：{_err}"
        cloud_weeks = set(cloud_df["週次"].astype(str))
        missing = df_local[~df_local["週次"].astype(str).isin(cloud_weeks)]
        if missing.empty:
            return True, 0, ""
        combined = (pd.concat([cloud_df, missing], ignore_index=True)
                    if not cloud_df.empty else missing)
        rows = [list(r) for _, r in combined.iterrows()]
        ok, _, err = _sync_to_gs("setAllScheduleHistory", rows)
        return ok, (len(missing) if ok else 0), err
    except Exception as e:
        return False, 0, str(e)

def fetch_audit_history_full_raw():
    """從雲端稽核歷史取得完整明細（含草稿/意見等特殊列，不篩選）→ (df, err)。

    v3.50（獨立稽查中-5）：跟 fetch_schedule_history_raw 是同一類問題，同樣的三態
    分法，見那邊的說明。
    """
    if not APPS_SCRIPT_URL or not WRITE_SECRET:
        return None, "未設定 APPS_SCRIPT_URL/WRITE_SECRET"
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "getAuditHistory", "secret": WRITE_SECRET},
                             timeout=30)
        d = resp.json()
        if not (resp.ok and d.get("ok")):
            return None, str(d.get("error", f"HTTP {resp.status_code}"))
        rows = d.get("rows") or []
        if len(rows) < 2:
            return pd.DataFrame(columns=["月份","卡號","姓名","狀態","位置"]), ""
        return pd.DataFrame([[str(c) for c in r] for r in rows[1:]], columns=[str(x) for x in rows[0]]), ""
    except Exception as e:
        return None, str(e)

def sync_audit_history_from_csv():
    """把本機稽核紀錄.csv 裡「雲端目前沒有的月份」補進雲端稽核歷史（同 v3.38 排班版邏輯，
    不覆蓋雲端既有資料，見 sync_schedule_history_from_csv 說明）。回傳 (ok, 新補上的筆數, err)。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return False, 0, "未設定 URL/Secret"
    csv_path = os.path.join(HERE, "稽核紀錄.csv")
    if not os.path.exists(csv_path): return False, 0, "找不到稽核紀錄.csv"
    try:
        df_local = pd.read_csv(csv_path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
        cloud_df, _err = fetch_audit_history_full_raw()
        if cloud_df is None:
            return False, 0, f"讀取雲端現況失敗，為安全起見取消同步：{_err}"
        cloud_months = set(cloud_df["月份"].astype(str))
        missing = df_local[~df_local["月份"].astype(str).isin(cloud_months)]
        if missing.empty:
            return True, 0, ""
        # v3.41：送出前先把「草稿」與「意見-」那些特殊列濾掉。GAS 端的
        # setAllAuditHistory 本來就會自己保留這些列（keptAud），我們這邊若又原封不動
        # 送回去，同一批草稿/意見會被寫兩次 → 列數翻倍（實測按1次：草稿1→2筆、
        # 意見1→2筆）。不會掉資料，但會累積雜訊、回饋清單出現重複。
        if not cloud_df.empty:
            _mon = cloud_df["月份"].astype(str)
            cloud_df = cloud_df[~(_mon.eq("草稿") | _mon.str.startswith("意見-"))]
        combined = (pd.concat([cloud_df, missing], ignore_index=True)
                    if not cloud_df.empty else missing)
        rows = [list(r) for _, r in combined.iterrows()]
        ok, _, err = _sync_to_gs("setAllAuditHistory", rows)
        return ok, (len(missing) if ok else 0), err
    except Exception as e:
        return False, 0, str(e)

def _reconstruct_disp_from_rows(rows):
    """從 cloud_rows 重建簡化版 disp DataFrame（日期×區 的 pivot，供草稿檢視）。
    rows 格式：[印日期, 區, 姓名] 或新格式 [印日期, 區, 姓名, 🔺, 治療欄]，只取前三欄。
    同區同印日多人時用「、」串接，不再只留第一個。
    """
    if not rows: return pd.DataFrame()
    try:
        cleaned = [[gs_date_to_ymd(r[0]), str(r[1]), str(r[2])] for r in rows]
        df = pd.DataFrame(cleaned, columns=["印日期","區","姓名"])
        pivot = df.pivot_table(index="區", columns="印日期", values="姓名",
                               aggfunc=lambda x: "、".join(x.dropna())).fillna("")
        pivot.index.name = None; pivot.columns.name = None
        return pivot
    except Exception:
        return pd.DataFrame([[str(r[0]), str(r[1]), str(r[2])] for r in rows],
                             columns=["印日期","區","姓名"])

# ── 印藥水定案本機草稿（app 重開可恢復）────────────────────
WEEK_DRAFT_PATH = os.path.join(HERE, "last_week_draft.json")

def _save_week_draft(rows, sheet0, disp_df):
    try:
        payload = {
            "rows": [[str(v) for v in r] for r in rows],
            "sheet0": str(sheet0),
            "disp": {
                "columns": [str(c) for c in disp_df.columns],
                "index":   [str(i) for i in disp_df.index],
                "data":    [[("" if str(v) in ("nan","None") else str(v))
                             for v in row] for row in disp_df.values]
            }
        }
        with open(WEEK_DRAFT_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    except Exception:
        pass

def _load_week_draft():
    if not os.path.exists(WEEK_DRAFT_PATH): return None
    try:
        with open(WEEK_DRAFT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def _clear_week_draft():
    try:
        if os.path.exists(WEEK_DRAFT_PATH): os.remove(WEEK_DRAFT_PATH)
    except Exception:
        pass


# ── LINE 群組公告文字格式 ─────────────────────────────────
def _build_line_txt(rows, disp_df=None):
    """LINE 群組公告：左欄顯示印藥水日期，每治療日獨立一列（不碰撞）。

    disp_df: 定案 DataFrame（index=一區/二區, columns=治療日欄標）。
    提供 disp_df 時從格子內容（如「張雅雯(7/1印)」）取得印藥水日期顯示於左欄。

    ⚠ v3.50（獨立稽查中-7）：以前這裡的年份是「整份公告共用一個」（從 rows[0] 猜
    一次），跟 v3.41 已經替「產生定案」修過的「逐格查表」完全不同步——跨年那一週
    （例如12月最後一週+1月第一週排在同一張表）後半段的月/日會被套上錯的年份，連帶
    治療日排序全錯（字串排序，"01/01"排在"12/31"前面）、標題起訖日顛倒、星期算錯。
    個人 LINE 提醒（送 GAS 的「本週名單」）一直是對的，因為那條路直接用 rows 裡
    已經算好的完整日期；出錯的只有這份「貼到 LINE 群組」的公告文字，造成「個人
    提醒跟群組公告對不上」（實測跨年週 1228~0103：公告寫「01/01是週四」，實際
    2027-01-01是週五；標題起訖日也顛倒）。
    改法：rows 每一列本來就有 [印日期(含年,已逐格查過表), 區, 姓名, 🔺, 治療欄key]，
    這裡直接拿 rows 建 (區,治療欄key)→印藥水日 的查表，不再從欄位標籤文字重新猜；
    治療日的年份則用「離印藥水日最近的年份」反推（治療日跟印藥水日本來就只差1~2
    個工作天，不會挑錯）。順帶修正中-4 延伸出來的問題：沒有(印)標注的格子代表
    這格沒有印藥水日（例如手動填進❌排不出，那個人根本沒送到雲端），以前會拿
    治療日充當印藥水日把她印出來，現在直接跳過不列進公告。
    """
    from datetime import datetime as _dt, date as _date
    DOW = {0:"週一",1:"週二",2:"週三",3:"週四",4:"週五",5:"週六",6:"週日"}

    # (區, 治療欄key) → 印藥水日字串。來自 rows，是「產生定案」逐格查表算出的正確值。
    date_lookup = {}
    for rr in rows:
        if len(rr) >= 5 and rr[2]:
            date_lookup[(str(rr[1]), str(rr[4]))] = str(rr[0])

    yr_val = pd.Timestamp.now().year
    for _r in rows:
        try: yr_val = int(str(_r[0]).split('-')[0]); break
        except Exception: pass

    def _dstr(yr, mo, dy): return f"{yr}-{mo:02d}-{dy:02d}"

    def _nearest_year(mo, dy, anchor_str):
        """已知月日、沒有年份時，挑一個離 anchor（印藥水日）最近的年份——治療日跟
        印藥水日本來就只差1~2個工作天，不會跨超過一年，不會挑錯。"""
        try:
            anchor = _dt.strptime(anchor_str, "%Y-%m-%d").date()
        except Exception:
            return yr_val
        best = None
        for y in (anchor.year - 1, anchor.year, anchor.year + 1):
            try: cand = _date(y, mo, dy)
            except ValueError: continue
            if best is None or abs((cand - anchor).days) < abs((best - anchor).days):
                best = cand
        return best.year if best else anchor.year

    def _parse_col(col_str, anchor_str=None):
        m = re.search(r'(\d{1,2})/(\d{1,2})', str(col_str))
        if m:
            mo, dy = int(m.group(1)), int(m.group(2))
            yr = _nearest_year(mo, dy, anchor_str) if anchor_str else yr_val
            return yr, mo, dy
        m = re.search(r'(\d{4})-(\d{2})-(\d{2})', str(col_str))
        if m: return int(m.group(1)), int(m.group(2)), int(m.group(3))
        return None, None, None

    def fmt(d_str):
        d = _dt.strptime(d_str, "%Y-%m-%d")
        return f"{DOW[d.weekday()]} {d.month:02d}/{d.day:02d}"  # 月日補零：07/06，確保等寬

    # treats: list of {t: 治療日str, p: 印藥水日str, a: {area: name}}
    # ⚠ v3.41 修正：每一「格」各自帶自己的印藥水日，不再一整欄共用一個。
    # 舊寫法用 `print_str is None` 只取該治療日欄「第一個」有(印)標注的日期，然後把
    # 整欄兩個區的人都算成那一天——但同一個治療日的一區/二區常常一個是白班(印T-1)、
    # 一個是小夜(印T-2)，印藥水日本來就不同天。實測4週48人次錯9次(19%)，被寫晚的人
    # 會晚一天備藥水。注意：送GAS的「本週名單」(個人LINE提醒用)日期一直是對的，
    # 錯的只有貼到LINE群組的這份公告文字，所以會出現「個人提醒跟群組公告對不上」。
    treats = []

    if disp_df is not None:
        for col in disp_df.columns:
            for area in ["一區","二區","三區"]:
                if area not in disp_df.index: continue
                v = str(disp_df.loc[area, col]).strip()
                if not v or v in ("nan","None","❌排不出"): continue
                nm_m = CELL_RE.match(v)
                if not nm_m:
                    # v3.50：沒有 (印) 標注＝這格沒有印藥水日（例如手動填進❌排不出，
                    # 見中-4）——這個人根本沒被送到雲端，公告不該把她印出來（以前會
                    # 拿治療日充當印藥水日，等於憑空生一個假日期，見上方說明）。
                    continue
                # 保留 🔺，但把「雙印」標記濾掉——group(4) 可能是「🔺雙印」，
                # 直接串上去會讓公告出現「廖緗玗雙印」這種被污染的姓名（v3.41）
                nm = nm_m.group(1).strip() + nm_m.group(4).replace("雙印", "").strip()
                if not nm: continue
                p_str = date_lookup.get((area, str(col)))
                if p_str is None:
                    # 防呆退路：理論上 disp 跟 rows 是同一輪「產生定案」算出來的，
                    # 不該對不上；對不上時至少用格子上寫的月日湊一個印藥水日。
                    p_mo, p_dy = int(nm_m.group(2)), int(nm_m.group(3))
                    p_str = _dstr(yr_val, p_mo, p_dy)
                t_yr, t_mo, t_dy = _parse_col(col, anchor_str=p_str)
                if t_yr is None: continue
                t_str = _dstr(t_yr, t_mo, t_dy)
                treats.append({"t": t_str, "p": p_str, "a": {area: nm}})
    else:
        # fallback：印藥水日分組，同一區同一天可能有多人，用 list 累積
        tmp = {}
        for r in rows:
            p_str, area, name = str(r[0]), str(r[1]), str(r[2])
            if not name or name in ("","❌排不出"): continue
            tmp.setdefault(p_str, {}).setdefault(area, []).append(name)
        for p_str in sorted(tmp):
            a = {area: "、".join(names) for area, names in tmp[p_str].items()}
            treats.append({"t": p_str, "p": p_str, "a": a})

    if not treats: return ""
    treats.sort(key=lambda x: x["t"])   # 依治療日排序

    # 標題用治療日範圍（說明這週涵蓋哪幾天）
    lines = [f"印藥水名單 (治療日 {fmt(treats[0]['t'])}~ {fmt(treats[-1]['t'])})", ""]

    # 依「印藥水日」合併輸出（不是依治療日）——不同治療日往前推剛好同一天印藥水時
    # （例如白班7/21治療日、小夜7/22治療日，往前推都是7/20），原本會各自出現一行、
    # 看起來像同一天印了兩次、容易誤會（2026-07-19、07-20兩次都有人反映看不懂），
    # 這裡先按印藥水日分組、同一天的人合併成一行。
    by_print = {}
    for e in treats:
        slot = by_print.setdefault(e["p"], {})
        for area, nm in e["a"].items():
            names = slot.setdefault(area, [])
            for nm_single in nm.split("、"):
                nm_single = nm_single.strip()
                if nm_single and nm_single not in names:
                    names.append(nm_single)

    for p_str in sorted(by_print):
        line = fmt(p_str)   # 左欄 = 印藥水日期
        for area in ["一區","二區","三區"]:
            names = by_print[p_str].get(area, [])
            if names: line += f"  {area}：{'、'.join(names)}"
        lines.append(line)

    roster = get_roster_full()
    if roster:
        printing = set()
        for e in treats:
            # 去掉 🔺 再比對；同一格可能有多人用「、」串接，拆開各別加入
            for nm_joined in e["a"].values():
                for nm_single in nm_joined.split("、"):
                    printing.add(re.sub(r'🔺', '', nm_single).strip())
        resting = [m["姓名"] for m in roster if m["姓名"] not in printing]
        if resting:
            lines += ["", "休息：" + "、".join(resting)]
    return "\n".join(lines)


# ── 💬 意見回饋：借用稽核歷史（特殊鍵「意見-時間」）存放，不動 LINE 程式 ──
APP_VER = "v3.53"
FEEDBACK_PREFIX = "意見-"

def push_feedback(step, detail, expect, urgency, who):
    """把一筆回饋寫進雲端（不影響排班/稽核：狀態欄非『稽核/休』故公平輪序會略過）。
    回傳 (ok, 錯誤訊息)（v3.50 獨立稽查低-19）。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return False, "尚未設定 Apps Script 網址或密鑰"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")   # 含微秒 → 每筆鍵唯一
    key = FEEDBACK_PREFIX + now
    blob = "問題：" + (detail or "").strip()
    if (expect or "").strip(): blob += "｜期望：" + expect.strip()
    blob += "｜版本：" + APP_VER
    row = [key, (step or ""), (who or "").strip() or "(未留名)", (urgency or ""), blob]
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "setAuditResult", "secret": WRITE_SECRET,
                                   "key": key, "rows": [row]},
                             timeout=20)
        if not resp.ok: return False, f"雲端回應碼異常：HTTP {resp.status_code}"
        d = resp.json()
        if not d.get("ok"): return False, f"雲端回報失敗：{d.get('error') or d}"
        return True, ""
    except Exception as e:
        return False, f"例外：{e}"

def _mask_name(name):
    """公開檢視用：把留言者姓名換成固定亂碼（同一人代碼一樣，但看不出是誰）。"""
    name = (name or "").strip()
    if not name or name == "(未留名)":
        return "匿名"
    return "訪客#" + hashlib.md5(name.encode("utf-8")).hexdigest()[:4]

def fetch_feedback_list():
    """讀回所有回饋（稽核歷史裡 月份 以『意見-』開頭的列），新到舊。留言者以亂碼呈現。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return []
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "getAuditHistory", "secret": WRITE_SECRET},
                             timeout=20)
        rows = resp.json().get("rows") or []
        if len(rows) < 2: return []
        hdr = [str(x).strip() for x in rows[0]]
        iM, iC, iN, iS, iP = (hdr.index("月份"), hdr.index("卡號"), hdr.index("姓名"),
                              hdr.index("狀態"), hdr.index("位置"))
        out = []
        for r in rows[1:]:
            k = str(r[iM]).strip()
            if not k.startswith(FEEDBACK_PREFIX): continue
            out.append({
                "時間": k[len(FEEDBACK_PREFIX):],
                "步驟": str(r[iC]).strip(),
                "急迫": str(r[iS]).strip(),
                "內容": str(r[iP]).strip(),
                "留言者": _mask_name(str(r[iN])),
            })
        out.reverse()   # 新的在最上面
        return out
    except Exception:
        return []

def fetch_latest_banbiao():
    """從雲端（Apps Script 讀 Gmail「班表」標籤的最新 Excel 附件）抓班表。
    回傳 (bytes, 說明) 或 (None, 錯誤訊息)。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET:
        return None, "雲端尚未設定"
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": "getLatestBanbiao", "secret": WRITE_SECRET},
                             timeout=60)
        d = resp.json()
        if not d.get("ok"):
            return None, d.get("error", "未知錯誤")
        data = base64.b64decode(d["b64"])
        info = f'{d.get("filename","班表")}（{d.get("date","")}）'
        return data, info
    except Exception as e:
        return None, str(e)

def build_corrected_history(cloud_rows, sheet_name, prev_hist_bytes):
    """用玉繡實際定案（cloud_rows）覆蓋 排班.py 原排的歷史，確保公平輪序正確。
    cloud_rows: [[印日期, 區, 姓名], ...]
    prev_hist_bytes: 排班.py 寫的 排班紀錄.csv bytes（含本週舊資料，會被替換）
    """
    roster = get_roster_names()
    if not roster: return prev_hist_bytes   # 讀不到名單就維持原版

    # 玉繡定案後實際印藥水的人（去掉空值）
    printed_names = {str(r[2]).strip() for r in cloud_rows if r[2]}

    # 讀舊歷史，移除本週（排班.py 版），保留其他週
    headers = ["週次","卡號","姓名","狀態","治療日"]
    existing = []
    if prev_hist_bytes:
        try:
            df_h = pd.read_csv(io.BytesIO(prev_hist_bytes), encoding="utf-8-sig",
                               dtype=str, keep_default_na=False)
            existing = df_h[df_h["週次"].astype(str) != str(sheet_name)].values.tolist()
        except Exception: pass

    # 依玉繡定案重建本週紀錄
    new_rows = []
    for name, card in roster.items():
        status = "印" if name in printed_names else "休"
        new_rows.append([sheet_name, card, name, status, ""])

    all_rows = existing + new_rows
    df_new = pd.DataFrame(all_rows, columns=headers)
    return df_new.to_csv(index=False).encode("utf-8-sig")


def build_corrected_audit_history(edited_ak, month_key, prev_hist_bytes):
    """用玉繡實際改過的稽核名單（edited_ak）覆蓋 稽核.py 原排的歷史。

    v3.41 新增。印藥水那邊早就有 build_corrected_history()（app.py 檔頭寫的
    「Fix1：公平歷史學玉繡實際決定，而非程式原排」），但**稽核這邊從來沒做過**：
    送出時 `ak_hist_b` 來自子行程原封不動的產出，而 LINE 通知用的是玉繡點格子改過的
    `edited_ak`，兩者來源不同、中間沒有任何同步。結果就是玉繡把某格從 A 改成 B →
    B 收到通知去稽核，雲端歷史卻記「A=稽核、B=休」，下個月 cost 對兩人各錯一格，
    而且會**逐月累積**——這正是「玉繡實際排的跟系統差異越來越大」的其中一個來源。

    edited_ak: DataFrame，欄位 區/組/班次/稽核者（稽核者可能帶「(跨區)」後綴）
    prev_hist_bytes: 稽核.py 寫的 稽核紀錄_輸出.csv bytes（本月那批會被替換）
    """
    roster = get_roster_names()          # {姓名: 卡號}（單一來源，v3.50）
    if not roster or edited_ak is None or edited_ak.empty:
        return prev_hist_bytes             # 讀不到名單/沒有編輯結果 → 維持原版

    headers = ["月份","卡號","姓名","狀態","位置"]
    # 玉繡定案後，每個人實際被分配到的位置（區/組/班次）
    pos_of = {}
    try:
        for _, r in edited_ak.iterrows():
            # v3.50（獨立稽查低-19）：跟 send_audit_notices() 統一成同一條 regex（含全形
            # 括號），避免兩邊清洗規則不同調又長出新的名字對不上問題。
            nm = re.sub(r'[\(（].*?[\)）]', '', str(r.get("稽核者",""))).strip()   # 去掉「(跨區)」等括號註記
            if not nm: continue
            pos_of[nm] = f"{str(r.get('區','')).strip()}/{str(r.get('組','')).strip()}/{str(r.get('班次','')).strip()}"
    except Exception:
        return prev_hist_bytes             # 欄位對不上就別亂改，維持原版

    # 讀舊歷史，移除本月（稽核.py 版），保留其他月
    existing = []
    if prev_hist_bytes:
        try:
            df_h = pd.read_csv(io.BytesIO(prev_hist_bytes), encoding="utf-8-sig",
                               dtype=str, keep_default_na=False)
            existing = df_h[df_h["月份"].astype(str) != str(month_key)].values.tolist()
        except Exception: pass

    new_rows = []
    for name, card in roster.items():
        if name in pos_of:
            new_rows.append([month_key, card, name, "稽核", pos_of[name]])
        else:
            new_rows.append([month_key, card, name, "休", ""])

    df_new = pd.DataFrame(existing + new_rows, columns=headers)
    return df_new.to_csv(index=False).encode("utf-8-sig")


# ── 雲端歷史：讀取 / 推送 ──────────────────────────────────
def fetch_history_csv(action):
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return None
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": action, "secret": WRITE_SECRET},
                             timeout=20)
        if resp.ok:
            data = resp.json()
            if data.get("ok") and data.get("rows"):
                rows = data["rows"]
                if len(rows) < 2: return None
                df = pd.DataFrame(rows[1:], columns=rows[0])
                return df.to_csv(index=False).encode("utf-8-sig")
    except Exception: pass
    return None

def push_history(action, hist_bytes, key):
    """回傳 (ok, n_rows, detail)：n_rows 是實際送出的筆數，detail 是失敗時的原因，
    方便診斷「回報成功但其實沒送資料」這種 GAS 端不驗證空陣列的狀況。"""
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return False, 0, "未設定 APPS_SCRIPT_URL/WRITE_SECRET"
    if not hist_bytes: return False, 0, "hist_bytes 是空的(build_corrected_history 沒有產生資料，可能組員名單讀取失敗)"
    try:
        df = pd.read_csv(io.BytesIO(hist_bytes), encoding="utf-8-sig",
                          dtype=str, keep_default_na=False)
        key_col = df.columns[0]
        week_rows = df[df[key_col].astype(str) == str(key)].values.tolist()
        if not week_rows:
            return False, 0, f"key='{key}' 在資料裡完全比對不到任何列（key_col='{key_col}'），送出前就已經是 0 筆"
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action": action, "secret": WRITE_SECRET,
                                   "key": key, "rows": week_rows},
                             timeout=20)
        rj = resp.json()
        ok = resp.ok and rj.get("ok", False)
        if ok:
            _parts = []
            if "before" in rj or "after" in rj:
                _parts.append(f"寫入前{rj.get('before','?')}列→寫入後{rj.get('after','?')}列")
            if "gotRows" in rj:
                _parts.append(f"GAS收到{rj.get('gotRows')}筆(送出{len(week_rows)}筆) key='{rj.get('gotKey','?')}'")
            if "ssId" in rj:
                _parts.append(f"寫入試算表: {rj.get('ssName','?')} (ID尾碼…{str(rj.get('ssId',''))[-8:]})")
            _detail = "GAS回報：" + "；".join(_parts) if _parts else ""
            return ok, len(week_rows), _detail
        return False, 0, f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return False, 0, f"例外：{e}"

# Fix2：稽核送出後 LINE 通知稽核者
def send_audit_notices(month_key, audit_df):
    """從稽核名單 DataFrame 解析每人位置，呼叫 Apps Script 發 LINE 通知。"""
    # v3.50（獨立稽查低-16）：呼叫端一律 `sent, miss, failed_names = send_audit_notices(...)`
    # 要拆 3 個值，但這裡兩條早退路徑原本回傳 `0, 0`（只有 2 個值），只要沒設定
    # APPS_SCRIPT_URL/WRITE_SECRET，或這個月稽核名單解析不出任何人（例如全部都是
    # 「❌排不出」），呼叫端就會直接 ValueError 崩潰。統一成 3-tuple。
    if not APPS_SCRIPT_URL or not WRITE_SECRET: return 0, 0, []
    notices = []
    seen = set()
    for _, row in audit_df.iterrows():
        # v3.50（獨立稽查低-19）：這裡原本只精準砍掉「(跨區)」這個字面字串，跟
        # build_corrected_audit_history() 的 `re.sub(r'\(.*?\)', '', ...)` 不是同一套
        # 清洗規則——audit_df 是可自由編輯的 data_editor 結果，玉繡如果打了其他括號
        # 註記（例如「(代)」、全形括號、或任何不是剛好等於「(跨區)」的內容），這裡就
        # 會漏清，名字對不到組員名單、也對不到 build_corrected_audit_history 存進歷史
        # 的乾淨姓名，導致「歷史記錄有這個人、卻沒收到 LINE 通知」的不一致。改用同一條
        # regex，兩邊統一。
        name = re.sub(r'[\(（].*?[\)）]', '', str(row.get("稽核者",""))).strip()
        if not name or name == "❌排不出" or name in seen: continue
        seen.add(name)
        area  = str(row.get("區","")).strip()
        group = str(row.get("組","")).strip()
        band  = str(row.get("班次","")).strip()
        notices.append({"name": name, "position": f"{area}/{group}/{band}"})
    if not notices: return 0, 0, []
    try:
        resp = requests.post(APPS_SCRIPT_URL,
                             json={"action":"sendAuditNotice","secret":WRITE_SECRET,
                                   "month":month_key,"notices":notices},
                             timeout=20)
        if resp.ok:
            d = resp.json()
            # v3.43：GAS v6.2 起會檢查 LINE API 回應碼，把「真的沒送出去」的人另外
            # 回報在 failed/failedNames（舊版 GAS 沒有這兩個欄位，取不到就當 0/空）。
            return d.get("sent",0), d.get("miss",0), list(d.get("failedNames") or [])
    except Exception: pass
    return 0, 0, []


# ── 月稽核 Stage1：快速偵測班型 ──────────────────────────
def detect_shifts_quick(data, yy, mm, filename_hint=None):
    """稽核 Stage1「📊 預覽班型」：從班表猜每人白班/小夜。

    v3.50：改成呼叫 稽核.py 的 parse_sheet()（見上方 _audit_shared 匯入），不再自己
    另外解析日期——沿用它已經測過的 4 層備援（表格內完整日期→同表其他日期借年份→
    檔名/分頁名借年份→整排讀不到時依檔名推算），日期格被打成文字或民國格式都不會
    再整批變 ❓。filename_hint 傳上傳檔案的檔名（例如「115.08.10~115.08.16.xls」），
    給 parse_sheet 的第3層備援用；沒有就退回舊行為（可能猜不到年份）。
    """
    if _audit_shared is None:
        return pd.DataFrame(columns=["卡號","姓名","程式猜測","確認班型"])
    person = {}
    try:
        xls = pd.ExcelFile(io.BytesIO(data))
        for sn in xls.sheet_names:
            try: df = pd.read_excel(io.BytesIO(data), sheet_name=sn, header=None)
            except Exception: continue
            status, name_of, by_name, _mon = _audit_shared.parse_sheet(df, filename_hint, sn)
            for card, name in name_of.items():
                person.setdefault(card, {"card": card, "name": name, "white": 0, "night": 0})
            for card, dmap in status.items():
                person.setdefault(card, {"card": card, "name": name_of.get(card, ""),
                                         "white": 0, "night": 0})
                for d, tup in dmap.items():
                    if d is None or d.year != yy or d.month != mm: continue
                    shift = str(tup[1]).strip()
                    if shift.startswith("D"): person[card]["white"] += 1
                    elif shift.startswith("E"): person[card]["night"] += 1
    except Exception: pass
    result=[]
    for key,info in person.items():
        w,n=info["white"],info["night"]
        detected="❓" if w==0 and n==0 else ("白班" if w>=n else "夜班")
        result.append({"卡號":info["card"],"姓名":info["name"],"程式猜測":detected,"確認班型":detected})
    result.sort(key=lambda x:x["姓名"])
    return pd.DataFrame(result) if result else pd.DataFrame(columns=["卡號","姓名","程式猜測","確認班型"])


def _file_key(up): return f"{up.name}_{up.size}"


# ── Streamlit 設定 ─────────────────────────────────────────
st.set_page_config(page_title="透析藥水排班", page_icon="💊", layout="wide")

SHEET_URL = "https://docs.google.com/spreadsheets/d/1UF-DjDcrIPDbp016vkIyV9zsLF6Qz5EBo6Bq-z6t-Js/edit"

try:
    APPS_SCRIPT_URL = st.secrets.get("APPS_SCRIPT_URL", "")
    WRITE_SECRET    = st.secrets.get("WRITE_SECRET", "")
except Exception:
    APPS_SCRIPT_URL = ""; WRITE_SECRET = ""

# ── 測試模式（小巫用）：排班演算法照常跑，但不寫雲端、不送 LINE ────
with st.sidebar:
    st.markdown("### ⚙️ 設定")
    TEST_MODE = st.toggle("🧪 測試模式（小巫用）", value=False,
                          help="開啟後可完整測試排班流程，但不會真的寫到雲端、也不會送 LINE 通知。")
    if TEST_MODE:
        st.warning("測試模式已開啟。\n\n所有「送到雲端」和「送通知」按鈕均為模擬，不影響正式資料。")

if TEST_MODE:
    st.error("🧪 測試模式 — 排班照常跑，但不寫雲端、不送 LINE。關掉左側開關即可切回正式模式。")

st.title("💊 透析藥水排班")
st.caption("上傳班表 Excel → 出名單(表格)。可直接點格子改人名。跨區標 🔺。")
st.caption(f"🟢 版本 {APP_VER}（延續上一版稽核bug往下查：①公平累計逐人明細（含「休息」"
           "字樣）誤混進「注意事項」警告清單 ②稽核「其他檔案下載」的Excel/文字檔是"
           "點格子改之前的舊版本，貼公告欄/傳LINE群組可能傳達錯誤名單——都已改成依"
           "你目前的修改重新產生）· 2026-08-10")

# ── 📊 首頁顯眼統計＋本機備份落後提醒（2026-07-20加，v3.38）─────────────
# 目的：2026-07-19~20那次「7/20資料被同步按鈕蓋掉」事件，玉繡是三週後才發現雲端資料
# 不對。這裡把「雲端目前累積筆數／最新一週」放在每次打開網頁都會看到的顯眼位置，
# 玉繡平常掃一眼「筆數有沒有變多、最新一週對不對」就能及早發現異常，不用等到查統計
# 才發現。同時主動比對本機git備份CSV是否落後於雲端，落後就直接顯示警告，不用等到
# 有人誤按「同步本機CSV→雲端」才發現備份是舊的。
@st.cache_data(ttl=300, show_spinner=False)
def _home_audit_snapshot():
    """首頁的稽核統計：累積筆數 + 最新月份。
    v3.47：使用者反映首頁只看得到印藥水、看不到稽核（「我的藥水稽核累積筆數咧」）——
    稽核跟印藥水一樣是每個月要送雲端的東西，同樣需要「數字有沒有在增加」一眼可判斷，
    不然又要等到對不上才發現（接續包第十六節那次就是三週後才發現）。
    回傳 (筆數, 最新月份) 或 (None, None)。"""
    df, _ = fetch_audit_history_full_raw()
    if df is None or df.empty:
        return None, None
    m = df["月份"].astype(str).str.strip()
    # 只算正常月份鍵，草稿/意見-/統計- 這些特殊列不列入
    real = df[m.str.match(r"^\d{3,4}-\d{2}$")]
    if real.empty:
        return len(df), None
    def _to_ce(k):
        y, mo = str(k).split("-")
        y = int(y)
        return (y + 1911 if y < 1911 else y, int(mo))   # 民國(115-07)/西元都能排
    months = sorted(real["月份"].astype(str).str.strip().unique(), key=_to_ce)
    return len(real), months[-1]

@st.cache_data(ttl=300, show_spinner=False)
def _home_stats_snapshot():
    # v3.50（獨立稽查中-6）：這個裝飾器原本掛在這裡，v3.47 新增 _home_audit_snapshot
    # 時被插在裝飾器跟這個函式定義之間，裝飾器就落到 _home_audit_snapshot 頭上、
    # 這支反而裸奔——每次 Streamlit rerun（玉繡按任何按鈕、改任何格子）都會多打一次
    # getScheduleHistory，App 變鈍、Apps Script 執行配額也被無謂消耗。
    cloud_df, _ = fetch_schedule_history_raw()
    n_audit, latest_audit = _home_audit_snapshot()
    if cloud_df is None or cloud_df.empty:
        # 排班讀不到但稽核讀得到時，也要把稽核顯示出來，不要整塊消失
        if n_audit is None: return None
        return {"n_cloud": None, "latest_cloud_week": None, "n_local": 0,
                "latest_local_week": None, "n_audit": n_audit, "latest_audit": latest_audit}
    def _latest_week(weeks):
        real = [w for w in weeks if re.match(r"^\d{4}~\d{4}$", str(w))]
        return real[-1] if real else None   # 取「最後一列」而非字串排序，避免跨年份排序錯誤
    n_cloud = len(cloud_df)
    latest_cloud_week = _latest_week(cloud_df["週次"].astype(str).tolist())
    n_local, latest_local_week = 0, None
    try:
        csv_path = os.path.join(HERE, "排班紀錄.csv")
        if os.path.exists(csv_path):
            df_local = pd.read_csv(csv_path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
            n_local = len(df_local)
            latest_local_week = _latest_week(df_local["週次"].astype(str).tolist())
    except Exception:
        pass
    return {"n_cloud": n_cloud, "latest_cloud_week": latest_cloud_week,
            "n_local": n_local, "latest_local_week": latest_local_week,
            "n_audit": n_audit, "latest_audit": latest_audit}

_snap = _home_stats_snapshot()
if _snap:
    _s1, _s2 = st.columns(2)
    _s1.metric("📊 雲端排班歷史累積筆數", _snap["n_cloud"] if _snap["n_cloud"] is not None else "—")
    _s2.metric("📅 雲端最新一週", _snap["latest_cloud_week"] or "—")
    # v3.47：稽核也要有，跟印藥水並列。稽核是每月一次，數字變化比較慢是正常的。
    _a1, _a2 = st.columns(2)
    _a1.metric("🩺 雲端稽核歷史累積筆數", _snap.get("n_audit") if _snap.get("n_audit") is not None else "—")
    _a2.metric("🗓 雲端最新稽核月份", _snap.get("latest_audit") or "—")
    st.caption("💡 上面兩個（印藥水）平常應該**每週**增加、下面兩個（稽核）**每月**更新。"
               "如果該增加卻好幾次沒變、或數字忽然變小，代表雲端資料可能被誤動過，"
               "請截圖跟AI反映，不要等到統計對不上才發現。")
    if (_snap["latest_local_week"] and _snap["latest_cloud_week"]
            and _snap["latest_local_week"] != _snap["latest_cloud_week"]):
        st.warning(f"⚠️ 本機git備份CSV最新只到「{_snap['latest_local_week']}」，比雲端的"
                   f"「{_snap['latest_cloud_week']}」舊——備份沒跟上雲端。目前「同步本機CSV→雲端」"
                   f"已經是「只補不蓋」，不會因此蓋掉雲端資料，但建議還是請AI把本機備份補到跟雲端一致。")
else:
    st.caption("（雲端統計暫時讀不到，不影響排班功能本身——如果一直讀不到，請告訴AI檢查一下）")

with st.expander("📖 第一次用？點我看「3 步驟」（給玉繡）", expanded=False):
    st.markdown("""
### 每週印藥水，只要 3 步：
**1️⃣ 上傳班表** → 選「🟦 每週印藥水」，把這週班表 Excel 傳上來。
**2️⃣ 排 + 微調** → 選「這一週」分頁 → 按「➡️ 排印藥水」。想換人就直接點格子改名字。
**3️⃣ 產生定案 → 送到雲端** → 按「✅ 產生定案」→「🚀 送到雲端」。完成！系統每晚自動 LINE 提醒，並記住這週誰印、誰休，下週排班更公平。

---
### 每月稽核（推薦「⚡ 快速點選」，免上傳）：
**1️⃣ 切換模式** → 上方選「🟩 每月稽核」→ 稽核方式留在「⚡ 快速點選」，選好「年」「月」。
**2️⃣ 點選白/夜＋區** → 畫面列出組員，系統已帶出上個月的設定；只要改這個月有變動的人，點一下白班/小夜、一區/二區即可。
　💾 只填一半沒關係——按「**暫存草稿**」存起來，明天打開會自動接續填。
**3️⃣ 排稽核** → 按「✅ 排稽核（快速）」。
**4️⃣ 送到雲端** → 名單排出來後按「🚀 送稽核結果到雲端」。每位稽核者馬上收到 LINE 通知，告訴他們「這個月負責哪一班稽核」。

> 也可改用「📤 上傳班表分析」：傳這個月的週班表 Excel，系統自己猜白/夜＋區，你再確認。班表要「Excel 檔本人」，截圖不行。
""")

# ── 🔊 語音導覽（點按鈕，用瀏覽器內建的聲音直接念出來，免音檔）──────────
_VOICE_YAO = (
    "玉繡你好。我們一步一步來，不用緊張。"
    "第一步，先打開排班網頁。如果畫面在睡覺、黑黑的，就點一下把它叫醒，等它跑一下。"
    "打開以後，看上面，選每週印藥水那個藍色的。"
    "接著，按上傳班表，把這個禮拜的班表，Excel 檔，傳上去。記得，要 Excel 檔本人，截圖不行喔。"
    "傳好以後，選這一週的分頁。通常系統會自己選好最接近今天的，你看一下對不對就好。"
    "然後，按排印藥水，等它幾秒鐘。"
    "等一下，就會跑出一張名單表格。如果想換人，直接點那一格，把名字改掉就好。"
    "改好以後，按產生定案。"
    "最後，按送到雲端。看到氣球飛出來，就成功囉。"
    "這樣就好了。系統每次都會記住這週誰印、誰休息，下次排班會自動讓印比較少的人先印，越排越公平。"
    "你不用再做別的事，輕鬆一下。"
)
_VOICE_JI = (
    "玉繡你好。這個更簡單，連班表都不用傳喔。"
    "第一步，一樣先打開排班網頁，在睡的話點一下叫醒它。"
    "打開以後，看上面，選每月稽核那個綠色的。"
    "下面會出現稽核方式，讓它停在快速點選就好，不用上傳東西。"
    "接著，選好年跟月。"
    "下面就會跑出組員的名單。系統會自動幫你帶上個月的設定。"
    "你只要看每一個人，是白班還是小夜，是一區還是二區。這個月有變動的，點一下改；沒變的就不用動。"
    "如果一下子填不完，沒關係，按暫存草稿，明天打開它會自動幫你帶回來，接著填就好。"
    "都確認好了，按排稽核。"
    "等一下，就會跑出這個月的稽核名單。想換人，一樣直接點格子改。"
    "最後，按送稽核結果到雲端。每一位稽核的人，就會收到 LINE 通知。"
    "這樣就完成囉。你做得很好，放輕鬆。"
)
with st.expander("🔊 語音導覽（不會用？點一下，手機念給你聽）", expanded=False):
    _btn = ("padding:14px 18px;margin:6px;border:none;border-radius:12px;"
            "font-size:18px;color:#fff;cursor:pointer;")
    _voice_html = """
    <div style="font-family:-apple-system,'PingFang TC',sans-serif;text-align:center">
      <button style="BTN background:#2563eb" onclick="sayIt(YAO)">🔵 印藥水導覽</button>
      <button style="BTN background:#16a34a" onclick="sayIt(JI)">🟢 稽核導覽</button>
      <button style="BTN background:#6b7280" onclick="stopAll()">⏹ 停止</button>
      <p style="color:#666;font-size:13px;margin-top:8px">點藍色聽「印藥水」、綠色聽「稽核」；正常語速、每句之間會停一下讓你跟著做。要停就按停止。</p>
    </div>
    <script>
      var YAO = __YAO__;
      var JI  = __JI__;
      var _stop = false;
      function _speakSeq(arr, i){
        if(_stop || i >= arr.length){ return; }
        var u = new SpeechSynthesisUtterance(arr[i]);
        u.lang = 'zh-TW';
        u.rate = 1.0;                                   // 正常語速
        u.onend = function(){
          // 有動作的句子（按/選/傳/點/改/存/送）多停一下，讓人來得及做
          var gap = /[按選傳點改存送]/.test(arr[i]) ? 4500 : 2500;
          setTimeout(function(){ _speakSeq(arr, i+1); }, gap);
        };
        window.speechSynthesis.speak(u);
      }
      function sayIt(t){
        _stop = false;
        try{ window.speechSynthesis.cancel(); }catch(e){}
        var parts = t.split('。');
        var arr = [];
        for(var k=0;k<parts.length;k++){
          var s = parts[k].replace(/^\\s+|\\s+$/g,'');
          if(s.length>0){ arr.push(s + '。'); }
        }
        _speakSeq(arr, 0);
      }
      function stopAll(){ _stop = true; try{ window.speechSynthesis.cancel(); }catch(e){} }
    </script>
    """
    _voice_html = (_voice_html
                   .replace("BTN", _btn)
                   .replace("__YAO__", json.dumps(_VOICE_YAO))
                   .replace("__JI__", json.dumps(_VOICE_JI)))
    components.html(_voice_html, height=175)

# ── 💬 回報問題／給建議（誰都能填，存到雲端給管理者看）──────────────
with st.expander("💬 有問題？回報一下（會存起來，大家都看得到）", expanded=False):
    st.caption("不用很會講～照下面選一選、簡單打幾個字就好。送出前可以先看下面「📋 大家回報過的問題」，看看是不是有人提過了。")
    fb_step = st.selectbox("① 你卡在哪一步？",
        ["上傳班表", "排印藥水", "微調名單", "送到雲端",
         "稽核－點選白夜/區", "暫存草稿", "收不到 LINE 通知", "語音導覽", "其他／不確定"],
        key="fb_step")
    fb_detail = st.text_area("② 發生什麼事？（你看到什麼、按了什麼、畫面寫什麼）", key="fb_detail")
    fb_expect = st.text_input("③ 你希望它變怎樣？（可不填）", key="fb_expect")
    fb_urg = st.radio("④ 急不急？", ["還好", "有點急", "很急"], horizontal=True, key="fb_urg")
    fb_who = st.text_input("⑤ 你的名字（可不填）", key="fb_who")
    if st.button("📨 送出回報", type="primary", key="fb_send"):
        if not fb_detail.strip():
            st.warning("請至少在 ② 簡單描述一下發生什麼事 🙏")
        elif not (APPS_SCRIPT_URL and WRITE_SECRET):
            st.error("雲端尚未設定，無法送出。")
        else:
            _fb_ok, _fb_err = push_feedback(fb_step, fb_detail, fb_expect, fb_urg, fb_who)
            if _fb_ok:
                st.success("✅ 已送出！謝謝你的回報，我們看到會處理 🙏")
                st.balloons()
            else:
                st.error(f"送出失敗：{_fb_err}")

# ── 📋 大家回報過的問題（公開；名字以亂碼呈現保護隱私；按「載入」才去抓）──
with st.expander("📋 大家回報過的問題（公開・看看有沒有人提過）", expanded=False):
    st.caption("名字會用亂碼遮起來，看不出是誰。你可以用「時間／內容」認出自己那筆。")
    if st.button("🔄 載入回報", key="fb_load"):
        st.session_state["_fbs"] = fetch_feedback_list()
    if "_fbs" in st.session_state:
        fbs = st.session_state["_fbs"]
        if not fbs:
            st.info("目前還沒有任何回報。")
        else:
            st.caption(f"共 {len(fbs)} 則（新到舊）")
            st.dataframe(pd.DataFrame(fbs), use_container_width=True, hide_index=True)

st.markdown("#### 1️⃣ 選種類")
mode = st.radio("要排哪一種？", ["🟦 每週印藥水", "🟩 每月稽核", "📊 統計管理"], horizontal=True)

# 每月稽核可選「快速點選（免上傳）」或「上傳班表分析」；每週印藥水可選雲端自動抓或自己上傳
audit_quick = False
week_cloud = False
if mode.startswith("📊"):
    pass   # 統計管理不需要上傳
elif mode.startswith("🟩"):
    method = st.radio("稽核方式", ["⚡ 快速點選（免上傳 Excel，推薦）", "📤 上傳班表分析"],
                      horizontal=True)
    audit_quick = method.startswith("⚡")
else:
    src = st.radio("班表從哪來？", ["📥 用雲端最新班表（免上傳，推薦）", "📤 自己上傳 Excel"],
                   horizontal=True)
    week_cloud = src.startswith("📥")

data = None; sheets = []
if mode.startswith("📊"):
    pass   # 不需要 data
elif mode.startswith("🟦") and week_cloud:
    # 從雲端 Gmail 自動抓最新班表（文書把班表寄進來後，這裡一鍵抓）
    if st.button("📥 抓取雲端最新班表", type="primary"):
        with st.spinner("從雲端抓最新班表中…"):
            _b, _info = fetch_latest_banbiao()
        if _b is None:
            st.error("抓不到雲端班表：" + _info + "（你也可以改選『自己上傳』）")
        else:
            st.session_state["cloud_banbiao"] = (_b, _info)
            # 只清排班輸出，保留上次定案（cloud_rows/disp），auto-apply 才能套回
            st.session_state.pop("yao", None)
            st.session_state.pop("yao_edit", None)
    if "cloud_banbiao" in st.session_state:
        data, _info = st.session_state["cloud_banbiao"]
        st.success("✅ 已載入雲端班表：" + _info)
        try:
            sheets = pd.ExcelFile(io.BytesIO(data)).sheet_names
        except Exception as e:
            st.error(f"讀不到班表分頁：{e}"); st.stop()
    else:
        st.info("👆 按「📥 抓取雲端最新班表」，把文書寄進來的最新班表抓進來。")
        st.stop()
elif not audit_quick:                     # 自己上傳（每週印藥水 / 上傳班表稽核）
    up = st.file_uploader("上傳班表 Excel（.xls / .xlsx）", type=["xls","xlsx"])
    if not up:
        st.info("👆 先上傳班表 Excel（含每人每天班別/床號的那種檔）。截圖不行喔！")
        st.stop()
    fk = _file_key(up)
    if st.session_state.get("_last_file") != fk:
        for k in ["yao","cloud_rows","cloud_disp","cloud_sheet0","ak","ak_shifts","ak_month_key","yao_edit"]:
            st.session_state.pop(k, None)
        st.session_state["_last_file"] = fk
    data = up.read()
    try:
        sheets = pd.ExcelFile(io.BytesIO(data)).sheet_names
    except Exception as e:
        st.error(f"讀不到班表分頁：{e}"); st.stop()


# ═══════════════════════ 每週印藥水 ═══════════════════════
if mode.startswith("🟦"):

    # ── 📬 自動偵測雲端草稿（首次進入印藥水模式時）──────────
    if "cloud_rows" not in st.session_state and APPS_SCRIPT_URL and WRITE_SECRET:
        if "week_draft_auto" not in st.session_state:
            with st.spinner("自動偵測雲端草稿…"):
                _ar, _as = fetch_week_draft()
            st.session_state["week_draft_auto"] = (_ar, _as) if _ar else None
        _pending = st.session_state.get("week_draft_auto")
        if _pending:
            _ar, _as = _pending
            _stale = _week_looks_stale(_as)
            if _stale:
                st.warning(f"📬 偵測到雲端有一份排班草稿（{_as}），但這個週次看起來**不像最近這週**"
                           "——可能是之前忘記清掉的舊草稿。載入後**不要直接送出**，"
                           "請先確認內容是不是這週的。")
            else:
                st.info(f"📬 偵測到玉繡的排班草稿（{_as}），要載入確認嗎？")
            _dc1, _dc2 = st.columns(2)
            if _dc1.button("✅ 載入草稿", key="auto_draft_load"):
                st.session_state["cloud_rows"]   = _ar
                st.session_state["cloud_disp"]   = _reconstruct_disp_from_rows(_ar)
                st.session_state["cloud_sheet0"] = _as
                st.session_state["cloud_rows_source"] = "draft"
                st.session_state.pop("week_draft_auto", None)
                st.rerun()
            if _dc2.button("✕ 略過", key="auto_draft_skip"):
                st.session_state["week_draft_auto"] = None
                st.rerun()

    # 草稿恢復：關掉 app 再回來，顯示上次定案
    if "cloud_rows" not in st.session_state:
        _wd = _load_week_draft()
        if _wd:
            st.info(f"📂 找到上次的定案（{_wd.get('sheet0','')}），要恢復嗎？")
            _cy, _cn = st.columns(2)
            if _cy.button("📋 載入草稿（確認後再送雲端）"):
                try:
                    _d = _wd["disp"]
                    st.session_state["cloud_rows"]   = _wd["rows"]
                    st.session_state["cloud_disp"]   = pd.DataFrame(
                        _d["data"], index=_d["index"], columns=_d["columns"])
                    st.session_state["cloud_sheet0"] = _wd["sheet0"]
                    st.session_state["cloud_rows_source"] = "draft"
                    st.rerun()
                except Exception as _e:
                    st.error(f"恢復失敗：{_e}")
            if _cn.button("❌ 不用，重新排"):
                _clear_week_draft(); st.rerun()

    # 正常排班流程（需要班表資料）
    if data is not None:
        st.markdown("#### 2️⃣ 選這一週 → 排班 → 微調")
        best = _best_sheet_index(sheets)
        sheet = st.selectbox("選「這一週」的分頁", sheets, index=best)

        with st.expander("⚙️ 本週特殊設定（選填）"):
            force_names_raw = st.text_area(
                "本週放假但可印藥水的人（一行一個姓名，不填則照班別自動判斷）",
                value=st.session_state.get("force_print_names",""),
                placeholder="例：\n黃怡璇\n潘冠秀",
                help="班別看起來是假（特休/公假等）但玉繡確認可以印的人，填在這裡就會被排入候選。"
                     "建議打全名最保險；只打名字（例：怡璇）也可以，但如果打錯字、對不到人，"
                     "畫面下方會跳警告告訴你哪一筆沒生效。"
            )
            st.session_state["force_print_names"] = force_names_raw

        if st.button("➡️ 排印藥水", type="primary"):
            with st.spinner("讀取雲端歷史 + 排班中…"):
                config_overrides = {}
                if APPS_SCRIPT_URL and WRITE_SECRET:
                    # v3.41：讀不到雲端資料時要明講。舊版 `if hist_csv:` 沒有 else，
                    # 抓失敗就靜默改用 repo 裡那份「已知落後」的本機備份算公平分數，
                    # 畫面完全沒提示（首頁自己都在警告本機備份比雲端舊）。
                    hist_csv = fetch_history_csv("getScheduleHistory")
                    if hist_csv: config_overrides["排班紀錄.csv"] = hist_csv
                    else: st.error("⚠️ 讀不到雲端『排班歷史』，這次會改用本機舊備份算公平分數，"
                                   "結果可能不準！請確認網路後重新排一次。")
                    mem_csv = fetch_members_as_csv()
                    if mem_csv: config_overrides["組員名單.csv"] = mem_csv
                    else: st.warning("⚠️ 讀不到雲端『組員名單』，改用本機備份（若最近有人入組/退組可能不準）。")
                    # v3.42：休診日改吃雲端「休診日」分頁（跟 LINE 小幫手 prevWorkday_
                    # 讀的是同一份），確保「排班算的印藥水日」跟「LINE 提醒的日期」
                    # 用同一組連假清單。讀不到要明講，不能靜默用本機備份——那正是
                    # 這次要根治的「兩份清單各自維護」問題。
                    hol_csv, hol_err = fetch_holidays_as_csv()
                    if hol_csv is not None:
                        config_overrides["休診日.csv"] = hol_csv
                        if hol_err: st.warning(f"⚠️ {hol_err}（請到「📊 統計管理 → 🗓 休診日」修正）")
                    else:
                        st.warning(f"⚠️ 讀不到雲端『休診日』（{hol_err}），這次改用本機 休診日.csv。"
                                   "如果最近有新增過年/連假，排出來的印藥水日可能跟 LINE 提醒對不上。")
                # 強制可印人員
                force_names = [n.strip() for n in force_names_raw.splitlines() if n.strip()]
                if force_names:
                    import io as _io
                    _fc = _io.StringIO(); _fc.write("姓名\n")
                    for _n in force_names: _fc.write(_n+"\n")
                    config_overrides["強制可印.csv"] = _fc.getvalue().encode("utf-8-sig")
                out, files, updated_hist = run_tool("排班.py", data, [sheet], config_overrides)
                st.session_state["yao"] = (out, files, sheet, updated_hist)
                st.session_state.pop("yao_edit", None)   # 清掉舊 editor 狀態，讓下面重新套定案

        if "yao" in st.session_state:
            out, files, sheet0, updated_hist = st.session_state["yao"]
            fn, b = pick(files, ".xlsx")
            if not b:
                st.error("沒產生名單，請看下方訊息。"); st.code(out); st.stop()
            grid  = pd.read_excel(io.BytesIO(b), index_col=0).fillna("")
            names, dates, marks = parse_grid(grid)
            yr     = year_from_cloud(files)      # 整週猜測值，僅供查不到時退回
            yr_map = year_map_from_cloud(files)   # v3.41：每一格自己的真實年份

            # 自動套回上次定案的修改（如顏凰任→張雅雯），避免重排後又要重改
            override_names = names.copy()
            _prev_rows  = st.session_state.get("cloud_rows", [])
            _prev_sheet = st.session_state.get("cloud_sheet0", "")
            _prev_disp  = st.session_state.get("cloud_disp")
            if _prev_rows and _prev_sheet == sheet0:
                for _cr in _prev_rows:
                    try:
                        _area = str(_cr[1]); _nm = str(_cr[2])
                        if not _nm or _nm in ("", "❌排不出"): continue
                        if (len(_cr) >= 5 and str(_cr[4])
                                and _area in override_names.index
                                and str(_cr[4]) in override_names.columns):
                            # 新格式：直接用存好的治療欄 key，不靠印日期推算，零碰撞
                            override_names.loc[_area, str(_cr[4])] = _nm
                        else:
                            # 舊格式（3欄）：向下相容，用印日期比對（同日多人時仍可能偏差）
                            _dstr = str(_cr[0])
                            _mo = int(_dstr.split('-')[1]); _dy = int(_dstr.split('-')[2])
                            _tgt = f"{_mo}/{_dy}"
                            for _col in dates.columns:
                                if str(dates.loc[_area, _col]).strip() == _tgt:
                                    override_names.loc[_area, _col] = _nm
                                    break
                    except Exception:
                        pass

                # 套回 🔺 標記：新格式從 rows[3]+rows[4] 讀，舊格式從 cloud_disp 讀
                # v3.50（獨立稽查低-19）：以前這裡先把「這次重新產生的整張表」的 marks
                # 全部清空成空字串，再用舊草稿的 (區,治療欄key) 逐格比對回填——正常情況
                # （欄位 key 沒變）沒問題，但只要有任何一格在舊草稿裡對不到現在的
                # (區,治療欄key)（例如這次重排後那一格的治療欄 key 稍微不同），這格就會
                # 永遠停在空字串：不是「維持這次新算出來的🔺」，而是「被清空後沒人補上」，
                # 使用者會看到某人明明是跨區借人、畫面卻沒有🔺標記，完全看不出來。
                # 改成：沒清空，只有舊草稿裡真的比對到的格子才覆蓋——比對不到的格子維持
                # parse_grid() 這次重新算出來的原始值，不會無故消失。
                _new_fmt = [cr for cr in _prev_rows if len(cr) >= 5]
                if _new_fmt:
                    for _cr in _new_fmt:
                        try:
                            _area, _mk, _col = str(_cr[1]), str(_cr[3]), str(_cr[4])
                            if _area in marks.index and _col in marks.columns:
                                marks.loc[_area, _col] = _mk
                        except Exception:
                            pass
                elif _prev_disp is not None and not _prev_disp.empty:
                    for _r in marks.index:
                        for _c in marks.columns:
                            if _r in _prev_disp.index and _c in _prev_disp.columns:
                                marks.loc[_r, _c] = "🔺" if "🔺" in str(_prev_disp.loc[_r, _c]) else ""

            st.subheader(f"印藥水名單（{sheet0}）")
            st.caption("👇 想換人就直接點格子改名字（日期自動沿用）。改好再按「產生定案」。🔺 = 跨區借人")
            # 顯示用：名字後面加跨區標記 🔺
            display_names = override_names.copy()
            for _r in override_names.index:
                for _c in override_names.columns:
                    _mk = str(marks.loc[_r, _c]).strip() if (_r in marks.index and _c in marks.columns) else ""
                    if _mk:
                        display_names.loc[_r, _c] = str(override_names.loc[_r, _c]) + _mk
            _edit_T = st.data_editor(display_names.T, use_container_width=True, key="yao_edit")
            edited = _edit_T.T   # 轉回 area×day 給後續邏輯用
            # v3.49：這串提醒以前是「沒有標題、直接倒在表格下面」，使用者根本認不出那是
            # 什麼、也找不到（問「注意事項區在哪???」）。補上標題與說明。
            _notes = extract_notes(out)
            if _notes:
                st.markdown("#### ⚠️ 注意事項（產生定案前請看過）")
                st.caption("排班過程中程式想告訴你的事：排不出人、跨區借人、日期被自動補回、"
                           "強制可印沒生效…等等。沒有異常時這一區不會出現。")
                for n in _notes: st.write("・" + n)

            # v3.51（2026-08-10真實事件）：排班.py 的 parse_sheet 第五輪偵測到「檔案日期
            # 跟這週對不起來」（例如檔名/分頁名寫 115.08.10~115.08.16，表格裡卻是兩週前
            # 的日期）時，會在上面的 _notes 裡印一則含「檔案週次不符」的警告——但那次
            # 事件就是靠玉繡自己肉眼比對格子內容才發現，警告文字本身很容易被忙起來的人
            # 掃過去。這裡額外做一道跟 _send_blocked（見下方送雲端那段）同款的硬性攔阻：
            # 偵測到這個字樣就必須勾選「已核對過」才能按「產生定案」，不能只是被動顯示。
            _week_mismatch = any("檔案週次不符" in n for n in _notes)
            if _week_mismatch:
                st.error("🚨 系統偵測到上傳的班表檔案，日期範圍跟這週對不起來，"
                          "很可能是排班組給錯檔案（例如誤用了舊週次的檔案）！"
                          "請先跟排班組核對清楚、拿到正確的這週檔案，不要直接繼續排下去。")
            _confirm_week_mismatch = (
                st.checkbox("我已經跟排班組核對過，確認上面表格的日期真的是這週正確的班表，仍要繼續",
                            key="confirm_week_mismatch")
                if _week_mismatch else True
            )

            # 公平累計統計（含本週預覽）
            _fair_lines = extract_fairness(out)
            if _fair_lines:
                with st.expander("📊 查看公平累計（印/休統計）", expanded=False):
                    st.caption("排序：印次越少 → 越優先被排到印。休次越多 → 下次更優先。")
                    st.code("\n".join(_fair_lines), language=None)

            st.markdown("#### 3️⃣ 產生定案 → 送到雲端")
            if st.button("✅ 產生定案（套用修改）", type="primary", disabled=not _confirm_week_mismatch):
                # v3.50（獨立稽查高-2、中-4）：格子是自由文字，過去完全沒對過組員名單。
                # 實測把「黃怡璇」打成「怡璇」（強制可印欄位的 placeholder 就寫著可以打
                # 簡稱，玉繡自然會在格子裡也這樣打）：她完全收不到 LINE 提醒（GAS 用姓名
                # 精確比對查不到 userId）、build_corrected_history 對不到名冊把她記成
                # 「休」（實際有印）、LINE 群組公告甚至同時把她列進「印」和「休息」——
                # 跟 v3.41 修掉的「雙印污染」是同一種三連錯，只是觸發條件從「印兩次」
                # 變成「打錯字」，遠比雙印常見。
                # 另外「❌排不出」那格如果被手動填上名字，因為那格沒有日期，`dt` 是空的，
                # 原本會整個靜默跳過不進 rows——那個人完全不會被送到雲端（沒有 LINE
                # 提醒、公平歷史也沒有她），但公告文字會拿治療日當印藥水日把她印出來，
                # 玉繡看畫面完全看不出這個人其實沒有真的被排進去。
                _roster_names = get_roster_names()          # {姓名: 卡號}，單一來源
                _unmatched = []     # 對不到組員名單的名字：[(位置, 打的內容)]
                _expanded  = []     # 簡稱自動展開：[(位置, 打的簡稱, 展開的全名)]
                _no_date   = []     # 有填名字但這格沒有印藥水日（例如手動填進❌排不出）
                disp = edited.copy(); rows = []
                for r in edited.index:
                    for c in edited.columns:
                        raw_val = str(edited.loc[r,c])
                        # v3.41：除了 🔺，也要把「雙印」標記拿掉。排班.py 的 celltext()
                        # 在印第二次的格子後面會接「雙印」（例：余怜緣(7/16印)雙印），
                        # 舊版只 sub 掉 🔺，導致姓名欄變成「余怜緣雙印」送進雲端，造成
                        # 三重傷害：①GAS buildUserMap_ 用姓名精確比對 → 查不到 userId
                        # → 該人完全收不到LINE提醒 ②build_corrected_history 對不上名冊
                        # → 明明印兩次卻被記成「休」，公平輪序連錯兩格 ③LINE群組公告同時
                        # 把她列進「印」和「休息」。雙印雖不常見(26週1次)，一發生就是靜默三連錯。
                        nm_raw = re.sub(r'🔺|雙印', '', raw_val).strip()  # 去掉顯示用標記
                        # 以 editor 內容為準：用戶有加 🔺 就保留，有去掉就不補
                        mk = "🔺" if "🔺" in raw_val else ""
                        dt = dates.loc[r,c]
                        nm = nm_raw
                        if nm_raw and nm_raw != "❌排不出":
                            if _roster_names and nm_raw not in _roster_names:
                                # 簡稱比對，比照 排班.py FORCE_PRINT 同一套規則
                                # （長度≥2 才比，避免單字誤傷；唯一匹配才自動展開）
                                _cands = [full for full in _roster_names
                                          if len(nm_raw) >= 2 and full.endswith(nm_raw)]
                                if len(_cands) == 1:
                                    _expanded.append((f"{r}/{c}", nm_raw, _cands[0]))
                                    nm = _cands[0]
                                else:
                                    _unmatched.append((f"{r}/{c}", nm_raw))
                            if not dt:
                                _no_date.append((f"{r}/{c}", nm))
                            disp.loc[r,c] = f"{nm}({dt}印){mk}" if dt else f"{nm}{mk}"
                            if dt:
                                mo,dy = dt.split("/")
                                mo_i, dy_i = int(mo), int(dy)
                                # v3.41：先查每格真實年份表，查不到（例如手動改動導致對不上）才退回整週猜測值
                                _row_yr = yr_map.get((r, mo_i, dy_i), yr)
                                # 格式：[印日期, 區, 姓名, 🔺標記, 治療欄key]
                                rows.append([f"{_row_yr}-{mo_i:02d}-{dy_i:02d}", r, nm, mk, str(c)])
                        else:
                            disp.loc[r,c] = nm_raw
                rows.sort(key=lambda x:(x[0],x[1]))
                st.session_state["cloud_rows"]   = rows
                st.session_state["cloud_disp"]   = disp
                st.session_state["cloud_sheet0"] = sheet0
                st.session_state["cloud_unmatched_names"] = _unmatched
                st.session_state["cloud_no_date_names"]   = _no_date
                if _expanded:
                    st.info("ℹ 已自動展開簡稱："
                             + "、".join(f"{pos} 『{raw}』→『{full}』" for pos,raw,full in _expanded))
                st.session_state["cloud_rows_source"] = "finalized"
                # v3.50（獨立稽查低-13）：以前這行在 TEST_MODE 外面，測試模式（小巫用，
                # 側欄明講「不會真的寫到雲端」）照樣把測試資料寫進本機草稿檔
                # last_week_draft.json；而 Streamlit Cloud 是同一個容器給所有人共用，
                # 玉繡接下來打開 app 就會看到「📂 找到上次的定案，要恢復嗎？」──載入的
                # 其實是小巫的測試資料，正是第九節那場事故（舊草稿被自動套回、錯資料
                # 真的送出去）的同一條路徑。改成只有非測試模式才寫本機草稿。
                if not TEST_MODE:
                    _save_week_draft(rows, sheet0, disp)   # 自動存本機
                if not TEST_MODE and APPS_SCRIPT_URL and WRITE_SECRET:
                    _draft_ok, _draft_err = push_week_draft(rows, sheet0)
                    if not _draft_ok:
                        # v3.44：以前這裡寫死「（網路問題？）」，害人往網路方向查；
                        # 實際成因是 GAS 端欄數對不上。改成把真正的原因顯示出來。
                        st.warning(f"⚠️ 雲端草稿暫存失敗：{_draft_err}\n\n"
                                   "（這只影響「給小巫預覽的草稿」，**不影響 LINE 提醒、也不影響統計**，"
                                   "可以照常按「🚀 送到雲端」。）")

    # 定案顯示（有定案就顯示，不管是否剛排班）
    if "cloud_rows" in st.session_state:
        rows   = st.session_state["cloud_rows"]
        disp   = st.session_state["cloud_disp"]
        sheet0 = st.session_state["cloud_sheet0"]
        _src = st.session_state.get("cloud_rows_source", "finalized")
        if _src == "draft":
            st.info("📋 已載入草稿（僅供確認，尚未送雲端）")
        else:
            st.success("✅ 定案完成！")
        if _src == "draft":
            # 草稿來源：用平鋪列表顯示，避免 pivot 因印日期不同而出現空白欄
            _flat = pd.DataFrame(
                [[gs_date_to_ymd(r[0]), str(r[1]), str(r[2])] for r in rows],
                columns=["印藥水日", "區", "姓名"]
            ).sort_values("印藥水日").reset_index(drop=True)
            st.dataframe(_flat, use_container_width=True, hide_index=True,
                         column_config={
                             "印藥水日": st.column_config.TextColumn("印藥水日", width="medium"),
                             "區":      st.column_config.TextColumn("區",      width="small"),
                             "姓名":    st.column_config.TextColumn("姓名",    width="medium"),
                         })
        else:
            st.dataframe(disp.T, use_container_width=True)   # 直式：日期當列，區當欄

        # 定案後顯示實際休息人員（依玉繡最終調整，非演算法原始結果）
        _roster_all = get_roster_full()
        if _roster_all:
            _printing = {str(r[2]).strip() for r in rows if r[2]}
            _resting  = [m["姓名"] for m in _roster_all if m["姓名"] not in _printing]
            if _resting:
                st.info("😴 本週休息：" + "、".join(_resting))

        # 💾 暫存草稿：讓小巫可以讀取確認
        if TEST_MODE:
            if st.button("🧪 暫存草稿（測試模擬）", key="week_draft_test"):
                st.info("🧪 測試模式：模擬暫存成功，但沒有真的寫到雲端。")
        elif APPS_SCRIPT_URL and WRITE_SECRET:
            _wd1, _wd2 = st.columns(2)
            if _wd1.button("💾 備份草稿（小巫更新程式後可查看）", key="week_draft_save"):
                with st.spinner("暫存中…"):
                    _ok, _err = push_week_draft(rows, sheet0)
                if _ok:
                    st.success("✅ 草稿已存到雲端！小巫可按「📥 讀取玉繡的排班草稿」來確認。")
                else:
                    st.error(f"暫存失敗：{_err}\n\n"
                             "（只影響給小巫預覽的草稿，不影響 LINE 提醒與統計，"
                             "可以照常按「🚀 送到雲端」。）")
            if _wd2.button("🗑 清除草稿", key="week_draft_clear"):
                if clear_week_draft_cloud():
                    st.success("✅ 草稿已清除。")
                else:
                    st.error("清除失敗。")

        # LINE 群組公告文字
        # v3.50（獨立稽查低-19）：這行註解原本講「pivot 用 aggfunc="first" 會丟失同區多人」，
        # 但那個問題在 _reconstruct_disp_from_rows()（見上方）早就改成 `、`.join 修掉了，
        # 現在草稿來源的 disp 已經不會弄丟同區多人的姓名——但這裡繼續不傳 disp 給草稿來源
        # 仍然是對的，只是理由變了：_build_line_txt 的 disp_df 路徑要靠儲存格文字裡的
        # 「(M/D印)」日期編碼取印藥水日（見 CELL_RE），而 _reconstruct_disp_from_rows()
        # 只還原姓名（可能「王小明、李小美」用頓號合併），完全沒有帶回這個日期編碼，disp
        # 路徑會直接抓不到日期。rows 本身每筆都已經帶著算好的完整印藥水日，是可靠的路，
        # 所以草稿來源繼續強制走 rows fallback（傳 None），不是因為 aggfunc 那個已修好的舊問題。
        _line_txt = _build_line_txt(rows, disp_df=(None if _src == "draft" else disp))
        if _line_txt:
            st.markdown("**📋 LINE 群組公告格式**")
            st.caption("長按複製，或按下方按鈕下載 txt 傳 LINE")
            st.code(_line_txt, language=None)
            st.download_button("⬇️ 下載 txt 傳 LINE 群組",
                               _line_txt.encode("utf-8"),
                               file_name=f"印藥水名單_{sheet0}.txt",
                               mime="text/plain")

        # v3.50（獨立稽查高-2、中-4）：格子裡有「對不到組員名單的名字」或「填了名字
        # 卻沒有印藥水日（例如手動填進❌排不出格）」時，在這裡明確擋下——不要讓它送出去
        # 才在雲端用姓名精確比對時默默失敗。只有本次「產生定案」按下時算出來的結果才會
        # 檢查（草稿來源沒有重跑過驗證，用 _src 判斷）。
        _unmatched = st.session_state.get("cloud_unmatched_names", []) if _src == "finalized" else []
        _no_date   = st.session_state.get("cloud_no_date_names", [])   if _src == "finalized" else []
        _send_blocked = False
        # v3.50（獨立稽查中-12）：從草稿載入的（不是剛按過「產生定案」）要多一道確認才能
        # 送出——草稿沒有時間戳，可能是上週留下沒清的舊資料，一鍵送出會覆蓋本週名單、
        # 本週LINE提醒失效（見 _week_looks_stale 的說明）。
        if _src == "draft":
            _stale_send = _week_looks_stale(sheet0)
            _draft_msg = (f"⚠️ 這是從雲端草稿載入的內容（週次「{sheet0}」），不是剛排出來的。"
                          + ("這個週次看起來不像最近這週，" if _stale_send else "")
                          + "送出前請確認上面列的名單是不是**這週**要送的。")
            st.warning(_draft_msg)
            _send_blocked = not st.checkbox(
                "我已經確認過上面的名單、日期都是這週正確的內容，仍要送出",
                key="confirm_draft_send")
        if _unmatched:
            st.error("❌ 這幾格的名字在組員名單裡找不到對應的人，送出去會**收不到 LINE 提醒**、"
                     "公平歷史也會記錯：\n" +
                     "\n".join(f"　・{pos}：『{raw}』" for pos, raw in _unmatched) +
                     "\n\n請改回組員名單裡的正確姓名（或至少 2 個字的簡稱，能唯一對到一個人）。")
        if _no_date:
            st.error("❌ 這幾格填了名字，但這格**沒有印藥水日**（例如手動填進「❌排不出」的格子），"
                     "這個人**不會被送到雲端**、收不到任何提醒：\n" +
                     "\n".join(f"　・{pos}：『{nm}』" for pos, nm in _no_date) +
                     "\n\n請改用有日期的格子安排這個人，或人工另外處理。")
        if _unmatched or _no_date:
            _send_blocked = not st.checkbox(
                "我知道上面列的問題，仍要照現在這樣送出（不建議，除非已經確認過）",
                key="force_send_with_issues")

        if TEST_MODE:
            if st.button("🧪 送到雲端（測試模擬）", type="secondary", disabled=_send_blocked):
                st.info(f"🧪 測試模式：模擬送出 {len(rows)} 筆，但實際上**沒有**寫到雲端，也沒有送 LINE 通知。")
                st.balloons()
        elif APPS_SCRIPT_URL and WRITE_SECRET:
            # 提示目前要送的是哪個版本（確認是定案版，不是機器版）
            _names_in_rows = "、".join(sorted({r[2] for r in rows if r[2]}))
            st.caption(f"⚠️ 送出前確認：本次定案人員 → {_names_in_rows}")
            if st.button("🚀 送到雲端（自動排提醒）", type="primary", disabled=_send_blocked):
                with st.spinner("送出中，請稍候…"):
                    try:
                        resp = requests.post(
                            APPS_SCRIPT_URL,
                            json={"action":"setWeek","secret":WRITE_SECRET,
                                  # 只送前3欄（印日期/區/姓名）給GAS，多餘的治療欄/🔺欄不外送
                                  "rows":[[str(r[0]), str(r[1]), str(r[2])] for r in rows]},
                            timeout=45)
                        if resp.ok and '"ok":true' in resp.text:
                            st.success(f"🎉 已送到雲端！共 {len(rows)} 筆。系統會自動 LINE 提醒，你不用再做任何事。")
                            st.balloons()
                            _, _, _, updated_hist = st.session_state.get("yao",(None,None,None,{}))
                            corrected = build_corrected_history(
                                rows, sheet0, (updated_hist or {}).get("排班紀錄.csv"))
                            ok2, n2, detail2 = push_history("setScheduleHistory", corrected, sheet0)
                            if ok2:
                                st.caption(f"✅ 排班歷史已同步（{n2} 筆，依玉繡實際定案），下週公平輪序更準確。")
                                if detail2:
                                    st.caption(f"🔍 診斷：{detail2}")
                            else:
                                st.error(f"⚠️ 本週名單已送出、LINE會照常提醒，但「排班歷史」同步失敗！"
                                          f"原因：{detail2}\n\n"
                                          "統計管理頁面的印次/休次不會更新這週，公平輪序會算錯。"
                                          "請到「📊 統計管理 → 印藥水統計」按「🔄 讀取」確認，"
                                          "如果這週真的沒出現，回來這裡重新按一次「🚀 送到雲端」重試。")
                            _clear_week_draft()         # 清除本機草稿
                            # 雲端草稿保留：讓小巫或玉繡重開 app 還能看到定案版
                            st.session_state.pop("week_draft_auto", None)
                        else:
                            st.error(f"送出失敗（{resp.status_code}）：{resp.text[:200]}")
                    except Exception as e:
                        st.error(f"送出失敗：{e}")
        else:
            st.warning("雲端直送尚未設定（請在 Streamlit Secrets 填 APPS_SCRIPT_URL 與 WRITE_SECRET）。")

        with st.expander("📋 手動備援（複製貼到試算表 / 下載 CSV）"):
            # 只取前3欄（rows 可能是新格式5欄），避免 DataFrame 欄數不符
            cloud = pd.DataFrame([[r[0], r[1], r[2]] for r in rows], columns=["印日期","區","姓名"])
            tsv = cloud.to_csv(index=False, sep="\t")
            st.markdown("① 按右上角複製鈕　→　② 開試算表「本週名單」　→　③ 點 A1 貼上")
            st.code(tsv, language=None)
            st.link_button("🔗 開啟試算表（本週名單）", SHEET_URL)
            st.download_button("⬇️ 下載 CSV 檔",
                               cloud.to_csv(index=False).encode("utf-8-sig"),
                               file_name=f"雲端貼上_{sheet0}.csv", mime="text/csv")

    if "yao" in st.session_state and data is not None:
        _, files, _, _ = st.session_state["yao"]
        _FILE_LABELS = {
            ".xlsx": "📋 列印用（Excel，貼到護理站公告欄）",
            ".txt":  "💬 傳 LINE 群組用（文字，複製貼上）",
            ".csv":  "☁️ 雲端貼上用（CSV，貼到 Google 試算表）",
        }
        with st.expander("⬇️ 其他檔案下載（列印用 xlsx / 貼 LINE 用 txt）"):
            for fn, b in files.items():
                ext = os.path.splitext(fn)[1].lower()
                label = _FILE_LABELS.get(ext, "")
                if label:
                    st.caption(label)
                st.download_button(f"⬇️ {fn}", b, file_name=fn, key="dl_"+fn)


# ═══════════════════════ 每月稽核 ═══════════════════════
# v3.50（獨立稽查中-11）：這裡原本是裸 else，配對的是第1774行「if mode.startswith("🟦")」，
# 但 mode 其實有三種（🟦🟩📊），裸 else 把「🟩每月稽核」跟「📊統計管理」都算進來——
# 選「📊統計管理」時，這整段稽核UI（年/月選擇器、Stage1預覽班型、Stage2稽核名單，
# 包含一顆活的「🚀送稽核結果到雲端」按鈕）會跟第2425行真正的統計管理UI**一起**畫出來，
# 一個會真的發LINE的按鈕出現在不該出現的地方。改成明確的 elif mode.startswith("🟩")，
# 📊模式時這整段完全不渲染。
elif mode.startswith("🟩"):
    c1, c2 = st.columns(2)
    # v3.50（獨立稽查中-10）：年份原本寫死 2026，月份卻跟著今天走——2027年1月玉繡
    # 照平常流程排稽核，畫面預設仍是「2026年1月」→ month_key="115-01" → GAS
    # writeHistory_ 依 key 整批刪除重寫 → 把2026年1月的稽核明細換成2027年的資料
    # （已用 gasmock 實測這個覆蓋機制是真的）。改成年份也跟著今天走。
    yy = c1.number_input("年", 2024, 2100, pd.Timestamp.now().year)
    mm = c2.number_input("月", 1, 12, pd.Timestamp.now().month)
    # v3.41：月份鍵一律用**民國**格式，跟 稽核.py 的 month_tag() 及雲端既有資料
    # （114-09 ~ 115-07 全是民國）保持一致。舊版用西元 "2026-07"，會造成
    # ①load_history 的 skip_month 比不到本月、本月結果混進歷史重算（實測公平分數偏差±2）
    # ②送雲端時同一個月同時存在 "115-07" 與 "2026-07" 兩把鍵 → 每個人被計算兩次
    month_key = f"{int(yy) - 1911}-{int(mm):02d}"

    if st.session_state.get("ak_month_key") != month_key:
        st.session_state.pop("ak_shifts", None)
        st.session_state.pop("ak", None)
        st.session_state["ak_month_key"] = month_key

    if audit_quick:
        # ── 快速模式：免上傳，直接點選白/夜＋區 ──────────────
        st.markdown("#### 2️⃣ 點選每人「白/夜」＋「區」→ 排稽核")
        roster = get_roster_full()
        if not roster:
            st.error("找不到組員名單（雲端與本機備份都讀不到）。請確認網路，或先在「📊 統計管理→👥 組員名單」確認雲端有資料。"); st.stop()
        _rw = roster_fallback_warning()
        if _rw: st.warning(_rw)
        # 帶入優先序：①雲端草稿（上次暫存）②上個月設定 ③預設
        draft   = fetch_audit_draft()
        prefill = fetch_last_audit_prefill()
        if draft:
            st.caption("📌 已帶回你上次「暫存」的草稿。改好可再按「💾 暫存」，或直接「✅ 排稽核」。")
        else:
            st.caption("免上傳 Excel。系統已帶出上個月的設定，只要改這個月有變動的人即可。")
        base = []
        for m in roster:
            nm = m["姓名"]
            pre = draft.get(nm) or prefill.get(nm)   # 有草稿/上次才帶；沒有就留「未設」
            if pre:
                typ, area = pre
            else:
                typ, area = "白班", "❓"               # 冷啟動：區留❓未設，逼人設定、避免默默全一區
            if typ not in ("白班","小夜"): typ = "白班"
            if area not in ("一區","二區","❓"): area = "❓"
            base.append({"卡號": m["卡號"], "姓名": nm, "班型": typ, "區": area})
        df_q = pd.DataFrame(base)
        edited_q = st.data_editor(
            df_q,
            column_config={
                "卡號": st.column_config.TextColumn("卡號", disabled=True),
                "姓名": st.column_config.TextColumn("姓名", disabled=True),
                "班型": st.column_config.SelectboxColumn("班型 ✏️", options=["白班","小夜"], required=True),
                "區":   st.column_config.SelectboxColumn("區 ✏️",   options=["一區","二區","❓"], required=True),
            },
            use_container_width=True, hide_index=True, key="quick_edit"
        )
        n_white = int((edited_q["班型"] == "白班").sum())
        n_night = int((edited_q["班型"] == "小夜").sum())
        n_a1    = int((edited_q["區"] == "一區").sum())
        n_a2    = int((edited_q["區"] == "二區").sum())
        n_unset = int((edited_q["區"] == "❓").sum())
        st.caption(f"目前：白班 {n_white}、小夜 {n_night}；一區 {n_a1}、二區 {n_a2}"
                   + (f"；❓未設區 {n_unset}" if n_unset else "") + f"（共 {len(edited_q)} 人）")
        if n_unset:
            st.warning(f"⚠️ 還有 {n_unset} 人的「區」是 ❓ 未設，請先點成一區/二區，否則他們會排不進去（會噴錯）。")
        if n_unset == 0 and n_a2 == 0:
            st.warning("⚠️ 目前沒有人在「二區」——二區的稽核會排不出來，確認是不是漏設了？")
        if n_unset == 0 and n_a1 == 0:
            st.warning("⚠️ 目前沒有人在「一區」。")
        if n_night == 0:
            st.warning("⚠️ 目前沒有人是「小夜」——第三班（小夜）會排不出來。")

        # 💾 暫存 / 🗑 清除暫存（雲端草稿，可分次填、明天再回來接續）
        if TEST_MODE:
            cda, cdb = st.columns(2)
            if cda.button("🧪 暫存草稿（測試模擬）"):
                st.info("🧪 測試模式：模擬暫存成功，但沒有真的寫到雲端。")
            if cdb.button("🧪 清除暫存（測試模擬）"):
                st.info("🧪 測試模式：模擬清除成功，但沒有真的動雲端。")
        elif APPS_SCRIPT_URL and WRITE_SECRET:
            cda, cdb = st.columns(2)
            if cda.button("💾 暫存草稿（之後可接續填）"):
                _da_ok, _da_err = push_audit_draft(edited_q)
                if _da_ok:
                    st.success("✅ 已暫存到雲端！下次打開會自動帶回，可接著填。")
                else:
                    st.error(f"暫存失敗：{_da_err}")
            if cdb.button("🗑 清除暫存（改用上月設定）"):
                _cd_ok, _cd_err = clear_audit_draft()
                if _cd_ok:
                    st.success("✅ 已清除暫存。重新整理後會改帶上個月的設定。")
                else:
                    st.error(f"清除失敗：{_cd_err}")

        if st.button("✅ 排稽核（快速）", type="primary"):
          if n_unset > 0:
            st.error(f"還有 {n_unset} 人的「區」是 ❓ 未設，請先全部點成一區/二區，再排稽核。")
          else:
            with st.spinner("讀取雲端歷史 + 排稽核中…"):
                quick_csv = edited_q.to_csv(index=False).encode("utf-8-sig")
                config_overrides = {"快速名冊.csv": quick_csv}
                if APPS_SCRIPT_URL and WRITE_SECRET:
                    hist_csv = fetch_history_csv("getAuditHistory")   # v3.41：失敗要吵，不要靜默用舊備份
                    if hist_csv: config_overrides["稽核紀錄.csv"] = hist_csv
                    else: st.error("⚠️ 讀不到雲端『稽核歷史』，這次會改用本機舊備份算公平分數，"
                                   "結果可能不準！請確認網路後重新排一次。")
                    mem_csv = fetch_members_as_csv()
                    if mem_csv: config_overrides["組員名單.csv"] = mem_csv
                    else: st.warning("⚠️ 讀不到雲端『組員名單』，改用本機備份（若最近有人入組/退組可能不準）。")
                    # 稽核.py 目前 load_holidays() 有讀、但演算法還沒用到 HOLIDAYS，
                    # 所以讀不到也不影響結果、不吵使用者。仍然一起注入，是為了讓
                    # 「休診日只有雲端一個來源」這件事對三個消費者（排班.py／稽核.py／
                    # .gs）都成立，將來稽核真的用到時不會又冒出第二份清單。
                    _hol_csv, _ = fetch_holidays_as_csv()
                    if _hol_csv is not None: config_overrides["休診日.csv"] = _hol_csv
                out, files, updated_hist = run_tool(
                    "稽核.py", None, ["--quick", month_key], config_overrides)
                st.session_state["ak"] = (out, files, updated_hist)
    else:
        # ── Stage 1：確認班型（上傳班表分析）──────────────────
        st.markdown("#### 2️⃣ 確認班型（程式猜測 → 玉繡確認）")
        st.caption("程式從班表判斷白/夜，不確定的顯示 ❓，請手動改。")

        if st.button("📊 預覽班型", type="secondary"):
            with st.spinner("分析班表中…"):
                # v3.50：把上傳檔名傳進去給第3層備援用（例如「115.08.10~115.08.16.xls」
                _fn_hint = getattr(up, "name", None) if "up" in dir() else None
                df_shifts = detect_shifts_quick(data, int(yy), int(mm), filename_hint=_fn_hint)
            if df_shifts.empty:
                st.error("找不到該月份的班表資料，請確認分頁是否包含此月份。")
            else:
                st.session_state["ak_shifts"] = df_shifts
                st.session_state.pop("ak", None)

        if "ak_shifts" in st.session_state:
            df_shifts = st.session_state["ak_shifts"]
            st.caption("👇 可直接點「確認班型」欄修改。")
            edited_shifts = st.data_editor(
                df_shifts,
                column_config={
                    "程式猜測": st.column_config.TextColumn("程式猜測", disabled=True),
                    "確認班型": st.column_config.SelectboxColumn(
                        "確認班型 ✏️", options=["白班","夜班","❓"], required=True)
                },
                use_container_width=True, hide_index=True, key="shift_edit"
            )
            uncertain = (edited_shifts["確認班型"] == "❓").sum()
            if uncertain > 0:
                st.warning(f"⚠️ 還有 {uncertain} 人班型是 ❓，這些人本月排稽核時會略過。")

            if st.button("✅ 確認班型 → 排稽核", type="primary"):
                with st.spinner("讀取雲端歷史 + 排稽核中…"):
                    override_df  = edited_shifts[["卡號","姓名","確認班型"]].rename(columns={"確認班型":"班型"})
                    override_csv = override_df.to_csv(index=False).encode("utf-8-sig")
                    config_overrides = {"班型覆蓋.csv": override_csv}
                    if APPS_SCRIPT_URL and WRITE_SECRET:
                        hist_csv = fetch_history_csv("getAuditHistory")   # v3.41：失敗要吵
                        if hist_csv: config_overrides["稽核紀錄.csv"] = hist_csv
                        else: st.error("⚠️ 讀不到雲端『稽核歷史』，這次會改用本機舊備份算公平分數，"
                                       "結果可能不準！請確認網路後重新排一次。")
                        mem_csv = fetch_members_as_csv()
                        if mem_csv: config_overrides["組員名單.csv"] = mem_csv
                        else: st.warning("⚠️ 讀不到雲端『組員名單』，改用本機備份（若最近有人入組/退組可能不準）。")
                        # 同上：稽核演算法目前沒用到休診日，一起注入是為了維持單一來源
                        _hol_csv, _ = fetch_holidays_as_csv()
                        if _hol_csv is not None: config_overrides["休診日.csv"] = _hol_csv
                    out, files, updated_hist = run_tool(
                        "稽核.py", data, [month_key], config_overrides)
                    st.session_state["ak"] = (out, files, updated_hist)

    # ── Stage 2：稽核名單 + 送雲端 ────────────────────────
    if "ak" in st.session_state:
        out, files, updated_hist = st.session_state["ak"]
        fn, b = pick(files, ".xlsx")
        if not b:
            st.error("沒產生名單，請看下方訊息。"); st.code(out); st.stop()

        st.markdown("#### 3️⃣ 稽核名單 → 送到雲端")
        df = pd.read_excel(io.BytesIO(b)).fillna("")
        st.subheader(f"稽核 AK 名單（{month_key}）")
        st.caption("可直接點「稽核者」欄改人名。")
        edited_ak = st.data_editor(df, use_container_width=True,
                                    key="ak_edit", hide_index=True)
        _notes_ak = extract_notes(out)
        if _notes_ak:
            st.markdown("#### ⚠️ 注意事項（送出前請看過）")
            st.caption("排稽核過程中程式想告訴你的事：排不出人、跨區借人、班型判斷…等等。")
            for n in _notes_ak: st.write("・" + n)

        # v3.52（玉繡實際回報）：上面「注意事項」裡如果有「本月休息」這行，是 稽核.py
        # 產生 out 當下（點格子微調**之前**）印的，是演算法原始結果的靜態文字，玉繡在
        # 上面表格點格子改稽核者之後不會重算——例如把「王乃君」改成「林欣儀」，畫面上
        # 的休息名單還是照舊算法原本的名單，沒把王乃君加進去、也沒把林欣儀移出來。
        # 跟印藥水那邊「定案後顯示實際休息人員（依玉繡最終調整）」（見上面 _resting）
        # 是同一類問題，印藥水那邊早就修過，稽核這邊當初漏掉。改成依 edited_ak 現況
        # 重新算，不依賴 稽核.py 印出來的舊字串；姓名清洗跟
        # build_corrected_audit_history()/send_audit_notices() 用同一條 regex，避免
        # 又長出第三種不一致的清洗規則。
        _roster_ak = get_roster_names()
        _resting_ak = []
        if _roster_ak and edited_ak is not None and not edited_ak.empty:
            _auditing_ak = set()
            for _, _r in edited_ak.iterrows():
                _nm_ak = re.sub(r'[\(（].*?[\)）]', '', str(_r.get("稽核者", ""))).strip()
                if _nm_ak: _auditing_ak.add(_nm_ak)
            _resting_ak = [nm for nm in _roster_ak if nm not in _auditing_ak]
            st.info("😴 本月休息（以這行為準）：" +
                    ("、".join(_resting_ak) if _resting_ak else "無") +
                    "\n\n⚠️ 如果上面「注意事項」也提到「本月休息」或某人「本月:休息」，"
                    "那是排出來當下、你還沒點格子改之前的舊版本，跟這裡可能不一樣——"
                    "不是系統給了兩個不同答案，是上面那些字沒有跟著你的修改更新，**請以這行為準**。")

        # v3.51：跟印藥水那邊同款的硬性攔阻，見上方 _week_mismatch 的說明。
        _week_mismatch_ak = any("檔案週次不符" in n for n in _notes_ak)
        if _week_mismatch_ak:
            st.error("🚨 系統偵測到上傳的班表檔案，日期範圍跟目標月份/週對不起來，"
                      "很可能是排班組給錯檔案！請先核對清楚再送出。")
        _confirm_week_mismatch_ak = (
            st.checkbox("我已經核對過，確認上面表格的日期真的是正確的班表，仍要繼續",
                        key="confirm_week_mismatch_ak")
            if _week_mismatch_ak else True
        )

        if TEST_MODE:
            if st.button("🧪 送稽核結果到雲端（測試模擬）", type="secondary", disabled=not _confirm_week_mismatch_ak):
                st.info("🧪 測試模式：模擬送出成功，但實際上**沒有**寫到雲端，也沒有送 LINE 通知給稽核者。")
                st.balloons()
        elif APPS_SCRIPT_URL and WRITE_SECRET:
            if st.button("🚀 送稽核結果到雲端", type="primary", disabled=not _confirm_week_mismatch_ak):
                with st.spinner("送出中，請稍候…"):
                    ak_hist_b = files.get("稽核紀錄_輸出.csv")
                    # v3.41：先用玉繡實際改過的名單修正歷史，再送出（比照印藥水的 Fix1）。
                    # 舊版直接送子行程原本的產出，玉繡手改的部分不會進歷史，公平輪序逐月累積誤差。
                    ak_hist_b = build_corrected_audit_history(edited_ak, month_key, ak_hist_b)
                    ok_hist, n_hist, detail_hist = False, 0, "沒有稽核紀錄檔案可送"
                    if ak_hist_b:
                        ok_hist, n_hist, detail_hist = push_history("setAuditResult", ak_hist_b, month_key)

                    # Fix2：LINE 通知每位稽核者
                    sent, miss, failed_names = send_audit_notices(month_key, edited_ak)

                    if ok_hist:
                        st.success(f"🎉 稽核歷史已送到雲端（{month_key}，{n_hist} 筆），下個月公平輪序更準確。")
                    else:
                        st.error(f"⚠️ 稽核歷史同步失敗：{detail_hist}")
                    if sent > 0:
                        st.success(f"📱 已 LINE 通知 {sent} 位稽核者各自的責任班次。")
                        st.balloons()
                    if miss > 0:
                        st.warning(f"⚠️ {miss} 人缺 userId，無法 LINE 通知（請確認「對照」分頁）。")
                    if failed_names:
                        # v3.43：以前 LINE API 回錯誤碼會被 GAS 整個吞掉、畫面照樣顯示
                        # 「已通知 N 人」，這幾個人其實根本沒收到。現在會明確列出來。
                        st.error(f"❌ 這 {len(failed_names)} 位的 LINE 通知**實際發送失敗**，"
                                 f"請改用其他方式告知：{'、'.join(failed_names)}"
                                 "（可能是對照表的 userId 失效，或 LINE 官方帳號額度／token 有問題）")

        st.download_button("⬇️ 下載稽核名單（已套用修改）",
                           edited_ak.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"稽核名單_{month_key}.csv", mime="text/csv")

        # v3.53 續修：下面「其他檔案下載」的 .xlsx／.txt 原本直接發 稽核.py 子行程產出
        # 的原始檔案——那是玉繡在上面表格點格子改稽核者**之前**的版本，跟送到雲端／
        # LINE通知的內容完全脫鉤。這兩個檔案的用途正好是「貼護理站公告欄」「傳LINE
        # 群組」，一旦她真的改過名字又下載這裡的檔案去公告，公告欄/群組看到的名字會
        # 跟系統實際記錄、LINE個別通知的內容兜不起來，比「畫面上一段文字沒更新」嚴重
        # 得多，是會真的傳達錯誤資訊出去的等級。改成用 edited_ak（她修改後的現況）
        # 現場重建這兩個檔案內容，不再發子行程當初的舊版本。
        def _build_audit_xlsx_bytes(df):
            buf = io.BytesIO()
            df.to_excel(buf, index=False)
            return buf.getvalue()

        def _build_audit_txt(df, tag, resting_names):
            lines = [f"📋 {tag} 稽核藥水 AK 名單", ""]
            for a in ["一區", "二區"]:
                lines.append(f"《{a}》")
                for gl in ["週一三五", "週二四六"]:
                    parts = []
                    for band in ["第一班", "第二班", "第三班"]:
                        sub = df[(df["區"] == a) & (df["組"] == gl) & (df["班次"] == band)]
                        nm = str(sub.iloc[0]["稽核者"]).strip() if not sub.empty else ""
                        parts.append(f"{band}:{nm or '❌排不出'}")
                    lines.append("　" + gl + "　" + "　".join(parts))
            lines += ["", "休息:" + ("、".join(resting_names) if resting_names else "無")]
            return "\n".join(lines).encode("utf-8")

        _ak_corrected_files = dict(files)
        if edited_ak is not None and not edited_ak.empty and {"區","組","班次","稽核者"} <= set(edited_ak.columns):
            for fn in list(_ak_corrected_files.keys()):
                if fn.endswith(".xlsx"):
                    _ak_corrected_files[fn] = _build_audit_xlsx_bytes(edited_ak)
                elif fn.endswith(".txt"):
                    _ak_corrected_files[fn] = _build_audit_txt(edited_ak, month_key, _resting_ak)

        with st.expander("⬇️ 其他檔案下載（已套用修改）"):
            _AK_FILE_LABELS = {
                ".csv":  "📊 稽核紀錄（上傳到雲端歷史用，仍為原始版本，不受格子編輯影響）",
                ".xlsx": "📋 列印用（Excel，已套用你的修改）",
                ".txt":  "💬 傳 LINE 群組用（文字，已套用你的修改）",
            }
            for fn, b in _ak_corrected_files.items():
                ext = os.path.splitext(fn)[1].lower()
                label = _AK_FILE_LABELS.get(ext, "")
                if label:
                    st.caption(label)
                st.download_button(f"⬇️ {fn}", b, file_name=fn, key="akdl_"+fn)


# ═══════════════════════ 統計管理 ═══════════════════════
if mode.startswith("📊"):
    st.markdown("#### 📊 統計管理")
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["📋 印藥水統計", "📋 稽核統計", "📋 最新稽核名單", "👥 組員名單", "🗓 休診日"])

    # ── Tab1：印藥水統計 ──────────────────────────────────
    with tab1:
        st.caption("每人累積印藥水次數與休息次數。可直接改，改完按「💾 存回雲端」，下次排班即生效。")
        _sc1, _sc2 = st.columns(2)
        if _sc1.button("🔄 讀取", type="primary", key="stats_load"):
            with st.spinner("讀取中…"):
                _st = fetch_schedule_stats()
            st.session_state["schedule_stats"] = _st if _st is not None else "empty"
        if not TEST_MODE and APPS_SCRIPT_URL and WRITE_SECRET:
            if _sc2.button("📤 同步本機CSV→雲端", key="stats_sync_local",
                           help="把 repo 裡排班紀錄.csv「雲端還沒有的週次」補進雲端，"
                                "雲端既有的週次不會被覆蓋或刪除（v3.38起，只補不蓋）。"):
                with st.spinner("讀取雲端現況並比對中…"):
                    _sok, _sn, _serr = sync_schedule_history_from_csv()
                if _sok and _sn == 0:
                    st.info("雲端已經有本機CSV全部的週次，沒有需要補的資料（沒有動到任何一筆）。")
                elif _sok:
                    st.success(f"✅ 已把本機獨有的 {_sn} 筆（雲端原本沒有的週次）補進雲端！按「🔄 讀取」確認。")
                    st.session_state.pop("schedule_stats", None)
                else:
                    _hint = "（Google 伺服器較慢，已自動重試，請再按一次）" if "逾時" in (_serr or "") else ""
                    st.error(f"同步失敗：{_serr or '未知錯誤'}{_hint}")
        if "schedule_stats" in st.session_state:
            df_st = st.session_state["schedule_stats"]
            if isinstance(df_st, str) and df_st == "empty":
                st.warning("雲端還沒有排班歷史。請按「📤 同步本機CSV→雲端」把今年全年歷史上傳。")
            elif isinstance(df_st, str):
                st.error(f"讀取失敗：{df_st}")
            else:
                df_st = df_st.copy()
                st.caption(f"共 {len(df_st)} 人｜淨值越小 → 印次少 → 下次優先被排印")
                edited_st = st.data_editor(df_st, column_config={
                    "卡號":        st.column_config.TextColumn("卡號", disabled=True),
                    "姓名":        st.column_config.TextColumn("姓名", disabled=True),
                    "印次":        st.column_config.NumberColumn("印次 ✏️", min_value=0, step=1),
                    "休次":        st.column_config.NumberColumn("休次 ✏️", min_value=0, step=1),
                    "淨值(印-休)": st.column_config.NumberColumn("淨值", disabled=True),
                }, use_container_width=True, hide_index=True, key="stats_edit")
                edited_st["淨值(印-休)"] = edited_st["印次"] - edited_st["休次"]
                st.download_button("⬇️ 下載統計 CSV", edited_st.to_csv(index=False).encode("utf-8-sig"),
                                   file_name="印藥水統計.csv", mime="text/csv", key="stats_dl")
                st.warning("⚠️ 這個「存回雲端」會把「排班歷史」整份清空重建，只留這裡的總數字，"
                            "**每一週實際印哪一天、哪週的明細會全部消失**（變成「統計-印01」這種"
                            "沒有日期的假列）。只有在你確定要「整批重設」所有人的累計數字時才用這個，"
                            "平常要修正某一週的資料，請用「每週印藥水」重新排那一週、送到雲端就好，"
                            "不要在這裡改數字存檔。")
                if TEST_MODE:
                    if st.button("🧪 存回雲端（模擬）", key="stats_save_test"):
                        st.info("🧪 測試模式：模擬儲存成功，沒有真的寫到雲端。")
                elif APPS_SCRIPT_URL and WRITE_SECRET:
                    _confirm_wipe = st.checkbox(
                        "我知道這樣會清空所有人的每週明細、只留總數字，仍要繼續", key="stats_save_confirm")
                    if st.button("💾 存回雲端", type="primary", key="stats_save", disabled=not _confirm_wipe):
                        with st.spinner("儲存中…"):
                            ok, err = save_schedule_stats(edited_st)
                        if ok:
                            st.success("✅ 排班統計已更新！下次排印藥水會自動用新數字。")
                            st.session_state["schedule_stats"] = edited_st.reset_index(drop=True)
                            st.balloons()
                        else:
                            st.error(f"儲存失敗：{err}")

    # ── Tab1 下半：個人明細查詢 ──────────────────────────
    with tab1:
        with st.expander("🔍 查詢個人印/休明細（點我展開）", expanded=False):
            _dc1, _dc2 = st.columns([2, 1])
            if _dc1.button("🔄 載入明細資料", key="detail_load"):
                with st.spinner("讀取中…"):
                    _raw, _raw_err = fetch_schedule_history_raw()
                if _raw is None:
                    st.session_state["schedule_detail"] = f"err:{_raw_err}"
                elif _raw.empty:
                    st.session_state["schedule_detail"] = "empty"
                else:
                    st.session_state["schedule_detail"] = _raw
            if "schedule_detail" in st.session_state:
                _raw = st.session_state["schedule_detail"]
                if isinstance(_raw, str) and _raw == "empty":
                    st.warning("雲端無歷史資料。")
                elif isinstance(_raw, str):
                    st.error(f"讀取失敗：{_raw[4:] if _raw.startswith('err:') else _raw}")
                else:
                    names = sorted(_raw["姓名"].unique().tolist())
                    sel_name = st.selectbox("選擇人員", names, key="detail_sel")
                    if sel_name:
                        person_df = _raw[_raw["姓名"] == sel_name].copy()
                        n_print = (person_df["狀態"] == "印").sum()
                        n_rest  = (person_df["狀態"] == "休").sum()
                        st.caption(f"**{sel_name}** — 印 {n_print} 次 ／ 休 {n_rest} 次")
                        # 週次可能被 Google Sheets 把前導零吃掉（0112→112），轉回 YYYY/MM/DD
                        from datetime import timezone, timedelta
                        _today = datetime.now(timezone(timedelta(hours=8))).date()
                        def _fmt_week(w):
                            s = str(w).strip()
                            # 純數字 3-4 碼 → 補零到4碼 → 推算年份 → YYYY/MM/DD
                            if re.match(r"^\d{3,4}$", s):
                                s = s.zfill(4)
                                try:
                                    mo, dy = int(s[:2]), int(s[2:])
                                    yr = _today.year
                                    d = date(yr, mo, dy)
                                    if (d - _today).days > 180:
                                        d = date(yr - 1, mo, dy)
                                    return d.strftime("%Y/%m/%d")
                                except Exception:
                                    return s
                            return s
                        person_df["日期"] = person_df["週次"].apply(_fmt_week)
                        show_cols = ["日期", "狀態"]
                        if "治療日" in person_df.columns and person_df["治療日"].str.strip().ne("").any():
                            show_cols.append("治療日")
                        disp = person_df[show_cols].sort_values("日期").reset_index(drop=True)
                        def _color_row(row):
                            color = "#d4edda" if row["狀態"] == "印" else "#fff3cd"
                            return [f"background-color:{color}"] * len(row)
                        st.dataframe(disp.style.apply(_color_row, axis=1),
                                     use_container_width=True, hide_index=True)

    # ── Tab2：稽核統計 ──────────────────────────────────
    with tab2:
        st.caption("每人累積稽核次數與休息次數。可直接改，改完按「💾 存回雲端」，下次排稽核即生效。")
        _ac1, _ac2 = st.columns(2)
        if _ac1.button("🔄 讀取", type="primary", key="audit_stats_load"):
            with st.spinner("讀取中…"):
                _ast = fetch_audit_stats()
            st.session_state["audit_stats"] = _ast if _ast is not None else "empty"
        if not TEST_MODE and APPS_SCRIPT_URL and WRITE_SECRET:
            if _ac2.button("📤 同步本機CSV→雲端", key="audit_sync_local",
                           help="把 repo 裡稽核紀錄.csv「雲端還沒有的月份」補進雲端，"
                                "雲端既有的月份不會被覆蓋或刪除（v3.38起，只補不蓋）。"):
                with st.spinner("讀取雲端現況並比對中…"):
                    _aok, _an, _aerr = sync_audit_history_from_csv()
                if _aok and _an == 0:
                    st.info("雲端已經有本機CSV全部的月份，沒有需要補的資料（沒有動到任何一筆）。")
                elif _aok:
                    st.success(f"✅ 已把本機獨有的 {_an} 筆（雲端原本沒有的月份）補進雲端！按「🔄 讀取」確認。")
                    st.session_state.pop("audit_stats", None)
                else:
                    _hint = "（Google 伺服器較慢，已自動重試，請再按一次）" if "逾時" in (_aerr or "") else ""
                    st.error(f"同步失敗：{_aerr or '未知錯誤'}{_hint}")
        if "audit_stats" in st.session_state:
            df_ast = st.session_state["audit_stats"]
            if isinstance(df_ast, str) and df_ast == "empty":
                st.warning("雲端還沒有稽核歷史。請按「📤 同步本機CSV→雲端」把今年全年歷史上傳。")
            elif isinstance(df_ast, str):
                st.error(f"讀取失敗：{df_ast}")
            else:
                df_ast = df_ast.copy()
                st.caption(f"共 {len(df_ast)} 人｜淨值越小 → 稽核次少 → 下次優先被排稽核")
                edited_ast = st.data_editor(df_ast, column_config={
                    "卡號":           st.column_config.TextColumn("卡號", disabled=True),
                    "姓名":           st.column_config.TextColumn("姓名", disabled=True),
                    "稽核次":         st.column_config.NumberColumn("稽核次 ✏️", min_value=0, step=1),
                    "休次":           st.column_config.NumberColumn("休次 ✏️", min_value=0, step=1),
                    "淨值(稽核-休)":  st.column_config.NumberColumn("淨值", disabled=True),
                }, use_container_width=True, hide_index=True, key="audit_stats_edit")
                edited_ast["淨值(稽核-休)"] = edited_ast["稽核次"] - edited_ast["休次"]
                st.download_button("⬇️ 下載統計 CSV", edited_ast.to_csv(index=False).encode("utf-8-sig"),
                                   file_name="稽核統計.csv", mime="text/csv", key="audit_stats_dl")
                # v3.41：補上跟 Tab1「印藥水統計」一模一樣的防呆。v3.35 幫印藥水那顆加了
                # 警告+必勾確認，但這顆結構完全相同的孿生按鈕被漏掉了——沒警告、沒勾選、
                # type="primary" 直接可按，一次誤觸就會把152筆稽核明細洗成「統計-稽01」假列。
                # 這正是接續包第十三節自己寫過的教訓（只修一個、沒推廣去檢查孿生函式）。
                st.warning("⚠️ 這個「存回雲端」會把「稽核歷史」整份清空重建，只留這裡的總數字，"
                            "**每個月實際誰稽核哪一區哪一班的明細會全部消失**（變成「統計-稽01」這種"
                            "沒有月份/位置的假列），連帶「最新稽核名單」也會讀不到東西。"
                            "只有在你確定要「整批重設」所有人的累計數字時才用這個，"
                            "平常要修正某個月的資料，請用「每月稽核」重排那個月、送到雲端就好，"
                            "不要在這裡改數字存檔。")
                if TEST_MODE:
                    if st.button("🧪 存回雲端（模擬）", key="audit_stats_save_test"):
                        st.info("🧪 測試模式：模擬儲存成功，沒有真的寫到雲端。")
                elif APPS_SCRIPT_URL and WRITE_SECRET:
                    _confirm_wipe_ak = st.checkbox(
                        "我知道這樣會清空所有人的每月稽核明細、只留總數字，仍要繼續",
                        key="audit_stats_save_confirm")
                    if st.button("💾 存回雲端", type="primary", key="audit_stats_save",
                                 disabled=not _confirm_wipe_ak):
                        with st.spinner("儲存中…"):
                            ok2, err2 = save_audit_stats(edited_ast)
                        if ok2:
                            st.success("✅ 稽核統計已更新！下次排稽核會自動用新數字。")
                            st.session_state["audit_stats"] = edited_ast.reset_index(drop=True)
                            st.balloons()
                        else:
                            st.error(f"儲存失敗：{err2}")

    # ── Tab3：最新稽核名單 ──────────────────────────────────
    with tab3:
        st.caption("讀取玉繡最新一次送出的稽核名單，確認當月稽核安排。")
        if st.button("🔄 讀取最新稽核名單", type="primary", key="latest_audit_load"):
            with st.spinner("讀取中…"):
                _lm, _lr = fetch_latest_audit_result()
            if _lm is None and isinstance(_lr, str):
                st.session_state["latest_audit"] = ("error", _lr)
            elif _lm is None:
                st.session_state["latest_audit"] = ("empty", None)
            else:
                st.session_state["latest_audit"] = (_lm, _lr)
        if "latest_audit" in st.session_state:
            _la = st.session_state["latest_audit"]
            if _la[0] == "error":
                st.error(f"讀取失敗：{_la[1]}")
            elif _la[0] == "empty":
                st.warning("雲端還沒有稽核歷史，請先同步稽核紀錄.csv 到雲端。")
            else:
                _month, _df_la = _la
                st.success(f"**{_month}** 稽核名單")
                _稽核者 = _df_la[_df_la["狀態"] == "稽核"].copy().reset_index(drop=True)
                _休息者 = _df_la[_df_la["狀態"] == "休"].copy().reset_index(drop=True)
                # 若有位置欄，拆成 區/組/班次 三欄顯示成表格
                if _稽核者["位置"].str.strip().any():
                    def _split_pos(p):
                        parts = str(p).split("/") if "/" in str(p) else ["", "", str(p)]
                        while len(parts) < 3: parts.append("")
                        return parts[0], parts[1], parts[2]
                    _稽核者[["區","組","班次"]] = pd.DataFrame(
                        [_split_pos(p) for p in _稽核者["位置"]], index=_稽核者.index)
                    st.dataframe(_稽核者[["區","組","班次","姓名"]].rename(columns={"姓名":"稽核者"}),
                                 use_container_width=True, hide_index=True)
                else:
                    for _, _row in _稽核者.iterrows():
                        st.write(f"✅ {_row['姓名']}")
                if not _休息者.empty:
                    st.markdown("**本月休息：**" + "、".join(_休息者["姓名"].tolist()))
        else:
            st.info("按「🔄 讀取最新稽核名單」載入玉繡最新一次排的稽核。")

    # ── Tab4：組員名單 ──────────────────────────────────
    with tab4:
        st.caption("雲端主檔組員名單。新增/刪除組員後按「💾 存回雲端」，之後排班就會用新名單。")
        _m1, _m2 = st.columns(2)
        if _m1.button("🔄 讀取", type="primary", key="members_load"):
            with st.spinner("讀取中…"):
                _mem = fetch_members_cloud()
            st.session_state["members_cloud"] = _mem if _mem is not None else "empty"
        if _m2.button("📤 從本機 CSV 同步到雲端", key="members_sync_local",
                      help="只在雲端還沒有組員名單時可用（初始化）。雲端已經有名單後，"
                           "這顆按鈕不會再覆蓋，請直接在下方表格編輯後按「存回雲端」。"):
            # 組員名單跟排班/稽核歷史不同：真的會有人被移除（離職/退組），不能比照
            # v3.38 那種「只補雲端沒有的」合併邏輯——如果雲端上正確地移除了某人、
            # 但本機CSV還留著舊名字，合併邏輯會把這個人誤救回來。所以這裡改成更嚴格
            # 的作法：只有雲端目前完全是空的（真的是第一次初始化）才允許這顆按鈕動作，
            # 雲端已有名單就一律拒絕，逼大家改用下方表格（會先讀到雲端現況再編輯）。
            _cloud_check = fetch_members_cloud()
            if _cloud_check is not None and not _cloud_check.empty:
                st.error(f"雲端已經有組員名單（{len(_cloud_check)}人），為避免蓋掉雲端現況，"
                         f"這顆按鈕已停用。請按上面「🔄 讀取」載入雲端名單，在下方表格直接"
                         f"新增/刪除/改名字，再按「💾 存回雲端」。")
            else:
                _local_csv = os.path.join(HERE, "組員名單.csv")
                if os.path.exists(_local_csv):
                    try:
                        _ldf = pd.read_csv(_local_csv, encoding="utf-8-sig")
                        _sm_ok, _sm_err = save_members_cloud(_ldf[["卡號","姓名"]])
                        if _sm_ok:
                            st.session_state["members_cloud"] = _ldf[["卡號","姓名"]].reset_index(drop=True)
                            st.success(f"✅ 已同步 {len(_ldf)} 人到雲端！")
                        else:
                            st.error(f"同步失敗：{_sm_err}")
                    except Exception as _e:
                        st.error(f"讀取本機 CSV 失敗：{_e}")
                else:
                    st.error("找不到本機 組員名單.csv，請確認 repo 裡有這個檔。")
        if "members_cloud" not in st.session_state:
            st.info("按「🔄 讀取」載入雲端組員名單；若第一次使用，按「📤 從本機 CSV 同步到雲端」初始化。")
        elif isinstance(st.session_state["members_cloud"], str):
            st.warning("雲端還沒有組員名單，請手動新增後存回雲端。")
            _empty = pd.DataFrame(columns=["卡號","姓名"])
            _new = st.data_editor(_empty, num_rows="dynamic", use_container_width=True,
                                  hide_index=True, key="members_edit_empty")
            if st.button("💾 存回雲端", type="primary", key="members_save_empty"):
                _me_ok, _me_err = save_members_cloud(_new)
                if _me_ok:
                    st.success("✅ 組員名單已儲存！")
                    st.session_state["members_cloud"] = _new
                    st.balloons()
                else:
                    st.error(f"儲存失敗：{_me_err}")
        else:
            df_mem = st.session_state["members_cloud"].copy()
            st.caption(f"共 {len(df_mem)} 人｜可新增列（點最下方 + 號）或直接改名字/卡號")
            edited_mem = st.data_editor(df_mem, num_rows="dynamic",
                                        use_container_width=True, hide_index=True, key="members_edit")
            st.download_button("⬇️ 下載組員名單 CSV", edited_mem.to_csv(index=False).encode("utf-8-sig"),
                               file_name="組員名單.csv", mime="text/csv", key="members_dl")
            if TEST_MODE:
                if st.button("🧪 存回雲端（模擬）", key="members_save_test"):
                    st.info("🧪 測試模式：模擬儲存成功，沒有真的寫到雲端。")
            elif APPS_SCRIPT_URL and WRITE_SECRET:
                if st.button("💾 存回雲端", type="primary", key="members_save"):
                    with st.spinner("儲存中…"):
                        ok3, err3 = save_members_cloud(edited_mem)
                    if ok3:
                        st.success("✅ 組員名單已更新！下次排班自動套用。")
                        st.session_state["members_cloud"] = edited_mem.reset_index(drop=True)
                        st.balloons()
                    else:
                        st.error(f"儲存失敗：{err3}")

    # ── Tab5：休診日（v3.42，單一來源）──────────────────────
    with tab5:
        st.caption("過年、國定假日這種「沒診、不上班」的日子。**週日不用列，程式自動跳過。**")
        st.info("🔗 這份清單是**唯一來源**：排班演算法算「印藥水日」往前推幾天，"
                "跟 LINE 小幫手算「提醒日」往前推幾天，都讀這一份。"
                "在這裡改一次，兩邊自動一致，不會再出現「排的日期」跟「LINE 通知的日期」對不上。")
        _h1, _h2 = st.columns(2)
        if _h1.button("🔄 讀取", type="primary", key="hol_load"):
            with st.spinner("讀取中…"):
                _hdf, _herr = fetch_holidays_cloud()
            st.session_state["holidays_cloud"] = _hdf if _hdf is not None else ("err:" + _herr)
        if _h2.button("📤 從本機 CSV 同步到雲端", key="hol_sync_local",
                      help="只在雲端「休診日」分頁還完全是空的時候可用（初始化）。"
                           "雲端已經有資料後，這顆按鈕不會覆蓋，請直接在下方表格編輯後存回雲端。"):
            # 比照 v3.40 組員名單的作法：休診日跟排班/稽核歷史不同，真的會需要「刪除」
            # （例如原本排的補班日取消了），不能用 v3.38「只補雲端沒有的」合併邏輯，
            # 否則刪掉的日子會被本機舊 CSV 救回來。所以只允許在雲端全空時初始化。
            _hchk, _herr2 = fetch_holidays_cloud()
            if _hchk is None:
                st.error(f"讀不到雲端休診日，先不動作以免蓋掉資料：{_herr2}")
            elif not _hchk.empty:
                st.error(f"雲端已經有 {len(_hchk)} 筆休診日，為避免蓋掉雲端現況，這顆按鈕已停用。"
                         "請按上面「🔄 讀取」載入後，在下方表格直接新增/刪除，再按「💾 存回雲端」。")
            else:
                _lh = os.path.join(HERE, "休診日.csv")
                if not os.path.exists(_lh):
                    st.error("找不到本機 休診日.csv。")
                else:
                    try:
                        _ldf = pd.read_csv(_lh, encoding="utf-8-sig", dtype=str).fillna("")
                        if "日期" not in _ldf.columns:
                            st.error("本機 休診日.csv 沒有「日期」欄位。")
                        elif _ldf.empty:
                            st.info("本機 休診日.csv 也是空的，沒有東西可以同步"
                                    "（代表目前確實沒有登記任何休診日，這是正常狀態）。")
                        else:
                            if "說明" not in _ldf.columns: _ldf["說明"] = ""
                            _ok, _n, _e = save_holidays_cloud(_ldf[["日期", "說明"]])
                            if _ok:
                                st.success(f"✅ 已同步 {_n} 筆休診日到雲端！")
                                st.session_state["holidays_cloud"] = _ldf[["日期", "說明"]].reset_index(drop=True)
                            else:
                                st.error(f"同步失敗：{_e}")
                    except Exception as _e:
                        st.error(f"讀取本機 CSV 失敗：{_e}")

        _hstate = st.session_state.get("holidays_cloud")
        if _hstate is None:
            st.info("按「🔄 讀取」載入雲端休診日。")
        elif isinstance(_hstate, str):
            st.error("讀取失敗：" + _hstate[4:])
            st.caption("⚠️ 讀不到的期間，排班會退回用本機 休診日.csv，"
                       "跟 LINE 小幫手讀的雲端分頁可能不一致——請先修好再排班。")
        else:
            _hdf = _hstate.copy()
            if _hdf.empty:
                st.warning("雲端目前沒有登記任何休診日。若今年有過年/連假要跳過，請在下面新增。")
                _hdf = pd.DataFrame(columns=["日期", "說明"])
            else:
                st.caption(f"共 {len(_hdf)} 天｜點最下方 ➕ 新增一列，或把整列清空來刪除")
            _edited_h = st.data_editor(
                _hdf, num_rows="dynamic", use_container_width=True, hide_index=True,
                column_config={
                    "日期": st.column_config.TextColumn(
                        "日期（YYYY-MM-DD）", help="一定要打成 2026-01-01 這種格式（西元、月日補零）"),
                    "說明": st.column_config.TextColumn("說明（例：春節）"),
                }, key="hol_edit")
            # 存出去之前先自己檢查格式，不要等 GAS 那邊靜默吃掉
            _bad = [str(v).strip() for v in _edited_h["日期"].tolist()
                    if str(v).strip() and not HOLIDAY_RE.match(str(v).strip())]
            if _bad:
                st.error("這幾筆日期格式不對（要 2026-01-01 這種）：" + "、".join(_bad))
            st.download_button("⬇️ 下載休診日 CSV", _edited_h.to_csv(index=False).encode("utf-8-sig"),
                               file_name="休診日.csv", mime="text/csv", key="hol_dl")
            if TEST_MODE:
                if st.button("🧪 存回雲端（模擬）", key="hol_save_test"):
                    st.info("🧪 測試模式：模擬儲存成功，沒有真的寫到雲端。")
            elif APPS_SCRIPT_URL and WRITE_SECRET:
                if st.button("💾 存回雲端", type="primary", key="hol_save", disabled=bool(_bad)):
                    with st.spinner("儲存中…"):
                        _ok, _n, _e = save_holidays_cloud(_edited_h)
                    if _ok:
                        st.success(f"✅ 已存回雲端（{_n} 天）！排班演算法與 LINE 小幫手都會立刻用新清單。")
                        st.session_state["holidays_cloud"] = _edited_h.reset_index(drop=True)
                        st.balloons()
                    else:
                        st.error(f"儲存失敗：{_e}")
        st.caption("💡 repo 裡的 `休診日.csv` 從 v3.42 起只是**離線備份**（雲端讀不到時的保底），"
                   "平常請一律在這一頁改，不要去改那個檔案。")
