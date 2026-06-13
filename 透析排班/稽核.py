# -*- coding: utf-8 -*-
"""
透析「稽核藥水 AK」每月自動排班程式  v0.1（草稿，待真實小班驗證）
===============================================================
這支跟「印藥水(排班.py)」是兄弟程式，但規則不同：

【稽核規則（玉繡 2026-06 確認）】
  • 每月排一次（月初前），一個班別稽核整個月。
  • 兩區洗腎室(一區/二區) × 兩組治療日(W135=週一三五 / W246=週二四六)
    × 三個班(第一班/第二班/第三班) = 每月共 12 位，每格 1 人。
  • 班次對應班別：
      - 第一班、第二班 → 由「白班(D)」組員稽核
      - 第三班         → 由「小夜(E)」組員稽核
      - 若當月小夜組員較多 → 小夜可補「第二班」
  • 分區(一區/二區)：看「第一週小班」的工作區域。
  • 白班/小夜：看「當月小班」(整個月多數)。
  • 一週稽核兩次：稽核者自己挑有上班的兩天搭配(程式只排到「誰+哪一班」，
    哪兩天由本人決定)。
  • 公平：15 人 −12 = 每月 3 人休息；輪流、列入統計、長期讓休息次數平均。
    每位組員都可以稽核。114/9 歸零重新統計。

【我(程式)目前的合理預設，待真實小班驗證後再調】
  ① 整月「白/夜」：數整個月 D 天數 vs E 天數，多者為準(平手算白)。
  ② 分區：用「最早那一週(第一週)」該員的責任區域 → 對到一區/二區；
     第一週沒有就退而用整月最常出現的區。
  ③ W135/W246 可不可排某人：看他整月有沒有在該組的日子上過班(有才排得進)。
  ④ 稽核預設「不跨區」(分區既然照工作區域)；排不出時標 ❌ 提示人工處理。
  ⑤ 公平：依「過去稽核次數」少的先排(= 之前較常休息的人，這個月先補上稽核)，
     剩下 3 個沒排到的就是本月休息 → 長期休息次數自然平均。

用法:  python 稽核.py <週班1.xls> [週班2.xls ...] [月份 例 2026-06]
        • 小班是「週班」(一週一檔)，稽核要看整月 → 可一次給多個週班檔，程式自動合併成整月。
        • 也支援「一檔多分頁(每頁一週)」的格式。
        • 月份不填 → 自動用「最後那一週所在的月份」。
"""
import os, sys, csv, re, traceback
from datetime import date, datetime, timedelta
import pandas as pd

# ===================== 路徑(與印藥水共用同一批設定檔) =====================
BASE = os.path.dirname(os.path.abspath(__file__))
F_ROSTER  = os.path.join(BASE, "組員名單.csv")
F_BEDS    = os.path.join(BASE, "床號分區.csv")
F_SHIFTS  = os.path.join(BASE, "不可印班別.csv")
F_HOLIDAY = os.path.join(BASE, "休診日.csv")
F_HISTORY = os.path.join(BASE, "稽核紀錄.csv")     # ← 稽核自己的公平累計，跟印藥水分開
OUT_DIR   = os.path.join(BASE, "輸出")
os.makedirs(OUT_DIR, exist_ok=True)

WARN = []
def warn(m): WARN.append(m)

# ===================== 安全讀 CSV =====================
def _read_rows(path):
    if not os.path.exists(path): return []
    try:
        with open(path, encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))
    except Exception as e:
        warn(f"⚠ 讀取 {os.path.basename(path)} 失敗({e})"); return []

# ===================== 載入設定 =====================
def load_beds():
    """回傳 床號字串->區域(一區/二區/…) 對照表。稽核只在意一區/二區。"""
    rows=_read_rows(F_BEDS); zone2area={}
    for r in rows:
        area=(r.get("區域類型") or "").strip(); bed=(r.get("床號") or "").strip()
        if area and bed: zone2area[bed]=area
    if not zone2area: warn("❌ 床號分區.csv 是空的或讀不到，無法判斷一區/二區")
    return zone2area

def load_shifts():
    rows=_read_rows(F_SHIFTS); lst=[(r.get("班別") or "").strip() for r in rows]
    return [s for s in lst if s]

