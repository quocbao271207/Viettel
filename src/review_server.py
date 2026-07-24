#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Công cụ CHỈNH GOLD bằng web (Python thuần, không cần cài gì).

    python3 src/review_server.py            # mở http://localhost:8000
    python3 src/review_server.py --port 8123 --gold dev/gold_curated.json

- Trái: văn bản gốc, tô màu các concept (THUỐC xanh / CHẨN_ĐOÁN cam / TRIỆU_CHỨNG tím).
- Phải: danh sách concept — sửa type/assertion/candidates, xoá, hoặc BÔI ĐEN text trái để THÊM.
- Dưới mỗi concept: phiếu các model (claude/gpt/gpt41/sol) vote gì -> quyết nhanh.
- Ô "Model đề xuất THÊM": concept voter có mà gold đang thiếu -> 1 nút thêm.
- Lưu -> ghi thẳng dev/gold_curated.json. Nút "Xuất ZIP nộp" -> out/candidates/curated.zip.
"""
from __future__ import annotations
import argparse, json, shutil, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import sections  # noqa: E402

DEFAULT_GOLD = ROOT / "dev/gold_curated.json"
GOLD_PATH = DEFAULT_GOLD
VOTER_FILES = ["claude", "gpt", "gpt41", "sol"]
ASSERTIONS = ["", "isNegated", "isHistorical", "isFamily", "isUncertain", "isHypothetical"]
TYPES = ["THUỐC", "CHẨN_ĐOÁN", "TRIỆU_CHỨNG"]


def locate(raw: str, concepts: list) -> list:
    """[(s,e,type,assertion,text)] cho phiếu voter (định vị bằng before+text)."""
    out, cursor = [], {}
    for c in concepts:
        text = (c.get("text") or "").strip()
        typ = (c.get("type") or "").strip()
        if not text or typ not in TYPES:
            continue
        before = (c.get("before") or "")[-15:]
        pos = raw.find(before + text)
        pos = pos + len(before) if pos >= 0 else raw.find(text, cursor.get(text, 0))
        if pos < 0:
            pos = raw.find(text)
        if pos < 0 or raw[pos:pos + len(text)] != text:
            continue
        cursor[text] = pos + len(text)
        out.append({"s": pos, "e": pos + len(text), "type": typ,
                    "assertion": c.get("assertion") or "", "text": text})
    return out


def load_json(p):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


class Handler(BaseHTTPRequestHandler):
    gold = {}
    voters = {}

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        b = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            self._send(200, PAGE, "text/html")
        elif u.path == "/api/data":
            fid = parse_qs(u.query).get("file", ["1"])[0]
            raw = sections.read_raw(ROOT / "input" / f"{fid}.txt")
            votes = {v: locate(raw, self.voters.get(v, {}).get(fid, [])) for v in self.voters}
            self._send(200, json.dumps({
                "file": fid, "raw": raw,
                "concepts": self.gold.get(fid, []),
                "votes": votes,
                "counts": {v: sum(len(d) for d in self.voters.get(v, {}).values()) for v in self.voters},
            }, ensure_ascii=False))
        elif u.path == "/api/progress":
            tot = sum(len(v) for v in self.gold.values())
            self._send(200, json.dumps({"total": tot, "voters": list(self.voters)}))
        else:
            self._send(404, "{}")

    def do_POST(self):
        u = urlparse(self.path)
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or "{}")
        if u.path == "/api/save":
            fid = str(body["file"])
            ents = sorted(body["concepts"], key=lambda x: x["position"][0])
            self.gold[fid] = ents
            GOLD_PATH.write_text(json.dumps(self.gold, ensure_ascii=False, indent=1), encoding="utf-8")
            self._send(200, json.dumps({"ok": True, "n": len(ents),
                                        "total": sum(len(v) for v in self.gold.values())}))
        elif u.path == "/api/export":
            out = ROOT / "out/candidates/curated/output"
            shutil.rmtree(out.parent, ignore_errors=True)
            out.mkdir(parents=True)
            for i in range(1, 101):
                (out / f"{i}.json").write_text(
                    json.dumps(self.gold.get(str(i), []), ensure_ascii=False, indent=1), encoding="utf-8")
            shutil.make_archive(str(ROOT / "out/candidates/curated"), "zip",
                                root_dir=out.parent, base_dir="output")
            self._send(200, json.dumps({"ok": True, "path": "out/candidates/curated.zip"}))
        else:
            self._send(404, "{}")


PAGE = r"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Chỉnh Gold — Viettel</title>
<style>
:root{--drug:#0a7d3c;--dx:#c2410c;--sym:#7c3aed;--bg:#f7f7f8;--line:#e3e3e6;}
*{box-sizing:border-box}html,body{height:100%}
body{margin:0;font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:#1a1a1a;display:flex;flex-direction:column;overflow:hidden}
header{flex-shrink:0;background:#fff;border-bottom:1px solid var(--line);padding:8px 14px;display:flex;gap:10px;align-items:center;flex-wrap:wrap;z-index:10}
header b{font-size:15px}button{font:inherit;padding:5px 11px;border:1px solid var(--line);background:#fff;border-radius:7px;cursor:pointer}
button:hover{background:#f0f0f2}button.pri{background:#2563eb;color:#fff;border-color:#2563eb}button.pri:hover{filter:brightness(.94)}
#nav input{width:52px;padding:4px;text-align:center;border:1px solid var(--line);border-radius:6px}
#status{color:#059669;font-weight:600}.muted{color:#888}
main{flex:1;min-height:0;display:grid;grid-template-columns:1fr 1fr;grid-template-rows:minmax(0,1fr);gap:12px;padding:12px;overflow:hidden}
@media(max-width:900px){main{grid-template-columns:1fr}}
.col{min-height:0;overflow-y:auto;display:flex;flex-direction:column;gap:12px;padding-right:4px}
.card{background:#fff;border:1px solid var(--line);border-radius:10px;padding:12px}
.col.left .card{flex:1;min-height:0;display:flex;flex-direction:column}
.card h3{position:sticky;top:-12px;background:#fff;padding-top:2px;margin:-2px 0 8px;z-index:2}
#raw{white-space:pre-wrap;word-break:break-word;font-size:14.5px;flex:1;overflow:auto;user-select:text}
::highlight(drug){background:#c9f2d8}::highlight(dx){background:#ffe0cc}::highlight(sym){background:#e9dcff}
::highlight(focus){background:#fde68a}
.ent{border:1px solid var(--line);border-radius:9px;padding:8px 10px;margin-bottom:9px}
.ent.drug{border-left:4px solid var(--drug)}.ent.dx{border-left:4px solid var(--dx)}.ent.sym{border-left:4px solid var(--sym)}
.ent .row1{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.ent .txt{font-weight:600;flex:1;min-width:120px;cursor:pointer}
.ent select,.ent input{font:inherit;padding:3px 5px;border:1px solid var(--line);border-radius:6px}
.ent input.cand{width:100%;margin-top:5px}
.votes{margin-top:5px;font-size:12px;color:#555;display:flex;gap:8px;flex-wrap:wrap}
.chip{background:#f0f0f2;border-radius:5px;padding:1px 6px}
.chip.agree{background:#dcfce7}.chip.diff{background:#fee2e2}
.del{color:#b91c1c;border-color:#f0caca}
#suggest .s{display:flex;gap:8px;align-items:center;padding:5px 0;border-bottom:1px dashed var(--line)}
h3{margin:2px 0 8px;font-size:13px;text-transform:uppercase;letter-spacing:.03em;color:#666}
#addbar{position:sticky;bottom:0;background:#fff;border-top:1px solid var(--line);padding:8px;margin:-12px;margin-top:10px;border-radius:0 0 10px 10px}
kbd{background:#eee;border-radius:4px;padding:0 4px;font-size:11px}
</style></head><body>
<header>
  <b>Chỉnh Gold</b>
  <span id="nav">File <button onclick="go(-1)">‹</button>
    <input id="fnum" type="number" min="1" max="100" value="1" onchange="load(this.value)"> /100
    <button onclick="go(1)">›</button></span>
  <button class="pri" onclick="save()">💾 Lưu file (⌘S)</button>
  <span id="status"></span>
  <span style="flex:1"></span>
  <span id="counts" class="muted"></span>
  <button onclick="exportZip()">📦 Xuất ZIP nộp</button>
</header>
<main>
  <div class="col left">
    <div class="card"><h3>Văn bản gốc — bôi đen để thêm concept</h3><div id="raw"></div></div>
  </div>
  <div class="col right">
    <div class="card"><h3>Concept trong gold (<span id="ecount">0</span>)</h3><div id="ents"></div>
      <div id="addbar" class="muted">Bôi đen 1 đoạn ở bên trái rồi bấm <button onclick="addFromSel()">＋ Thêm concept</button></div>
    </div>
    <div class="card"><h3>Model đề xuất THÊM (chưa có trong gold)</h3><div id="suggest"></div></div>
  </div>
</main>
<script>
let D=null, F=1, dirty=false;
const TYPES=["THUỐC","CHẨN_ĐOÁN","TRIỆU_CHỨNG"];
const ASS=["","isNegated","isHistorical","isFamily","isUncertain","isHypothetical"];
const cls=t=>t==="THUỐC"?"drug":t==="CHẨN_ĐOÁN"?"dx":"sym";
const esc=s=>s.replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

async function load(n){
  if(dirty && !confirm("Chưa lưu file này. Bỏ thay đổi?")) {document.getElementById("fnum").value=F; return;}
  F=Math.max(1,Math.min(100,+n)); document.getElementById("fnum").value=F;
  const r=await fetch("/api/data?file="+F); D=await r.json(); dirty=false;
  document.getElementById("counts").textContent=Object.entries(D.counts).map(([k,v])=>k+":"+v).join("  ");
  render();
}
function render(){
  document.getElementById("raw").textContent=D.raw;
  paintHighlights();
  renderEnts(); renderSuggest();
  document.getElementById("status").textContent="";
}
function paintHighlights(){
  if(!CSS.highlights) return;
  CSS.highlights.clear();
  const tn=document.getElementById("raw").firstChild; if(!tn) return;
  const buck={drug:[],dx:[],sym:[]};
  for(const e of D.concepts){const r=document.createRange();
    try{r.setStart(tn,e.position[0]);r.setEnd(tn,e.position[1]);buck[cls(e.type)].push(r);}catch(_){}}
  for(const k in buck) CSS.highlights.set(k,new Highlight(...buck[k]));
}
function voteChips(e){
  // phiếu voter cho span chồng lấn
  const out=[];
  for(const [v,arr] of Object.entries(D.votes)){
    const hit=arr.find(a=>Math.min(a.e,e.position[1])>Math.max(a.s,e.position[0]) && a.type===e.type);
    if(hit){const cur=(e.assertions[0]||"");const same=hit.assertion===cur;
      out.push(`<span class="chip ${same?'agree':'diff'}">${v}:${hit.assertion||"∅"}</span>`);}
    else out.push(`<span class="chip">${v}:—</span>`);
  }
  return out.join("");
}
function renderEnts(){
  const box=document.getElementById("ents"); box.innerHTML="";
  document.getElementById("ecount").textContent=D.concepts.length;
  D.concepts.forEach((e,i)=>{
    const d=document.createElement("div"); d.className="ent "+cls(e.type);
    d.innerHTML=`<div class="row1">
      <span class="txt" title="Bấm để tô vị trí">${esc(e.text)}</span>
      <select onchange="upd(${i},'type',this.value)">${TYPES.map(t=>`<option ${t===e.type?"selected":""}>${t}</option>`).join("")}</select>
      <select onchange="upd(${i},'assert',this.value)">${ASS.map(a=>`<option value="${a}" ${a===(e.assertions[0]||"")?"selected":""}>${a||"∅ hiện tại"}</option>`).join("")}</select>
      <button class="del" onclick="del(${i})">✕</button></div>
      <input class="cand" value="${esc((e.candidates||[]).join(", "))}" placeholder="mã candidates, cách nhau dấu phẩy"
        onchange="upd(${i},'cand',this.value)">
      <div class="votes">${voteChips(e)}</div>`;
    d.querySelector(".txt").onclick=()=>focusSpan(e.position);
    box.appendChild(d);
  });
}
function renderSuggest(){
  // concept voter có mà gold thiếu (span không chồng concept gold nào cùng type)
  const box=document.getElementById("suggest"); box.innerHTML="";
  const seen=new Set();
  const rows=[];
  for(const [v,arr] of Object.entries(D.votes)) for(const a of arr){
    const covered=D.concepts.some(e=>e.type===a.type && Math.min(e.position[1],a.e)>Math.max(e.position[0],a.s));
    const key=a.type+"|"+a.s+"|"+a.e;
    if(!covered && !seen.has(key)){seen.add(key);rows.push({...a,by:[v]});}
  }
  if(!rows.length){box.innerHTML='<span class="muted">— Không có (gold đã bao phủ mọi phiếu)</span>';return;}
  rows.sort((a,b)=>a.s-b.s);
  rows.forEach(a=>{const s=document.createElement("div");s.className="s";
    s.innerHTML=`<span class="chip ${cls(a.type)==='drug'?'agree':''}">${a.type}</span>
      <b>${esc(a.text)}</b> <span class="muted">${a.assertion||"∅"}</span>
      <span style="flex:1"></span><button onclick='addSug(${JSON.stringify(a)})'>＋ thêm vào gold</button>`;
    s.querySelector("b").style.cursor="pointer"; s.querySelector("b").onclick=()=>focusSpan([a.s,a.e]);
    box.appendChild(s);});
}
function focusSpan(pos){
  const tn=document.getElementById("raw").firstChild;const r=document.createRange();
  try{r.setStart(tn,pos[0]);r.setEnd(tn,pos[1]);
    if(CSS.highlights){CSS.highlights.set("focus",new Highlight(r));setTimeout(()=>CSS.highlights.delete("focus"),1600);}
    r.startContainer.parentElement.scrollIntoView({block:"center"});
    const sel=getSelection();sel.removeAllRanges();sel.addRange(r);
  }catch(_){}
}
function upd(i,k,val){const e=D.concepts[i];
  if(k==="type")e.type=val; else if(k==="assert")e.assertions=val?[val]:[];
  else if(k==="cand")e.candidates=val.split(",").map(s=>s.trim()).filter(Boolean);
  dirty=true; if(k==="type"){renderEnts();paintHighlights();}
}
function del(i){D.concepts.splice(i,1);dirty=true;renderEnts();paintHighlights();renderSuggest();}
function selOffsets(){
  const sel=getSelection(); if(!sel.rangeCount||sel.isCollapsed)return null;
  const r=sel.getRangeAt(0); const raw=document.getElementById("raw").firstChild;
  if(r.startContainer!==raw||r.endContainer!==raw)return null;
  const s=Math.min(r.startOffset,r.endOffset), e=Math.max(r.startOffset,r.endOffset);
  return {s,e,text:D.raw.slice(s,e)};
}
function addFromSel(){const o=selOffsets();
  if(!o){alert("Hãy bôi đen 1 đoạn văn bản ở khung bên trái trước.");return;}
  const t=prompt("Loại? 1=THUỐC 2=CHẨN_ĐOÁN 3=TRIỆU_CHỨNG","2");
  const type=({1:"THUỐC",2:"CHẨN_ĐOÁN",3:"TRIỆU_CHỨNG"})[t]; if(!type)return;
  D.concepts.push({text:o.text,type,candidates:[],assertions:[],position:[o.s,o.e]});
  dirty=true;D.concepts.sort((a,b)=>a.position[0]-b.position[0]);renderEnts();paintHighlights();renderSuggest();
}
function addSug(a){D.concepts.push({text:a.text,type:a.type,candidates:[],
  assertions:a.assertion?[a.assertion]:[],position:[a.s,a.e]});
  dirty=true;D.concepts.sort((x,y)=>x.position[0]-y.position[0]);renderEnts();paintHighlights();renderSuggest();}
async function save(){
  const r=await fetch("/api/save",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({file:F,concepts:D.concepts})});
  const j=await r.json();dirty=false;
  document.getElementById("status").textContent=`✓ đã lưu ${j.n} concept (tổng ${j.total})`;
}
async function exportZip(){if(dirty)await save();
  const r=await fetch("/api/export",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});
  const j=await r.json();document.getElementById("status").textContent="📦 "+j.path;}
function go(d){load(F+d);}
addEventListener("keydown",e=>{if((e.metaKey||e.ctrlKey)&&e.key==="s"){e.preventDefault();save();}});
load(1);
</script></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--gold", default=str(DEFAULT_GOLD))
    args = ap.parse_args()
    global GOLD_PATH
    GOLD_PATH = Path(args.gold) if Path(args.gold).is_absolute() else ROOT / args.gold

    Handler.gold = load_json(GOLD_PATH)
    Handler.voters = {v: load_json(ROOT / f"dev/votes/{v}.json") for v in VOTER_FILES
                      if (ROOT / f"dev/votes/{v}.json").exists()}
    tot = sum(len(v) for v in Handler.gold.values())
    print(f"Gold: {GOLD_PATH.name} ({tot} concept) | voter tham chiếu: {list(Handler.voters)}")
    print(f"\n  ➜  Mở trình duyệt:  http://localhost:{args.port}\n\n  (Ctrl+C để dừng)")
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
