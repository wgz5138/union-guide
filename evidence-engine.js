/* evidence-engine.js — 提示詞生成、JSON 解析、報告渲染（邏輯層，無直接 DOM 操作）
   依賴：ebn-common.js（val, esc）、evidence-data.js（CASP, allQs, qById, CASP_VERSION）
   全域變數 TYPE、MODE 由 evidence.html 的 <script> 管理 */

/* ── 題目附注 ── */
function qNote(q){
  if(q.costben) return " 【成本效益權衡題：請把帳『攤開算給使用者看』再下結論，rationale 要寫出這筆權衡：(1) 本篇顯示的好處（效果量）；(2) 本篇顯示的壞處／副作用；(3) 權衡時務必同時算『病人傷害』與『金錢成本』兩筆——介入本身多半是低價耗材（例：一瓶 2% 消毒劑），而它所預防的併發症（例：一次感染＝病人受的苦＋抗生素療程＋延長住院＋併發症/死亡風險），無論在傷害或金錢上都高出好幾個量級；這個落差就是判斷依據。據此給明確的「是/否/無法判斷」：感染預防／控制類介入，只要本篇顯示有效、又無明確的嚴重傷害，那麼無論從金錢或病人傷害任一角度看都是壓倒性的，請直接給斬釘截鐵的「是（值得）」，把那個輾壓式的落差講清楚，**不要無謂地模稜兩可、不要堆「但仍須考量」之類的保留語**。唯一會改變答案的是「本篇有沒有證明它有效、安全」這個前提：若本篇顯示介入有顯著傷害、或根本沒效、或完全缺乏可比資料，才據實給「否」或「無法判斷」。（即：該斟酌的是前提有沒有成立，不是值不值得；前提一旦成立，結論不必擺盪。）】";
  if(q.apply) return " 【適用性題：請依研究的族群／場域與一般臨床情境，直接給明確的「是 / 否 / 無法判斷」＋理由（不要留白），rationale 最後補一句提醒：請對照你自己的單位／病人再確認。】";
  if(q.results) return " 【結果題：rationale 必須把每一個結果指標／outcome 用中文一項一項列出（含森林圖裡的每個結果），每項都附數據——效果量（OR／RR／HR／MD 等）、95% CI、p 值，Meta 再加異質性 I²，並逐項明確標示是否統計顯著（p<0.05＝顯著、p≥0.05＝不顯著；效果量 95% CI 未跨過無效值＝顯著）；不要只寫一句籠統結論。answer 給一句最重要的整體結果（若本題是是非題，answer 給「是/否/無法判斷」、把逐項數據放 rationale）。】";
  return " 【是非題：answer 必須是明確的「是 / 否 / 無法判斷」三選一，並在 rationale 說清楚為什麼，不要模稜兩可、不要籠統。】";
}

function bothChecklists(){
  let s="";
  [["RCT","RCT（隨機對照試驗）→ CASP RCT 檢核表（11 題）"],["SR","系統回顧／Meta-analysis → CASP 系統性回顧檢核表（10 題）"]].forEach(([t,label])=>{
    s+=`\n=== 若你判斷是 ${label} ===\n`;
    CASP[t].sections.forEach(sec=>{ sec.qs.forEach(q=>{ s+=`  ${q.n}. ${q.zh}（提示：${q.hint}）${qNote(q)}\n`; }); });
  });
  return s;
}

/* ── 提示詞生成 ── */
function wordCount(){ return val("f-words")||"180~300"; }

