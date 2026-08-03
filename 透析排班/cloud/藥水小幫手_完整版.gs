/**
 * 透析印藥水 LINE 小幫手 v6.3 — Apps Script
 * ════════════════════════════════════════════════════════
 *  v6.3（2026-08-02）修玉繡回報的「暫存失敗」，順帶挖出一顆更嚴重的地雷：
 *  【症狀】按「✅ 產生定案」跳「⚠️ 雲端草稿暫存失敗（網路問題？）」、按「💾 備份草稿」
 *   跳「暫存失敗，請稍後再試」。**不是網路問題。**
 *  【成因1】「排班草稿」分頁表頭只有 4 欄，但 app.py 的 push_week_draft() 送的是 6 欄
 *   （[週次] + [印日期, 區, 姓名, 🔺跨區, 治療欄key]）。Range.setValues() 欄數對不上
 *   直接拋例外 → 每次都失敗。而且 app.py 讀回來時本來就預期有第5欄才能走「零碰撞」
 *   那條路（同一個印藥水日有多人時，不用靠日期猜是哪一格），所以這個功能從加進來
 *   就沒真正生效過，小巫也從來看不到草稿。表頭補成 6 欄（DRAFT_HEADERS）對齊兩端。
 *  【成因2／更嚴重】writeAllRowsFast_() 是「先 clearContents() 再 setValues()」。
 *   setValues() 一失敗，分頁就停在「已清空、新資料沒寫進去」＝**資料整份消失**。
 *   「排班草稿」就是這樣每次被清成空的（已實際重現：寫入前 2 列 → 失敗後 0 列）。
 *   而這個函式同時被 setWeek(本週名單)、setAllScheduleHistory(排班歷史)、setMembers
 *   (組員名單)、writeHistory_ 共用——同一顆踩在排班歷史上就是整年資料歸零，正是這個
 *   專案出事過好幾次的災情類型（接續包第十三、十六節）。改成先把每列正規化成表頭
 *   寬度、欄數超過就丟例外**中止且完全不動原有資料**，全部檢查完才清空寫入。
 *  v6.2（2026-08-01）補完接續包第二十三節剩下的兩個 GAS 待辦：
 *  【#14】pushLine_() 沒檢查 LINE API 回應碼：原本 muteHttpExceptions:true 把回應
 *   整個吞掉、回傳值也沒人看，就算 LINE 回 401(token失效)/403(額度)/400(userId無效)，
 *   程式一樣當成功、照樣寫「提醒紀錄」、照樣算 sent++。這會同時騙過三道防線：
 *   ①同仁其實沒收到 ②提醒紀錄有假紀錄，dedup 之後永遠不會重試 ③v6.0 健康檢查看到
 *   有紀錄就以為沒事、連玉繡都不會被通知。改成檢查 getResponseCode()，只有 2xx 算成功；
 *   sendReminders 發送失敗就**不寫提醒紀錄**（下次執行自動重試、健康檢查也抓得到），
 *   sendAuditNotice 把失敗人數與名字回傳給網頁，健康檢查那則也會在 log 標明有沒有送出去。
 *  【#16】補發（catch-up）文案沿用「今天」用詞：印藥水日已經過去了才補發時，訊息照講
 *   「⚠️ 今天 M/d 就要印」，但那個日期根本不是今天，同仁會看不懂或誤以為排錯。改成
 *   印藥水日已過就講「⚠️ 補發通知：M/d 就要印…（這個日期已經過了），如果還沒印請盡快
 *   處理」。提前提醒那一層維持原文案（那層的印藥水日一定還沒到，本來就沒有這個問題）。
 *  v6.1（2026-08-01）休診日改成「單一來源」：原本休診日有兩份各自維護的清單——
 *  webapp/休診日.csv（排班.py 的 prev_treat() 用，決定印藥水日往前推幾天）跟這支
 *  .gs 裡寫死的 EXTRA_HOLIDAYS 陣列（prevWorkday_() 用，決定 LINE 提醒往前推的
 *  日子）。改一邊不會同步到另一邊，兩邊一旦對不上，就會出現「排班算出來的印藥水日」
 *  跟「LINE 提醒的日期」差一天——跟 v5.8 修掉的 off-by-one 是同一類災情，只是還沒
 *  實際爆發（因為到目前為止兩份清單剛好都是空的）。
 *  改法：試算表新增「休診日」分頁（欄位：日期, 說明）當唯一來源。
 *   • 這支 .gs 的 isWorkday_() 改讀該分頁（getHolidaySet_()，同一次執行只讀一次、
 *     結果快取起來，避免 prevWorkday_ 迴圈重複打 API）
 *   • app.py 新增 getHolidays/setHolidays 兩個 action，排班前把雲端休診日當
 *     config_override 餵給 排班.py／稽核.py，跟組員名單走同一套「雲端優先、
 *     本機 CSV 保底」模式
 *   • EXTRA_HOLIDAYS 從此只是「分頁還不存在時的一次性種子」，不再是維護入口
 *  日期一律經 normDate_() 正規化再比對——Google Sheets 會把「2026-01-01」存成
 *  日期型別，getValues() 拿到的是 Date 物件，直接 String() 會變 "Wed Jan 01 2026…"
 *  永遠比不中（這正是 app.py v3.41 gs_date_to_ymd 修過的同一類型別陷阱）。
 *  v6.0（2026-07-21）加「主動健康檢查」：使用者反映「有些同仁沒收到提醒也不會主動
 *  告知」——光靠v5.9的補發機制還是被動的，如果補發之後還是漏了（例如缺userId對照、
 *  發送當下出錯），沒有人會發現。改成每次sendReminders()執行完，順便掃一次本週名單
 *  裡所有印藥水日「今天或已過」的人，檢查提醒紀錄有沒有他至少一則紀錄，完全沒有的人
 *  直接組清單發LINE通知玉繡本人，變成系統主動抓漏，不用等同仁反映才知道。
 *  v5.9（2026-07-21）加「補發」機制：v5.8修好算錯天之後，發生林欣儀/高翠盈那週完全沒
 *  收到提醒——原因是名單送到雲端的時間(7/19傍晚)晚於她們提醒窗口該發生的日子(7/17~18)，
 *  每天固定一次的排程執行時名單還沒進來，之後也沒有補救機制。就算玉繡照平常週日送出
 *  下週名單，只要有人印藥水日是週一，提前提醒該發的日子是週六，一樣會卡到同樣的縫——
 *  不是「送太晚」的問題，是「每天只固定檢查一次」這個機制本身沒有補漏的能力。
 *  解法：`setWeek` 收到新名單、寫入本週名單的當下，立刻呼叫 sendReminders(true)（補發
 *  模式）——只要有人的提醒窗口「今天或更早」已經到期但還沒發過，馬上補發，不用等隔天
 *  固定排程。原本的每日固定觸發（呼叫 sendReminders()，不帶參數）行為完全不變。
 *  防重複也一併加固：改成掃「提醒紀錄」全部歷史列（不再只看「今天」），因為補發可能
 *  發生在跟「精準當天」不同的日子，只看「今天」會讓dedup在補發後的隔天固定排程失效、
 *  重複發送。
 *  v5.8（2026-07-20）修正提醒日期系統性提早一個工作天的bug：sendReminders() 原本假設
 *  「本週名單」存的日期是「上班日」，還要再往前推一個上班日才是真正印藥水日。但這欄
 *  日期本身就已經是 app.py（排班.py）算好、Streamlit畫面顯示、玉繡實際送出的真正印藥水日，
 *  不需要再往前推。實測0720~0726整週12人全部被提早一個工作天發提醒（不是單一個案），
 *  已拿掉多餘的那一次 prevWorkday_()，改成直接用名單存的日期當印藥水日。
 *  v5.7（2026-07-19）：v5.6 加的 Logger.log 使用者在「執行項目」畫面點不開看不到內容，
 *  改成直接把 ss.getId()/ss.getName()/寫入前後列數/收到的rows筆數/key 塞進回傳的 JSON，
 *  這樣 app.py 收到回應時就能直接把診斷資訊顯示在 Streamlit 畫面上，不必再靠 Apps Script
 *  的記錄檔 UI。Logger.log 保留，當作備援。
 *  功能①：自動收 userId（LINE webhook）
 *  功能②：每天自動發提醒 ★名單日期=印藥水日（v5.8修正，跳過週日/休診日）；提前一則+當天一則；
 *  含防重複；名單送到當下立即補發已逾期未發的提醒（v5.9）；主動健康檢查、發現完全
 *  沒收到提醒的人直接通知玉繡（v6.0）
 *  功能③：接收網頁送來的名單（setWeek）
 *  功能④：儲存/讀取排班歷史（供下週公平輪序）
 *  功能⑤：儲存/讀取稽核歷史（供下月公平輪序）
 *  功能⑥：getLatestBanbiao — 讀 Gmail「班表」標籤最新 Excel 附件（網頁一鍵抓班表）
 *  功能⑦：組員名單雲端主檔、排班草稿（小巫雙重確認）、整批覆寫歷史（統計管理頁用）
 *  功能⑧：休診日雲端主檔（getHolidays/setHolidays，v6.1）——本檔算提醒日、排班.py
 *          算印藥水日，兩邊讀同一個「休診日」分頁，改一個地方兩邊自動一致
 *
 *  v5.4（2026-07-19）：發現這份 v5.3 跟 Streamlit 實際呼叫的 URL 是同一個部署但版本落後、
 *  且比對後發現 v5.3 少了 app.py 會呼叫的 6 個功能（setWeekDraft/getWeekDraft/
 *  setAllScheduleHistory/getMembers/setMembers/setAllAuditHistory），導致這幾個功能
 *  呼叫時 GAS 回「unknown action」。已從舊版本補回這 6 個函式，v5.3 原本的提醒邏輯
 *  （二階段提醒＋防重複）完全沒動。
 *
 *  v5.5（2026-07-19）：整批資料（例如全年389筆排班歷史）用逐列 appendRow() 寫入太慢，
 *  實測連續逾時。改用 writeAllRowsFast_()（Range.setValues() 一次寫入整批），
 *  setWeek/setAllScheduleHistory/setAllAuditHistory/setMembers/setWeekDraft/
 *  writeHistory_ 全部套用，行為不變、只是變快。
 */

