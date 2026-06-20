/**
 * 透析印藥水 LINE 小幫手 — Apps Script（一份搞定）
 * ════════════════════════════════════════════════════════
 *  功能①：自動收 userId（webhook）   功能②：每天自動發提醒
 *
 *  這張試算表需要 3 個分頁：
 *    userid    自動收 userId（程式寫入，不用管）
 *    對照      姓名 | userId        （名字↔userId，用班表全名）
 *    本週名單  印日期 | 區 | 姓名    （玉繡每週貼）
 *
 *  一次性設定：
 *    1) 下面 LINE_TOKEN 貼上金鑰。
 *    2) 部署→新增部署作業→網頁應用程式→執行身分:我、存取權:任何人→部署→授權，
 *       複製 /exec 網址，貼到 LINE 後台的 Webhook URL。
 *    3) 執行一次 testSelf → 授權 → 確認自己收到測試訊息。
 *    4) 觸發條件(時鐘圖示)→新增→函式 sendReminders、時間驅動、每日(例:晚上8點)。
 *  完成後：收 userId 與每日提醒都全自動。
 */

var LINE_TOKEN = "貼上你的金鑰";   // ← Channel access token


/* ━━━━━━━━━━ ① 收 userId（webhook）━━━━━━━━━━ */
function doPost(e) {
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sh = ss.getSheetByName("userid");
    if (!sh) { sh = ss.insertSheet("userid"); sh.appendRow(["時間", "事件", "userId", "傳來的文字(名字)"]); }
    var body = JSON.parse(e.postData.contents);
    (body.events || []).forEach(function (ev) {
      var uid = ev.source && ev.source.userId;
      var text = (ev.type === "message" && ev.message && ev.message.type === "text") ? ev.message.text : "";
      if (uid) sh.appendRow([new Date(), ev.type, uid, text]);
    });
  } catch (err) {}
  return ContentService.createTextOutput("OK");
}
function doGet() { return ContentService.createTextOutput("ok"); }


/* ━━━━━━━━━━ ② 每日提醒（提醒「明天」要印的人）━━━━━━━━━━ */
function sendReminders() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var tz = "Asia/Taipei";
  var target = new Date(Date.now() + 24 * 60 * 60 * 1000);
  var tStr = Utilities.formatDate(target, tz, "yyyy-MM-dd");
  var tMd  = Utilities.formatDate(target, tz, "M/d");

  var sh = ss.getSheetByName("本週名單");
  if (!sh) { Logger.log("找不到『本週名單』分頁"); return; }
  var rows = sh.getDataRange().getValues();
  var head = rows[0].map(function (x) { return String(x).trim(); });
  var iD = head.indexOf("印日期"), iZ = head.indexOf("區"), iN = head.indexOf("姓名");

  var map = {}, mh = ss.getSheetByName("對照");
  if (mh) {
    var mr = mh.getDataRange().getValues();
    for (var i = 1; i < mr.length; i++) {
      var nm = String(mr[i][0]).trim(), uid = String(mr[i][1]).trim();
      if (nm && uid) map[nm] = uid;
    }
  }

  var todo = {};
  for (var r = 1; r < rows.length; r++) {
    if (normDate(rows[r][iD], tz) !== tStr) continue;
    var nm = String(rows[r][iN]).trim(), area = String(rows[r][iZ]).trim();
    if (!nm) continue;
    if (!todo[nm]) todo[nm] = [];
    if (area && todo[nm].indexOf(area) < 0) todo[nm].push(area);
  }

  var sent = 0, miss = 0;
  for (var name in todo) {
    var uid = map[name];
    if (!uid) { Logger.log("缺 userId：" + name); miss++; continue; }
    var zone = todo[name].join("、"), zpart = zone ? ("「" + zone + "」") : "";
    pushLine(uid, "🔔 記得明天(" + tMd + ")要印" + zpart + "藥水喔！🙏");
    sent++;
  }
  Logger.log("提醒完成：發 " + sent + " 人，缺 " + miss + " 人(目標印日 " + tStr + ")");
}


/* ━━━━━━━━━━ 共用 ━━━━━━━━━━ */
function normDate(v, tz) {
  if (v instanceof Date) return Utilities.formatDate(v, tz, "yyyy-MM-dd");
  var s = String(v).trim().replace(/\//g, "-");
  var m = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  return m ? (m[1] + "-" + ("0" + m[2]).slice(-2) + "-" + ("0" + m[3]).slice(-2)) : s;
}
function pushLine(uid, text) {
  UrlFetchApp.fetch("https://api.line.me/v2/bot/message/push", {
    method: "post", contentType: "application/json",
    headers: { "Authorization": "Bearer " + LINE_TOKEN },
    payload: JSON.stringify({ to: uid, messages: [{ type: "text", text: text }] }),
    muteHttpExceptions: true
  });
}
function testSelf() { pushLine("U04e906cc9268998aa4f8edf69286858f", "🔔 測試:小幫手正常運作 🙏"); }
