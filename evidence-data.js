/* evidence-data.js — CASP 題庫與輔助查詢（純資料層，零 DOM）
   載入順序：ebn-common.js → evidence-data.js → evidence-engine.js → <script> */

const CASP_VERSION = "CASP 2024";

const CASP = {
  RCT:{ name:"CASP RCT 檢核表（11 題）", sections:[
    {sec:"A · 基本研究設計是否站得住腳？", qs:[
      {n:1,zh:"研究是否針對一個清楚聚焦的研究問題？",hint:"對象、介入、對照、結果指標",en:"Clearly focused research question?",plain:"它有沒有講清楚：研究誰、給什麼、跟什麼比、看什麼結果。"},
      {n:2,zh:"受試者分配到各組是否採隨機分派？",hint:"如何隨機、分配是否隱藏",en:"Was assignment randomised?",plain:"是不是用抽籤/電腦亂數分組，而不是研究者挑的。"},
      {n:3,zh:"進入研究的受試者最後是否都有交代清楚？",hint:"失去追蹤、ITT、是否提早中止",en:"Were all participants accounted for?",plain:"中途退出的人有沒有說明，有沒有用 ITT 分析。"}]},
    {sec:"B · 研究方法是否嚴謹？", qs:[
      {n:4,zh:"受試者、人員與結果評估者是否盲性？",hint:"單盲、雙盲、評估者盲性",en:"Blinding?",plain:"病人/研究者/評估的人知不知道誰在哪一組。"},
      {n:5,zh:"兩組開始時的條件是否相近？",hint:"基線特性是否平衡",en:"Groups similar at start?",plain:"兩組一開始的年齡、病情是不是差不多。"},
      {n:6,zh:"除了實驗介入，各組是否接受相同照護？",hint:"是否被同等對待",en:"Treated equally apart from intervention?",plain:"除了那個新做法，其他照顧有沒有一樣。"}]},
    {sec:"C · 結果是什麼？", qs:[
      {n:7,zh:"介入的效果是否完整呈現？",hint:"檢力、主次要結果、數據、p值/CI",en:"Effects reported comprehensively?",plain:"該報的數據有沒有都報出來。",results:true},
      {n:8,zh:"是否報告了效果估計值的精確度？",hint:"信賴區間 CI",en:"Precision reported (CI)?",plain:"有沒有給信賴區間（CI）。",results:true},
      {n:9,zh:"好處是否大於壞處與成本？",hint:"效益 vs 副作用、成本",en:"Benefits outweigh harms/costs?",plain:"值不值得——AI 把好處、病人傷害、金錢成本攤開算給你看（感染預防通常划算）。",costben:true}]},
    {sec:"D · 結果對你的臨床有幫助嗎？", qs:[
      {n:10,zh:"結果能否套用到你的臨床對象/情境？",hint:"你的病人是否夠相似",en:"Applicable locally?",plain:"你的病人跟研究對象像不像——AI 會先給判斷，你再對照單位確認。",apply:true},
      {n:11,zh:"與現有做法相比，是否帶來更大價值？",hint:"和常規比較",en:"Greater value than existing?",plain:"比現在的做法好不好——AI 依實證給判斷，你再確認。",apply:true}]}
  ]},
  SR:{ name:"CASP 系統性回顧 / Meta 檢核表（10 題）", sections:[
    {sec:"A · 回顧的結果是否可信？", qs:[
      {n:1,zh:"是否針對一個清楚聚焦的問題？",hint:"PICO",en:"Clearly focused question?",plain:"有沒有講清楚要回答什麼問題。"},
      {n:2,zh:"作者是否搜尋了正確類型的研究？",hint:"研究設計是否符合問題",en:"Right type of papers?",plain:"納入的研究種類對不對題。"},
      {n:3,zh:"重要且相關的研究是否都納入了？",hint:"資料庫、參考文獻、未發表、灰色文獻",en:"All relevant studies included?",plain:"有沒有漏掉重要研究、找得夠不夠廣。"},
      {n:4,zh:"是否充分評估了納入研究的品質？",hint:"偏差風險評讀",en:"Quality of included studies assessed?",plain:"有沒有檢查每篇研究做得好不好。"},
      {n:5,zh:"合併各研究結果（meta）是否合理？",hint:"異質性、結果是否相近",en:"Reasonable to combine?",plain:"把不同研究加在一起算，合不合理。"}]},
    {sec:"B · 結果是什麼？", qs:[
      {n:6,zh:"這篇回顧的整體結果是什麼？",hint:"數值、OR/RR/效果量",en:"Overall results?",plain:"合起來的結論數字是多少。",results:true},
      {n:7,zh:"結果有多精確？",hint:"信賴區間 CI",en:"How precise (CI)?",plain:"有沒有給信賴區間（CI）。",results:true}]},
    {sec:"C · 結果對你的臨床有幫助嗎？", qs:[
      {n:8,zh:"結果能否套用到你的臨床對象？",hint:"病人是否夠相似",en:"Applicable locally?",plain:"你的病人跟研究對象像不像——AI 會先給判斷，你再對照單位確認。",apply:true},
      {n:9,zh:"是否考量了所有重要的結果指標？",hint:"有沒有漏掉重要好處/壞處",en:"All important outcomes considered?",plain:"重要的好處壞處有沒有都看——看論文就能答。"},
      {n:10,zh:"好處是否值得壞處與成本？",hint:"效益 vs 風險、成本",en:"Benefits worth harms/costs?",plain:"值不值得——AI 把好處、病人傷害、金錢成本攤開算給你看（感染預防通常划算）。",costben:true}]}
  ]}
};

const allQs = t => CASP[t].sections.flatMap(s=>s.qs);
const qById = (t,n) => allQs(t).find(q=>q.n===n);