var LINE_TOKEN  = "zeJ2uTt7yRF4EQZ1nN0tgQqZqfzkScfWxTmEtGjPDbByEtjEKkQucms/SYc9uYiEyHbODMrsqlB2L+z0Xl1EPpe4/w/nIR9AT6xb+7gBUgsPlqjEsj4Hp907Zr/gMkpiJWlSWaU20t4vI6au33BKbAdB04t89/1O/w1cDnyilFU=";   // ← Channel access token（不要按 Reissue！）
var WRITE_SECRET = "yaoshui2026";   // ← 網頁送名單用的暗號（與 Streamlit Secrets 一致）

// ★休診日的唯一來源＝試算表的「休診日」分頁（欄位：日期, 說明），格式 "2026-01-01"。
//   週日自動跳過，不用列在裡面。要新增/刪除休診日，請到 Streamlit「📊 統計管理 →
//   🗓 休診日」編輯，或直接改試算表那個分頁——排班演算法（排班.py 的 prev_treat）
//   跟這裡的 LINE 提醒（prevWorkday_）都讀同一份，不會再出現兩邊對不上的情況。
//
// ⚠️ 下面這個陣列**不是維護入口**，只是「休診日分頁還不存在時」用來建立分頁的一次性
//   種子（v6.1 之前的舊資料搬家用）。分頁一旦建立，就一律以分頁為準，改這裡沒有用。
var HOLIDAY_SHEET = "休診日";

