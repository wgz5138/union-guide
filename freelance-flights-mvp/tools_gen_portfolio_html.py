#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 A2310-作品集.md 轉成排版 HTML（給瀏覽器列印成 PDF，或用 libreoffice 轉 PDF）。
僅處理本文件用到的 Markdown 子集：標題/表格/清單(含編號)/粗體/行內碼/引言/分隔線/程式區塊。"""
import html
import re
import sys

SRC = sys.argv[1] if len(sys.argv) > 1 else "A2310-作品集.md"
OUT = sys.argv[2] if len(sys.argv) > 2 else "A2310-作品集.html"


def inline(s):
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return s


def convert(md):
    out, i, lines = [], 0, md.split("\n")
    in_code = False
    while i < len(lines):
        ln = lines[i]
        if ln.strip().startswith("```"):
            if not in_code:
                out.append("<pre>"); in_code = True
            else:
                out.append("</pre>"); in_code = False
            i += 1; continue
        if in_code:
            out.append(html.escape(ln)); i += 1; continue
        if not ln.strip():
            i += 1; continue
        if ln.startswith("# "):
            out.append(f"<h1>{inline(ln[2:])}</h1>"); i += 1; continue
        if ln.startswith("## "):
            out.append(f"<h2>{inline(ln[3:])}</h2>"); i += 1; continue
        if ln.strip() == "---":
            out.append("<hr>"); i += 1; continue
        # 表格
        if ln.lstrip().startswith("|"):
            tbl = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                tbl.append(lines[i]); i += 1
            cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in tbl]
            body = [r for r in cells if not all(set(c) <= set("-: ") for c in r)]
            out.append("<table>")
            for ri, row in enumerate(body):
                tag = "th" if ri == 0 else "td"
                out.append("<tr>" + "".join(
                    f"<{tag}>{inline(c)}</{tag}>" for c in row) + "</tr>")
            out.append("</table>"); continue
        # 引言（可多行）
        if ln.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].startswith(">"):
                buf.append(inline(lines[i].lstrip(">").strip())); i += 1
            out.append("<blockquote>" + "<br>".join(buf) + "</blockquote>"); continue
        # 清單（- 或 數字.）含縮排續行
        m = re.match(r"^(\d+)\.\s+(.*)", ln) or re.match(r"^[-*]\s+(.*)", ln)
        if m:
            ordered = bool(re.match(r"^\d+\.", ln))
            items = []
            while i < len(lines):
                mm = re.match(r"^(\d+)\.\s+(.*)", lines[i]) or re.match(
                    r"^[-*]\s+(.*)", lines[i])
                if mm:
                    items.append(mm.groups()[-1]); i += 1
                elif lines[i].startswith("   ") and items:   # 續行
                    items[-1] += " " + lines[i].strip(); i += 1
                elif not lines[i].strip():
                    i += 1; break
                else:
                    break
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(
                f"<li>{inline(x)}</li>" for x in items) + f"</{tag}>")
            continue
        out.append(f"<p>{inline(ln)}</p>"); i += 1
    return "\n".join(out)


CSS = """
@page { size: A4; margin: 18mm 16mm; }
* { font-family: 'WenQuanYi Zen Hei','Noto Sans CJK TC',sans-serif; }
body { color:#1a1a1a; line-height:1.6; font-size:11pt; }
h1 { font-size:19pt; border-bottom:3px solid #2356b6; padding-bottom:6px; }
h2 { font-size:14pt; color:#2356b6; margin-top:22px;
     border-left:5px solid #2356b6; padding-left:8px; }
table { border-collapse:collapse; width:100%; margin:10px 0; font-size:10pt; }
th,td { border:1px solid #bbb; padding:6px 8px; vertical-align:top; text-align:left; }
th { background:#2356b6; color:#fff; }
tr:nth-child(even) td { background:#f3f6fc; }
blockquote { background:#fff8e6; border-left:5px solid #e0a800;
             padding:8px 12px; margin:10px 0; color:#5a4a00; }
pre { background:#f5f5f5; border:1px solid #ddd; padding:10px;
      font-family:monospace; font-size:9.5pt; white-space:pre-wrap; }
code { background:#eef; padding:1px 4px; border-radius:3px; font-size:9.5pt; }
hr { border:none; border-top:1px solid #ddd; margin:16px 0; }
strong { color:#11244e; }
ul,ol { margin:6px 0 6px 22px; }
li { margin:3px 0; }
"""

with open(SRC, encoding="utf-8") as f:
    body = convert(f.read())
doc = (f"<!DOCTYPE html><html lang='zh-TW'><head><meta charset='utf-8'>"
       f"<style>{CSS}</style></head><body>{body}</body></html>")
with open(OUT, "w", encoding="utf-8") as f:
    f.write(doc)
print("wrote", OUT)
