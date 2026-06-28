# -*- coding: utf-8 -*-
"""
透析「稽核藥水 AK」每月自動排班程式  v0.3
===============================================================
v0.3 新增:
  • 快速模式（免上傳 Excel）：python 稽核.py --quick 2026-06
    直接讀「快速名冊.csv」(卡號, 姓名, 班型, 區) 排稽核，
    白/夜與一區/二區由網頁玉繡點選決定，不必解析班表。
v0.2 新增:
  • 支援「班型覆蓋.csv」— 網頁 Stage 1 玉繡確認後寫入，程式優先採用
    格式: 卡號, 姓名, 班型（白班/夜班）
  • 稽核歷史可從外部 CSV 傳入（雲端學習用）

用法:  python 稽核.py <週班1.xls> [週班2.xls ...] [月份 例 2026-06]
        python 稽核.py --quick 2026-06            # 快速模式，讀 快速名冊.csv
"""
import os, sys, csv, re, traceback
from datetime import date, datetime, timedelta
import pandas as pd

BASE      = os.path.dirname(os.path.abspath(__file__))
F_ROSTER  = os.path.join(BASE, "組員名單.csv")
F_BEDS    = os.path.join(BASE, "床號分區.csv")
F_SHIFTS  = os.path.join(BASE, "不可印班別.csv")
F_HOLIDAY = os.path.join(BASE, "休診日.csv")
F_HISTORY = os.path.join(BASE, "稽核紀錄.csv")
F_SHIFT_OVERRIDE = os.path.join(BASE, "班型覆蓋.csv")   # ← Stage 1 玉繡確認的班型
F_QUICK   = os.path.join(BASE, "快速名冊.csv")           # ← 快速模式：卡號,姓名,班型,區
OUT_DIR   = os.path.join(BASE, "輸出")
os.makedirs(OUT_DIR, exist_ok=True)

WARN = []
def warn(m): WARN.append(m)

def _read_rows(path):
    if not os.path.exists(path): return []
    try:
        with open(path, encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))
    except Exception as e:
        warn(f"⚠ 讀取 {os.path.basename(path)} 失敗({e})"); return []

def load_beds():
    rows=_read_rows(F_BEDS); zone2area={}
    for r in rows:
        area=(r.get("區域類型") or "").strip(); bed=(r.get("床號") or "").strip()
        if area and bed: zone2area[bed]=area
    if not zone2area: warn("❌ 床號分區.csv 是空的或讀不到")
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

def load_shift_overrides():
    """讀玉繡在 Stage 1 確認的班型。回傳 {卡號: "白"/"夜", 姓名: "白"/"夜"}"""
    overrides = {}
    for r in _read_rows(F_SHIFT_OVERRIDE):
        card = (r.get("卡號") or "").strip()
        name = (r.get("姓名") or "").strip()
        typ  = (r.get("班型") or "").strip()
        if not typ or typ == "❓": continue
        mapped = "白" if "白" in typ else ("夜" if "夜" in typ else None)
        if mapped:
            if card: overrides[card] = mapped
            if name: overrides[name] = mapped
    return overrides

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
    sheets=[]
    for path in paths:
        try: xls=pd.ExcelFile(path)
        except Exception as e: warn(f"⚠ 打不開檔案 {os.path.basename(path)}({e})"); continue
        for sn in xls.sheet_names:
            try: df=pd.read_excel(path, sheet_name=sn, header=None)
            except Exception as e: warn(f"⚠ {os.path.basename(path)} 分頁「{sn}」讀取失敗({e})"); continue
            st,no,bn,mon=parse_sheet(df)
            if mon: sheets.append((mon,st,no,bn,f"{os.path.basename(path)}#{sn}"))
    if not sheets: raise RuntimeError("所有檔案都抓不到表頭或日期，請確認是正確的小班檔")
    sheets.sort(key=lambda x:x[0])
    if want_month is None:
        last=sheets[-1][0]; want_month=(last.year, last.month)
    yy,mm=want_month
    def touches_month(mon):
        for i in range(7):
            d=mon+timedelta(days=i)
            if d.year==yy and d.month==mm: return True
        return False
    month_sheets=[s for s in sheets if touches_month(s[0])]
    if not month_sheets:
        raise RuntimeError(f"找不到 {yy}-{mm:02d} 月份的分頁，請確認月份或檔案")
    month_status={}; name_of={}; by_name={}
    for mon,st,no,bn,sn in month_sheets:
        name_of.update(no)
        for n,c in bn.items(): by_name.setdefault(n,c)
        for card,days in st.items():
            for d,rec in days.items():
                if d.year==yy and d.month==mm:
                    month_status.setdefault(card,{})[d]=rec
    first_week_monday=month_sheets[0][0]
    first_week_status=month_sheets[0][1]
    return month_status, name_of, by_name, (yy,mm), first_week_monday, first_week_status

