#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chuẩn bị re-rank mã ICD: mỗi cụm bệnh/triệu chứng DISTINCT -> top-K ứng viên SapBERT (code+mô tả).
-> dev/rerank_input.json  để LLM chọn mã đúng nhất.

    python3 src/rerank_prepare.py --topk 8
"""
from __future__ import annotations
import argparse, json, sys, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
import torch
from transformers import AutoModel, AutoTokenizer

ROOT = Path(__file__).resolve().parent.parent
MODEL = "cambridgeltl/SapBERT-UMLS-2020AB-all-lang-from-XLMR"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topk", type=int, default=8)
    ap.add_argument("--gold", default="dev/gold_resolved.json")
    ap.add_argument("--out", default="dev/rerank_input.json")
    ap.add_argument("--skip-done", action="store_true",
                    help="bỏ cụm đã có mã trong dev/rerank_out/*.json (chỉ cụm MỚI)")
    args = ap.parse_args()

    g = json.loads((ROOT / args.gold).read_text(encoding="utf-8"))
    # cụm DISTINCT (type,text) cho phi-thuốc
    uniq = {}
    for ents in g.values():
        for e in ents:
            if e["type"] != "THUỐC":
                uniq.setdefault((e["type"], e["text"]), 0)
            uniq[(e["type"], e["text"])] = uniq.get((e["type"], e["text"]), 0) + 1
    terms = [(t, txt, n) for (t, txt), n in uniq.items()]
    if args.skip_done:
        import glob as _glob
        done = {}
        for f in sorted(_glob.glob(str(ROOT / "dev/rerank_out/*.json"))):
            done.update(json.loads(Path(f).read_text(encoding="utf-8")))
        terms = [t for t in terms if t[1] not in done]
        print(f"bỏ {len(done)} cụm đã re-rank; còn lại cụm mới:")
    print(f"{len(terms)} cụm distinct (bệnh+triệu chứng), tổng {sum(n for *_ , n in terms)} lần nhắc")

    idx = torch.load(ROOT / "data/icd10_sapbert.pt", weights_only=False)
    E, codes = idx["E"], idx["codes"]
    c2e = json.loads((ROOT / "data/gaz.json").read_text(encoding="utf-8")).get("icd_code2en", {})
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(MODEL)
    mdl = AutoModel.from_pretrained(MODEL).eval().to(dev)

    texts = [txt for _, txt, _ in terms]
    vecs = []
    for i in range(0, len(texts), 256):
        enc = tok(texts[i:i+256], return_tensors="pt", padding=True, truncation=True, max_length=32).to(dev)
        with torch.inference_mode():
            o = mdl(**enc)
        vecs.append(torch.nn.functional.normalize(o.last_hidden_state[:, 0, :], dim=-1).float().cpu())
    Q = torch.cat(vecs)
    S = Q @ E.T
    topv, topi = S.topk(args.topk, dim=1)

    out = []
    for k, (typ, txt, n) in enumerate(terms):
        opts = [[codes[j], c2e.get(codes[j], "")] for j in topi[k].tolist()]
        out.append({"text": txt, "type": typ, "n_mentions": n, "options": opts})
    out.sort(key=lambda x: -x["n_mentions"])
    (ROOT / args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> {args.out} ({len(out)} cụm, mỗi cụm {args.topk} ứng viên)")


if __name__ == "__main__":
    main()