/* v6.3：「排班草稿」分頁的表頭。原本只有 4 欄（週次/印日期/區/姓名），但 app.py 的
 * push_week_draft() 送的是 6 欄——[週次] + [印日期, 區, 姓名, 🔺跨區, 治療欄key]，
 * 欄數對不上，Range.setValues() 每次都拋例外，玉繡按「💾 備份草稿」或「產生定案」
 * 一律看到「暫存失敗」。而且 app.py 讀回來時本來就預期有第5欄（治療欄key）才能走
 * 「零碰撞」那條路（同一個印藥水日有多人時不用靠日期猜是哪一格），等於這個功能
 * 從加入以來就沒真正生效過。表頭補成 6 欄，跟兩端實際的資料格式對齊。 */
var DRAFT_HEADERS = ["週次","印日期","區","姓名","跨區","治療欄"];
var EXTRA_HOLIDAYS = [
  // "2026-01-01",
  // "2026-02-16",
];


/* ━━━━━━━━━━ doPost（LINE webhook ＋ 網頁 API）━━━━━━━━━━ */
function doPost(e) {
  try {
    var body = JSON.parse(e.postData.contents);
    var ss = SpreadsheetApp.getActiveSpreadsheet();

    // ── LINE webhook（有 events 欄位，沒有 action）──
    if (body.events) {
      var sh = ensureSheet_(ss, "userid", ["時間","事件","userId","傳來的文字"]);
      (body.events || []).forEach(function(ev) {
        var uid = ev.source && ev.source.userId;
        var text = (ev.type === "message" && ev.message && ev.message.type === "text")
                   ? ev.message.text : "";
        if (uid) sh.appendRow([new Date(), ev.type, uid, text]);
      });
      return ContentService.createTextOutput("OK");
    }

    // ── 網頁 API（需要暗號）──
    if (body.secret !== WRITE_SECRET) {
      return jsonOut_({ok: false, error: "wrong secret"});
    }

    var action = body.action || "";

    if (action === "setWeek") {
      var sh2 = ensureSheet_(ss, "本週名單", ["印日期","區","姓名"]);
      writeAllRowsFast_(sh2, ["印日期","區","姓名"], body.rows || []);
      // v5.9：名單送到的當下，立刻補發「已經過期還沒發過」的提醒，不用等隔天9點多的
      // 固定排程——這樣不管玉繡幾點送出名單，只要有人的提醒窗口已經過了，送出的當下
      // 就會馬上補發，不會卡在「送太晚、當天排程已經跑過」這個縫隙裡（見接續包第二十節）。
      try { sendReminders(true); } catch (e) { Logger.log("setWeek 補發提醒失敗：" + e); }
      return jsonOut_({ok: true, count: (body.rows || []).length});
    }

    if (action === "getScheduleHistory") {
      return jsonOut_({ok: true, rows: sheetToArray_(ss, "排班歷史")});
    }

    if (action === "setScheduleHistory") {
      Logger.log("setScheduleHistory 收到 key=" + JSON.stringify(body.key)
                 + " rows筆數=" + ((body.rows || []).length)
                 + " 第一筆=" + JSON.stringify((body.rows || [])[0])
                 + " ss.getId()=" + ss.getId()
                 + " ss.getName()=" + ss.getName());
      var beforeCount = sheetToArray_(ss, "排班歷史").length;
      writeHistory_(ss, "排班歷史", ["週次","卡號","姓名","狀態","治療日"],
                    body.key, body.rows || []);
      var afterCount = sheetToArray_(ss, "排班歷史").length;
      Logger.log("setScheduleHistory 寫入前列數=" + beforeCount + " 寫入後列數=" + afterCount);
      return jsonOut_({ok: true, before: beforeCount, after: afterCount,
                        ssId: ss.getId(), ssName: ss.getName(),
                        gotRows: (body.rows || []).length, gotKey: String(body.key)});
    }

    if (action === "setAllScheduleHistory") {
      var shAll = ensureSheet_(ss, "排班歷史", ["週次","卡號","姓名","狀態","治療日"]);
      writeAllRowsFast_(shAll, ["週次","卡號","姓名","狀態","治療日"], body.rows || []);
      return jsonOut_({ok: true});
    }

    if (action === "getAuditHistory") {
      return jsonOut_({ok: true, rows: sheetToArray_(ss, "稽核歷史")});
    }

    if (action === "setAuditResult") {
      writeHistory_(ss, "稽核歷史", ["月份","卡號","姓名","狀態","位置"],
                    body.key, body.rows || []);
      return jsonOut_({ok: true});
    }

    if (action === "setAllAuditHistory") {
      var headersAud = ["月份","卡號","姓名","狀態","位置"];
      var shAudAll = ensureSheet_(ss, "稽核歷史", headersAud);
      var dataAud = shAudAll.getLastRow() > 0 ? shAudAll.getDataRange().getValues() : [headersAud];
      // 保留草稿與意見回饋，清除正常月份和統計重建記錄
      var keptAud = [];
      for (var iAud = 1; iAud < dataAud.length; iAud++) {
        var mAud = String(dataAud[iAud][0]).trim();
        if (mAud === "草稿" || mAud.indexOf("意見-") === 0) keptAud.push(dataAud[iAud]);
      }
      writeAllRowsFast_(shAudAll, headersAud, keptAud.concat(body.rows || []));
      return jsonOut_({ok: true});
    }

    if (action === "getMembers") {
      var shMem = ensureSheet_(ss, "組員名單", ["卡號","姓名"]);
      return jsonOut_({ok: true, rows: shMem.getDataRange().getValues()});
    }

    if (action === "setMembers") {
      var shMem2 = ensureSheet_(ss, "組員名單", ["卡號","姓名"]);
      writeAllRowsFast_(shMem2, ["卡號","姓名"], body.rows || []);
      return jsonOut_({ok: true});
    }

    // ── 休診日（v6.1）：唯一來源，排班.py 與本檔的 prevWorkday_ 都讀這一份 ──
    if (action === "getHolidays") {
      // 先呼叫 getHolidaySet_ 是為了讓分頁不存在時自動建立（含舊種子搬家），
      // 這樣 app.py 第一次讀就能拿到正常的表頭而不是空回應。
      getHolidaySet_("Asia/Taipei");
      var shHol = ensureSheet_(ss, HOLIDAY_SHEET, ["日期","說明"]);
      return jsonOut_({ok: true, rows: shHol.getDataRange().getValues()});
    }

    if (action === "setHolidays") {
      var shHol2 = ensureSheet_(ss, HOLIDAY_SHEET, ["日期","說明"]);
      writeAllRowsFast_(shHol2, ["日期","說明"], body.rows || []);
      _HOLIDAY_CACHE = null;                 // 同一次執行若後續要算日期，要吃到新清單
      return jsonOut_({ok: true, count: (body.rows || []).length});
    }

    if (action === "getWeekDraft") {
      var shDraft = ensureSheet_(ss, "排班草稿", DRAFT_HEADERS);
      return jsonOut_({ok: true, rows: shDraft.getDataRange().getValues()});
    }

    if (action === "setWeekDraft") {
      var shDraft2 = ensureSheet_(ss, "排班草稿", DRAFT_HEADERS);
      writeAllRowsFast_(shDraft2, DRAFT_HEADERS, body.rows || []);
      return jsonOut_({ok: true, count: (body.rows || []).length});
    }

    if (action === "sendAuditNotice") {
      var map2 = buildUserMap_(ss);
      var month = body.month || "";
      var sent2 = 0, miss2 = 0, failed2 = 0, failedNames = [];
      (body.notices || []).forEach(function(n) {
        var uid3 = map2[n.name];
        if (!uid3) { Logger.log("缺 userId（稽核通知）：" + n.name); miss2++; return; }
        // v6.2（#14）：LINE 真的送失敗時要算成失敗、回報給網頁，不能一律 sent2++
        if (pushLine_(uid3, "📋 " + month + " 你這個月負責【" + n.position + "】稽核藥水，請自行安排兩天進行稽核。🙏")) {
          sent2++;
        } else {
          failed2++; failedNames.push(n.name);
        }
      });
      Logger.log("稽核通知：發 " + sent2 + " 人，缺 userId " + miss2 + " 人，LINE發送失敗 " + failed2 + " 人");
      return jsonOut_({ok: true, sent: sent2, miss: miss2,
                       failed: failed2, failedNames: failedNames});
    }

    if (action === "getLatestBanbiao") {
      var label = GmailApp.getUserLabelByName("班表");
      var threads = label ? label.getThreads(0, 30) : [];
      var bestAtt = null, bestDate = null;
      for (var ti = 0; ti < threads.length; ti++) {
        var msgs = threads[ti].getMessages();
        for (var mi = 0; mi < msgs.length; mi++) {
          var md = msgs[mi].getDate();
          var atts = msgs[mi].getAttachments();
          for (var ai = 0; ai < atts.length; ai++) {
            if (atts[ai].getName().toLowerCase().indexOf(".xls") >= 0) {
              if (!bestDate || md > bestDate) { bestDate = md; bestAtt = atts[ai]; }
            }
          }
        }
      }
      if (!bestAtt) {
        return jsonOut_({ok: false, error: "找不到『班表』標籤下的 Excel 附件（請確認班表信已進來並貼上『班表』標籤）"});
      }
      return jsonOut_({
        ok: true,
        filename: bestAtt.getName(),
        date: Utilities.formatDate(bestDate, "Asia/Taipei", "yyyy-MM-dd HH:mm"),
        b64: Utilities.base64Encode(bestAtt.getBytes())
      });
    }

    return jsonOut_({ok: false, error: "unknown action: " + action});
  } catch(err) {
    return jsonOut_({ok: false, error: String(err)});
  }
}