def match_members(roster, month_status, name_of, by_name):
    members=[]
    for m in roster:
        card,name=m["card"],m["name"]
        if card and card in month_status:
            members.append({"card":card,"name":name or name_of.get(card,name)})
        elif name and name in by_name and by_name[name] in month_status:
            nc=by_name[name]
            warn(f"⚠ 「{name}」卡號 {card or '(空)'} → 班表 {nc}(姓名補抓)")
            members.append({"card":nc,"name":name})
        else:
            warn(f"❌ 名單上的「{name}({card})」這個月小班找不到 → 離職/換人/整月休假?(本月略過)")
    return members

W135_WD={0,2,4}; W246_WD={1,3,5}

def classify(members, month_status, first_week_status, overrides=None):
    """回傳 info[card] = {type:'白'/'夜'/None, area, w135, w246, ...}
       overrides: {card_or_name: '白'/'夜'} — 玉繡在 Stage 1 手動確認的班型，優先採用。
    """
    if overrides is None: overrides = {}
    info={}
    for m in members:
        c=m["card"]; nm=m["name"]
        src = first_week_status if first_week_status.get(c) else month_status
        white=night=0; w135=w246=False
        for d,(cat,shift,zone) in src.get(c,{}).items():
            s=(shift or "").strip()
            if is_excluded_shift(s): continue
            if s.startswith("D"): white+=1
            elif s.startswith("E"): night+=1
            if d.weekday() in W135_WD: w135=True
            if d.weekday() in W246_WD: w246=True
        # 自動判斷（平手算白）
        if white==0 and night==0: typ=None
        elif white>=night: typ="白"
        else: typ="夜"
        # 玉繡覆蓋優先
        if c in overrides: typ=overrides[c]
        elif nm in overrides: typ=overrides[nm]
        area=_area_of(c, src)
        if area=="未知": area=_area_of_month(c, month_status)
        info[c]={"type":typ,"area":area,"w135":w135,"w246":w246,
                 "white":white,"night":night,"name":nm}
    return info

def _area_of(card, week_status):
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

def load_history(skip_month=None):
    cnt={}; rest={}
    for r in _read_rows(F_HISTORY):
        if r.get("月份")==skip_month: continue
        c=r.get("卡號"); st=r.get("狀態")
        if st=="稽核": cnt[c]=cnt.get(c,0)+1
        elif st=="休":  rest[c]=rest.get(c,0)+1
    return cnt, rest

AREAS=["一區","二區"]; GROUPS=["W135","W246"]; SHIFTS=[1,2,3]
BAND=["","第一班","第二班","第三班"]

def assign(members, info, hist_cnt, hist_rest=None):
    if hist_rest is None: hist_rest = {}
    cards=[m["card"] for m in members]
    idx={c:i for i,c in enumerate(cards)}
    # 公平排序：印次數 - 休息次數，負值越大（休越多）越優先稽核
    cost={c: hist_cnt.get(c,0) - hist_rest.get(c,0) for c in cards}
    n_white=sum(1 for c in cards if info[c]["type"]=="白")
    n_night=sum(1 for c in cards if info[c]["type"]=="夜")
    # 白班優先排第二班；只有白班人數 < 小夜人數時，才允許小夜補第二班
    allow_night_band2 = n_white < n_night
    slots=[(a,g,s) for a in AREAS for g in GROUPS for s in SHIFTS]
    def need_type(s):
        if s==3: return "夜"
        if s==2: return "白或夜" if allow_night_band2 else "白"
        return "白"
    def type_ok(c,s):
        t=info[c]["type"]; nt=need_type(s)
        if t is None: return False
        if nt=="夜": return t=="夜"
        if nt=="白": return t=="白"
        return True
    def cands(a,s,cross):
        res=[]
        for c in cards:
            if c in used: continue
            if not type_ok(c,s): continue
            if (info[c]["area"]==a) == cross: continue
            res.append(c)
        return res
    def pick(a,s,cross):
        pool=cands(a,s,cross)
        pool.sort(key=lambda c:(cost[c], idx[c]))
        return pool[0] if pool else None
    assigned={}; used=set(); crossed=set()
    order=sorted(slots, key=lambda sl: len(cands(sl[0],sl[2],False)))
    for sl in order:
        c=pick(sl[0],sl[2],False)
        if c is not None: assigned[sl]=c; used.add(c)
    for sl in slots:
        if sl in assigned: continue
        c=pick(sl[0],sl[2],True)
        if c is not None:
            assigned[sl]=c; used.add(c); crossed.add(sl)
            warn(f"※ {sl[0]} 第{sl[2]}班 本區排不出 → 跨區借「{info[c].get('name','')}」")
    for sl in slots:
        if sl not in assigned:
            warn(f"❌ {sl[0]} {sl[1]} 第{sl[2]}班 完全排不出人，請人工處理")
    return slots, assigned, used, crossed

