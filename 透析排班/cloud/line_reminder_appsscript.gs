/**
 * 每日 LINE 提醒（時間觸發版）— 加到「同一個 Apps Script 專案」即可
 * ───────────────────────────────────────────────
 * 需要試算表有三個分頁：
 *   本週名單 : 印日期, 區, 姓名   ← 玉繡每週貼(從網頁版下載的「雲端貼上版」)
 *   對照     : 姓名, userId       ← 名字↔userId(用班表全名)
 *   userid   : 收 userId 用(webhook 自動寫,這支不讀它)
 *
 * 設定步驟（小巫做一次）：
 *   1. 下面 LINE_TOKEN 貼上金鑰(Channel access token)。
 *   2. 試算表建「對照」分頁(姓名, userId),把已收到的人貼進去。
 *   3. 先執行一次 testReminder → 授權 → 看自己有沒有收到測試訊息。
 *   4. 左側「觸發條件(時鐘圖示)」→ 新增 → 選 sendReminders、
 *      時間驅動、每日,挑一個時段(例如晚上 7~9 點,提醒「明天」要印的人)。
 *   完成後每天自動發,不用再管。
 */

var LINE_TOKEN = "貼上你的金鑰";   // ← 這裡換成 Channel access token

// 每日自動執行：找出「明天」要印的人 → 私訊提醒
function sendReminders() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var tz = "Asia/Taipei";
  var target = new Date(Date.now() + 24 * 60 * 60 * 1000);      // 明天
  var tStr = Utilities.formatDate(target, tz, "yyyy-MM-dd");
  var tMd  = Utilities.formatDate(target, tz, "M/d");

  var sh = ss.getSheetByName("本週名單");
  if (!sh) { Logger.log("找不到『本週名單』分頁"); return; }
  var rows = sh.getDataRange().getValues();
  var head = rows[0].map(function (x) { return String(x).trim(); });
  var iD = head.indexOf("印日期"), iZ = head.indexOf("區"), iN = head.indexOf("姓名");

  var map = {};
  var mh = ss.getSheetByName("對照");
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
    var nm = String(rows[r][iN]).trim();
    var area = String(rows[r][iZ]).trim();
    if (!nm) continue;
    if (!todo[nm]) todo[nm] = [];
    if (area && todo[nm].indexOf(area) < 0) todo[nm].push(area);
  }

  var sent = 0, miss = 0;
  for (var name in todo) {
    var uid = map[name];
    if (!uid) { Logger.log("缺 userId：" + name); miss++; continue; }
    var zone = todo[name].join("、");
    var zpart = zone ? ("「" + zone + "」") : "";
    pushLine(uid, "🔔 記得明天(" + tMd + ")要印" + zpart + "藥水喔！🙏");
    sent++;
  }
  Logger.log("提醒完成：發 " + sent + " 人，缺 userId " + miss + " 人(目標印日 " + tStr + ")");
}

function normDate(v, tz) {
  if (v instanceof Date) return Utilities.formatDate(v, tz, "yyyy-MM-dd");
  var s = String(v).trim().replace(/\//g, "-");
  var m = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  if (m) return m[1] + "-" + ("0" + m[2]).slice(-2) + "-" + ("0" + m[3]).slice(-2);
  return s;
}

function pushLine(uid, text) {
  UrlFetchApp.fetch("https://api.line.me/v2/bot/message/push", {
    method: "post",
    contentType: "application/json",
    headers: { "Authorization": "Bearer " + LINE_TOKEN },
    payload: JSON.stringify({ to: uid, messages: [{ type: "text", text: text }] }),
    muteHttpExceptions: true
  });
}

// 測試用：寄一則給小巫自己(確認金鑰+發送正常)
function testReminder() {
  pushLine("U04e906cc9268998aa4f8edf69286858f", "🔔 測試:提醒功能正常運作 🙏");
}
