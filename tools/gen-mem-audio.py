#!/usr/bin/env python3
"""重新產生 lawyer.html「記憶訓練」40 張卡的預錄語音（mem-audio/NN.mp3）。

用法：
    python3 tools/gen-mem-audio.py            # 只補產生缺少的檔案
    python3 tools/gen-mem-audio.py --force    # 全部重新產生（改過卡片文字後用這個）

原理：從 lawyer.html 抓出 MEMO_CARDS 陣列（用 Node 的 JS 引擎 eval，因為那是
JS 陣列字面值不是 JSON），組出跟前端 ttsSpeak 完全一樣的朗讀文字
（ref＋title＋plain＋記憶口訣＋tip），呼叫 translate.googleapis.com 的
translate_tts（非官方端點，只在「產生當下」用一次，使用者端完全不會呼叫它），
存成 mem-audio/00.mp3～39.mp3，索引對應 MEMO_CARDS 陣列順序。

⚠️ 新增或修改任何一張卡的文字後，必須用 --force（或先刪對應檔案）重新產生，
   否則使用者聽到的還是舊內容的語音。
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAWYER_HTML = os.path.join(REPO, "lawyer.html")
OUTDIR = os.path.join(REPO, "mem-audio")


def extract_memo_cards():
    """用 Node 執行一段小腳本把 lawyer.html 裡的 MEMO_CARDS 陣列 eval 出來，
    避免自己重寫一套脆弱的 JS 陣列字面值 parser。"""
    node_script = r"""
const fs = require("fs");
const src = fs.readFileSync(process.argv[1], "utf8");
const start = src.indexOf("const MEMO_CARDS=[");
const afterStart = src.indexOf("[", start);
let depth = 0, i = afterStart, inStr = false, strCh = null, esc = false;
for (; i < src.length; i++) {
  const ch = src[i];
  if (inStr) {
    if (esc) { esc = false; }
    else if (ch === "\\") { esc = true; }
    else if (ch === strCh) { inStr = false; }
    continue;
  }
  if (ch === "\"" || ch === "\x27" || ch === "`") { inStr = true; strCh = ch; continue; }
  if (ch === "[") depth++;
  if (ch === "]") { depth--; if (depth === 0) { i++; break; } }
}
const MEMO_CARDS = eval(src.slice(afterStart, i));
const manifest = MEMO_CARDS.map((c, idx) => ({
  idx, ref: c.ref,
  text: c.ref + "，" + c.title + "。" + c.plain + "。記憶口訣：" + c.tip
}));
process.stdout.write(JSON.stringify(manifest));
"""
    out = subprocess.run(["node", "-e", node_script, LAWYER_HTML], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def chunks(text, maxlen=180):
    segs = re.split(r"(?<=[。！？；\n])", text)
    out, buf = [], ""
    for s in segs:
        if not s.strip():
            continue
        if len(buf + s) > maxlen:
            if buf:
                out.append(buf.strip())
            buf = s
        else:
            buf += s
    if buf.strip():
        out.append(buf.strip())
    return out or [text[:maxlen]]


def fetch_tts(text, retries=3):
    url = ("https://translate.googleapis.com/translate_tts?ie=UTF-8&tl=zh-TW"
           "&client=tw-ob&ttsspeed=0.85&q=" + urllib.parse.quote(text))
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
                if resp.status == 200 and len(data) > 500:
                    return data
        except Exception as e:
            print(f"  重試 {attempt+1} 失敗: {e}", file=sys.stderr)
            time.sleep(1.5)
    raise RuntimeError("fetch_tts 失敗: " + text[:20])


def main():
    force = "--force" in sys.argv
    manifest = extract_memo_cards()
    print(f"共 {len(manifest)} 張卡")
    os.makedirs(OUTDIR, exist_ok=True)
    for item in manifest:
        idx = item["idx"]
        out_path = os.path.join(OUTDIR, f"{idx:02d}.mp3")
        if not force and os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
            print(f"[{idx:02d}] 已存在，跳過（用 --force 強制重產）")
            continue
        text = item["text"]
        segs = chunks(text)
        print(f"[{idx:02d}] {item['ref']}　{len(text)}字　切成 {len(segs)} 段")
        buf = bytearray()
        for seg in segs:
            buf.extend(fetch_tts(seg))
            time.sleep(0.3)
        with open(out_path, "wb") as f:
            f.write(buf)
        print(f"  -> {out_path} ({len(buf)} bytes)")


if __name__ == "__main__":
    main()