function buildPromptUnknown(){
  const title=val("f-title"),author=val("f-author"),journal=val("f-journal"),group=val("f-group"),context=val("f-context"),text=val("f-text"),mins=val("f-mins");
  let meta="";
  if(title)meta+=`標題：${title}\n`; if(author)meta+=`作者：${author}\n`; if(journal)meta+=`年份/期刊：${journal}\n`;
  if(group)meta+=`組別：${group}\n`; if(context)meta+=`我的臨床情境：${context}\n`;
  const src = text ? `以下是文獻內容（摘要或全文）：\n"""\n${text}\n"""` :
    `※ 我會在對話框另外附上文獻 PDF，請依該檔評讀；看不到附檔就先提醒我，不要憑空編造。`;
  const speechReq = MODE==="leader"
    ? `,\n  "anticipatedQA":[{"q":"老師/長官可能問的問題","a":"建議怎麼答"}],\n  "speech":{"opening":"開場白逐字稿","perQuestion":{"1":"第1題上台要講的話"},"closing":"結尾逐字稿"}${mins?`（演講稿總長請抓約 ${mins}）`:""}`
    : "";
  const L=[];
  L.push("你是一位資深的實證護理（EBN）專家。請『嚴格依 CASP 官方檢核表每一題的判讀重點，以及標準實證醫學評讀方法學（Cochrane Handbook、GRADE、JAMA Users′ Guides）』來評讀文獻、完成實證報告——這些是國際公認的金標準，每題該看什麼、該判讀哪些統計量，一律以標準為準，不要自行增減或憑喜好取捨。");
  L.push("");
  L.push("⚠️ 我不確定這篇是哪一種研究，請你『先判斷』：它是 RCT（隨機對照試驗），還是 系統性回顧／Meta-analysis？");
  L.push("－ 若是 RCT → 用 CASP RCT 檢核表（11 題）。");
  L.push("－ 若是 系統回顧／Meta → 用 CASP 系統性回顧檢核表（10 題）。");
  L.push("把判斷結果填在 JSON 的 studyType（\"RCT\" 或 \"SR\"）與 typeNote（一句話說明為何），然後『只用你選的那張表』的全部題目逐題評讀。");
  L.push("");
  if(meta) L.push(meta);
  L.push(src);
  L.push("");
  L.push("兩張表的題目如下（只用你判斷的那一張、全部題目都要做）：");
  L.push(bothChecklists());
  L.push("== 輸出要求（重要）==");
  L.push("只輸出一個 JSON 物件，前後不要任何說明文字，不要用 ``` 包起來。結構：");
  L.push("{");
  L.push('  "studyType":"RCT 或 SR", "typeNote":"為何這樣判斷（一句）",');
  L.push('  "title":"文獻標題", "citation":"APA 引用", "group":"'+(group||"")+'",');
  L.push('  "clinicalQuestion":"一句臨床問題（PICO 句型）",');
  L.push('  "pico":{"P":"對象","I":"介入","C":"對照","O":"結果指標"},');
  L.push('  "summary":"150~250字中文重點摘要", "evidenceLevel":"證據等級（Melnyk 七級，例 Level II）", "qualityGrade":"高/中/低＋半句說明",');
  L.push('  "appraisal":[{"no":題號,"section":"A/B/C/D","question":"中文題目","answer":"每題都要依 CASP 給明確的『是/否/無法判斷』三選一（結果題改給一句最重要的整體結果）；不可留白叫我自己填；適用性題也要先給判斷、再於 rationale 提醒我對照單位；成本效益權衡題把好處/病人傷害/金錢成本攤開算後給是/否/無法判斷","rationale":"用白話、一句一句解釋（把讀者當統計／實證小白）：先點出本題答案，再帶出用到的統計數據（95% CI、I²、p 值或其他）並說白每個數字代表什麼意思，最後用『因為…所以我判斷 是／否／無法判斷』把推理講清楚，讓使用者看得懂、能跟著一起判斷；約 '+wordCount()+' 字，務必充實、可直接交報告，嚴禁只給答案或一兩句帶過","quote":"原文英文佐證句：要涵蓋本題判斷與 rationale 中每一個主要論點及數據的依據；請照抄原文（可多句、用 ; 分隔），找不到就留空，絕不可杜撰","plain":"投影片用的精簡重點，一句話、25字以內","verify":"若你對本題判斷或數據沒有十足把握、或原文未明確支持，填一句『待查原因』（例：原文只提到整體成本、未分項）；很有把握且原文明確支持就填空字串"}]'+speechReq+',');
  L.push('  "clinicalApplication":"臨床應用建議'+(context?"，請扣緊我的臨床情境":"")+'", "conclusion":"3~5句整體結論"');
  L.push("}");
  L.push("");
  L.push("規則：appraisal 要包含『你選的那張表』的全部題目（RCT 11 題或 SR 10 題），題號完整；每一題都要依 CASP 標準給明確答案、不可留白（適用性題先給判斷再提醒對照單位；成本效益權衡題把好處/病人傷害/金錢成本攤開算後給是/否/無法判斷）；每題 rationale 要寫 "+wordCount()+" 字（給 Word/PDF 書面報告，內容要充實具體）、plain 一句話精簡（25字內，給 PPT 投影片）；全部繁體中文（quote 可留英文）；只輸出 JSON。");
  L.push("引用規範（重要）：整份評讀的每一個論點與數據都必須有文獻原文依據——rationale 與 summary 只能寫文獻真正支持的內容，並把支持這些論點與數據的原文英文句放進該題的 quote 欄（可多句、用 ; 分隔）。凡文獻沒有提到的，一律不要寫，更不可推測、估算或杜撰；無法從原文找到依據時，寧可不寫該點。數字（百分比、p 值、OR／RR／HR、95% CI、樣本數、追蹤時間等）尤其要逐一對應原文。");
  L.push("自我標記（重要）：對任何你沒有十足把握、或原文未明確支持的判斷與數據，請在該題 verify 欄寫一句待查原因（寧可標記、也不要假裝確定）；完全確定且原文明確支持的才留空。");
  L.push("作答原則：是非題的 answer 一律明確給『是 / 否 / 無法判斷』，並在 rationale 說清楚為什麼，不要模稜兩可、不要籠統；標為『結果題』的，rationale 要把每個結果指標與數據（效果量、95% CI、p 值、I²）逐項用中文列出，不可只給一句總結。統計顯著性一律用金標準判定：p<0.05＝顯著、p≥0.05＝不顯著；效果量 95% CI 未跨過無效值（比值類為 1、差值類為 0）＝顯著，跨過＝不顯著。凡提到結果都要明確標示顯著或不顯著，不要模糊；但『不顯著(p≥0.05)』請說成『未達統計顯著』，不可說成『確定無效』（可能是樣本太小、檢力不足）。並提醒：統計顯著≠臨床重要，請一併看效果量大小、判斷對病人是否真的有意義。異質性 I² 也要判讀並說明：I²<25% 低、25–50% 中等、50–75% 高、>75% 很高，高異質性代表各研究差異大、合併結論要更保守。最重要：每一題給的『是/否/無法判斷』後面，rationale 都一定要有完整文字說明『為什麼這樣判』（約 "+wordCount()+" 字），這是使用者要交報告用的——只給答案而沒有充分解釋＝沒做完。rationale 請像教學一樣一句一句解釋給看不懂統計的人聽：把用到的每個數字（95% CI、I²、p 值等）是什麼意思講白，再交代『因為這些→所以我判是／否／無法判斷』，讓使用者能看懂並一起判斷。");
  L.push("統計判讀清單（論文有出現的都要逐一白話解讀、並說對病人的意義；沒出現的不要硬掰）：①效果量 RR／OR／HR／MD／SMD；②絕對 vs 相對：ARR（絕對風險下降）、RRR（相對風險下降）、NNT／NNH（要治療幾人才多救一人／多害一人，能算就算、能引就引）——只報 RRR 容易誤導，務必同時點出絕對值；③精確度：95% CI、p 值、標準差/誤差；④Meta 異質性整套：I²、Cochran Q 的 p、Tau²、預測區間、固定 vs 隨機效應；⑤偏差：發表偏差（漏斗圖／Egger）、ITT vs 一致性分析、追蹤流失率、檢力/樣本數是否足夠；⑥證據力：GRADE 確定性（高/中/低/極低）、次群組與敏感度分析；⑦臨床顯著性：是否達 MCID（最小重要差異）；⑧診斷型研究才有：敏感度/特異度/PPV/NPV/概似比/AUC。每一個都用『數字＋白話意義＋對病人代表什麼』來講。");
  L.push("『無法判斷』的使用界線（很重要）：只有當『文獻根本沒有報告足夠資訊』時才可用「無法判斷」；若文獻有正反兩面的證據，那是要你『權衡後給較站得住的是/否＋理由』，絕不可因為有兩面、拉鋸就退成無法判斷（那叫擺盪，不是評讀）。另：判斷『各組是否同等對待（組內共同介入是否平衡）』時，依據是偏差風險的『偏離預期介入／performance bias』面向——若該面向多為低到中度即偏向「是」；切勿把『各研究之間流程不一致（那是研究『間』的異質性，屬能否合併那題）』誤當成『同一試驗組內未同等對待』。");
  return L.join("\n");
}

