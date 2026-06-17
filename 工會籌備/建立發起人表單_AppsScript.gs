/*** 高榮企業工會 · 發起人資料 線上收集表單（隱私版）****************************
 *  目的：讓 40+ 位發起人「各自」線上填資料，自動匯到一張只有幹部看得到的
 *        試算表；每個人看不到別人的身分證字號（比共編 Word 安全很多）。
 *  收集欄位對齊勞工局官方「發起人連署及略歷冊」，方便最後套印列印簽名。
 *
 *  ── 用法（只跑一次）──────────────────────────────────
 *  1. 到 https://script.google.com → 新增專案
 *  2. 貼上這段 → 上方函式選「buildForm」→ 按「執行」→ 授權
 *  3. 看「執行記錄」會印出兩個網址：
 *       ‧ 【填寫網址】→ 貼到 LINE 群，給發起人各自填
 *       ‧ 【回覆試算表】→ 幹部看彙整資料（含身分證，請設限只給籌備幹部）
 *  （之後若要改題目，改完再跑一次會建「新的一份」，建議只跑一次）
 *********************************************************************/

function buildForm() {
  const form = FormApp.create('高榮企業工會 發起人連署資料表（籌備中）');

  form.setDescription(
    '感謝您支持籌組「高雄榮民總醫院企業工會」。\n' +
    '本表用於彙整發起人資料，最後將套印進勞工局官方「發起人連署及略歷冊」，由本人親簽蓋章後送件。\n\n' +
    '【個資告知】蒐集者：高榮企業工會籌備小組。目的：工會籌組、會務聯繫及依法申請補助／獎勵。' +
    '項目：姓名、身分證字號、出生年月日、通信地址、聯絡電話、受僱身分、工會會籍狀態。' +
    '僅供上述目的使用、不對外提供；您得請求查閱或刪除。送出即表示同意。'
  );

  // 發起人資格（先篩掉主管）
  form.addMultipleChoiceItem()
    .setTitle('您是否為「代表雇主行使管理權之主管人員」？')
    .setHelpText('依勞工局規定，主管／管理職不得擔任企業工會發起人。')
    .setChoiceValues(['否（一般受僱同仁）', '是（主管／管理職）'])
    .setRequired(true);

  form.addTextItem().setTitle('姓名').setRequired(true);

  form.addTextItem()
    .setTitle('身分證字號')
    .setHelpText('用於勞工局送件登記，僅籌備幹部可見。')
    .setRequired(true)
    .setValidation(FormApp.createTextValidation()
      .requireTextMatchesPattern('[A-Za-z][0-9]{9}')
      .setHelpText('請輸入正確格式，例：A123456789').build());

  form.addDateItem().setTitle('出生年月日').setRequired(true);

  form.addParagraphTextItem().setTitle('通信地址').setRequired(true);

  form.addTextItem().setTitle('行動電話（手機）').setRequired(true);
  form.addTextItem().setTitle('公務／市內電話（分機）').setRequired(false);
  form.addTextItem().setTitle('部門 / 職稱').setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('受僱身分別')
    .setChoiceValues(['約用', '契約', '派遣', '育嬰留職停薪（在職）', '其他'])
    .showOtherOption(true)
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('您目前是否已具其他工會之會員身分？')
    .setHelpText('企業工會發起人連署時應未具其他工會會籍。')
    .setChoiceValues(['否（未加入其他工會）', '是（已是其他工會會員）'])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('在職證明，您可提供的方式（擇一即可，現場再交）')
    .setChoiceValues(['勞保投保資料表', '薪資單／薪資轉帳明細', '人資開立之在職證明', '職員證／識別證影本', '需協助'])
    .showOtherOption(true)
    .setRequired(false);

  form.addMultipleChoiceItem()
    .setTitle('我已閱讀上方個資告知，並同意連署發起本工會')
    .setChoiceValues(['是，我同意連署'])
    .setRequired(true);

  // 建立回覆試算表
  const ss = SpreadsheetApp.create('高榮工會_發起人資料_彙整');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, ss.getId());

  Logger.log('================ 完成！把下面網址收好 ================');
  Logger.log('【填寫網址(給發起人)】 ' + form.getPublishedUrl());
  Logger.log('【短網址】 ' + form.shortenFormUrl(form.getPublishedUrl()));
  Logger.log('【回覆試算表(僅幹部看)】 ' + ss.getUrl());
  Logger.log('【表單編輯後台】 ' + form.getEditUrl());
  Logger.log('提醒：請到回覆試算表「共用」，只開給籌備幹部，保護身分證等個資。');
}
