/**
 * 透析印藥水 LINE 小幫手 — Apps Script v2
 * ════════════════════════════════════════════════════════
 * v2 新增：排班歷史 + 稽核歷史 API（供 Streamlit app 讀寫）
 *
 * 試算表需要以下分頁（程式會自動建立，不用手動建）：
 *   本週名單   — 印日期 | 區 | 姓名
 *   排班歷史   — 週次 | 卡號 | 姓名 | 狀態 | 治療日     ← NEW
 *   稽核歷史   — 月份 | 卡號 | 姓名 | 狀態 | 位置       ← NEW
 *   對照       — 姓名 | userId
 *   userid     — 自動收（不用管）
 *
 * 兩個要填的變數：
 *   LINE_TOKEN  → LINE Developers 的 Channel access token
 *   WRITE_SECRET → 與 Streamlit Secrets 的 WRITE_SECRET 相同（預設 yaoshui2026）
 */

var LINE_TOKEN   = "貼上你的金鑰";   // ← LINE Channel access token
var WRITE_SECRET = "yaoshui2026";     // ← 與 Streamlit Secrets 同步


/* ━━━━━━━━━━ 路由：LINE webhook vs. App API ━━━━━━━━━━ */
function doPost(e) {
  try {
    var body = JSON.parse(e.postData.contents);

    // App API 呼叫（有 action 欄位）
    if (body.action) {
      if (body.secret !== WRITE_SECRET)
        return json_({ok: false, error: "unauthorized"});
      return handleAction_(body);
    }

    // LINE webhook（有 events 陣列）
    handleWebhook_(body);
    return ContentService.createTextOutput("OK");
  } catch(err) {
    return ContentService.createTextOutput("OK");
  }
}

function doGet() { return ContentService.createTextOutput("ok"); }


/* ━━━━━━━━━━ Action 路由 ━━━━━━━━━━ */
function handleAction_(body) {
  var a = body.action;
  if (a === "setWeek")            return setWeek_(body);
  if (a === "getScheduleHistory") return getScheduleHistory_();
  if (a === "setScheduleHistory") return setScheduleHistory_(body);
  if (a === "getAuditHistory")    return getAuditHistory_();
  if (a === "setAuditResult")     return setAuditResult_(body);
  if (a === "sendAuditNotice")    return sendAuditNotice_(body);
  if (a === "getLatestBanbiao")   return getLatestBanbiao_();
  if (a === "getWeekDraft")            return getWeekDraft_();
  if (a === "setWeekDraft")            return setWeekDraft_(body);
  if (a === "setAllScheduleHistory")   return setAllScheduleHistory_(body);
  if (a === "getMembers")              return getMembers_();
  if (a === "setMembers")              return setMembers_(body);
  if (a === "setAllAuditHistory")      return setAllAuditHistory_(body);
  return json_({ok: false, error: "unknown action: " + a});
}


/* ━━━━━━━━━━ setWeek：寫入本週印藥水名單 ━━━━━━━━━━ */
function setWeek_(body) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = getOrCreate_(ss, "本週名單", ["印日期","區","姓名"]);
  sh.clearContents();
  sh.appendRow(["印日期","區","姓名"]);
  (body.rows || []).forEach(function(r) { sh.appendRow(r); });
  return json_({ok: true});
}


/* ━━━━━━━━━━ 排班歷史（印藥水公平輪序）━━━━━━━━━━ */
function getScheduleHistory_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = getOrCreate_(ss, "排班歷史", ["週次","卡號","姓名","狀態","治療日"]);
  return json_({ok: true, rows: sh.getDataRange().getValues()});
}

function setScheduleHistory_(body) {
  var key     = String(body.key || "");
  var newRows = body.rows || [];
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = getOrCreate_(ss, "排班歷史", ["週次","卡號","姓名","狀態","治療日"]);

  // 保留其他週次、移除當週舊資料
  var data   = sh.getDataRange().getValues();
  var header = data[0];
  var kept   = [header];
  for (var i = 1; i < data.length; i++) {
    if (String(data[i][0]) !== key) kept.push(data[i]);
  }
  sh.clearContents();
  kept.forEach(function(r)    { sh.appendRow(r); });
  newRows.forEach(function(r) { sh.appendRow(r); });
  return json_({ok: true});
}


