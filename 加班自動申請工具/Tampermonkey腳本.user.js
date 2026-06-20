// ==UserScript==
// @name         加班補申請自動填表（方案 B：整頁重載版）
// @namespace    kvgh-union-overtime
// @version      1.0
// @description  送出後整頁重載的傳統系統用：每次頁面載入自動接續下一筆。高榮護理工會。
// @match        https://你的醫院系統網址/加班申請頁面*
// @grant        none
// @run-at       document-idle
// ==/UserScript==

/* ------------------------------------------------------------
 *  適用：按「送出」後整頁重新載入的傳統 postback 系統。
 *  原理：每次頁面載入都執行一次 → 從瀏覽器儲存讀「下一筆」→
 *        填表、送出 → 頁面重載後再執行，自動接續。
 *
 *  ⚠ @match 請改成實際申請頁面網址。
 *  ⚠ 不處理卡號／密碼，登入請本人手動完成。
 *  ⚠ 需安裝 Tampermonkey 擴充套件（院內禁止安裝就不能用此方案）。
 *     請於院方規定與資安政策允許範圍內使用。
 * ------------------------------------------------------------ */
(function () {
  'use strict';

  /* ======================= 你要修改的設定 ======================= */
  const DRY_RUN = true;            // true=只填不送出（先確認欄位）；確認後改 false
  const DELAY_BEFORE_SUBMIT = 1200; // 填完到按送出的等待(ms)

  const SELECTORS = {
    dateInput:   '#txtDate',
    minuteInput: '#txtMinutes',
    periodInput: '#selPeriod',   // 沒有就設 null
    submitBtn:   '#btnSubmit',
    successText: '申請成功',      // 重載後頁面若出現此文字 = 上一筆成功
  };

  // 申請清單（依你的刷卡紀錄整理後貼進來）
  const RECORDS = [
    { date: '2020-01-03', minutes: 20, period: '班後' },
    { date: '2020-01-06', minutes: 35, period: '班後' },
    // ...
  ];
  /* ============================================================ */

  const KEY_IDX  = 'ot_b_index';
  const KEY_DONE = 'ot_b_done';

  const getIdx  = () => parseInt(localStorage.getItem(KEY_IDX) || '0', 10);
  const setIdx  = (n) => localStorage.setItem(KEY_IDX, String(n));
  const getDone = () => { try { return JSON.parse(localStorage.getItem(KEY_DONE) || '[]'); } catch { return []; } };
  const addDone = (d) => { const a = getDone(); a.push(d); localStorage.setItem(KEY_DONE, JSON.stringify(a)); };

  function setValue(selector, value) {
    if (!selector) return true;
    const el = document.querySelector(selector);
    if (!el) return false;
    const proto = el.tagName === 'SELECT' ? HTMLSelectElement.prototype
                : el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype
                : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
    if (setter) setter.call(el, value); else el.value = value;
    el.dispatchEvent(new Event('input',  { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  }

  function banner(msg, color) {
    let bar = document.getElementById('__ot_bar');
    if (!bar) {
      bar = document.createElement('div');
      bar.id = '__ot_bar';
      bar.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:99999;padding:8px 14px;'
        + 'font:14px/1.4 sans-serif;color:#fff;text-align:center;box-shadow:0 2px 6px rgba(0,0,0,.3)';
      document.body.appendChild(bar);
    }
    bar.style.background = color || '#1A7A4A';
    bar.textContent = msg;
  }

  function step() {
    let idx = getIdx();

    // 若上一筆已送出，畫面出現成功字樣 → 記錄完成、前進到下一筆
    if (idx > 0 && SELECTORS.successText && document.body.innerText.includes(SELECTORS.successText)) {
      const prev = RECORDS[idx - 1];
      if (prev && !getDone().includes(prev.date)) addDone(prev.date);
    }

    if (idx >= RECORDS.length) {
      banner(`🎉 全部完成：共 ${RECORDS.length} 筆（已完成 ${getDone().length}）`, '#0F5C36');
      return;
    }

    const rec = RECORDS[idx];
    banner(`處理中 ${idx + 1}/${RECORDS.length}：${rec.date}　${DRY_RUN ? '（試跑不送出）' : ''}`, '#C0392B');

    const okDate = setValue(SELECTORS.dateInput, rec.date);
    const okMin  = setValue(SELECTORS.minuteInput, String(rec.minutes));
    if (rec.period) setValue(SELECTORS.periodInput, rec.period);

    if (!okDate || !okMin) {
      banner(`⚠ 找不到欄位，請檢查 SELECTORS 設定（停在 ${rec.date}）`, '#7B1818');
      return;
    }

    if (DRY_RUN) {
      banner(`🧪 試跑：已填 ${rec.date}，未送出。確認欄位正確後把 DRY_RUN 改 false。`, '#B7860B');
      return; // 試跑只填第一筆
    }

    // 正式：前進索引（避免送出後重載重複本筆），再按送出
    setIdx(idx + 1);
    setTimeout(() => {
      const btn = document.querySelector(SELECTORS.submitBtn);
      if (btn) btn.click();
      else banner(`⚠ 找不到送出按鈕（停在 ${rec.date}）`, '#7B1818');
    }, DELAY_BEFORE_SUBMIT);
  }

  // 提供重置：在 Console 輸入 OT_RESET_B()
  window.OT_RESET_B = () => { localStorage.removeItem(KEY_IDX); localStorage.removeItem(KEY_DONE); location.reload(); };

  window.addEventListener('load', () => setTimeout(step, 600));
})();
