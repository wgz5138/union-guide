#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
威力彩開獎統計分析
====================

讀取 data/superlotto638.json（由 scraper.py 抓取的官方真實資料），
產出：
    report/analysis_report.md   人類可讀的中文分析報告
    report/stats.json           機器可讀的統計數字

分析內容（全部基於真實歷史資料）：
    1. 第一區 1~38 / 第二區 1~8 每個號碼的出現次數與頻率
    2. 冷熱號（全期 + 近 N 期）
    3. 遺漏值（距今幾期沒出現）
    4. 號碼結構：奇偶比、大小比、總和分布、連號
    5. 機率與「該買幾個號碼」的誠實分析（包牌成本 vs 中獎機率）

重要立場：
    樂透每期皆為獨立隨機事件，歷史統計「不能」預測或提高單注命中特定號碼的機率。
    本報告的頻率/冷熱僅供參考與選號趣味；唯一真正提高中獎『機率』的方式是
    買進更多組不同號碼（包牌），其代價是成本同步上升。本程式如實呈現此取捨。
"""

import json
import math
import os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(HERE, "data", "superlotto638.json")
REPORT_DIR = os.path.join(HERE, "report")

FIRST_MAX = 38   # 第一區 1~38 選 6
SECOND_MAX = 8   # 第二區 1~8 選 1
TICKET_PRICE = 50  # 每注 NT$50

# 一注中頭獎機率 = 1 / (C(38,6) * 8)
C38_6 = math.comb(FIRST_MAX, 6)          # 2,760,681
JACKPOT_SPACE = C38_6 * SECOND_MAX        # 22,085,448


def load():
    with open(DATA_PATH, encoding="utf-8") as f:
        meta = json.load(f)
    return meta, meta["draws"]


def basic_freq(draws):
    first = Counter()
    second = Counter()
    for d in draws:
        for n in d["first_zone"]:
            first[n] += 1
        second[d["second_zone"]] += 1
    return first, second


def gaps(draws):
    """遺漏值：每個號碼距離最後一次出現過了幾期（0 = 最新一期才出現）。"""
    last_seen_first = {n: None for n in range(1, FIRST_MAX + 1)}
    last_seen_second = {n: None for n in range(1, SECOND_MAX + 1)}
    total = len(draws)
    for idx, d in enumerate(draws):  # idx 由舊到新
        for n in d["first_zone"]:
            last_seen_first[n] = idx
        last_seen_second[d["second_zone"]] = idx
    gap_first = {n: (total - 1 - i if i is not None else None)
                 for n, i in last_seen_first.items()}
    gap_second = {n: (total - 1 - i if i is not None else None)
                  for n, i in last_seen_second.items()}
    return gap_first, gap_second


def structure(draws):
    odd_even = Counter()      # 第一區奇數個數 (0~6)
    big_small = Counter()     # 第一區 >=20 的個數
    sums = []
    consec = 0                # 含至少一組連號的期數
    for d in draws:
        fz = d["first_zone"]
        odd = sum(1 for n in fz if n % 2 == 1)
        odd_even[odd] += 1
        big = sum(1 for n in fz if n >= 20)
        big_small[big] += 1
        sums.append(sum(fz))
        if any(b - a == 1 for a, b in zip(fz, fz[1:])):
            consec += 1
    return odd_even, big_small, sums, consec


def topn(counter, n, reverse=True):
    items = sorted(counter.items(), key=lambda kv: (kv[1], kv[0]), reverse=reverse)
    return items[:n]


def fmt_pct(x):
    p = x * 100
    if p == 0:
        return "0%"
    if p < 0.001:           # 極小機率改用科學記號，避免顯示成 0.0000%
        return f"{p:.3g}%"
    return f"{p:.4f}%"


def buy_table():
    """包牌：第一區選 k 個號碼（1 個第二區固定）時的注數、成本、頭獎機率。

    選第一區 k 個號碼可組出 C(k,6) 注（每注配同一個第二區），
    命中頭獎（6+第二區）需『開出的 6 個第一區號碼全在你的 k 個內』且第二區命中。
    機率 = [C(k,6)/C(38,6)] * (1/8)  （等同你買的注數 / 22,085,448）
    """
    rows = []
    for k in range(6, 16):
        tickets = math.comb(k, 6)
        cost = tickets * TICKET_PRICE
        p_jackpot = tickets / JACKPOT_SPACE
        # 命中『第一區 6 個』(不論第二區) 的機率
        p_six = math.comb(k, 6) / C38_6
        rows.append((k, tickets, cost, p_jackpot, p_six))
    return rows


def build_report(meta, draws):
    n = len(draws)
    first, second = basic_freq(draws)
    gap_first, gap_second = gaps(draws)
    odd_even, big_small, sums, consec = structure(draws)

    recent_n = min(100, n)
    recent = draws[-recent_n:]
    rf, rs = basic_freq(recent)

    L = []
    A = L.append
    A("# 威力彩開獎統計分析報告\n")
    A(f"- **資料來源**：{meta['source']}")
    A(f"- **抓取時間**：{meta['scraped_at']}")
    A(f"- **涵蓋期數**：{n} 期（{draws[0]['period']} ~ {draws[-1]['period']}）")
    A(f"- **開獎日期範圍**：{draws[0]['date']} ~ {draws[-1]['date']}")
    A("\n> 以下所有數字都來自官方真實開獎資料，程式只做統計，沒有任何臆測號碼。\n")

    A("---\n## 1. 第一區號碼出現次數（1~38，選 6）\n")
    A("理論上每期開 6 個號碼，平均每個號碼出現次數 ≈ "
      f"{n*6/FIRST_MAX:.1f} 次。\n")
    A("| 號碼 | 出現次數 | 頻率 | 遺漏(距今幾期) |")
    A("|---:|---:|---:|---:|")
    for num in range(1, FIRST_MAX + 1):
        c = first[num]
        A(f"| {num} | {c} | {fmt_pct(c/n)} | {gap_first[num]} |")

    A("\n**第一區最常開出 Top10**：")
    A(", ".join(f"{num}({c})" for num, c in topn(first, 10)))
    A("\n**第一區最少開出 Bottom10**：")
    A(", ".join(f"{num}({c})" for num, c in topn(first, 10, reverse=False)))

    A("\n---\n## 2. 第二區號碼出現次數（1~8，選 1）\n")
    A(f"平均每個號碼出現次數 ≈ {n/SECOND_MAX:.1f} 次。\n")
    A("| 號碼 | 出現次數 | 頻率 | 遺漏 |")
    A("|---:|---:|---:|---:|")
    for num in range(1, SECOND_MAX + 1):
        c = second[num]
        A(f"| {num} | {c} | {fmt_pct(c/n)} | {gap_second[num]} |")

    A(f"\n---\n## 3. 近 {recent_n} 期冷熱號\n")
    A("**第一區近期最熱 Top10**：")
    A(", ".join(f"{num}({c})" for num, c in topn(rf, 10)))
    A("\n**第二區近期分布**：")
    A(", ".join(f"{num}({rs[num]})" for num in range(1, SECOND_MAX + 1)))

    A("\n---\n## 4. 號碼結構分析（第一區）\n")
    A("### 奇數個數分布（每期 6 個號碼中有幾個奇數）")
    A("| 奇數個數 | 期數 | 占比 |")
    A("|---:|---:|---:|")
    for k in range(0, 7):
        A(f"| {k} | {odd_even[k]} | {fmt_pct(odd_even[k]/n)} |")
    A("\n### 大號(>=20)個數分布")
    A("| 大號個數 | 期數 | 占比 |")
    A("|---:|---:|---:|")
    for k in range(0, 7):
        A(f"| {k} | {big_small[k]} | {fmt_pct(big_small[k]/n)} |")
    A(f"\n### 第一區六碼總和\n")
    avg = sum(sums) / n
    A(f"- 平均總和：**{avg:.1f}**（理論期望值 = 6×(1+38)/2 = 117）")
    A(f"- 最小：{min(sums)}，最大：{max(sums)}")
    A(f"- 含至少一組連號的期數：{consec}（{fmt_pct(consec/n)}）")

    A("\n---\n## 5. 機率真相 & 「該買幾個號碼」\n")
    A("### 5.1 單注中獎機率（這是數學事實，與歷史冷熱無關）")
    A(f"- 第一區從 38 選 6 共 **C(38,6) = {C38_6:,}** 種組合")
    A(f"- 再乘第二區 8 選 1 → 頭獎樣本空間 = **{JACKPOT_SPACE:,}** 種")
    A(f"- 故 **一注中頭獎機率 = 1 / {JACKPOT_SPACE:,} ≈ {fmt_pct(1/JACKPOT_SPACE)}**")
    A("\n> ⚠ 重要：每一期都是獨立隨機抽樣。某號碼過去開很多次，**不代表**下一期更會開；"
      "開很少次也**不代表**『該補了』。賭徒謬誤（賭客謬誤）正是如此。上面的冷熱表"
      "可以拿來『選自己順眼的號碼』，但**它無法提高你單注命中的機率**。\n")

    A("### 5.2 唯一真正提高中獎『機率』的方法：包牌（買更多組號碼）")
    A("第一區若選 k 個號碼包牌（搭配 1 個第二區），可組出 C(k,6) 注。"
      "注數越多，命中機率越高，但花費同步上升：\n")
    A("| 第一區選幾個號碼 | 注數 C(k,6) | 花費(每注$50) | 中頭獎機率 | 中『第一區6碼』機率 |")
    A("|---:|---:|---:|---:|---:|")
    for k, tickets, cost, pj, p6 in buy_table():
        A(f"| {k} | {tickets:,} | NT${cost:,} | {fmt_pct(pj)} (1/{round(1/pj):,}) "
          f"| {fmt_pct(p6)} |")
    A("\n解讀：")
    A("- 買 1 注：中頭獎機率約 1/2208 萬。")
    A("- 第一區全包 38 個號碼 = C(38,6)=2,760,681 注，搭 8 個第二區則需 "
      f"2,760,681×8 = {JACKPOT_SPACE:,} 注、花 NT${JACKPOT_SPACE*TICKET_PRICE:,}"
      " 才能 100% 命中頭獎——但這金額遠超 10 億頭獎，**穩賠**。")
    A("- 結論：包牌能等比例放大機率，卻也等比例放大成本，且期望值仍為負。")

    A("\n### 5.3 期望值（為什麼長期一定虧）")
    jackpot = 1_000_000_000
    ev_jackpot_only = jackpot / JACKPOT_SPACE
    A(f"- 假設頭獎累積到 **NT${jackpot:,}（10 億）**，僅計頭獎的每注期望回收 ≈ "
      f"NT${ev_jackpot_only:.1f}")
    A(f"- 每注成本 NT${TICKET_PRICE}。即使只看頭獎，10 億時期望回收約 "
      f"NT${ev_jackpot_only:.0f}，已接近成本——但這忽略了：")
    A("  1. 頭獎可能**多人均分**（中獎人越多分越少）；")
    A("  2. 高額獎金需扣**所得稅與印花稅**（實領縮水）；")
    A("  3. 多數情況頭獎沒這麼高，期望值明顯為負。")
    A("- **誠實的結論**：沒有任何選號法能讓樂透變成正期望值的投資。"
      "請當作娛樂、量力而為。\n")

    A("---\n## 6. 給你的實務建議（如實、不騙你）\n")
    A("1. **想提高中獎機率** → 唯一有效手段是『買更多組不同號碼』(包牌)，"
      "上面表 5.2 告訴你各注數對應的機率與花費，自己抓預算即可。\n")
    A("2. **冷熱號、遺漏值** → 拿來挑選自己喜歡的號碼可以，但別相信它能『預測』，"
      "因為每期獨立隨機。\n")
    A("3. **避免熱門組合可降低均分風險** → 很多人愛選『生日(1~31)』、連號、"
      "對稱號。若真的中了，選冷門組合能降低與他人均分的機率（這影響的是"
      "『中了之後分多少』，不是『中不中』）。\n")
    A("4. **設定預算上限**，把它當娛樂支出，不要當投資。\n")

    return "\n".join(L)


def main():
    if not os.path.exists(DATA_PATH):
        raise SystemExit(
            f"找不到資料檔 {DATA_PATH}\n"
            "請先執行 `python3 scraper.py` 從官方 API 抓取真實開獎資料。"
        )
    os.makedirs(REPORT_DIR, exist_ok=True)
    meta, draws = load()
    if not draws:
        raise SystemExit("資料檔內沒有任何開獎紀錄。")

    report = build_report(meta, draws)
    report_path = os.path.join(REPORT_DIR, "analysis_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    # 同時輸出機器可讀統計
    first, second = basic_freq(draws)
    stats = {
        "count": len(draws),
        "first_zone_freq": {str(k): first[k] for k in range(1, FIRST_MAX + 1)},
        "second_zone_freq": {str(k): second[k] for k in range(1, SECOND_MAX + 1)},
        "jackpot_odds_one_in": JACKPOT_SPACE,
    }
    with open(os.path.join(REPORT_DIR, "stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f"分析完成，共 {len(draws)} 期。")
    print(f"報告：{report_path}")
    print(f"頭獎機率：1 / {JACKPOT_SPACE:,}")


if __name__ == "__main__":
    main()
