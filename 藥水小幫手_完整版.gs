/**
 * 透析印藥水 LINE 小幫手 — Apps Script v2.1
 *
 * Web App URL（部署後固定）：
 *   https://script.google.com/macros/s/AKfycbx25V8mO_F14agwPLesmKfQP_1m7LRmEVgC639De3TjYf661istXWGYEmFrez1feHs/exec
 *
 * SS_ID（Google Sheets）：
 *   1UF-DjDcrIPDbp016vkIyV9zsLF6Qz5EBo6Bq-z6t-Js
 *
 * 重建步驟：
 *   1. 新增 GAS 獨立專案
 *   2. 貼上此檔案全部程式碼
 *   3. 更新 LINE_TOKEN（從 LINE Developers Console 複製）
 *   4. 部署 Web App（Execute as: Me，Access: Anyone）→ 複製新網址
 *   5. 請預秀到 LINE Developers Console 更新 Webhook URL
 *   6. 設定觸發條件：sendReminders 每天早上 7 點
 */

var LINE_TOKEN   = "zeJ2uTt7yRF4EQZ1nN0tgQqZqfzkScfWxTmEtGjPDbByEtjEKkQucms/SYc9uYiEyHbODMrsqlB2L+z0Xl1EPpe4/w/nIR9AT6xb+7gBUgsPlqjEsj4Hp907Zr/gMkpiJWlSWaU20t4vI6au33BKbAdB04t89/1O/w1cDnyilFU=";
var WRITE_SECRET = "yaoshui2026";
var SS_ID        = "1UF-DjDcrIPDbp016vkIyV9zsLF6Qz5EBo6Bq-z6t-Js";