def load_holidays():
    rows=_read_rows(F_HOLIDAY); hs=set()
    for r in rows:
        s=(r.get("日期") or "").strip()
        if not s: continue
        try: hs.add(datetime.strptime(s[:10], "%Y-%m-%d").date())
        except Exception: warn(f"⚠ 休診日『{s}』格式不對，已略過")
    return hs

def load_roster():
    rows=_read_rows(F_ROSTER); seen=set(); roster=[]
    for r in rows:
        c=(r.get("卡號") or "").strip(); n=(r.get("姓名") or "").strip()
        if not c and not n: continue
        if (c,n) in seen: continue
        seen.add((c,n)); roster.append({"card":c,"name":n})
    if not roster: warn("❌ 組員名單.csv 是空的！")
    return roster

ZONE2AREA={}; SHIFT_EXCLUDE=[]; HOLIDAYS=set()

def is_excluded_shift(s):
    s=(s or "").strip()
    if not s: return True
    for tok in SHIFT_EXCLUDE:
        if s==tok: return True
        if len(tok)>=3 and tok in s: return True
    return False

def zone_area(zone):
    z=(zone or "").strip()
    return ZONE2AREA.get(z, "未知") if z else "空"

# ===================== 小班解析(沿用印藥水的動態定位) =====================
def _cell(df,r,c):
    if r<0 or r>=len(df) or c<0 or c>=df.shape[1]: return ""
    v=df.iat[r,c]; return "" if pd.isna(v) else str(v).strip()

def parse_date(v):
    if v is None: return None
    if isinstance(v,(pd.Timestamp,datetime)):
        try: return v.date()
        except Exception: return None
    s=str(v).strip()
    m=re.search(r"(\d{4})\D?(\d{1,2})\D(\d{1,2})(?!\d)", s) or re.search(r"(\d{4})\D?(\d{2})(\d{2})(?!\d)", s)
    if m:
        try: return date(int(m.group(1)),int(m.group(2)),int(m.group(3)))
        except Exception: return None
    return None

def parse_sheet(df):
    """單一分頁(一週) → status[card][date]=(類別,班別,責任區域), name_of, by_name, monday"""
    hr=None
    for i in range(len(df)):
        if _cell(df,i,0)=="卡號" and _cell(df,i,1)=="姓名": hr=i; break
    if hr is None: return {}, {}, {}, None
    blocks=[c for c in range(df.shape[1]) if _cell(df,hr,c)=="類別"]
    bdates=[]
    for c in blocks:
        d=None
        for rr in range(hr-1,hr-4,-1):
            d=parse_date(df.iat[rr,c]) if 0<=rr<len(df) else None
            if d: break
        bdates.append(d)
    status={}; name_of={}; by_name={}
    for r in range(hr+1,len(df)):
        card=_cell(df,r,0); name=_cell(df,r,1)
        if not card and not name: continue
        if card and name: name_of[card]=name; by_name.setdefault(name,card)
        if not card: continue
        for c,d in zip(blocks,bdates):
            if d is None: continue
            status.setdefault(card,{})[d]=(_cell(df,r,c),_cell(df,r,c+1),_cell(df,r,c+2))
    monday=bdates[0] if bdates and bdates[0] else None
    return status, name_of, by_name, monday

def parse_month(paths, want_month):
    """讀一個或多個週班檔(每檔可含多分頁)，合併出『目標月份』的整月資料。
       paths = [檔案路徑,...]； want_month = (year,month) 或 None(自動用最後一週的月份)。"""
    sheets=[]   # (monday, status, name_of, by_name, 來源標籤)
    for path in paths:
        try: xls=pd.ExcelFile(path)
        except Exception as e: warn(f"⚠ 打不開檔案 {os.path.basename(path)}({e})"); continue
        for sn in xls.sheet_names:
            try: df=pd.read_excel(path, sheet_name=sn, header=None)
            except Exception as e: warn(f"⚠ {os.path.basename(path)} 分頁「{sn}」讀取失敗({e})"); continue
            st,no,bn,mon=parse_sheet(df)
            if mon: sheets.append((mon,st,no,bn,f"{os.path.basename(path)}#{sn}"))
    if not sheets: raise RuntimeError("所有檔案都抓不到『卡號/姓名』表頭或日期，請確認是正確的小班檔")
    sheets.sort(key=lambda x:x[0])
    # 決定目標月份
    if want_month is None:
        last=sheets[-1][0]; want_month=(last.year, last.month)
    yy,mm=want_month
    # 取出該月份有出現的分頁(該週有任何一天落在該月)
    def touches_month(mon):
        for i in range(7):
            d=mon+timedelta(days=i)
            if d.year==yy and d.month==mm: return True
        return False
    month_sheets=[s for s in sheets if touches_month(s[0])]
    if not month_sheets:
        raise RuntimeError(f"找不到 {yy}-{mm:02d} 月份的分頁，請確認月份或檔案")
    # 合併整月 status + 姓名表
    month_status={}; name_of={}; by_name={}
    for mon,st,no,bn,sn in month_sheets:
        name_of.update(no)
        for n,c in bn.items(): by_name.setdefault(n,c)
        for card,days in st.items():
            for d,rec in days.items():
                if d.year==yy and d.month==mm:           # 只收該月的治療日
                    month_status.setdefault(card,{})[d]=rec
    first_week_monday=month_sheets[0][0]
    first_week_status=month_sheets[0][1]
    return month_status, name_of, by_name, (yy,mm), first_week_monday, first_week_status

