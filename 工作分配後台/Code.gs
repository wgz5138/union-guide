/*** 高榮企業工會 · 工作分配 後台 Web App *********************************
 *  做法：這支程式直接掛在你那張 Google 試算表上，
 *  讀寫同一張表 = 所有幹部即時看到同一份進度（真協作）。
 *
 *  ── 安裝（一次就好）──────────────────────────────────
 *  1. 打開你的試算表 → 上方「擴充功能 → Apps Script」
 *  2. 把這個檔貼進 Code.gs，再新增一個 HTML 檔取名「Index」貼進 Index.html
 *  3. 上方「部署 → 新增部署作業 → 類型選『網頁應用程式』」
 *       ‧ 執行身分：我
 *       ‧ 誰可以存取：「所有人」(這樣幹部點連結直接用、免登入)
 *  4. 按「部署」→ 第一次會要授權 → 複製『網頁應用程式網址』
 *  5. 把那個網址貼到幹部 LINE 群，手機可「加到主畫面」當 App 用
 *  （之後改了程式碼要按「部署 → 管理部署作業 → 編輯(鉛筆) → 新版本」才會生效）
 *********************************************************************/

// 若你的工作分配在某個分頁，填它的名字；留空白則用第一個分頁
const SHEET_NAME = '';

// 狀態循環順序（點一下往下一個切換）
const STATUS_CYCLE = ['待辦', '進行中', '完成'];

function getSheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  return SHEET_NAME ? ss.getSheetByName(SHEET_NAME) : ss.getSheets()[0];
}

// 用標題列找欄位位置，欄位順序變了也不會壞
function colMap_(headers) {
  const find = (names) => {
    for (let i = 0; i < headers.length; i++) {
      const h = String(headers[i]).replace(/\s/g, '');
      if (names.some(n => h.indexOf(n) > -1)) return i;
    }
    return -1;
  };
  return {
    block: find(['區塊', '分類', '群組']),
    item:  find(['工作項目', '項目', '任務', '工作']),
    owner: find(['負責人', '負責', '人員']),
    time:  find(['時間', '日期', '期限']),
    status:find(['狀態', '進度']),
    note:  find(['備註', '說明', '備考']),
  };
}

function doGet() {
  return HtmlService.createHtmlOutputFromFile('Index')
    .setTitle('工會籌備 · 工作分配')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no')
    .addMetaTag('apple-mobile-web-app-capable', 'yes')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

// 讀全部任務
function getData() {
  const sh = getSheet_();
  const values = sh.getDataRange().getValues();
  if (values.length < 2) return { tasks: [], owners: [] };
  const c = colMap_(values[0]);
  const tasks = [];
  const owners = {};
  for (let r = 1; r < values.length; r++) {
    const row = values[r];
    const item = c.item > -1 ? String(row[c.item]).trim() : '';
    if (!item) continue; // 跳過空列
    const owner = c.owner > -1 ? String(row[c.owner]).trim() : '';
    let status = c.status > -1 ? String(row[c.status]).trim() : '';
    if (STATUS_CYCLE.indexOf(status) === -1) status = '待辦';
    if (owner) owner.split(/[\/、,，]/).forEach(o => { o = o.trim(); if (o) owners[o] = 1; });
    tasks.push({
      row: r + 1, // 試算表實際列號（含標題）
      block: c.block > -1 ? String(row[c.block]).trim() : '其他',
      item: item,
      owner: owner,
      time: c.time > -1 ? String(row[c.time]).trim() : '',
      status: status,
      note: c.note > -1 ? String(row[c.note]).trim() : '',
    });
  }
  return { tasks: tasks, owners: Object.keys(owners), updated: nowStr_() };
}

// 改某一列狀態
function updateStatus(rowNumber, newStatus) {
  if (STATUS_CYCLE.indexOf(newStatus) === -1) throw new Error('狀態不合法');
  const sh = getSheet_();
  const c = colMap_(sh.getDataRange().getValues()[0]);
  if (c.status < 0) throw new Error('找不到「狀態」欄');
  sh.getRange(rowNumber, c.status + 1).setValue(newStatus);
  return { ok: true, row: rowNumber, status: newStatus, updated: nowStr_() };
}

function nowStr_() {
  return Utilities.formatDate(new Date(), 'Asia/Taipei', 'MM/dd HH:mm');
}