function doGet() { return ContentService.createTextOutput("ok"); }


/* ━━━━━━━━━━ 上班日工具（跳過週日 + 休診日）━━━━━━━━━━ */

/* v6.1：休診日改讀試算表「休診日」分頁（唯一來源，跟 排班.py 讀的是同一份）。
 * ★快取：prevWorkday_() 每個人最多會往回試 21 天、每天都問一次 isWorkday_()，
 *   12 個人就是好幾百次；沒有快取的話會把 Sheets API 打爆、執行也會變超慢。
 *   這個變數是「同一次執行」內有效（Apps Script 每次 doPost/觸發器都是全新執行，
 *   所以不會拿到隔夜的舊資料）。
 * ★型別陷阱：Sheets 會把 "2026-01-01" 存成日期型別，getValues() 回傳 Date 物件，
 *   直接 String() 會變 "Wed Jan 01 2026 00:00:00 GMT+0800"，永遠比不中 yyyy-MM-dd。
 *   一律先過 normDate_() 正規化。
 */
var _HOLIDAY_CACHE = null;
function getHolidaySet_(tz) {
  if (_HOLIDAY_CACHE) return _HOLIDAY_CACHE;
  var set = {};
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sh = ss.getSheetByName(HOLIDAY_SHEET);
    if (!sh) {
      // 分頁還不存在 → 建立，並把舊的 EXTRA_HOLIDAYS 種子搬進去（一次性搬家）。
      // 之後這個分頁就是唯一來源，改陣列不再有任何效果。
      sh = ss.insertSheet(HOLIDAY_SHEET);
      var seed = [["日期", "說明"]];
      for (var si = 0; si < EXTRA_HOLIDAYS.length; si++) {
        seed.push([EXTRA_HOLIDAYS[si], "（v6.1 從程式碼搬過來的舊資料）"]);
      }
      sh.getRange(1, 1, seed.length, 2).setValues(seed);
      Logger.log("已建立「" + HOLIDAY_SHEET + "」分頁，搬入種子 " + EXTRA_HOLIDAYS.length + " 筆");
    }
    var rows = sh.getDataRange().getValues();
    for (var i = 1; i < rows.length; i++) {
      var s = normDate_(rows[i][0], tz);
      if (/^\d{4}-\d{2}-\d{2}$/.test(s)) set[s] = true;
      else if (String(rows[i][0]).trim()) Logger.log("休診日格式不對，已略過：" + rows[i][0]);
    }
  } catch (e) {
    // 讀不到分頁（權限/API 暫時失敗）→ 退回程式碼裡的種子，並記 log。
    // 寧可用舊清單也不要當成「完全沒有休診日」而把提醒日算錯。
    Logger.log("讀取休診日分頁失敗，暫時改用 EXTRA_HOLIDAYS 種子：" + e);
    for (var k = 0; k < EXTRA_HOLIDAYS.length; k++) set[EXTRA_HOLIDAYS[k]] = true;
  }
  _HOLIDAY_CACHE = set;
  return set;
}