# ===================== 比對名單(卡號優先、姓名補抓) =====================
def match_members(roster, month_status, name_of, by_name):
    members=[]
    for m in roster:
        card,name=m["card"],m["name"]
        if card and card in month_status:
            members.append({"card":card,"name":name_of.get(card,name) or name})
        elif name and name in by_name and by_name[name] in month_status:
            nc=by_name[name]
            warn(f"⚠ 「{name}」卡號 {card or '(空)'} → 班表 {nc}(姓名補抓)")
            members.append({"card":nc,"name":name})
        else:
            warn(f"❌ 名單上的「{name}({card})」這個月小班找不到 → 離職/換人/整月休假?(本月略過)")
    return members

# ===================== 判定每人：白/夜、區域、W組可用性 =====================
W135_WD={0,2,4}   # 週一三五 (Mon=0)
W246_WD={1,3,5}   # 週二四六

def classify(members, month_status, first_week_status):
    """回傳 info[card] = {type:'白'/'夜'/None, area:'一區'/'二區'/'未知', w135:bool, w246:bool}"""
    info={}
    for m in members:
        c=m["card"]; days=month_status.get(c,{})
        white=night=0; w135=w246=False; area_count={}
        for d,(cat,shift,zone) in days.items():
            s=(shift or "").strip()
            if is_excluded_shift(s):   # 大夜/勤務/休假等不算「有效上班」
                continue
            # 白/夜
            if s.startswith("D"): white+=1
            elif s.startswith("E"): night+=1
            # 在哪組有上班日
            if d.weekday() in W135_WD: w135=True
            if d.weekday() in W246_WD: w246=True
        # 整月白/夜(多數；平手算白)
        typ = None
        if white==0 and night==0: typ=None
        elif white>=night: typ="白"
        else: typ="夜"
        # 區域：優先看第一週
        area=_area_of(c, first_week_status)
        if area=="未知" or area in ("空",):
            area=_area_of_month(c, month_status)
        info[c]={"type":typ,"area":area,"w135":w135,"w246":w246,
                 "white":white,"night":night}
    return info

def _area_of(card, week_status):
    """某員在某一週小班裡，責任區域對到的(一區/二區)，取最常出現的。"""
    cnt={}
    for d,(cat,shift,zone) in week_status.get(card,{}).items():
        if is_excluded_shift((shift or "").strip()): continue
        a=zone_area(zone)
        if a in ("一區","二區"): cnt[a]=cnt.get(a,0)+1
    if not cnt: return "未知"
    return max(cnt, key=cnt.get)

def _area_of_month(card, month_status):
    cnt={}
    for d,(cat,shift,zone) in month_status.get(card,{}).items():
        if is_excluded_shift((shift or "").strip()): continue
        a=zone_area(zone)
        if a in ("一區","二區"): cnt[a]=cnt.get(a,0)+1
    if not cnt: return "未知"
    return max(cnt, key=cnt.get)

# ===================== 公平累計 =====================
def load_history(skip_month=None):
    cnt={}; rest={}
    for r in _read_rows(F_HISTORY):
        if r.get("月份")==skip_month: continue
        c=r.get("卡號"); st=r.get("狀態")
        if st=="稽核": cnt[c]=cnt.get(c,0)+1
        elif st=="休":  rest[c]=rest.get(c,0)+1
    return cnt, rest