function buildPrompt(){
  if(TYPE==="UNK") return buildPromptUnknown();
  const d=CASP[TYPE];
  const title=val("f-title"),author=val("f-author"),journal=val("f-journal"),group=val("f-group"),context=val("f-context"),text=val("f-text"),mins=val("f-mins");
  let nums = MODE==="member" ? assignedNums() : allQs(TYPE).map(q=>q.n);
  if(MODE==="member" && nums.length===0) nums = allQs(TYPE).map(q=>q.n);
  const qs = nums.map(n=>qById(TYPE,n));

  let qLines="";
  qs.forEach(q=>{ qLines += `  ${q.n}. ${q.zh}（提示：${q.hint}）${qNote(q)} / 原文：${q.en}\n`; });

  let meta="";
  if(title)meta+=`標題：${title}\n`; if(author)meta+=`作者：${author}\n`; if(journal)meta+=`年份/期刊：${journal}\n`;
  if(group)meta+=`組別：${group}\n`; if(context)meta+=`我的臨床情境：${context}\n`;

  const src = text ? `以下是文獻內容（摘要或全文）：\n"""\n${text}\n"""` :
    `※ 我會在對話框另外附上文獻 PDF，請依該檔評讀；看不到附檔就先提醒我，不要憑空編造。`;

  const typeLabel = TYPE==="RCT" ? "隨機對照試驗（RCT），用 CASP RCT 檢核表" : "系統性回顧 / Meta-analysis，用 CASP 系統性回顧檢核表";
  const scope = MODE==="member"
    ? `我只負責其中第 ${nums.join("、")} 題，請「只」評讀這幾題（不要做其他題）。`
    : `請評讀全部 ${nums.length} 題，作為這篇的「完整正確版」。`;

  const speechReq = MODE==="leader"
    ? `,\n  "anticipatedQA":[{"q":"老師/長官可能問的問題","a":"建議怎麼答"}],\n  "speech":{"opening":"開場白逐字稿","perQuestion":{"1":"第1題上台要講的話"},"closing":"結尾逐字稿"}${mins?`（演講稿總長請抓約 ${mins}）`:""}`
    : `,\n  "speech":{"perQuestion":{"${nums[0]}":"這題上台要講的話"}}`;

  const L=[];
  L.push("你是一位資深的實證護理（EBN）專家。請『嚴格依 CASP 官方檢核表每一題的判讀重點，以及標準實證醫學評讀方法學（Cochrane Handbook、GRADE、JAMA Users′ Guides）』來評讀文獻、完成實證報告——這些是國際公認的金標準，每題該看什麼、該判讀哪些統計量，一律以標準為準，不要自行增減或憑喜好取捨。");
  L.push("");
  L.push("文獻類型："+typeLabel+"。"+scope);
  L.push("（若你發現我選的檢核表類型與本篇實際研究設計不符，務必在 JSON 的 typeWarning 欄填一句明確警告＋建議改用哪張表重產；但本次仍依我指定的表評讀。）");
  L.push("");
  if(meta) L.push(meta);
  L.push(src);
  L.push("");
  L.push("請逐題評讀以下題目（題號、題目照抄）：");
  L.push(qLines);
  L.push("== 輸出要求（重要）==");
  L.push("只輸出一個 JSON 物件，前後不要任何說明文字，不要用 ``` 包起來。結構：");
  L.push("{");
  L.push('  "studyType":"'+TYPE+'", "typeWarning":"若本篇實際研究設計與我選的檢核表（'+(TYPE==="RCT"?"RCT 隨機對照試驗":"系統回顧/Meta")+'）不符，填一句警告＋建議改用哪張表重產（例：本篇其實是 Meta，建議改用系統回顧檢核表）；相符就填空字串",');
  L.push('  "title":"文獻標題", "citation":"APA 引用", "group":"'+(group||"")+'",');
  if(MODE==="leader"){
    L.push('  "clinicalQuestion":"一句臨床問題（PICO 句型）",');
    L.push('  "pico":{"P":"對象","I":"介入","C":"對照","O":"結果指標"},');
    L.push('  "summary":"150~250字中文重點摘要", "evidenceLevel":"證據等級（Melnyk 七級，例 Level II）", "qualityGrade":"高/中/低＋半句說明",');
  }
  L.push('  "appraisal":[{"no":題號,"section":"A/B/C/D","question":"中文題目","answer":"每題都要依 CASP 給明確的『是/否/無法判斷』三選一（結果題改給一句最重要的整體結果）；不可留白叫我自己填；適用性題也要先給判斷、再於 rationale 提醒我對照單位；成本效益權衡題把好處/病人傷害/金錢成本攤開算後給是/否/無法判斷","rationale":"用白話、一句一句解釋（把讀者當統計／實證小白）：先點出本題答案，再帶出用到的統計數據（95% CI、I²、p 值或其他）並說白每個數字代表什麼意思，最後用『因為…所以我判斷 是／否／無法判斷』把推理講清楚，讓使用者看得懂、能跟著一起判斷；約 '+wordCount()+' 字，務必充實、可直接交報告，嚴禁只給答案或一兩句帶過","quote":"原文英文佐證句：要涵蓋本題判斷與 rationale 中每一個主要論點及數據的依據；請照抄原文（可多句、用 ; 分隔），找不到就留空，絕不可杜撰","plain":"投影片用的精簡重點，一句話、25字以內","verify":"若你對本題判斷或數據沒有十足把握、或原文未明確支持，填一句『待查原因』（例：原文只提到整體成本、未分項）；很有把握且原文明確支持就填空字串"}]'+speechReq);
  if(MODE==="leader") L.push(',\n  "clinicalApplication":"臨床應用建議'+(context?"，請扣緊我的臨床情境":"")+'", "conclusion":"3~5句整體結論"');
  L.push("}");
  L.push("");
  L.push("規則：appraisal 只能包含第 "+nums.join("、")+" 題，題號完整對應；每一題都要依 CASP 標準給明確答案、不可留白（適用性題先給判斷再提醒對照單位；成本效益權衡題把好處/病人傷害/金錢成本攤開算後給是/否/無法判斷）；每題 rationale 要寫 "+wordCount()+" 字（給 Word/PDF 書面報告，內容要充實具體）、plain 一句話精簡（25字內，給 PPT 投影片）；全部繁體中文（quote 可留英文）；再次強調只輸出 JSON。");
  L.push("引用規範（重要）：整份評讀的每一個論點與數據都必須有文獻原文依據——rationale 與 summary 只能寫文獻真正支持的內容，並把支持這些論點與數據的原文英文句放進該題的 quote 欄（可多句、用 ; 分隔）。凡文獻沒有提到的，一律不要寫，更不可推測、估算或杜撰；無法從原文找到依據時，寧可不寫該點。數字（百分比、p 值、OR／RR／HR、95% CI、樣本數、追蹤時間等）尤其要逐一對應原文。");
  L.push("自我標記（重要）：對任何你沒有十足把握、或原文未明確支持的判斷與數據，請在該題 verify 欄寫一句待查原因（寧可標記、也不要假裝確定）；完全確定且原文明確支持的才留空。");
  L.push("作答原則：是非題的 answer 一律明確給『是 / 否 / 無法判斷』，並在 rationale 說清楚為什麼，不要模稜兩可、不要籠統；標為『結果題』的，rationale 要把每個結果指標與數據（效果量、95% CI、p 值、I²）逐項用中文列出，不可只給一句總結。統計顯著性一律用金標準判定：p<0.05＝顯著、p≥0.05＝不顯著；效果量 95% CI 未跨過無效值（比值類為 1、差值類為 0）＝顯著，跨過＝不顯著。凡提到結果都要明確標示顯著或不顯著，不要模糊；但『不顯著(p≥0.05)』請說成『未達統計顯著』，不可說成『確定無效』（可能是樣本太小、檢力不足）。並提醒：統計顯著≠臨床重要，請一併看效果量大小、判斷對病人是否真的有意義。異質性 I² 也要判讀並說明：I²<25% 低、25–50% 中等、50–75% 高、>75% 很高，高異質性代表各研究差異大、合併結論要更保守。最重要：每一題給的『是/否/無法判斷』後面，rationale 都一定要有完整文字說明『為什麼這樣判』（約 "+wordCount()+" 字），這是使用者要交報告用的——只給答案而沒有充分解釋＝沒做完。rationale 請像教學一樣一句一句解釋給看不懂統計的人聽：把用到的每個數字（95% CI、I²、p 值等）是什麼意思講白，再交代『因為這些→所以我判是／否／無法判斷』，讓使用者能看懂並一起判斷。");
  L.push("統計判讀清單（論文有出現的都要逐一白話解讀、並說對病人的意義；沒出現的不要硬掰）：①效果量 RR／OR／HR／MD／SMD；②絕對 vs 相對：ARR（絕對風險下降）、RRR（相對風險下降）、NNT／NNH（要治療幾人才多救一人／多害一人，能算就算、能引就引）——只報 RRR 容易誤導，務必同時點出絕對值；③精確度：95% CI、p 值、標準差/誤差；④Meta 異質性整套：I²、Cochran Q 的 p、Tau²、預測區間、固定 vs 隨機效應；⑤偏差：發表偏差（漏斗圖／Egger）、ITT vs 一致性分析、追蹤流失率、檢力/樣本數是否足夠；⑥證據力：GRADE 確定性（高/中/低/極低）、次群組與敏感度分析；⑦臨床顯著性：是否達 MCID（最小重要差異）；⑧診斷型研究才有：敏感度/特異度/PPV/NPV/概似比/AUC。每一個都用『數字＋白話意義＋對病人代表什麼』來講。");
  L.push("『無法判斷』的使用界線（很重要）：只有當『文獻根本沒有報告足夠資訊』時才可用「無法判斷」；若文獻有正反兩面的證據，那是要你『權衡後給較站得住的是/否＋理由』，絕不可因為有兩面、拉鋸就退成無法判斷（那叫擺盪，不是評讀）。另：判斷『各組是否同等對待（組內共同介入是否平衡）』時，依據是偏差風險的『偏離預期介入／performance bias』面向——若該面向多為低到中度即偏向「是」；切勿把『各研究之間流程不一致（那是研究『間』的異質性，屬能否合併那題）』誤當成『同一試驗組內未同等對待』。");
  return L.join("\n");
}

