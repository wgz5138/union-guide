/**
 * 🧩 一鍵建立「實證護理小工具 · 使用回饋」Google 表單
 * 作者不用一題一題打——這支腳本會自動把整張表單（含追問分支）生出來。
 *
 * 怎麼用（手機或電腦都可，約 1 分鐘）：
 *  1. 開 https://script.google.com → 右上角「新增專案 / New project」
 *  2. 把這整段程式碼「全選貼上」（蓋掉原本看到的那幾行）
 *  3. 上方按「執行 / Run」（會跑 buildFeedbackForm）
 *  4. Google 跳出授權視窗 → 繼續 → 選你的帳號(wgz5138@gmail.com) →（若顯示「未驗證」點「進階→前往」）→ 允許
 *  5. 完成！表單網址會自動寄到你自己的信箱。大家的回覆也都自動匯進這張表單裡，登入 Google 一次就全部看完。
 */
function buildFeedbackForm() {
  var form = FormApp.create('實證護理小工具 · 使用回饋（30 秒）');
  form.setDescription('謝謝你試用 🙏 點幾個選項就好，幫我把工具改得更順手。匿名、不會記名字。');
  try { form.setCollectEmail(false); } catch (e) {}
  try { form.setProgressBar(true); } catch (e) {}
  try { form.setShowLinkToRespondAgain(false); } catch (e) {}

  // 第 1 題
  form.addMultipleChoiceItem()
    .setTitle('1. 你主要用哪一個？')
    .setChoiceValues(['評讀工具（交報告用）', '臨床快查（找文獻用）', '兩個都用', '還沒真的用過']);

  // 第 2 題
  form.addMultipleChoiceItem()
    .setTitle('2. 第一次上手會不會難？')
    .setChoiceValues(['很直覺，馬上就會', '看一下說明就會', '有點卡，摸索了一陣子', '看不懂，需要有人教']);

  // 第 3 題
  form.addMultipleChoiceItem()
    .setTitle('3. 整體有幫上忙嗎？')
    .setChoiceValues(['很有幫助', '有一點', '普通', '沒什麼幫助']);

  // 第 4 題（可複選）
  form.addCheckboxItem()
    .setTitle('4. 最想要它變更好的地方？（可複選）')
    .setChoiceValues(['介面再簡單一點', '字再大一點', '速度再快一點', '教學/說明更清楚',
                      '找文獻更準', '報告或簡報更好用', '手機操作更順', '都很好，沒特別']);

  // ── 分頁（追問用，先建好讓第 5 題分流）──
  var mobileSection = form.addPageBreakItem()
    .setTitle('手機上是哪裡卡？').setHelpText('剛剛選了會卡才會看到這頁～');
  form.addCheckboxItem()
    .setTitle('主要卡在哪？（可複選）')
    .setChoiceValues(['按鈕按不動 / 沒反應', '想複製卻複製不了', '畫面跑版、字被切到',
                      '載入很慢', '從 LINE 等 App 點開怪怪的', '其他（最後一題寫）']);

  var lastSection = form.addPageBreakItem().setTitle('最後一題');
  form.addParagraphTextItem().setTitle('還有什麼想說的？（沒有可以直接交出）');

  // 第 5 題：手機順不順 → 依答案分流（「卡」才往下追問，否則跳過）
  var q5 = form.addMultipleChoiceItem().setTitle('5. 在手機上用順不順？');
  q5.setChoices([
    q5.createChoice('很順', lastSection),                          // 跳過手機細項，直接到最後
    q5.createChoice('偶爾會卡', FormApp.PageNavigationType.CONTINUE), // 接著問「卡在哪」
    q5.createChoice('常常卡', FormApp.PageNavigationType.CONTINUE),
    q5.createChoice('我沒在手機上用', lastSection)
  ]);
  // 分流的題目必須是第一頁的「最後一題」，把它移到第 4 題之後、分頁之前
  form.moveItem(q5.getIndex(), 4);

  // ── 把連結寄到你自己的信箱 ──
  var pub = form.getPublishedUrl();
  var edit = form.getEditUrl();
  try {
    var me = Session.getActiveUser().getEmail();
    if (me) {
      MailApp.sendEmail(me, '✅ 你的回饋表單建好了',
        '【給別人填的網址】（可做成 QR、貼桌上）：\n' + pub +
        '\n\n【你看大家回覆 / 改題目】：\n' + edit +
        '\n\n把上面第一條網址貼給 AI，就能在工具加一顆「💬 給建議」按鈕直接連過去。');
    }
  } catch (e) {}
  Logger.log('給別人填： ' + pub);
  Logger.log('看回覆／改題： ' + edit);
}
