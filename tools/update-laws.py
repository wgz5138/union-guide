#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
從「全國法規資料庫」官方 Open API 下載整包法規（ZIP），抽出我們關心的
法條，產出精簡的 laws.json 供 lawyer.html 直接讀取。

官方端點（回傳的是「全部法規打包成一個 ZIP」，內含一個 JSON）：
  https://law.moj.gov.tw/api/Ch/Law/JSON

JSON 結構（官方 schema，欄位名以官方為準，本程式對缺漏採容錯）：
  { "UpdateDate": "YYYYMMDD",
    "Laws": [ { "LawName", "LawModifiedDate", "LawURL",
                "LawArticles": [ {"ArticleType":"A"|"C", "ArticleNo":"第 24 條",
                                  "ArticleContent":"…"} ] } ] }

設計：
- 勞動法群／個資／商標 → 整部收錄；民法、刑法 → 只收常用條（避免上千條爆量）。
- 找不到的法規只警告、不讓整個流程失敗（法規可能更名）。
- 此程式不在開發容器跑（無外網）；由 GitHub Action 在有網路的 runner 執行。
"""
import io, json, re, sys, zipfile, urllib.request, datetime

API_URL = "https://law.moj.gov.tw/api/Ch/Law/JSON"
OUT = "laws.json"

# 法規 -> 要收的條（None = 整部；set = 只收這些條號的數字字串，如 "24"、"227-2"）
# 名稱必須與官方「LawName」完全一致。
WANT = {
    # —— 勞動法群（主場：整部收錄）——
    "勞動基準法": None,
    "勞動基準法施行細則": None,
    "勞動事件法": None,
    "勞工退休金條例": None,
    "性別平等工作法": None,        # 2023 年由「性別工作平等法」更名
    "職業安全衛生法": None,
    "勞資爭議處理法": None,
    # —— 個資 / 商標（整部）——
    "個人資料保護法": None,
    "商標法": None,
    # —— 民法（巨型法典：只收常用條）——
    "民法": {"148", "184", "188", "195", "216", "227-2", "247-1", "487"},
    # —— 刑法（只收常用條）——
    "中華民國刑法": {"304", "305", "309", "310", "313", "315", "342"},
}

# 法規 -> 分類（給工具的 cat 欄）
CAT = {
    "勞動基準法": "勞動", "勞動基準法施行細則": "勞動", "勞動事件法": "勞動",
    "勞工退休金條例": "勞動", "性別平等工作法": "勞動", "職業安全衛生法": "勞動",
    "勞資爭議處理法": "勞動",
    "個人資料保護法": "個資", "商標法": "商標",
    "民法": "民事", "中華民國刑法": "刑事",
}


def art_num(s):
    """從 '第 227-2 條' 抽出 '227-2'（去空白）。"""
    m = re.search(r"第\s*([0-9]+(?:-[0-9]+)?)\s*條", s or "")
    return m.group(1) if m else None


def art_label(s):
    """正規化條號顯示成 '第227-2條'（無空白），與工具內格式一致。"""
    n = art_num(s)
    return "第%s條" % n if n else (s or "").replace(" ", "")


def clean(t):
    t = (t or "").replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r"[ \t　]+", " ", t)        # 收斂全形/半形空白
    t = re.sub(r"\n{2,}", "\n", t).strip()
    return t


def download_json():
    req = urllib.request.Request(API_URL, headers={"User-Agent": "union-guide-law-updater/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = r.read()
    # 可能是 ZIP，也可能直接是 JSON
    if raw[:2] == b"PK":
        zf = zipfile.ZipFile(io.BytesIO(raw))
        name = next((n for n in zf.namelist() if n.lower().endswith(".json")), None)
        if not name:
            raise RuntimeError("ZIP 內找不到 .json：%s" % zf.namelist())
        data = zf.read(name)
    else:
        data = raw
    # 官方檔常為 UTF-8（偶帶 BOM）
    return json.loads(data.decode("utf-8-sig"))


def main():
    print("下載：", API_URL)
    doc = download_json()
    laws_in = doc.get("Laws") or doc.get("laws") or []
    update_date = doc.get("UpdateDate") or doc.get("updateDate") or datetime.date.today().strftime("%Y%m%d")
    print("官方 UpdateDate：", update_date, "／法規筆數：", len(laws_in))

    by_name = {}
    for L in laws_in:
        nm = (L.get("LawName") or "").strip()
        if nm in WANT:
            by_name[nm] = L

    out = []
    for nm, want in WANT.items():
        L = by_name.get(nm)
        if not L:
            print("⚠ 找不到法規（可能更名）：", nm, file=sys.stderr)
            continue
        modified = L.get("LawModifiedDate") or ""
        chapter = ""
        arts = L.get("LawArticles") or []
        taken = 0
        for a in arts:
            atype = (a.get("ArticleType") or "").upper()
            content = a.get("ArticleContent") or ""
            no = a.get("ArticleNo") or ""
            if atype == "C":                      # 編章節標題：記下當作 title 提示
                chapter = clean(content).replace("\n", " ")
                continue
            n = art_num(no)
            if not n:
                continue
            if want is not None and n not in want:
                continue
            out.append({
                "law": nm,
                "art": art_label(no),
                "title": chapter,
                "text": clean(content),
                "cat": CAT.get(nm, "其他"),
                "modified": modified,
            })
            taken += 1
        print("  收錄 %-12s %d 條" % (nm, taken))

    if not out:
        raise RuntimeError("沒有收到任何法條，疑似結構改變，中止（不覆蓋 laws.json）。")

    payload = {
        "updated": update_date,
        "source": "全國法規資料庫 law.moj.gov.tw（api/Ch/Law/JSON）",
        "note": "官方現行條文；民法、刑法為常用條精選，其餘為整部收錄。",
        "count": len(out),
        "laws": out,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print("✅ 寫出 %s：%d 條（官方更新日 %s）" % (OUT, len(out), update_date))


if __name__ == "__main__":
    main()
