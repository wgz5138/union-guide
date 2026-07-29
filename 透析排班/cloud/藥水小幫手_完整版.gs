/**
 * 透析印藥水 LINE 小幫手 v6.0 — Apps Script
 * ════════════════════════════════════════════════════════
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

// ★休診日（沒診、不上班的日子）：過年/國定假日要的話自己加，格式 "2026-01-01"。週日自動跳，不用列。
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

    if (action === "getWeekDraft") {
      var shDraft = ensureSheet_(ss, "排班草稿", ["週次","印日期","區","姓名"]);
      return jsonOut_({ok: true, rows: shDraft.getDataRange().getValues()});
    }

    if (action === "setWeekDraft") {
      var shDraft2 = ensureSheet_(ss, "排班草稿", ["週次","印日期","區","姓名"]);
      writeAllRowsFast_(shDraft2, ["週次","印日期","區","姓名"], body.rows || []);
      return jsonOut_({ok: true});
    }

    if (action === "sendAuditNotice") {
      var map2 = buildUserMap_(ss);
      var month = body.month || "";
      var sent2 = 0, miss2 = 0;
      (body.notices || []).forEach(function(n) {
        var uid3 = map2[n.name];
        if (!uid3) { Logger.log("缺 userId（稽核通知）：" + n.name); miss2++; return; }
        pushLine_(uid3, "📋 " + month + " 你這個月負責【" + n.position + "】稽核藥水，請自行安排兩天進行稽核。🙏");
        sent2++;
      });
      Logger.log("稽核通知：發 " + sent2 + " 人，缺 userId " + miss2 + " 人");
      return jsonOut_({ok: true, sent: sent2, miss: miss2});
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
function isWorkday_(d, tz) {
  if (d.getDay() === 0) return false;                       // 週日休
  var s = Utilities.formatDate(d, tz, "yyyy-MM-dd");
  return EXTRA_HOLIDAYS.indexOf(s) < 0;                     // 不在休診清單
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

  var sent = 0, miss = 0, dup = 0;
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
      pushLine_(uid2, makeMsg(md, zpart));
      logSh.appendRow([todayStr, type, name, info.printStr, new Date()]);
      sentKeys[key] = true;
      sent++;
    }
  }
  flush_(advance, "前一天", function(md, zpart) { return "🔔 記得 " + md + " 要印" + zpart + "藥水喔！🙏"; });
  flush_(sameday, "當天",   function(md, zpart) { return "⚠️ 今天 " + md + " 就要印" + zpart + "藥水喔！別忘了 🙏"; });

  Logger.log((catchUp ? "[補發]" : "[固定排程]") + "提醒完成：提前 " + Object.keys(advance).length + " 人、當天 "
             + Object.keys(sameday).length + " 人，實發 " + sent + " 則，已發過跳過 " + dup
             + " 則，缺 userId " + miss + " 次（今天 " + todayStr + "）");

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
  pushLine_(adminUid,
    "⚠️ 小幫手健康檢查：以下人員的印藥水提醒完全沒有任何發送紀錄，麻煩人工確認一下——\n"
    + missed.join("、")
    + "\n（可能原因：本週名單送達時間晚於提醒窗口、缺userId對照、或發送當下出錯）");
  Logger.log("健康檢查：發現 " + missed.length + " 人完全沒收到提醒，已通知玉繡：" + missed.join("、"));
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
function writeAllRowsFast_(sh, headers, rows) {
  sh.clearContents();
  var allRows = [headers].concat(rows);
  if (allRows.length > 0) {
    sh.getRange(1, 1, allRows.length, headers.length).setValues(allRows);
  }
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
  if (v instanceof Date) return Utilities.formatDate(v, tz, "yyyy-MM-dd");
  var s = String(v).trim().replace(/\//g, "-");
  var m = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  return m ? (m[1] + "-" + ("0"+m[2]).slice(-2) + "-" + ("0"+m[3]).slice(-2)) : s;
}
function pushLine_(uid, text) {
  UrlFetchApp.fetch("https://api.line.me/v2/bot/message/push", {
    method: "post", contentType: "application/json",
    headers: {"Authorization": "Bearer " + LINE_TOKEN},
    payload: JSON.stringify({to: uid, messages: [{type: "text", text: text}]}),
    muteHttpExceptions: true
  });
}