# ===================== 核心排班 =====================
# 12 格：區 × 組 × 班次。班次1,2=白班；班次3=小夜(小夜多時可補班次2)。
AREAS=["一區","二區"]; GROUPS=["W135","W246"]; SHIFTS=[1,2,3]

def assign(members, info, hist_cnt):
    idx={m["card"]:i for i,m in enumerate(members)}
    cost={m["card"]:hist_cnt.get(m["card"],0) for m in members}  # 過去稽核次數(少者先排)
    # 先看當月小夜人數，決定「小夜是否補第二班」
    night_pool=[m["card"] for m in members if info[m["card"]]["type"]=="夜"]
    white_pool=[m["card"] for m in members if info[m["card"]]["type"]=="白"]
    # 需求：班次3 共 4 格(夜)，班次1+2 共 8 格(白)。
    # 若夜>4：多出來的夜可補第二班(共 4 個第二班格)。
    extra_night_to_band2 = max(0, len(night_pool)-4)

    slots=[(a,g,s) for a in AREAS for g in GROUPS for s in SHIFTS]  # 12 格
    def need_type(s):  # 該班次需要的班別
        if s==3: return "夜"
        if s==2: return "白或夜" if extra_night_to_band2>0 else "白"
        return "白"
    def w_ok(c,g):
        return info[c]["w135"] if g=="W135" else info[c]["w246"]
    def type_ok(c,s):
        t=info[c]["type"]; nt=need_type(s)
        if t is None: return False
        if nt=="白": return t=="白"
        if nt=="夜": return t=="夜"
        return True   # 白或夜
    def cands(a,g,s):
        res=[]
        for m in members:
            c=m["card"]
            if info[c]["area"]!=a: continue
            if not type_ok(c,s): continue
            if not w_ok(c,g): continue
            res.append(c)
        return res

    assigned={}; used=set()
    # 先排限制最緊的(候選最少的)格子，避免卡死
    order=sorted(slots, key=lambda sl: len(cands(*sl)))
    for (a,g,s) in order:
        pool=[c for c in cands(a,g,s) if c not in used]
        # 公平：過去稽核少的先(= 較常休息者先補)，再看穩定順序
        pool.sort(key=lambda c:(cost[c], idx[c]))
        if pool:
            c=pool[0]; assigned[(a,g,s)]=c; used.add(c)
        else:
            warn(f"❌ {a} {g} 第{s}班 排不出人(看區域/白夜/該組有無上班)，請人工處理")
    return slots, assigned, used

