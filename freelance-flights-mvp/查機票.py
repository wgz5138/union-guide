#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
互動查機票：自己輸入「出發、目的地、月份」，馬上查最便宜＋推 Telegram。

用法（在 freelance-flights-mvp 資料夾裡）：
    python 查機票.py

它會一步步問你問題，你用中文打地名就好（例：高雄、東京、日本、首爾）。
查詢、記 CSV、推 Telegram 全都沿用 travelpayouts_flights.py 的設定，
所以 token、門檻、地名對照表都共用，不用重設。
"""

import travelpayouts_flights as tp


def 問(提示, 預設=""):
    答 = input(提示).strip()
    return 答 or 預設


def main():
    print("=" * 46)
    print("✈️  互動查機票（直接按 Enter 用預設值）")
    print("=" * 46)
    print("可用中文地名：")
    print("　" + "、".join(tp.地名對照表.keys()))
    print("（表上沒有的，直接打英文代碼也行；門檻價 %d 元）" % tp.THRESHOLD)
    print("-" * 46)

    while True:
        origin = 問("出發地？（預設 高雄）：", "高雄")
        dest = 問("目的地？（例 東京 / 日本 / 首爾）：")
        if not dest:
            print("沒填目的地，結束。👋")
            break
        month = 問("去程月份？（例 2026-09）：")
        ret = 問("回程月份？（要查來回才填；單程直接按 Enter）：")

        route = {"origin": origin, "dest": dest, "month": month}
        if ret:
            route["return"] = ret

        print("\n查詢中…")
        try:
            row = tp.search_cheapest(route)
        except Exception as e:
            print("⚠ 查詢出錯：", e)
            row = None

        if row:
            tp.save_csv(row)     # 記進 CSV
            tp.notify(row)       # 印出結果＋（有設 Telegram 就）推到手機
        else:
            print("　這條最近查無票價，換個月份或目的地試試。")

        if 問("\n再查一筆？（輸入 y 繼續，其他鍵結束）：").lower() != "y":
            print("掰掰 👋")
            break


if __name__ == "__main__":
    main()