function isWorkday_(d, tz) {
  if (d.getDay() === 0) return false;                       // 週日休
  var s = Utilities.formatDate(d, tz, "yyyy-MM-dd");
  return !getHolidaySet_(tz)[s];                            // 不在休診清單
}
/** 嚴格「之前」最近的上班日 */
function prevWorkday_(d, tz) {
  var x = new Date(d.getTime());
  for (var i = 0; i < 21; i++) {
    x = new Date(x.getTime() - 24 * 60 * 60 * 1000);
    if (isWorkday_(x, tz)) return x;
  }
  return x;
}
/** "yyyy-MM-dd" → Date（本地時間正午，避時區誤差） */
function parseYmd_(s) {
  var m = String(s).trim().match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  if (!m) return null;
  return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]), 12, 0, 0);
}


/* ━━━━━━━━━━ 每日提醒（錨定「印藥水日」；兩層＋防重複＋補發）━━━━━━━━━━
 * v5.9（2026-07-21）加補發機制：v5.8修好「算錯天」之後，又發生「林欣儀/高翠盈這次
 *   完全沒收到提醒」——查證後發現不是bug，是那週名單送進雲端的時間(7/19傍晚)，晚於
 *   她們倆提醒窗口該發生的日子(7/17~18)，daily trigger當時執行時名單根本還沒進來，
 *   之後也沒有任何機制會回頭補發。玉繡就算照平常週日送出下週名單，只要有人印藥水日
 *   落在週一，提前提醒該發的日子是週六，一樣會卡到同樣的縫——不是「送太晚」的問題，
 *   是「每天只固定檢查一次」這個機制本身沒有補救漏接的能力。
 *   解法：`setWeek` 收到新名單、寫入本週名單的當下，立刻呼叫 sendReminders(true)
 *   （catchUp模式）——只要有人的提醒窗口「今天或更早」就已經到期、但還沒發過，馬上
 *   補發，不用等隔天固定排程。原本的每日固定觸發（呼叫 sendReminders()，不帶參數）
 *   完全不受影響，還是只在「精準等於今天」才發，行為不變。
 * ★防重複：v5.9 改成掃「提醒紀錄」全部歷史列建立 dedup key（不再只看「今天」寫入的
 *   那幾列）——因為補發可能發生在跟「精準當天」不同的日子，舊版只比對「今天」會讓
 *   隔天的固定排程誤判成沒發過、重複發送一次。
 * 第一層（提前）：印藥水日的前一個上班日 → 「🔔 記得 M/d 要印…」
 * 第二層（當天）：印藥水日當天             → 「⚠️ 今天 M/d 要印…」
 * catchUp=true 時，這兩層的判斷從「精準等於今天」放寬成「今天或更早（已經過期還沒發）」。
 */