/* ━━━━━━━━━━ 組員名單（雲端主檔）━━━━━━━━━━ */
function getMembers_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = getOrCreate_(ss, "組員名單", ["卡號","姓名"]);
  return json_({ok: true, rows: sh.getDataRange().getValues()});
}

function setMembers_(body) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = getOrCreate_(ss, "組員名單", ["卡號","姓名"]);
  sh.clearContents();
  sh.appendRow(["卡號","姓名"]);
  (body.rows || []).forEach(function(r) { sh.appendRow(r); });
  return json_({ok: true});
}


/* ━━━━━━━━━━ 整批覆寫稽核歷史（統計修正用）━━━━━━━━━━ */
function setAllAuditHistory_(body) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = getOrCreate_(ss, "稽核歷史", ["月份","卡號","姓名","狀態","位置"]);
  sh.clearContents();
  sh.appendRow(["月份","卡號","姓名","狀態","位置"]);
  (body.rows || []).forEach(function(r) { sh.appendRow(r); });
  return json_({ok: true});
}


/* ━━━━━━━━━━ 整批覆寫排班歷史（統計修正用）━━━━━━━━━━ */
function setAllScheduleHistory_(body) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = getOrCreate_(ss, "排班歷史", ["週次","卡號","姓名","狀態","治療日"]);
  sh.clearContents();
  sh.appendRow(["週次","卡號","姓名","狀態","治療日"]);
  (body.rows || []).forEach(function(r) { sh.appendRow(r); });
  return json_({ok: true});
}


/* ━━━━━━━━━━ 排班草稿（供小巫雙重確認）━━━━━━━━━━ */
function getWeekDraft_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = getOrCreate_(ss, "排班草稿", ["週次","印日期","區","姓名"]);
  return json_({ok: true, rows: sh.getDataRange().getValues()});
}

function setWeekDraft_(body) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = getOrCreate_(ss, "排班草稿", ["週次","印日期","區","姓名"]);
  sh.clearContents();
  sh.appendRow(["週次","印日期","區","姓名"]);
  (body.rows || []).forEach(function(r) { sh.appendRow(r); });
  return json_({ok: true});
}


/* ━━━━━━━━━━ 稽核歷史（稽核公平輪序）━━━━━━━━━━ */
function getAuditHistory_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = getOrCreate_(ss, "稽核歷史", ["月份","卡號","姓名","狀態","位置"]);
  return json_({ok: true, rows: sh.getDataRange().getValues()});
}

function setAuditResult_(body) {
  var key     = String(body.key || "");
  var newRows = body.rows || [];
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = getOrCreate_(ss, "稽核歷史", ["月份","卡號","姓名","狀態","位置"]);

  // 保留其他月份、移除當月舊資料
  var data   = sh.getDataRange().getValues();
  var header = data[0];
  var kept   = [header];
  for (var i = 1; i < data.length; i++) {
    if (String(data[i][0]) !== key) kept.push(data[i]);
  }
  sh.clearContents();
  kept.forEach(function(r)    { sh.appendRow(r); });
  newRows.forEach(function(r) { sh.appendRow(r); });
  return json_({ok: true});
}


/* ━━━━━━━━━━ sendAuditNotice：LINE 通知稽核者 ━━━━━━━━━━ */
function sendAuditNotice_(body) {
  var notices = body.notices || [];
  var month   = body.month || "";
  var map     = loadUserMap_();
  var sent = 0, miss = 0;
  notices.forEach(function(n) {
    var uid = map[n.name];
    if (!uid) { miss++; return; }
    pushLine_(uid,
      "📋 " + month + " 稽核藥水 AK 名單\n" +
      "您的位置：" + n.position + "\n請確認，謝謝！🙏");
    sent++;
  });
  return json_({ok: true, sent: sent, miss: miss});
}


