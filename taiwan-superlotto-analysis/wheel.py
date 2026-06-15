#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
威力彩包牌選號產生器
======================

威力彩規則：第一區 1~38 選 6、第二區 1~8 選 1，每注 NT$100。
頭獎機率 = 1 / (C(38,6)×8) = 1 / 22,085,448。

「包牌」= 第一區挑一組 k 個號碼（k>6），把這 k 個號碼能組出的所有 C(k,6) 種
6 碼組合全買下來（再各搭配你選的第二區號碼）。
保證：**只要當期開出的 6 個第一區號碼全都落在你挑的這 k 個裡，你必中一注「第一區 6 中 6」**；
若第二區也在你選的範圍內，那一注就是頭獎。

⚠ 誠實提醒：包牌只是「等比例放大注數→等比例放大機率」，成本同步放大，
   期望值仍為負。沒有任何選號法能讓樂透變成穩賺。請當娛樂、量力而為。

用法範例：
  # 1) 包牌全餐：第一區挑 9 個號碼，第二區挑 2 個號碼，列出所有注單並存檔
  python3 wheel.py wheel --pool "3 14 24 38 7 22 16 19 31" --second "2 5" --out tickets.csv

  # 2) 依預算試算：我有 2 萬元，第二區固定 1 個，能包幾個號碼？
  python3 wheel.py budget --budget 20000 --second-count 1

  # 3) 快速隨機選號：隨機產生 5 注（可加 --avoid-birthday 偏好 >31 的號碼以降低均分風險）
  python3 wheel.py random --count 5 --avoid-birthday
