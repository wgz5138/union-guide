/* ebn-common.js ── evidence / search / lawyer 共用工具庫
   載入順序：<script src="ebn-common.js"> 在各頁自己的 <script> 之前 */

/* ── Toast ── */
function toast(m){ const t=document.getElementById("toast"); t.textContent=m; t.classList.add("show"); clearTimeout(t._t); t._t=setTimeout(()=>t.classList.remove("show"),2400); }

/* ── Clipboard ── */
function fb(text,ok){ const ta=document.createElement("textarea"); ta.value=text; ta.style.position="fixed"; ta.style.opacity="0"; document.body.appendChild(ta); ta.select(); try{document.execCommand("copy");toast(ok);}catch(e){toast("複製失敗");} document.body.removeChild(ta); }
function copy(text,ok){ if(navigator.clipboard&&navigator.clipboard.writeText){ navigator.clipboard.writeText(text).then(()=>toast(ok)).catch(()=>fb(text,ok)); } else fb(text,ok); }
function copyEl(id,ok){ const el=document.getElementById(id); el.focus(); el.select(); try{el.setSelectionRange(0,el.value.length);}catch(e){}
  const failMsg="已幫你選取，長按選『拷貝』";
  if(navigator.clipboard&&navigator.clipboard.writeText){ navigator.clipboard.writeText(el.value).then(()=>toast(ok)).catch(()=>{ let d=false; try{d=document.execCommand("copy");}catch(e){} if(d)toast(ok); else{toast(failMsg);showAppBanner();} }); return; }
  let d=false; try{d=document.execCommand("copy");}catch(e){} if(d)toast(ok); else{toast(failMsg);showAppBanner();} }

/* ── App 內建瀏覽器提醒橫幅 ── */
function showAppBanner(){ if(sessionStorage.getItem("hideAppBanner"))return; const b=document.getElementById("appbanner"); if(b)b.classList.add("show"); }
(function(){ const x=document.getElementById("appbanner-x"); if(x)x.addEventListener("click",()=>{ document.getElementById("appbanner").classList.remove("show"); sessionStorage.setItem("hideAppBanner","1"); });
  if(/FBAN|FBAV|FBIOS|Instagram|Line\/|MicroMessenger|Twitter|TikTok|GSA\//i.test(navigator.userAgent||"")) showAppBanner(); })();

/* ── 工具函式 ── */
function val(id){ return (document.getElementById(id).value||"").trim(); }
function esc(t){ return String(t==null?"":t).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }

/* ── 密碼雜湊（pwOk 留各頁，cyrb53 共用） ── */
function cyrb53(s,seed=0){ s=s||""; let h1=0xdeadbeef^seed,h2=0x41c6ce57^seed; for(let i=0,c;i<s.length;i++){c=s.charCodeAt(i);h1=Math.imul(h1^c,2654435761);h2=Math.imul(h2^c,1597334677);} h1=Math.imul(h1^(h1>>>16),2246822507);h1^=Math.imul(h2^(h2>>>13),3266489909);h2=Math.imul(h2^(h2>>>16),2246822507);h2^=Math.imul(h1^(h1>>>13),3266489909); return ""+(4294967296*(2097151&h2)+(h1>>>0)); }

/* ── 版本工具（BUILD 由各頁定義為全域 const） ── */
function verLabel(){ const b=BUILD,n=+b.slice(8); return b.slice(0,4)+"-"+b.slice(4,6)+"-"+b.slice(6,8)+"（版號 "+(n<10?"0"+n:n)+"）"; }
function checkUpdate(manual,verFile){ const vs=document.getElementById("ver-status"); if(manual&&vs)vs.textContent=" · 檢查中…"; try{ fetch((verFile||"ver.txt")+"?t="+Date.now(),{cache:"no-store"}).then(r=>r.ok?r.text():null).then(v=>{ if(!v){ if(vs)vs.textContent=""; if(manual)toast("查不到更新資訊（可能沒網路）"); return; } v=v.trim(); if(v&&v!==BUILD){ const b=document.getElementById("updbanner"); if(b)b.classList.add("show"); if(vs)vs.textContent=" · 🔄 有新版（往上看橫幅）"; if(manual)toast("有新版！上方橫幅按「立即更新」"); } else{ if(vs)vs.textContent=" · ✓ 已是最新版"; if(manual)toast("✓ 你已經是最新版了"); } }).catch(()=>{ if(vs)vs.textContent=""; if(manual)toast("檢查失敗，請稍後再試"); }); }catch(e){ if(manual)toast("檢查失敗"); } }
function initVersionCheck(verFile){ checkUpdate(false,verFile); const cb=document.getElementById("checkupd-btn"); if(cb)cb.addEventListener("click",e=>{e.preventDefault();checkUpdate(true,verFile);}); const ub=document.getElementById("updbtn"); if(ub)ub.addEventListener("click",async()=>{ try{const ks=await caches.keys();await Promise.all(ks.map(k=>caches.delete(k)));}catch(e){} try{const rs=await navigator.serviceWorker.getRegistrations();await Promise.all(rs.map(r=>r.unregister()));}catch(e){} location.replace(location.pathname+"?v="+Date.now()); }); const ux=document.getElementById("updbanner-x"); if(ux)ux.addEventListener("click",()=>{ const b=document.getElementById("updbanner"); if(b)b.classList.remove("show"); }); }

/* ── 離線支援 ── */
if("serviceWorker" in navigator){ window.addEventListener("load",()=>{ navigator.serviceWorker.register("sw.js").catch(()=>{}); }); }

/* ── Claude API 工具 ── */
const PRICE={"claude-sonnet-4-6":{in:3,out:15},"claude-haiku-4-5":{in:1,out:5},"claude-opus-4-8":{in:5,out:25}};
const USD2NTD=31.5;
function ntd(usd){ const v=usd*USD2NTD; return "NT$"+(v<100?v.toFixed(2):Math.round(v)); }
function apiHeaders(key){ return {"x-api-key":key,"anthropic-version":"2023-06-01","anthropic-dangerous-direct-browser-access":"true","content-type":"application/json"}; }
function apiErr(err){ const s=err&&err.status,b=(err&&err.body)||""; if(s===401)return"金鑰不對(401)"; if(s===400&&/credit|balance|billing/i.test(b))return"金鑰沒額度，請先到 console.anthropic.com 儲值"; if(s===429)return"太頻繁(429)，稍候再試"; return"失敗"+(s?("("+s+")"):"")+"，可改用免費複製貼上"; }