def emit(members, info, slots, assigned, used, crossed, hist_cnt, hist_rest, tag,
         name_of=None, fw_mon=None):
    """共用輸出：螢幕表格 + Excel + 文字 + 稽核紀錄 CSV。
       Excel 模式與快速模式皆呼叫此函式，產出格式完全一致。"""
    name_of = name_of or {}
    nm=lambda c: ({m["card"]:m["name"] for m in members}).get(c) or name_of.get(c,c)
    def disp(a,g,s):
        c=assigned.get((a,g,s))
        if not c: return "❌排不出"
        return nm(c) + ("(跨區)" if (a,g,s) in crossed else "")
    rest_members=[m["card"] for m in members if m["card"] not in used]

    head = f"（第一週起 {fw_mon}）" if fw_mon else "（快速點選模式）"
    print(f"\n■ 月份：{tag}{head}")
    print(f"■ 規則：每月12位｜白班→一二班、小夜→三班｜分區看第一週小班\n")
    print("="*14+f"  {tag} 稽核藥水 AK 名單  "+"="*14)
    for a in AREAS:
        print(f"\n【{a}】")
        for g in GROUPS:
            gl = "週一三五" if g=="W135" else "週二四六"
            cells=[f"{BAND[s]}:{disp(a,g,s)}" for s in SHIFTS]
            print(f"  {gl}　"+"　".join(cells))
    print("\n本月休息:", "、".join(nm(c) for c in rest_members) or "無",
          f"（{len(rest_members)} 人）")

    print("\n【公平累計】(含本月)")
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

    rows_out=[]
    for a in AREAS:
        for g in GROUPS:
            gl="週一三五" if g=="W135" else "週二四六"
            for s in SHIFTS:
                rows_out.append({"區":a,"組":gl,"班次":BAND[s],"稽核者":disp(a,g,s)})
    out_x=os.path.join(OUT_DIR,f"稽核名單_{tag}.xlsx")
    try:
        pd.DataFrame(rows_out).to_excel(out_x, index=False); print(f"\n✔ Excel：{out_x}")
    except Exception as e: warn(f"⚠ 寫 Excel 失敗：{e}")

    lines=[f"📋 {tag} 稽核藥水 AK 名單",""]
    for a in AREAS:
        lines.append(f"《{a}》")
        for g in GROUPS:
            gl="週一三五" if g=="W135" else "週二四六"
            parts=[f"{BAND[s]}:{disp(a,g,s)}" for s in SHIFTS]
            lines.append(f"　{gl}　"+"　".join(parts))
    lines+=["","休息:"+("、".join(nm(c) for c in rest_members) or "無")]
    out_t=os.path.join(OUT_DIR,f"稽核名單_{tag}.txt")
    try:
        with open(out_t,"w",encoding="utf-8") as f: f.write("\n".join(lines))
        print(f"✔ 文字(可貼LINE)：{out_t}")
    except Exception as e: warn(f"⚠ 寫文字檔失敗：{e}")

    # 輸出稽核紀錄 CSV（供雲端歷史同步）
    out_h=os.path.join(OUT_DIR,f"稽核紀錄_輸出.csv")
    all_hist_rows=[]
    keep=[r for r in _read_rows(F_HISTORY) if r.get("月份")!=tag]
    for m in members:
        c=m["card"]; st="稽核" if c in used else "休"
        pos=""
        for k,v in assigned.items():
            if v==c: pos=f"{k[0]}/{'週一三五' if k[1]=='W135' else '週二四六'}/{BAND[k[2]]}"; break
        row={"月份":tag,"卡號":c,"姓名":m["name"],"狀態":st,"位置":pos}
        keep.append(row); all_hist_rows.append(row)
    try:
        with open(F_HISTORY,"w",newline="",encoding="utf-8-sig") as f:
            w=csv.DictWriter(f,fieldnames=["月份","卡號","姓名","狀態","位置"]); w.writeheader()
            for r in keep: w.writerow(r)
        # 另輸出「本月新增」到輸出目錄，app.py 讀取後送到雲端
        with open(out_h,"w",newline="",encoding="utf-8-sig") as f:
            w=csv.DictWriter(f,fieldnames=["月份","卡號","姓名","狀態","位置"]); w.writeheader()
            for r in all_hist_rows: w.writerow(r)
    except Exception as e:
        print(f"⚠ 寫稽核紀錄失敗：{e}")