/* ━━━━━━━━━━ 路由 ━━━━━━━━━━ */
function doPost(e) {
  try {
    var body = JSON.parse(e.postData.contents);
    if (body.action) {
      if (body.secret !== WRITE_SECRET)
        return json_({ok: false, error: "unauthorized"});
      return handleAction_(body);
    }
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
  if (a === "setWeek")               return setWeek_(body);
  if (a === "getScheduleHistory")    return getScheduleHistory_();
  if (a === "setScheduleHistory")    return setScheduleHistory_(body);
  if (a === "getAuditHistory")       return getAuditHistory_();
  if (a === "setAuditResult")        return setAuditResult_(body);
  if (a === "sendAuditNotice")       return sendAuditNotice_(body);
  if (a === "getLatestBanbiao")      return getLatestBanbiao_();
  if (a === "getWeekDraft")          return getWeekDraft_();
  if (a === "setWeekDraft")          return setWeekDraft_(body);
  if (a === "setAllScheduleHistory") return setAllScheduleHistory_(body);
  if (a === "getMembers")            return getMembers_();
  if (a === "setMembers")            return setMembers_(body);
  if (a === "setAllAuditHistory")    return setAllAuditHistory_(body);
  if (a === "deleteScheduleWeek")    return deleteScheduleWeek_(body);
  if (a === "deleteAuditMonth")      return deleteAuditMonth_(body);
  return json_({ok: false, error: "unknown action: " + a});
}


/* ━━━━━━━━━━ 批次寫入（setValues，不用 appendRow 迴圈）━━━━━━━━━━ */
function writeAll_(sh, rows2d) {
  sh.clearContents();
  if (!rows2d || rows2d.length === 0) return;
  var cols = rows2d.reduce(function(m, r) { return Math.max(m, r.length); }, 0);
  if (cols === 0) return;
  var data = rows2d.map(function(r) {
    var row = r.slice();
    while (row.length < cols) row.push("");
    return row;
  });
  sh.getRange(1, 1, data.length, cols).setValues(data);
}


/* ━━━━━━━━━━ 本週名單 ━━━━━━━━━━ */
function setWeek_(body) {
  var ss = SpreadsheetApp.openById(SS_ID);
  var sh = getOrCreate_(ss, "本週名單", ["印日期","區","姓名"]);
  writeAll_(sh, [["印日期","區","姓名"]].concat(body.rows || []));
  return json_({ok: true});
}


/* ━━━━━━━━━━ 排班歷史 ━━━━━━━━━━ */
function getScheduleHistory_() {
  var ss = SpreadsheetApp.openById(SS_ID);
  var sh = getOrCreate_(ss, "排班歷史", ["週次","卡號","姓名","狀態","治療日"]);
  return json_({ok: true, rows: sh.getDataRange().getValues()});
}

function setScheduleHistory_(body) {
  var key = String(body.key || "");
  var newRows = body.rows || [];
  var ss = SpreadsheetApp.openById(SS_ID);
  var sh = getOrCreate_(ss, "排班歷史", ["週次","卡號","姓名","狀態","治療日"]);
  var data = sh.getDataRange().getValues();
  var kept = [data[0]];
  for (var i = 1; i < data.length; i++) {
    if (String(data[i][0]) !== key) kept.push(data[i]);
  }
  writeAll_(sh, kept.concat(newRows));
  return json_({ok: true});
}

function setAllScheduleHistory_(body) {
  var ss = SpreadsheetApp.openById(SS_ID);
  var sh = getOrCreate_(ss, "排班歷史", ["週次","卡號","姓名","狀態","治療日"]);
  writeAll_(sh, [["週次","卡號","姓名","狀態","治療日"]].concat(body.rows || []));
  return json_({ok: true});
}

function deleteScheduleWeek_(body) {
  var key = String(body.key || "");
  if (!key) return json_({ok: false, error: "key is required"});
  var ss = SpreadsheetApp.openById(SS_ID);
  var sh = getOrCreate_(ss, "排班歷史", ["週次","卡號","姓名","狀態","治療日"]);
  var data = sh.getDataRange().getValues();
  var kept = [data[0]];
  for (var i = 1; i < data.length; i++) {
    if (String(data[i][0]).trim() !== key) kept.push(data[i]);
  }
  writeAll_(sh, kept);
  return json_({ok: true, deleted: data.length - kept.length});
}


/* ━━━━━━━━━━ 組員名單 ━━━━━━━━━━ */
function getMembers_() {
  var ss = SpreadsheetApp.openById(SS_ID);
  var sh = getOrCreate_(ss, "組員名單", ["卡號","姓名"]);
  return json_({ok: true, rows: sh.getDataRange().getValues()});
}

function setMembers_(body) {
  var ss = SpreadsheetApp.openById(SS_ID);
  var sh = getOrCreate_(ss, "組員名單", ["卡號","姓名"]);
  writeAll_(sh, [["卡號","姓名"]].concat(body.rows || []));
  return json_({ok: true});
}


/* ━━━━━━━━━━ 排班草稿 ━━━━━━━━━━ */
function getWeekDraft_() {
  var ss = SpreadsheetApp.openById(SS_ID);
  var sh = getOrCreate_(ss, "排班草稿", ["週次","印日期","區","姓名"]);
  return json_({ok: true, rows: sh.getDataRange().getValues()});
}

function setWeekDraft_(body) {
  var ss = SpreadsheetApp.openById(SS_ID);
  var sh = getOrCreate_(ss, "排班草稿", ["週次","印日期","區","姓名"]);
  writeAll_(sh, [["週次","印日期","區","姓名"]].concat(body.rows || []));
  return json_({ok: true});
}


/* ━━━━━━━━━━ 稽核歷史 ━━━━━━━━━━ */
function getAuditHistory_() {
  var ss = SpreadsheetApp.openById(SS_ID);
  var sh = getOrCreate_(ss, "稽核歷史", ["月份","卡號","姓名","狀態","位置"]);
  return json_({ok: true, rows: sh.getDataRange().getValues()});
}

function setAuditResult_(body) {
  var key = String(body.key || "");
  var newRows = body.rows || [];
  var ss = SpreadsheetApp.openById(SS_ID);
  var sh = getOrCreate_(ss, "稽核歷史", ["月份","卡號","姓名","狀態","位置"]);
  var data = sh.getDataRange().getValues();
  var kept = [data[0]];
  for (var i = 1; i < data.length; i++) {
    if (String(data[i][0]) !== key) kept.push(data[i]);
  }
  writeAll_(sh, kept.concat(newRows));
  return json_({ok: true});
}

function setAllAuditHistory_(body) {
  var ss = SpreadsheetApp.openById(SS_ID);
  var sh = getOrCreate_(ss, "稽核歷史", ["月份","卡號","姓名","狀態","位置"]);
  var data = sh.getDataRange().getValues();
  var kept = [data[0]];
  for (var i = 1; i < data.length; i++) {
    var tag = String(data[i][0]).trim();
    if (tag === "草稿" || tag.indexOf("意見-") === 0) kept.push(data[i]);
  }
  writeAll_(sh, kept.concat(body.rows || []));
  return json_({ok: true});
}

function deleteAuditMonth_(body) {
  var key = String(body.key || "");
  if (!key) return json_({ok: false, error: "key is required"});
  var ss = SpreadsheetApp.openById(SS_ID);
  var sh = getOrCreate_(ss, "稽核歷史", ["月份","卡號","姓名","狀態","位置"]);
  var data = sh.getDataRange().getValues();
  var kept = [data[0]];
  for (var i = 1; i < data.length; i++) {
    if (String(data[i][0]).trim() !== key) kept.push(data[i]);
  }
  writeAll_(sh, kept);
  return json_({ok: true, deleted: data.length - kept.length});
}


/* ━━━━━━━━━━ 稽核 LINE 通知 ━━━━━━━━━━ */
function sendAuditNotice_(body) {
  var notices = body.notices || [];
  var month   = body.month || "";
  var map     = loadUserMap_();
  var sent = 0, miss = 0;
  notices.forEach(function(n) {
    var uid = map[n.name];
    if (!uid) { miss++; return; }
    try {
      pushLine_(uid,
        "📋 " + month + " 稽核藥水 AK 名單\n" +
        "您的位置：" + n.position + "\n請確認，謝謝！🙏");
      sent++;
    } catch(e) {
      Logger.log("推送失敗 " + n.name + "：" + e);
      miss++;
    }
  });
  return json_({ok: true, sent: sent, miss: miss});
}


/* ━━━━━━━━━━ 從 Gmail 抓最新班表 ━━━━━━━━━━ */
function getLatestBanbiao_() {
  try {
    var label = GmailApp.getUserLabelByName("班表");
    if (!label) return json_({ok: false, error: "找不到 Gmail 標籤「班表」"});
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


/* ━━━━━━━━━━ 每日提醒（排程觸發）━━━━━━━━━━ */
function sendReminders() {
  try {
    var ss  = SpreadsheetApp.openById(SS_ID);
    var tz  = "Asia/Taipei";
    var target = new Date(Date.now() + 24 * 60 * 60 * 1000);
    var tStr   = Utilities.formatDate(target, tz, "yyyy-MM-dd");
    var tMd    = Utilities.formatDate(target, tz, "M/d");

    var sh = ss.getSheetByName("本週名單");
    if (!sh) { Logger.log("找不到『本週名單』分頁"); return; }
    var rows = sh.getDataRange().getValues();
    if (!rows || !rows[0]) { Logger.log("本週名單是空的"); return; }

    var head = rows[0].map(function(x) { return String(x).trim(); });
    var iD = head.indexOf("印日期");
    var iZ = head.indexOf("區");
    var iN = head.indexOf("姓名");
    if (iD < 0 || iN < 0) { Logger.log("本週名單欄位對不上，找不到「印日期」或「姓名」"); return; }

    var map  = loadUserMap_();
    var todo = {};
    for (var r = 1; r < rows.length; r++) {
      if (normDate_(rows[r][iD], tz) !== tStr) continue;
      var nm   = String(rows[r][iN]).trim();
      var area = iZ >= 0 ? String(rows[r][iZ]).trim() : "";
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
      try {
        pushLine_(uid, "🔔 記得明天(" + tMd + ")要印" + zpart + "藥水喔！🙏");
        sent++;
      } catch(pushErr) {
        Logger.log("推送失敗 " + name + "：" + pushErr);
        miss++;
      }
    }
    Logger.log("提醒完成：發 " + sent + " 人，缺 " + miss + " 人（目標印日 " + tStr + "）");
  } catch(e) {
    Logger.log("sendReminders 錯誤：" + e.toString());
  }
}


/* ━━━━━━━━━━ LINE webhook：收 userId ━━━━━━━━━━ */
function handleWebhook_(body) {
  var ss = SpreadsheetApp.openById(SS_ID);
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
  if (!sh) { sh = ss.insertSheet(name); sh.appendRow(headers); }
  return sh;
}

function loadUserMap_() {
  var ss = SpreadsheetApp.openById(SS_ID);
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
  pushLine_("U04e906cc9268998aa4f8edf69286858f", "🔔 測試：小幫手正常運作 🙏");
}
