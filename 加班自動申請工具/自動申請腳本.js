/* ============================================================
 *  加班補申請 — 自動填表腳本（方案 A：Console 貼上版）
 *  高雄榮總護理工會
 * ------------------------------------------------------------
 *  使用方式：
 *    1. 本人登入系統、進到「加班申請」頁面。
 *    2. 把下方 CONFIG.records 換成你的日期清單，
 *       並把 SELECTORS 改成你頁面實際的欄位選擇器。
 *    3. 按 F12 → Console，貼上「整個檔案內容」→ Enter。
 *    4. 預設 DRY_RUN = true，只會「填表但不送出」第一筆，
 *       讓你先確認欄位有填對。確認無誤後把 DRY_RUN 改 false 再貼一次。
 *
 *  重要：本腳本不會處理你的卡號／密碼，登入請本人手動完成。
 *  請於院方規定與資安政策允許範圍內使用。
 * ============================================================ */
(function () {
  'use strict';

  /* ======================= 你要修改的設定 ======================= */
  const CONFIG = {
    // 安全開關：true = 只填表不送出（試跑）；確認沒問題再改 false 正式送出
    DRY_RUN: true,

    // 每筆之間的等待秒數（避免太快被系統擋）
    DELAY_BETWEEN_SEC: 3,

    // 送出後，等畫面回應的秒數
    WAIT_AFTER_SUBMIT_SEC: 2,

    // 是否避免重複送已完成的日期（記在瀏覽器 localStorage）
    SKIP_DONE: true,

    // 你的申請清單：一天一筆
    //   date    = 申請日期 (YYYY-MM-DD)
    //   minutes = 該日要補申請的加班分鐘數
    //   period  = 時段，例如 '班前' 或 '班後'（沒有就留空字串）
    records: [
      { date: '2020-01-03', minutes: 20, period: '班後' },
      { date: '2020-01-06', minutes: 35, period: '班後' },
      // ...（依你的刷卡紀錄整理出整份清單貼進來）
    ],
  };

  // 你頁面實際的欄位「選擇器」。找法見 說明.md。
  const SELECTORS = {
    dateInput:   '#txtDate',       // 日期輸入框
    minuteInput: '#txtMinutes',    // 分鐘數輸入框
    periodInput: '#selPeriod',     // 時段下拉（沒有就設成 null）
    submitBtn:   '#btnSubmit',     // 送出按鈕
    // 送出成功的判斷（擇一）：成功時頁面會出現的文字
    successText: '申請成功',        // 例：'申請成功' / '已送出'（找不到就設 null）
  };
  /* ============================================================ */


  /* ===== 以下為程式邏輯，一般不需修改 ===== */
  const STORE_KEY = 'ot_auto_done_dates';
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  function loadDone() {
    try { return new Set(JSON.parse(localStorage.getItem(STORE_KEY) || '[]')); }
    catch { return new Set(); }
  }
  function saveDone(set) {
    localStorage.setItem(STORE_KEY, JSON.stringify([...set]));
  }

  // 設定欄位值並觸發事件（相容 React / Vue / 一般表單）
  function setValue(selector, value) {
    if (!selector) return true; // 該欄位不存在於此頁就略過
    const el = document.querySelector(selector);
    if (!el) { console.warn('⚠ 找不到欄位：', selector); return false; }
    const proto = el.tagName === 'TEXTAREA'
      ? window.HTMLTextAreaElement.prototype
      : el.tagName === 'SELECT'
        ? window.HTMLSelectElement.prototype
        : window.HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
    if (setter) setter.call(el, value); else el.value = value;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    el.dispatchEvent(new Event('blur', { bubbles: true }));
    return true;
  }

  function pageHasSuccess() {
    if (!SELECTORS.successText) return true; // 沒設定就當作成功（無法自動判斷）
    return document.body.innerText.includes(SELECTORS.successText);
  }

  async function fillOne(rec) {
    const okDate = setValue(SELECTORS.dateInput, rec.date);
    const okMin  = setValue(SELECTORS.minuteInput, String(rec.minutes));
    if (rec.period) setValue(SELECTORS.periodInput, rec.period);
    if (!okDate || !okMin) throw new Error('欄位填寫失敗，請檢查 SELECTORS 設定');

    if (CONFIG.DRY_RUN) {
      console.log('🧪 [試跑] 已填好但「不送出」：', rec);
      return 'dryrun';
    }

    const btn = document.querySelector(SELECTORS.submitBtn);
    if (!btn) throw new Error('找不到送出按鈕：' + SELECTORS.submitBtn);
    btn.click();

    await sleep(CONFIG.WAIT_AFTER_SUBMIT_SEC * 1000);
    return pageHasSuccess() ? 'ok' : 'unknown';
  }

  async function run() {
    const done = CONFIG.SKIP_DONE ? loadDone() : new Set();
    const todo = CONFIG.records.filter((r) => !done.has(r.date));
    const failed = [];

    console.log('%c=== 加班自動申請開始 ===', 'font-weight:bold;font-size:14px');
    console.log(`模式：${CONFIG.DRY_RUN ? '🧪 試跑（不送出）' : '🚀 正式送出'}`);
    console.log(`待處理 ${todo.length} 筆（已完成 ${done.size} 筆略過）`);

    for (let i = 0; i < todo.length; i++) {
      const rec = todo[i];
      try {
        console.log(`\n[${i + 1}/${todo.length}] 處理 ${rec.date} ...`);
        const res = await fillOne(rec);
        if (res === 'dryrun') {
          console.log('試跑只跑第一筆。確認欄位填對後，把 CONFIG.DRY_RUN 改成 false 再重新貼上執行。');
          return;
        }
        if (res === 'ok') {
          console.log(`✅ ${rec.date} 申請成功`);
          done.add(rec.date); saveDone(done);
        } else {
          console.warn(`❓ ${rec.date} 無法確認是否成功，請稍後人工檢查`);
          failed.push(rec.date);
        }
      } catch (e) {
        console.error(`❌ ${rec.date} 失敗：`, e.message);
        failed.push(rec.date);
      }
      await sleep(CONFIG.DELAY_BETWEEN_SEC * 1000);
    }

    console.log('\n%c=== 全部處理完畢 ===', 'font-weight:bold;font-size:14px');
    console.log(`成功/已完成：${done.size} 筆`);
    if (failed.length) {
      console.warn(`需人工處理 ${failed.length} 筆：`, failed);
    } else {
      console.log('🎉 沒有失敗的筆數');
    }
  }

  // 提供手動清除「已完成記錄」的方法：在 Console 輸入 OT_RESET()
  window.OT_RESET = () => { localStorage.removeItem(STORE_KEY); console.log('已清除完成記錄'); };

  run();
})();