def run():
    """Excel 模式：解析班表 → 猜白/夜＋區 → 排稽核。"""
    args=sys.argv[1:]
    files=[a for a in args if a.lower().endswith((".xls",".xlsx"))]
    month_args=[a for a in args if re.fullmatch(r"\d{4}\D?\d{1,2}", a)]
    missing=[f for f in files if not os.path.exists(f)]
    if not files or missing:
        if missing: print("❌ 找不到這些檔案：" + "、".join(missing))
        print("用法: python 稽核.py <週班1.xls> [週班2.xls ...] [月份 例 2026-06]")
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

    roster=load_roster()
    members=match_members(roster, month_status, name_of, by_name)

    # 載入班型覆蓋（玉繡 Stage 1 確認）
    overrides = load_shift_overrides()
    if overrides:
        print(f"ℹ 套用班型覆蓋：{len(overrides)} 人")

    info=classify(members, month_status, fw_status, overrides)
    tag=f"{yy}-{mm:02d}"
    hist_cnt,hist_rest=load_history(skip_month=tag)
    slots,assigned,used,crossed=assign(members, info, hist_cnt, hist_rest)
    emit(members, info, slots, assigned, used, crossed, hist_cnt, hist_rest, tag,
         name_of=name_of, fw_mon=fw_mon)


def run_quick(month_arg):
    """快速模式：讀 快速名冊.csv（卡號,姓名,班型,區）直接排稽核，不必解析班表。"""
    rows=_read_rows(F_QUICK)
    if not rows:
        print("❌ 找不到『快速名冊.csv』或內容是空的。"); return

    if month_arg:
        m=re.search(r"(\d{4})\D?(\d{1,2})", month_arg); yy,mm=int(m.group(1)),int(m.group(2))
    else:
        t=date.today(); yy,mm=t.year,t.month
    tag=f"{yy}-{mm:02d}"

    members=[]; info={}; seen=set()
    for r in rows:
        card=(r.get("卡號") or "").strip(); name=(r.get("姓名") or "").strip()
        typ_raw=(r.get("班型") or "").strip(); area=(r.get("區") or "").strip()
        if not card and not name: continue
        key=card or name
        if key in seen: continue
        seen.add(key)
        typ = "白" if "白" in typ_raw else ("夜" if ("夜" in typ_raw or "小夜" in typ_raw) else None)
        if area not in ("一區","二區"):
            warn(f"⚠ 「{name}」的區『{area}』不是一區/二區，本月可能排不進去")
        members.append({"card":key,"name":name})
        info[key]={"type":typ,"area":area,"name":name}

    print(f"ℹ 快速點選模式：{len(members)} 人")
    hist_cnt,hist_rest=load_history(skip_month=tag)
    slots,assigned,used,crossed=assign(members, info, hist_cnt, hist_rest)
    emit(members, info, slots, assigned, used, crossed, hist_cnt, hist_rest, tag)


def main():
    try:
        if "--quick" in sys.argv[1:]:
            month_args=[a for a in sys.argv[1:] if re.fullmatch(r"\d{4}\D?\d{1,2}", a)]
            run_quick(month_args[0] if month_args else None)
        else:
            run()
    except Exception as e:
        print("\n❌ 程式遇到沒預期到的狀況，但已幫你攔下來(不會弄壞檔案)。")
        print("   錯誤訊息：", e); traceback.print_exc()

if __name__=="__main__":
    main()