function sendReminders(catchUp) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var tz = "Asia/Taipei";
  var todayStr = Utilities.formatDate(new Date(), tz, "yyyy-MM-dd");

  var sh = ss.getSheetByName("本週名單");
  if (!sh) { Logger.log("找不到『本週名單』分頁"); return; }
  var rows = sh.getDataRange().getValues();
  var head = rows[0].map(function(x) { return String(x).trim(); });
  var iD = head.indexOf("印日期"); if (iD < 0) iD = head.indexOf("上班日");
  var iZ = head.indexOf("區"), iN = head.indexOf("姓名");

  var map = buildUserMap_(ss);
  var advance = {};   // 提前提醒：姓名 → {areas:[], printStr=印藥水日}
  var sameday = {};   // 當天提醒：姓名 → {areas:[], printStr=印藥水日}

  for (var r = 1; r < rows.length; r++) {
    var dStr = normDate_(rows[r][iD], tz);                  // 名單上的日期 = 印藥水日本身（v5.8修正，不用再往前推）
    var dd = parseYmd_(dStr);
    if (!dd) continue;
    var pDay = dd;                                          // 印藥水日 = 名單存的日期本身
    var aDay = prevWorkday_(pDay, tz);                      // 提前日 = 印藥水日的前一個上班日
    var Pstr = Utilities.formatDate(pDay, tz, "yyyy-MM-dd");
    var Astr = Utilities.formatDate(aDay, tz, "yyyy-MM-dd");

    var nm2 = String(rows[r][iN]).trim(), area = String(rows[r][iZ]).trim();
    if (!nm2) continue;

    var bucket = null;
    if (catchUp) {
      // 補發模式：窗口「今天或更早」就算到期，優先歸類到當天(較晚/較急的那一層)
      if (Pstr <= todayStr) bucket = sameday;
      else if (Astr <= todayStr) bucket = advance;
    } else {
      // 平常固定排程：維持原本「精準等於今天」的行為，不變動
      if (Pstr === todayStr) bucket = sameday;
      else if (Astr === todayStr) bucket = advance;
    }
    if (!bucket) continue;

    if (!bucket[nm2]) bucket[nm2] = {areas: [], printStr: Pstr};   // printStr 一律存「印藥水日」
    if (area && bucket[nm2].areas.indexOf(area) < 0) bucket[nm2].areas.push(area);
  }

  // ★防重複：v5.9 改成掃「提醒紀錄」全部歷史（不再只限今天），因為補發可能發生在
  // 跟「精準當天」不同的日子，只看「今天」會讓dedup在補發後的隔天固定排程時失效。
  var logSh = ensureSheet_(ss, "提醒紀錄", ["日期","類型","姓名","印日","時間"]);
  var sentKeys = {};
  var logRows = logSh.getDataRange().getValues();
  for (var li = 1; li < logRows.length; li++) {
    sentKeys[ logRows[li][1] + "|" + logRows[li][2] + "|" + normDate_(logRows[li][3], tz) ] = true;
  }

  var sent = 0, miss = 0, dup = 0, failed = 0;
  function flush_(todo, type, makeMsg) {
    for (var name in todo) {
      var info = todo[name];
      var key = type + "|" + name + "|" + info.printStr;
      if (sentKeys[key]) { dup++; continue; }              // 已經發過(不管是哪一天發的) → 跳過
      var uid2 = map[name];
      if (!uid2) { Logger.log("缺 userId：" + name); miss++; continue; }
      var md = Utilities.formatDate(parseYmd_(info.printStr), tz, "M/d");
      var zone = info.areas.join("、");
      var zpart = zone ? ("「" + zone + "」") : "";
      // v6.2（#16）：印藥水日已經過去了才補發的情況，文案要講清楚是補發，
      // 不能照講「今天」——那個日期根本不是今天，同仁會看不懂或以為排錯。
      var overdue = info.printStr < todayStr;
      // v6.2（#14）：只有真的送成功才寫「提醒紀錄」。送失敗就不寫，讓下一次執行
      // 自動重試，v6.0 健康檢查也才抓得到「這個人完全沒有紀錄」。
      if (!pushLine_(uid2, makeMsg(md, zpart, overdue))) {
        Logger.log("發送失敗，不寫提醒紀錄以便下次重試：" + type + "|" + name + "|" + info.printStr);
        failed++;
        continue;
      }
      logSh.appendRow([todayStr, type, name, info.printStr, new Date()]);
      sentKeys[key] = true;
      sent++;
    }
  }
  flush_(advance, "前一天", function(md, zpart, overdue) {
    // 提前提醒這一層的印藥水日一定還沒到（catchUp 只在 Pstr > todayStr 時歸到這層），
    // 所以照原本的講法即可，overdue 不會是 true。
    return "🔔 記得 " + md + " 要印" + zpart + "藥水喔！🙏";
  });
  flush_(sameday, "當天", function(md, zpart, overdue) {
    return overdue
      ? "⚠️ 補發通知：" + md + " 就要印" + zpart + "藥水（這個日期已經過了），如果還沒印請盡快處理 🙏"
      : "⚠️ 今天 " + md + " 就要印" + zpart + "藥水喔！別忘了 🙏";
  });

  Logger.log((catchUp ? "[補發]" : "[固定排程]") + "提醒完成：提前 " + Object.keys(advance).length + " 人、當天 "
             + Object.keys(sameday).length + " 人，實發 " + sent + " 則，已發過跳過 " + dup
             + " 則，缺 userId " + miss + " 次，LINE發送失敗 " + failed + " 則（今天 " + todayStr + "）");

  // v6.0：主動健康檢查，發現有人完全沒收到提醒就直接通知玉繡，不用等同仁自己反映
  try { checkMissedReminders_(ss, tz, todayStr, sentKeys, map); } catch (e) { Logger.log("健康檢查失敗：" + e); }
}