/* ── 解析與報告渲染 ── */
function extractAllJSON(raw){
  const out=[]; if(!raw) return out;
  let s=raw, depth=0, start=-1, inStr=false, esc=false;
  for(let i=0;i<s.length;i++){
    const c=s[i];
    if(inStr){ if(esc)esc=false; else if(c==="\\")esc=true; else if(c==='"')inStr=false; continue; }
    if(c==='"'){inStr=true;continue;}
    if(c==="{"){ if(depth===0)start=i; depth++; }
    else if(c==="}"){ depth--; if(depth===0&&start>=0){ const body=s.slice(start,i+1); const o=tryParse(body); if(o)out.push(o); start=-1; } }
  }
  return out;
}
function tryParse(b){ try{return JSON.parse(b);}catch(e){} try{return JSON.parse(b.replace(/,\s*([}\]])/g,"$1"));}catch(e){} return null; }
function ansClass(a){ const s=String(a||""); if(/判斷|judge/.test(s))return"judge"; if(/^是|yes/i.test(s))return"yes"; if(/^否|no/i.test(s))return"no"; return"unsure"; }
function norm(a){ const s=String(a||""); if(/^是|yes/i.test(s))return"yes"; if(/^否|no/i.test(s))return"no"; return"other"; }

function renderReport(d, masterMap){
  let h=`<div class="report" id="report-paper">`;
  if(d.group) h+=`<div class="rp-watermark mono">${esc(d.group)}　實證報告</div>`;
  h+=`<div class="rp-title">${esc(d.title||"實證文獻評讀報告")}</div>`;
  if(d.citation) h+=`<div class="rp-cite">${esc(d.citation)}</div>`;
  const tName=(d.studyType==="SR")?"系統性回顧 / Meta":"隨機對照試驗 RCT";
  h+=`<div class="rp-badges"><span class="badge type">${tName}</span>`;
  if(d.evidenceLevel)h+=`<span class="badge lvl">證據等級：${esc(d.evidenceLevel)}</span>`;
  if(d.qualityGrade)h+=`<span class="badge grade">品質：${esc(d.qualityGrade)}</span>`;
  h+=`</div>`;
  if(d.typeWarning)h+=`<div class="rp-typewarn">⚠️ 類型可能選錯：${esc(d.typeWarning)}　→ 請回上方改選正確的檢核表類型後「重產」一次。</div>`;
  if(d.typeNote)h+=`<div style="font-size:12px;color:var(--muted);margin:-8px 0 14px">🤖 AI 判斷類型：${esc(d.typeNote)}</div>`;
  h+=`<div class="rp-disclaimer">⚠️ AI 評讀可能有誤或遺漏。標有 <b>⚠ 待查</b> 的項目＝AI 自己沒把握、最該你核對的地方；其餘也請用下方<b>原文螢光筆</b>對照查證。最終以原文與你的專業判斷為準。</div>`;
  if(d.clinicalQuestion)h+=`<div class="rp-block"><div class="rp-h">臨床問題</div><div class="rp-text">${esc(d.clinicalQuestion)}</div></div>`;
  if(d.pico){ h+=`<div class="rp-block"><div class="rp-h">PICO</div><div class="pico">`;
    [["P","對象 P"],["I","介入 I"],["C","對照 C"],["O","結果 O"]].forEach(([k,l])=>{ h+=`<div class="pk">${l}</div><div class="pv">${esc(d.pico[k]||"—")}</div>`; });
    h+=`</div></div>`; }
  if(d.summary)h+=`<div class="rp-block"><div class="rp-h">重點摘要</div><div class="rp-text">${esc(d.summary)}</div></div>`;
  if(Array.isArray(d.appraisal)&&d.appraisal.length){
    h+=`<div class="rp-block"><div class="rp-h">CASP 逐題評讀</div>`;
    d.appraisal.slice().sort((a,b)=>(+a.no)-(+b.no)).forEach(it=>{
      let mism="",flag="";
      if(masterMap){ const m=masterMap[+it.no];
        if(m && norm(m.answer)!==norm(it.answer) && !/判斷/.test(String(it.answer))){
          mism=" mismatch"; flag=`<div class="appr-flag">⚠ 與正確版不一致：正確版為「${esc(m.answer)}」，此處為「${esc(it.answer)}」</div>`; }
      }
      h+=`<div class="appr${mism}"><div class="appr-head"><span class="appr-no">${esc(it.no)}</span><span class="appr-q">${esc(it.question)}</span><span class="ans ${ansClass(it.answer)}">${esc(it.answer)}</span>${it.verify?`<span class="vflag">⚠ 待查</span>`:""}</div>
        <div class="appr-body">${it.plain?`<div class="appr-plain">🗣 ${esc(it.plain)}</div>`:""}
        <div class="appr-rat"><b>理由：</b>${esc(it.rationale)}</div>
        ${it.quote?`<div class="appr-quote">原文：<mark class="hl">${esc(it.quote)}</mark></div>`:""}${it.verify?`<div class="appr-verify"><b>⚠ 待查</b>（AI 自己沒把握、最該你核對的地方，核對後請刪掉這行）：${esc(it.verify)}</div>`:""}${flag}</div></div>`;
    });
    h+=`</div>`;
  }
  if(Array.isArray(d.anticipatedQA)&&d.anticipatedQA.length){
    h+=`<div class="rp-block"><div class="rp-h">可能被問的問題＋建議答法</div>`;
    d.anticipatedQA.forEach(qa=>{ h+=`<div class="qa-item"><div class="qa-q">Q：${esc(qa.q)}</div><div class="qa-a">A：${esc(qa.a)}</div></div>`; });
    h+=`</div>`;
  }
  if(d.clinicalApplication)h+=`<div class="rp-block"><div class="rp-h">臨床應用建議</div><div class="rp-text">${esc(d.clinicalApplication)}</div></div>`;
  if(d.conclusion)h+=`<div class="rp-block"><div class="rp-h">整體結論</div><div class="conc">${esc(d.conclusion)}</div></div>`;
  h+=`</div>`;
  return h;
}
