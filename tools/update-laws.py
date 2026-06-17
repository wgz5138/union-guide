#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
從「全國法規資料庫」官方 Open API 下載整包法規（ZIP），抽出我們關心的
法條，產出精簡的 laws.json 供 lawyer.html 直接讀取。

官方端點（各自回傳「打包成一個 ZIP」，內含一個 JSON）：
  https://law.moj.gov.tw/api/Ch/Law/JSON    （法律，如 勞動基準法）
  https://law.moj.gov.tw/api/Ch/Order/JSON  （命令／施行細則，如 勞動基準法施行細則）

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
import io, json, re, ssl, sys, zipfile, urllib.request, datetime

API_URLS = [
    "https://law.moj.gov.tw/api/Ch/Law/JSON",     # 法律
    "https://law.moj.gov.tw/api/Ch/Order/JSON",   # 命令／施行細則
]
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
    # —— 勞動法擴充包（使用者加選）——
    "就業服務法": None,
    "勞工保險條例": None,
    "勞工職業災害保險及保護法": None,
    "大量解僱勞工保護法": None,
    "工會法": None,
    "工會法施行細則": None,
    "工會財務處理準則": None,
    "團體協約法": None,
    "不當勞動行為裁決辦法": None,   # 工會被打壓救濟（工會法§35）
    "勞資爭議調解辦法": None,       # 取代已廢止的勞資爭議處理法施行細則之調解部分
    "就業保險法": None,
    "勞工請假規則": None,
    "勞資會議實施辦法": None,
    # —— 個資（整部）——
    "個人資料保護法": None,
    # —— 人身保護／騷擾防治（使用者加選）——
    "性騷擾防治法": None,
    "跟蹤騷擾防制法": None,
    "家庭暴力防治法": None,
    "性別平等教育法": None,
    # —— 交通（使用者加選）——
    "道路交通管理處罰條例": None,
    # —— 醫事人員專業法（使用者加選；護理師相關）——
    "護理人員法": None,
    "醫師法": None,
    "藥師法": None,
    "醫事人員人事條例": None,   # 使用者說的「醫事人員法」＝公立醫院醫事人員人事/待遇
    "醫療法": None,
    # —— 公務（使用者加選）——
    "公務員服務法": None,
    "國軍退除役官兵輔導條例": None,   # 榮民醫院（退輔會）母法
    # —— 稅務（使用者加選）——
    "所得稅法": None,
    "稅捐稽徵法": None,
    "加值型及非加值型營業稅法": None,
    # —— 不動產 / 社區（使用者加選）——
    "公寓大樓管理條例": None,
    # —— 民法 / 刑法（巨型法典：只收常用條，保持 laws.json 精簡；實務深度改用判決查詢橋）——
    "民法": {"125", "126", "128", "129", "130", "137",          # 消滅時效（加班費=§126 五年）
             "148", "179", "184", "188", "195", "216", "227-2", "247-1", "487"},
    "中華民國刑法": {"304", "305", "309", "310", "313", "315", "342"},
}