/* ━━━━━━━━━━ 健康檢查：主動抓漏（v6.0，2026-07-21）━━━━━━━━━━
 * 使用者反映「有些同仁沒收到提醒也不會主動告知」——光靠v5.9的補發機制還是被動的
 * （只在setWeek送出的當下補一次），如果補發之後還是漏了(例如缺userId、發送當下
 * 出錯)，沒有人會知道。這裡在每次sendReminders()執行完，順便掃一次「本週名單」
 * 裡所有印藥水日「今天或已過」的人，檢查「提醒紀錄」裡有沒有他至少一則紀錄
 * （前一天或當天任一則都算）。完全查無紀錄的人，直接組成清單發LINE通知玉繡本人
 * （對照表裡的「邱玉繡」），變成系統主動抓漏、不用等同仁反映才知道。
 * 同一人同一天會每次執行都重複通知，直到問題解決為止——這是刻意的，玉繡是管理者，
 * 沒解決前持續提醒比漏掉不通知更安全。
 */
function checkMissedReminders_(ss, tz, todayStr, sentKeysAll, map) {
  var sh = ss.getSheetByName("本週名單");
  if (!sh) return;
  var rows = sh.getDataRange().getValues();
  var head = rows[0].map(function(x) { return String(x).trim(); });
  var iD = head.indexOf("印日期"); if (iD < 0) iD = head.indexOf("上班日");
  var iN = head.indexOf("姓名");
  if (iD < 0 || iN < 0) return;

  var missed = [], seen = {};
  for (var r = 1; r < rows.length; r++) {
    var dd = parseYmd_(normDate_(rows[r][iD], tz));
    if (!dd) continue;
    var Pstr = Utilities.formatDate(dd, tz, "yyyy-MM-dd");
    if (Pstr > todayStr) continue;                     // 印藥水日還沒到，還不用檢查
    var nm2 = String(rows[r][iN]).trim();
    var seenKey = nm2 + "|" + Pstr;
    if (!nm2 || seen[seenKey]) continue;
    seen[seenKey] = true;
    var hasAdvance = sentKeysAll["前一天|" + nm2 + "|" + Pstr];
    var hasSameday = sentKeysAll["當天|" + nm2 + "|" + Pstr];
    if (!hasAdvance && !hasSameday) {
      missed.push(nm2 + "(" + Utilities.formatDate(dd, tz, "M/d") + "印)");
    }
  }
  if (missed.length === 0) return;

  var adminUid = map["邱玉繡"];
  if (!adminUid) { Logger.log("健康檢查發現漏發但找不到玉繡的userId：" + missed.join("、")); return; }
  var notified = pushLine_(adminUid,
    "⚠️ 小幫手健康檢查：以下人員的印藥水提醒完全沒有任何發送紀錄，麻煩人工確認一下——\n"
    + missed.join("、")
    + "\n（可能原因：本週名單送達時間晚於提醒窗口、缺userId對照、或發送當下出錯）");
  // v6.2（#14）：連這則警告都送不出去，代表 LINE 端整個有問題（token 失效之類），
  // 一定要在 log 講清楚，否則會變成「系統以為通知過了、其實沒人知道」的雙重靜默。
  Logger.log("健康檢查：發現 " + missed.length + " 人完全沒收到提醒："
             + missed.join("、")
             + (notified ? " → 已通知玉繡" : " → ⚠️ 連通知玉繡的 LINE 訊息都發送失敗！"));
}


/* ━━━━━━━━━━ 試算表選單（手動工具）━━━━━━━━━━ */
function onOpen() {
  SpreadsheetApp.getUi().createMenu("📋 藥水小幫手")
    .addItem("清空本週名單", "clearWeek")
    .addItem("測試：發 LINE 給自己", "testSelf")
    .addToUi();
}
function clearWeek() {
  var sh = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("本週名單");
  if (!sh) return;
  sh.clearContents();
  sh.appendRow(["印日期","區","姓名"]);
  SpreadsheetApp.getUi().alert("✅ 本週名單已清空");
}
function testSelf() {
  pushLine_("U04e906cc9268998aa4f8edf69286858f", "🔔 測試：小幫手正常運作 🙏");
}
function testGetLatestBanbiao() {
  var label = GmailApp.getUserLabelByName("班表");
  var threads = label ? label.getThreads(0, 30) : [];
  var bestAtt = null, bestDate = null;
  for (var ti = 0; ti < threads.length; ti++) {
    var msgs = threads[ti].getMessages();
    for (var mi = 0; mi < msgs.length; mi++) {
      var md = msgs[mi].getDate();
      var atts = msgs[mi].getAttachments();
      for (var ai = 0; ai < atts.length; ai++) {
        if (atts[ai].getName().toLowerCase().indexOf(".xls") >= 0) {
          if (!bestDate || md > bestDate) { bestDate = md; bestAtt = atts[ai]; }
        }
      }
    }
  }
  Logger.log(bestAtt ? ("找到：" + bestAtt.getName() + "（" + bestDate + "）")
                     : "沒找到『班表』標籤下的 Excel 附件");
}


/* ━━━━━━━━━━ 工具函式 ━━━━━━━━━━ */
function jsonOut_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
                       .setMimeType(ContentService.MimeType.JSON);
}
function ensureSheet_(ss, name, headers) {
  var sh = ss.getSheetByName(name);
  if (!sh) { sh = ss.insertSheet(name); sh.appendRow(headers); }
  return sh;
}
function sheetToArray_(ss, name) {
  var sh = ss.getSheetByName(name);
  if (!sh || sh.getLastRow() < 1) return [];
  return sh.getDataRange().getValues();
}
/* 一次寫入整批列（setValues 只有 1 次 API 呼叫），取代逐列 appendRow()（N 次 API 呼叫）。
 * 逐列寫入在資料量大（例如整年 300~400 列歷史）時很容易逾時，這是 2026-07-19 發現的效能問題。 */