/* ━━━━━━━━━━ getLatestBanbiao：從 Gmail 抓最新班表 Excel ━━━━━━━━━━ */
function getLatestBanbiao_() {
  try {
    var label = GmailApp.getUserLabelByName("班表");
    if (!label) return json_({ok: false, error: "找不到 Gmail 標籤「班表」，請先建立並貼標籤"});
    var threads = label.getThreads(0, 10);
    if (!threads.length) return json_({ok: false, error: "標籤「班表」裡沒有郵件"});
    for (var t = 0; t < threads.length; t++) {
      var msgs = threads[t].getMessages();
      for (var m = msgs.length - 1; m >= 0; m--) {
        var atts = msgs[m].getAttachments();
        for (var a = 0; a < atts.length; a++) {
          var fn = atts[a].getName();
          if (/\.(xls|xlsx)$/i.test(fn)) {
            return json_({
              ok: true,
              filename: fn,
              date: Utilities.formatDate(msgs[m].getDate(), "Asia/Taipei", "yyyy-MM-dd"),
              b64: Utilities.base64Encode(atts[a].getBytes())
            });
          }
        }
      }
    }
    return json_({ok: false, error: "標籤「班表」裡沒有找到 Excel 附件"});
  } catch(err) {
    return json_({ok: false, error: String(err)});
  }
}


/* ━━━━━━━━━━ sendReminders：每日提醒（排程觸發）━━━━━━━━━━ */
function sendReminders() {
  var ss  = SpreadsheetApp.getActiveSpreadsheet();
  var tz  = "Asia/Taipei";
  var target = new Date(Date.now() + 24 * 60 * 60 * 1000);
  var tStr   = Utilities.formatDate(target, tz, "yyyy-MM-dd");
  var tMd    = Utilities.formatDate(target, tz, "M/d");

  var sh = ss.getSheetByName("本週名單");
  if (!sh) { Logger.log("找不到『本週名單』分頁"); return; }
  var rows = sh.getDataRange().getValues();
  var head = rows[0].map(function(x) { return String(x).trim(); });
  var iD   = head.indexOf("印日期");
  var iZ   = head.indexOf("區");
  var iN   = head.indexOf("姓名");

  var map  = loadUserMap_();
  var todo = {};
  for (var r = 1; r < rows.length; r++) {
    if (normDate_(rows[r][iD], tz) !== tStr) continue;
    var nm   = String(rows[r][iN]).trim();
    var area = String(rows[r][iZ]).trim();
    if (!nm) continue;
    if (!todo[nm]) todo[nm] = [];
    if (area && todo[nm].indexOf(area) < 0) todo[nm].push(area);
  }

  var sent = 0, miss = 0;
  for (var name in todo) {
    var uid = map[name];
    if (!uid) { Logger.log("缺 userId：" + name); miss++; continue; }
    var zone  = todo[name].join("、");
    var zpart = zone ? ("「" + zone + "」") : "";
    pushLine_(uid, "🔔 記得明天(" + tMd + ")要印" + zpart + "藥水喔！🙏");
    sent++;
  }
  Logger.log("提醒完成：發 " + sent + " 人，缺 " + miss + " 人(目標印日 " + tStr + ")");
}


/* ━━━━━━━━━━ LINE webhook：收 userId ━━━━━━━━━━ */
function handleWebhook_(body) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName("userid");
  if (!sh) {
    sh = ss.insertSheet("userid");
    sh.appendRow(["時間","事件","userId","傳來的文字(名字)"]);
  }
  (body.events || []).forEach(function(ev) {
    var uid  = ev.source && ev.source.userId;
    var text = (ev.type === "message" && ev.message && ev.message.type === "text")
               ? ev.message.text : "";
    if (uid) sh.appendRow([new Date(), ev.type, uid, text]);
  });
}


/* ━━━━━━━━━━ 工具函式 ━━━━━━━━━━ */
function getOrCreate_(ss, name, headers) {
  var sh = ss.getSheetByName(name);
  if (!sh) {
    sh = ss.insertSheet(name);
    sh.appendRow(headers);
  }
  return sh;
}

function loadUserMap_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var mh = ss.getSheetByName("對照");
  var map = {};
  if (!mh) return map;
  var mr = mh.getDataRange().getValues();
  for (var i = 1; i < mr.length; i++) {
    var nm  = String(mr[i][0]).trim();
    var uid = String(mr[i][1]).trim();
    if (nm && uid) map[nm] = uid;
  }
  return map;
}

function json_(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
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
    headers: { "Authorization": "Bearer " + LINE_TOKEN },
    payload: JSON.stringify({ to: uid, messages: [{ type: "text", text: text }] }),
    muteHttpExceptions: true
  });
}

function testSelf() {
  pushLine_("U04e906cc9268998aa4f8edf69286858f", "🔔 測試:小幫手 v2 正常運作 🙏");
}