# ===================== 顯示 / 輸出 =====================
BAND=["","第一班","第二班","第三班"]
def run():
    args=sys.argv[1:]
    # 參數分兩種：檔案路徑(.xls/.xlsx) 與 月份(像 2026-06)
    files=[a for a in args if a.lower().endswith((".xls",".xlsx"))]
    month_args=[a for a in args if re.fullmatch(r"\d{4}\D?\d{1,2}", a)]
    missing=[f for f in files if not os.path.exists(f)]
    if not files or missing:
        if missing: print("❌ 找不到這些檔案：" + "、".join(missing))
        print("用法: python 稽核.py <週班1.xls> [週班2.xls ...] [月份 例 2026-06]")
        print("（小班是週班，可一次給多個週班檔，程式自動合併成整月）")
        return

    global ZONE2AREA, SHIFT_EXCLUDE, HOLIDAYS
    ZONE2AREA=load_beds(); SHIFT_EXCLUDE=load_shifts(); HOLIDAYS=load_holidays()

    want=None
    if month_args:
        mm=re.search(r"(\d{4})\D?(\d{1,2})", month_args[0])
        want=(int(mm.group(1)), int(mm.group(2)))

    try:
        month_status,name_of,by_name,(yy,mm),fw_mon,fw_status=parse_month(files, want)
    except Exception as e:
        print(f"❌ 讀班表失敗：{e}"); return
    if len(files)>1:
        print(f"ℹ 已合併 {len(files)} 個週班檔")

    roster=load_roster()
    members=match_members(roster, month_status, name_of, by_name)
    info=classify(members, month_status, fw_status)
    tag=f"{yy}-{mm:02d}"
    hist_cnt,hist_rest=load_history(skip_month=tag)
    slots,assigned,used=assign(members, info, hist_cnt)
    nm=lambda c: name_of.get(c,c)
    rest_members=[m["card"] for m in members if m["card"] not in used]

    # ---------- 螢幕 ----------
    print(f"\n■ 檔案：{os.path.basename(path)}　月份：{tag}（第一週起 {fw_mon}）")
    print(f"■ 規則：每月12位｜白班→一二班、小夜→三班｜分區看第一週小班\n")
    print("="*14+f"  {tag} 稽核藥水 AK 名單  "+"="*14)
    for a in AREAS:
        print(f"\n【{a}】")
        for g in GROUPS:
            gl = "週一三五" if g=="W135" else "週二四六"
            cells=[]
            for s in SHIFTS:
                c=assigned.get((a,g,s))
                cells.append(f"{BAND[s]}:{nm(c) if c else '❌排不出'}")
            print(f"  {gl}　"+"　".join(cells))
    print("\n本月休息(輪流公平):", "、".join(nm(c) for c in rest_members) or "無",
          f"（{len(rest_members)} 人）")

    # 公平累計
    print("\n【公平累計】(含本月；稽=稽核月數、休=休息月數)")
    nc=dict(hist_cnt); nr=dict(hist_rest)
    for c in used: nc[c]=nc.get(c,0)+1
    for c in rest_members: nr[c]=nr.get(c,0)+1
    for m in sorted(members, key=lambda m:nc.get(m["card"],0)):
        c=m["card"]; mk="稽核" if c in used else "休息"
        ty=info[c]["type"] or "—"; ar=info[c]["area"]
        print(f'  {m["name"]:<5} 稽{nc.get(c,0):>2} 休{nr.get(c,0):>2}  本月:{mk}（{ty}/{ar}）')

    if WARN:
        print("\n【提醒/警告】")
        for w in WARN: print("  "+w)

    # ---------- 輸出 Excel + 文字 ----------
    rows=[]
    for a in AREAS:
        for g in GROUPS:
            gl="週一三五" if g=="W135" else "週二四六"
            for s in SHIFTS:
                c=assigned.get((a,g,s))
                rows.append({"區":a,"組":gl,"班次":BAND[s],"稽核者":(nm(c) if c else "❌排不出")})
    out_x=os.path.join(OUT_DIR,f"稽核名單_{tag}.xlsx")
    try:
        pd.DataFrame(rows).to_excel(out_x, index=False); print(f"\n✔ Excel：{out_x}")
    except Exception as e: warn(f"⚠ 寫 Excel 失敗：{e}")

    lines=[f"📋 {tag} 稽核藥水 AK 名單",""]
    for a in AREAS:
        lines.append(f"《{a}》")
        for g in GROUPS:
            gl="週一三五" if g=="W135" else "週二四六"
            parts=[f"{BAND[s]}:{nm(assigned.get((a,g,s))) if assigned.get((a,g,s)) else '❌'}" for s in SHIFTS]
            lines.append(f"　{gl}　"+"　".join(parts))
    lines+=["","休息:"+("、".join(nm(c) for c in rest_members) or "無")]
    out_t=os.path.join(OUT_DIR,f"稽核名單_{tag}.txt")
    try:
        with open(out_t,"w",encoding="utf-8") as f: f.write("\n".join(lines))
        print(f"✔ 文字(可貼LINE)：{out_t}")
    except Exception as e: warn(f"⚠ 寫文字檔失敗：{e}")

    # ---------- 寫回稽核紀錄(同月覆蓋) ----------
    keep=[r for r in _read_rows(F_HISTORY) if r.get("月份")!=tag]
    for m in members:
        c=m["card"]; st="稽核" if c in used else "休"
        pos=""
        for k,v in assigned.items():
            if v==c: pos=f"{k[0]}/{ '週一三五' if k[1]=='W135' else '週二四六'}/{BAND[k[2]]}"; break
        keep.append({"月份":tag,"卡號":c,"姓名":m["name"],"狀態":st,"位置":pos})
    try:
        with open(F_HISTORY,"w",newline="",encoding="utf-8-sig") as f:
            w=csv.DictWriter(f,fieldnames=["月份","卡號","姓名","狀態","位置"]); w.writeheader()
            for r in keep: w.writerow(r)
    except Exception as e:
        print(f"⚠ 寫稽核紀錄失敗(不影響本次名單)：{e}")

def main():
    try: run()
    except Exception as e:
        print("\n❌ 程式遇到沒預期到的狀況，但已幫你攔下來(不會弄壞檔案)。")
        print("   錯誤訊息：", e); traceback.print_exc()

if __name__=="__main__":
    main()