/* ⚠️ v6.3 重要修正：原本第一行就 sh.clearContents()，然後才 setValues()。
 * 只要 setValues() 因為任何原因失敗（最常見：某一列的欄數跟表頭對不上，Google 會直接
 * 拋例外），分頁就會停在「已經清空、但新資料沒寫進去」的狀態——**資料整份消失**。
 * 這不是假設，是 2026-08-02 實際重現出來的：「排班草稿」就是這樣每次被清成空的。
 * 而這個函式同時被 setWeek(本週名單)、setAllScheduleHistory(排班歷史)、setMembers
 * (組員名單)、writeHistory_ 使用——同一顆地雷踩在排班歷史上就是整年資料歸零，
 * 正是這個專案已經出事過好幾次的那種災情（見接續包第十三、十六節）。
 * 改成：先把每一列正規化成表頭寬度（短的補空白），欄數超過表頭就直接丟例外
 * **中止、完全不動原有資料**；全部檢查過了才 clearContents + setValues。 */
function writeAllRowsFast_(sh, headers, rows) {
  var w = headers.length;
  var src = rows || [];
  var norm = [];
  for (var i = 0; i < src.length; i++) {
    var r = src[i] || [];
    if (r.length > w) {
      throw new Error("寫入「" + sh.getName() + "」中止：第 " + (i + 1) + " 筆有 " + r.length
                      + " 欄，超過表頭的 " + w + " 欄。原有資料未被更動。");
    }
    var row = r.slice();
    while (row.length < w) row.push("");     // 短的補空白，setValues 才不會抱怨
    norm.push(row);
  }
  // 到這裡才動真格的：前面任何一列有問題都已經丟例外了，不會出現「清空後寫入失敗」
  sh.clearContents();
  var allRows = [headers].concat(norm);
  sh.getRange(1, 1, allRows.length, w).setValues(allRows);
}
function writeHistory_(ss, sheetName, headers, key, newRows) {
  if (!key && newRows.length === 0) return;
  var sh = ensureSheet_(ss, sheetName, headers);
  var vals = sh.getLastRow() > 0 ? sh.getDataRange().getValues() : [headers];
  var kept = vals.filter(function(r, i) {
    return i === 0 || String(r[0]) !== String(key);
  });
  writeAllRowsFast_(sh, headers, kept.slice(1).concat(newRows));
}
function buildUserMap_(ss) {
  var map = {}, sh = ss.getSheetByName("對照");
  if (!sh) return map;
  var rows = sh.getDataRange().getValues();
  for (var i = 1; i < rows.length; i++) {
    var nm = String(rows[i][0]).trim(), uid = String(rows[i][1]).trim();
    if (nm && uid) map[nm] = uid;
  }
  return map;
}
function normDate_(v, tz) {
  // 用「有沒有 getFullYear」判斷是不是日期物件，不用 instanceof Date——instanceof 只認
  // 同一個 realm 建出來的 Date，遇到別處傳進來的日期物件會判成 false，接著掉進下面的
  // 字串分支，String(日期) 會變 "Mon Feb 16 2026 00:00:00 GMT+0800" 而比不中任何
  // yyyy-MM-dd，日期就被靜默丟掉。休診日(v6.1)整份清單都靠這個函式正規化，不能有這種洞。
  if (v && typeof v.getFullYear === "function") return Utilities.formatDate(v, tz, "yyyy-MM-dd");
  var s = String(v).trim().replace(/\//g, "-");
  var m = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  return m ? (m[1] + "-" + ("0"+m[2]).slice(-2) + "-" + ("0"+m[3]).slice(-2)) : s;
}
/* v6.2 修正（接續包第二十三節待辦#14）：原本 muteHttpExceptions:true 把 LINE API 的
 * 回應整個吞掉，回傳值也沒人看——就算 LINE 回 401(token失效)、403(額度用完)、
 * 400(userId 無效)，程式一樣當作發送成功、照樣寫進「提醒紀錄」、照樣算 sent++。
 * 後果很嚴重：①同仁其實沒收到 ②「提醒紀錄」有假紀錄，dedup 之後永遠不會重試
 * ③v6.0 的健康檢查看到有紀錄就以為沒事，連玉繡都不會被通知——三道防線同時被騙過。
 * 改成檢查 getResponseCode()，只有 2xx 才算成功；失敗回 false 並記下狀態碼與回應內容，
 * 由呼叫端決定「不要寫紀錄、算成失敗」，這樣下一次執行會自動重試、健康檢查也抓得到。
 * 回傳：true=送成功、false=沒送成功。
 */
function pushLine_(uid, text) {
  try {
    var resp = UrlFetchApp.fetch("https://api.line.me/v2/bot/message/push", {
      method: "post", contentType: "application/json",
      headers: {"Authorization": "Bearer " + LINE_TOKEN},
      payload: JSON.stringify({to: uid, messages: [{type: "text", text: text}]}),
      muteHttpExceptions: true
    });
    var code = resp.getResponseCode();
    if (code >= 200 && code < 300) return true;
    Logger.log("LINE 發送失敗 code=" + code + " uid=" + uid
               + " 回應=" + String(resp.getContentText()).slice(0, 300));
    return false;
  } catch (e) {
    Logger.log("LINE 發送例外 uid=" + uid + "：" + e);
    return false;
  }
}
