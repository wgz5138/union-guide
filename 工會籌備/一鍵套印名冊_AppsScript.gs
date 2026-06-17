/*** 一鍵套印：把表單回覆 → 產生官方格式「發起人連署及略歷冊」Google 文件 *******
 *  做法：讀表單那張回覆試算表，自動排版成官方名冊，存成 Google 文件可直接列印。
 *  ‧ 自動「排除主管」（填『是(主管)』者不列入）
 *  ‧ 自動統計有效人數、提醒已具其他工會會籍者
 *
 *  ── 用法 ──────────────────────────────────────────
 *  1. 把這整段「貼在 buildForm 下面」（同一個 Apps Script 專案）
 *  2. 上方函式下拉選「makeRoster」→ 按「執行」（第一次會再授權一次）
 *  3. 看「執行記錄」→ 點【名冊文件網址】開啟 → 檔案→列印（或下載 PDF）
 *********************************************************************/

function makeRoster() {
  // 1) 找到表單的回覆試算表
  const files = DriveApp.getFilesByName('高榮工會_發起人資料_彙整');
  if (!files.hasNext()) throw new Error('找不到「高榮工會_發起人資料_彙整」。請先跑 buildForm，且至少要有 1 人填表。');
  const ss = SpreadsheetApp.open(files.next());
  const sh = ss.getSheets()[0];
  const values = sh.getDataRange().getValues();
  if (values.length < 2) throw new Error('目前還沒有人填表，無法產生名冊。');

  // 2) 用標題自動對欄位
  const head = values[0];
  const col = (kw) => { for (let i = 0; i < head.length; i++) if (String(head[i]).replace(/\s/g,'').indexOf(kw) > -1) return i; return -1; };
  const cMgr=col('管理權'), cName=col('姓名'), cId=col('身分證'), cBirth=col('出生'),
        cAddr=col('通信地址'), cMobile=col('行動電話'), cOffice=col('公務'), cUnion=col('其他工會');

  // 3) 整理資料、排除主管
  const people = []; let excluded = 0, unionWarn = 0;
  for (let r = 1; r < values.length; r++) {
    const row = values[r];
    if (!String(row[cName]).trim()) continue;
    if (cMgr > -1 && String(row[cMgr]).indexOf('是') === 0) { excluded++; continue; }
    if (cUnion > -1 && String(row[cUnion]).indexOf('是') === 0) unionWarn++;
    let birth = row[cBirth];
    if (birth instanceof Date) birth = Utilities.formatDate(birth, 'Asia/Taipei', 'yyyy/MM/dd');
    const tel = (cOffice>-1 && row[cOffice] ? '公:'+row[cOffice]+'  ' : '') +
                (cMobile>-1 && row[cMobile] ? '手機:'+row[cMobile] : '');
    people.push([String(row[cName]).trim(), String(row[cId]).trim(), birth, String(row[cAddr]).trim(), tel]);
  }
  if (!people.length) throw new Error('沒有可列入的發起人（可能都被判定為主管）。');

  // 4) 組表格資料（含表頭）
  const header = ['編號','姓名','身分證字號','出生年月日','通信地址','聯絡電話','發起連署簽名','蓋章'];
  const cells = [header];
  people.forEach((p, i) => cells.push([String(i+1), p[0], p[1], p[2], p[3], p[4], '', '']));

  // 5) 建立 Google 文件（A4）
  const stamp = Utilities.formatDate(new Date(), 'Asia/Taipei', 'yyyyMMdd_HHmm');
  const doc = DocumentApp.create('高榮企業工會_發起人連署及略歷冊_' + stamp);
  const body = doc.getBody();
  body.setPageWidth(595).setPageHeight(842);
  body.setMarginTop(36).setMarginBottom(30).setMarginLeft(28).setMarginRight(28);

  const title = body.appendParagraph('（高雄市）高榮企業工會　發起人連署及略歷冊');
  title.setHeading(DocumentApp.ParagraphHeading.HEADING1).setAlignment(DocumentApp.HorizontalAlignment.CENTER);
  title.editAsText().setFontSize(15).setBold(true);

  const table = body.appendTable(cells);
  table.setAttributes({ [DocumentApp.Attribute.FONT_SIZE]: 9 });
  // 表頭粗體
  const hr = table.getRow(0);
  for (let c = 0; c < hr.getNumCells(); c++) hr.getCell(c).setAttributes({ [DocumentApp.Attribute.BOLD]: true });
  // 欄寬
  const widths = [26, 55, 80, 64, 132, 78, 60, 40];
  widths.forEach((w, i) => table.setColumnWidth(i, w));

  const foot = body.appendParagraph(
    '依《工會法》第 11 條規定，發起人數須達 30 人以上，發起人應親自分別簽名及蓋章；' +
    '代表雇主行使管理權之主管人員不得為發起人。本表格不敷使用時請自行影印重複使用。');
  foot.editAsText().setFontSize(9);

  doc.saveAndClose();

  // 6) 報告
  Logger.log('================ 名冊產生完成 ================');
  Logger.log('【名冊文件網址】 ' + doc.getUrl());
  Logger.log('有效發起人：' + people.length + ' 人　(已自動排除主管 ' + excluded + ' 人)');
  Logger.log(people.length >= 30 ? '✅ 已達 30 人門檻' : '⚠ 尚未達 30 人，還差 ' + (30 - people.length) + ' 人');
  if (unionWarn) Logger.log('⚠ 有 ' + unionWarn + ' 人填「已具其他工會會籍」，請個別確認資格');
  Logger.log('開啟文件後：檔案 → 列印，給每位發起人親簽＋蓋章。');
}