# 法規 -> 分類（給工具的 cat 欄；用於法規庫瀏覽分類）
CAT = {
    "勞動基準法": "勞動", "勞動基準法施行細則": "勞動", "勞動事件法": "勞動",
    "勞工退休金條例": "勞動", "性別平等工作法": "勞動", "職業安全衛生法": "勞動",
    "勞資爭議處理法": "勞動",
    "就業服務法": "勞動", "勞工保險條例": "勞動", "勞工職業災害保險及保護法": "勞動",
    "大量解僱勞工保護法": "勞動", "工會法": "勞動", "工會法施行細則": "勞動", "工會財務處理準則": "勞動", "團體協約法": "勞動",
    "不當勞動行為裁決辦法": "勞動", "勞資爭議調解辦法": "勞動",
    "就業保險法": "勞動", "勞工請假規則": "勞動", "勞資會議實施辦法": "勞動",
    "個人資料保護法": "個資",
    "性騷擾防治法": "人身", "跟蹤騷擾防制法": "人身",
    "家庭暴力防治法": "人身", "性別平等教育法": "人身",
    "道路交通管理處罰條例": "交通",
    "護理人員法": "醫事", "醫師法": "醫事", "藥師法": "醫事", "醫事人員人事條例": "醫事", "醫療法": "醫事",
    "公務員服務法": "公務", "國軍退除役官兵輔導條例": "公務",
    "所得稅法": "稅務", "稅捐稽徵法": "稅務", "加值型及非加值型營業稅法": "稅務",
    "公寓大樓管理條例": "不動產",
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


def _fetch(url, ctx):
    req = urllib.request.Request(url, headers={"User-Agent": "union-guide-law-updater/1.0"})
    with urllib.request.urlopen(req, timeout=120, context=ctx) as r:
        return r.read()


def download_json(url):
    # 一般驗證，但關掉過嚴的 X509_STRICT：台灣政府憑證鏈常缺 Subject Key Identifier，
    # 新版 OpenSSL 嚴格模式會擋下（仍保留主機名／信任鏈驗證）。
    ctx = ssl.create_default_context()
    strict = getattr(ssl, "VERIFY_X509_STRICT", 0)
    if strict:
        ctx.verify_flags &= ~strict
    try:
        raw = _fetch(url, ctx)
    except ssl.SSLCertVerificationError as e:
        # 最後手段：公開、唯讀的官方法規資料，憑證鏈瑕疵時不驗證憑證重試（大聲記錄）。
        print("⚠ 憑證驗證仍失敗（%s）；改用『不驗證憑證』重試——公開法規、唯讀，可接受。" % e, file=sys.stderr)
        raw = _fetch(url, ssl._create_unverified_context())
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
    laws_in = []
    update_date = ""
    ok = 0
    for url in API_URLS:
        print("下載：", url)
        try:
            doc = download_json(url)
        except Exception as e:
            print("⚠ 下載失敗（%s）：%s" % (url, e), file=sys.stderr)
            continue
        part = doc.get("Laws") or doc.get("Orders") or doc.get("laws") or []
        laws_in += part
        update_date = doc.get("UpdateDate") or doc.get("updateDate") or update_date
        ok += 1
        print("  取得 %d 筆" % len(part))
    if not ok:
        raise RuntimeError("兩個官方端點都下載失敗，中止（不覆蓋 laws.json）。")
    if not update_date:
        update_date = datetime.date.today().strftime("%Y%m%d")
    print("官方 UpdateDate：", update_date, "／合計法規筆數：", len(laws_in))

    def norm_name(s):
        return re.sub(r"\s+", "", s or "")

    # 以「去空白」的法規名為鍵，吸收官方資料中可能的空白差異
    by_name = {}
    for L in laws_in:
        by_name[norm_name(L.get("LawName"))] = L

    out = []
    for nm, want in WANT.items():
        L = by_name.get(norm_name(nm))
        if not L:
            # 診斷：列出官方名稱中「包含此關鍵字」的候選，方便對名（更名／別字）
            key = norm_name(nm)
            cand = [x.get("LawName") for x in laws_in if key in norm_name(x.get("LawName"))][:3]
            print("⚠ 找不到法規：", nm, "｜官方近似名稱：", cand or "（無）", file=sys.stderr)
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

    # 併入補充條目（官方 API 抓不到的附表／附件，例如工會財務處理準則的會計科目表）。
    # 放在 tools/supplements.json，每次自動更新都會一併併入、不被覆蓋。
    try:
        with open("tools/supplements.json", encoding="utf-8") as f:
            supp = json.load(f)
        have = {(norm_name(o["law"]), o["art"].replace(" ", "")) for o in out}
        added = 0
        for s in supp:
            if not s.get("law") or not s.get("art") or not s.get("text"):
                continue
            key = (norm_name(s["law"]), s["art"].replace(" ", ""))
            if key in have:
                continue
            out.append({"law": s["law"].strip(), "art": s["art"].strip(),
                        "title": s.get("title", "").strip(), "text": s["text"].strip(),
                        "cat": s.get("cat", "其他").strip(), "modified": s.get("modified", "")})
            added += 1
        if added:
            print("  併入補充條目 %d 條（supplements.json）" % added)
    except FileNotFoundError:
        pass
    except Exception as e:
        print("⚠ 讀取 supplements.json 失敗（略過）：", e, file=sys.stderr)

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
