/**
 * LINE Webhook → 自動把「加好友 / 傳名字」的人記進 Google 試算表
 * ─────────────────────────────────────────────
 * 免費、無筆數上限、以後新人也自動收。設定一次永久有效。
 *
 * 部署步驟（小巫做一次）：
 *  1. 建一張 Google 試算表（例如「藥水機器人資料」）。
 *  2. 在那張表上方選單：擴充功能 → Apps Script。
 *  3. 把本檔內容整段貼進去，存檔。
 *  4. 右上「部署 → 新增部署作業」→ 類型選「網頁應用程式」。
 *       執行身分：我
 *       誰可以存取：任何人
 *     →「部署」→ 第一次會要你「授權」，照著同意。
 *  5. 複製產生的「網頁應用程式 URL」(結尾是 /exec)。
 *  6. 到 LINE 後台把 Webhook URL 換成這個 /exec 網址 → Verify 應顯示成功。
 *  完成！之後誰加好友+私訊名字，就會自動出現在試算表的「userid」分頁。
 */
function doPost(e) {
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sh = ss.getSheetByName("userid");
    if (!sh) {
      sh = ss.insertSheet("userid");
      sh.appendRow(["時間", "事件", "userId", "傳來的文字(名字)"]);
    }
    var body = JSON.parse(e.postData.contents);
    (body.events || []).forEach(function (ev) {
      var uid = ev.source && ev.source.userId;
      var text = (ev.type === "message" && ev.message && ev.message.type === "text")
                 ? ev.message.text : "";
      if (uid) sh.appendRow([new Date(), ev.type, uid, text]);
    });
  } catch (err) {
    // 出錯也回 200，避免 LINE 重送
  }
  return ContentService.createTextOutput("OK");
}

// 給瀏覽器直接打開測試用（會顯示 ok，不影響 LINE）
function doGet() {
  return ContentService.createTextOutput("ok");
}