"""

import argparse
import csv
import math
import random
import sys
from itertools import combinations

FIRST_MIN, FIRST_MAX = 1, 38
SECOND_MIN, SECOND_MAX = 1, 8
PICK = 6
TICKET_PRICE = 100  # 威力彩每注 NT$100（由官方 銷售總額/銷售注數 驗證）

C38_6 = math.comb(FIRST_MAX, PICK)           # 2,760,681
JACKPOT_SPACE = C38_6 * SECOND_MAX            # 22,085,448


def parse_int_list(s):
    if not s:
        return []
    return [int(x) for x in s.replace(",", " ").split()]


def fmt_prob(tickets):
    """回傳 (百分比字串, 1/N 字串)。"""
    if tickets <= 0:
        return "0%", "—"
    p = tickets / JACKPOT_SPACE
    pct = f"{p*100:.3g}%" if p * 100 < 0.001 else f"{p*100:.4f}%"
    one_in = round(JACKPOT_SPACE / tickets)
    return pct, f"1/{one_in:,}"


def disclaimer():
    print("\n" + "─" * 56)
    print("⚠ 提醒：包牌等比例放大注數與成本，期望值仍為負。")
    print("  樂透每期獨立隨機，沒有方法能保證或長期獲利，請當娛樂、設預算上限。")
    print("─" * 56)


# ---------------------------------------------------------------- wheel
def cmd_wheel(args):
    pool = sorted(set(parse_int_list(args.pool)))
    seconds = sorted(set(parse_int_list(args.second))) if args.second else list(
        range(SECOND_MIN, SECOND_MAX + 1))

    # 驗證
    if any(not (FIRST_MIN <= n <= FIRST_MAX) for n in pool):
        sys.exit(f"第一區號碼須介於 {FIRST_MIN}~{FIRST_MAX}：{pool}")
    if len(pool) < PICK:
        sys.exit(f"第一區至少要挑 {PICK} 個號碼才能包牌（你只給了 {len(pool)} 個）。")
    if any(not (SECOND_MIN <= s <= SECOND_MAX) for s in seconds):
        sys.exit(f"第二區號碼須介於 {SECOND_MIN}~{SECOND_MAX}：{seconds}")

    k = len(pool)
    combos = list(combinations(pool, PICK))
    n_first = len(combos)                       # = C(k,6)
    n_tickets = n_first * len(seconds)
    cost = n_tickets * TICKET_PRICE
    pct, one_in = fmt_prob(n_tickets)
    # 命中「第一區 6 碼」(不論第二區) 的機率
    p_six_pct = f"{n_first / C38_6 * 100:.4g}%"

    print("=== 威力彩包牌全餐 ===")
    print(f"第一區包牌號碼（{k} 個）：{' '.join(f'{n:02d}' for n in pool)}")
    print(f"第二區號碼（{len(seconds)} 個）：{' '.join(f'{s:02d}' for s in seconds)}")
    print(f"總注數：C({k},6) × {len(seconds)} = {n_first:,} × {len(seconds)} = {n_tickets:,} 注")
    print(f"總花費：{n_tickets:,} × NT${TICKET_PRICE} = NT${cost:,}")
    print(f"中頭獎機率：{pct}（約 {one_in}）")
    print(f"命中『第一區 6 個號碼』機率（不論第二區）：{p_six_pct}")
    print(f"保證：當期開出的 6 個第一區號碼若全在上面 {k} 個之中，必中一注 6 碼；")
    print(f"      且第二區若也在你選的 {len(seconds)} 個之中 → 中頭獎。")

    if args.out:
        with open(args.out, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["第幾注", "獎號1", "獎號2", "獎號3", "獎號4", "獎號5", "獎號6", "第二區"])
            i = 0
            for c in combos:
                for s in seconds:
                    i += 1
                    w.writerow([i, *c, s])
        print(f"\n已將全部 {n_tickets:,} 注寫入：{args.out}")
    elif n_tickets <= 30:
        print("\n注單：")
        i = 0
        for c in combos:
            for s in seconds:
                i += 1
                print(f"  第{i:>3}注  第一區 {' '.join(f'{x:02d}' for x in c)}  第二區 {s:02d}")
    else:
        print(f"\n（注數較多，未在畫面列出；加 --out 檔名.csv 可匯出全部 {n_tickets:,} 注）")
    disclaimer()


# ---------------------------------------------------------------- budget
def cmd_budget(args):
    budget = args.budget
    m = args.second_count
    if m < 1 or m > SECOND_MAX:
        sys.exit(f"--second-count 須介於 1~{SECOND_MAX}")
    print(f"=== 依預算試算（預算 NT${budget:,}，第二區選 {m} 個）===\n")
    print("| 第一區挑幾個 | 注數 | 花費 | 中頭獎機率 | 預算內? |")
    print("|---:|---:|---:|---:|:---:|")
    best_k = None
    for k in range(PICK, FIRST_MAX + 1):
        n_first = math.comb(k, PICK)
        n_tickets = n_first * m
        cost = n_tickets * TICKET_PRICE
        pct, one_in = fmt_prob(n_tickets)
        ok = cost <= budget
        if ok:
            best_k = k
        mark = "✅" if ok else "—"
        print(f"| {k} | {n_tickets:,} | NT${cost:,} | {pct} ({one_in}) | {mark} |")
        if cost > budget and k > (best_k or PICK) + 1:
            break
    print()
    if best_k:
        n_first = math.comb(best_k, PICK)
        n_tickets = n_first * m
        cost = n_tickets * TICKET_PRICE
        pct, one_in = fmt_prob(n_tickets)
        print(f"👉 預算 NT${budget:,} 內，最多可第一區包 **{best_k} 個號碼**"
              f"（{n_tickets:,} 注、NT${cost:,}），中頭獎機率約 {one_in}。")
        print(f"   產生注單：python3 wheel.py wheel --pool \"<{best_k}個號碼>\""
              f"{' --second ...' if m>1 else ''} --out tickets.csv")
    else:
        print(f"預算不足以包牌（最少 {PICK} 個號碼 × {m} 第二區 = "
              f"{m} 注 = NT${m*TICKET_PRICE}）。")
    disclaimer()


# ---------------------------------------------------------------- random
def cmd_random(args):
    n = args.count
    rng = random.Random(args.seed)
    pool = list(range(FIRST_MIN, FIRST_MAX + 1))
    seen = set()
    tickets = []
    guard = 0
    while len(tickets) < n and guard < n * 1000:
        guard += 1
        if args.avoid_birthday:
            # 至少 2 個號碼 >31，降低與「生日選號」族群均分的機率
            first = sorted(random.sample(pool, PICK))
            if sum(1 for x in first if x > 31) < 2:
                continue
        else:
            first = sorted(random.sample(pool, PICK))
        second = random.randint(SECOND_MIN, SECOND_MAX)
        key = (tuple(first), second)
        if key in seen:
            continue
        seen.add(key)
        tickets.append((first, second))
    print(f"=== 隨機選號 {len(tickets)} 注"
          f"{'（已避開生日偏好：至少2個號碼>31）' if args.avoid_birthday else ''} ===")
    for i, (first, second) in enumerate(tickets, 1):
        print(f"  第{i:>2}注  第一區 {' '.join(f'{x:02d}' for x in first)}  第二區 {second:02d}")
    print(f"\n花費：{len(tickets)} 注 × NT${TICKET_PRICE} = NT${len(tickets)*TICKET_PRICE:,}")
    print(f"每注中頭獎機率：1/{JACKPOT_SPACE:,}（隨機與包牌單注機率相同）")
    disclaimer()


def main():
    p = argparse.ArgumentParser(description="威力彩包牌選號產生器")
    sub = p.add_subparsers(dest="cmd", required=True)

    pw = sub.add_parser("wheel", help="包牌全餐：給一組號碼，產生所有組合注單")
    pw.add_argument("--pool", required=True, help="第一區號碼，空白或逗號分隔，如 \"3 14 24 38 7 22\"")
    pw.add_argument("--second", default=None, help="第二區號碼(可多個)，省略=全包 1~8")
    pw.add_argument("--out", default=None, help="輸出注單 CSV 檔名")
    pw.set_defaults(func=cmd_wheel)

    pb = sub.add_parser("budget", help="依預算試算最多能包幾個號碼")
    pb.add_argument("--budget", type=int, required=True, help="預算（元）")
    pb.add_argument("--second-count", type=int, default=1, help="第二區要選幾個(1~8)，預設1")
    pb.set_defaults(func=cmd_budget)

    pr = sub.add_parser("random", help="快速隨機選號")
    pr.add_argument("--count", type=int, default=5, help="要產生幾注，預設5")
    pr.add_argument("--avoid-birthday", action="store_true",
                    help="偏好至少2個號碼>31，降低與生日選號族群均分的機率")
    pr.add_argument("--seed", type=int, default=None, help="亂數種子(可重現)")
    pr.set_defaults(func=cmd_random)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
