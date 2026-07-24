#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bản nộp tốt nhất từ NER + SapBERT: thuốc(RxNorm) + bệnh(ICD full) + triệu chứng(ICD chương R).

    python3 src/finalize_submission.py --out C_final

Phát hiện: SapBERT toàn-index map triệu chứng văn nói SAI ("sốt cao"->tăng kali máu).
Sửa: TRIỆU_CHỨNG chỉ khớp trong mã chương R (R00-R99 = triệu chứng/dấu hiệu ICD-10);
CHẨN_ĐOÁN khớp toàn index. Gán mã là cược một chiều (add_icd10.py) nên an toàn với concept
gold-có-mã; rủi ro duy nhất là concept gold-rỗng — vẫn cần gold để chốt ngưỡng.
"""
from __future__ import annotations
import argparse, json, shutil, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
import torch
from transformers import AutoModel, AutoTokenizer

ROOT = Path(__file__).resolve().parent.parent
MODEL = "cambridgeltl/SapBERT-UMLS-2020AB-all-lang-from-XLMR"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", default="out/baseline_all.json")
    ap.add_argument("--out", default="C_final")
    ap.add_argument("--sym-min", type=float, default=0.55, help="ngưỡng cosine tối thiểu cho triệu chứng")
    args = ap.parse_args()

    idx = torch.load(ROOT / "data/icd10_sapbert.pt", weights_only=False)
    E, codes = idx["E"], idx["codes"]
    r_mask = torch.tensor([c.startswith("R") for c in codes])   # chương R = triệu chứng
    print(f"index {len(codes):,} mã | chương R (triệu chứng): {int(r_mask.sum())}")

    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(MODEL)
    mdl = AutoModel.from_pretrained(MODEL).eval().to(dev)

    preds = json.loads((ROOT / args.src).read_text(encoding="utf-8"))
    tgt = [(f, i, e) for f, v in preds.items() for i, e in enumerate(v) if e["type"] != "THUỐC"]

    def embed(texts):
        out = []
        for i in range(0, len(texts), 256):
            enc = tok(texts[i:i+256], return_tensors="pt", padding=True, truncation=True, max_length=32).to(dev)
            with torch.inference_mode():
                o = mdl(**enc)
            out.append(torch.nn.functional.normalize(o.last_hidden_state[:, 0, :], dim=-1).float().cpu())
        return torch.cat(out)

    Q = embed([e["text"] for _, _, e in tgt])
    n_dx = n_sym = 0
    r_idx = torch.where(r_mask)[0]
    for (f, i, e), q in zip(tgt, Q):
        if e["type"] == "CHẨN_ĐOÁN":
            b = int((q @ E.T).argmax())
            preds[f][i]["candidates"] = [codes[b]]
            n_dx += 1
        else:  # TRIỆU_CHỨNG -> chỉ chương R, kèm ngưỡng
            sims = q @ E[r_mask].T
            s, bi = sims.max(dim=0)
            if float(s) >= args.sym_min:
                preds[f][i]["candidates"] = [codes[r_idx[int(bi)]]]
                n_sym += 1
            else:
                preds[f][i]["candidates"] = []
    print(f"gán mã: CHẨN_ĐOÁN {n_dx} (ICD full) | TRIỆU_CHỨNG {n_sym} (chương R, cosine≥{args.sym_min})")

    out = ROOT / "out" / args.out / "output"
    shutil.rmtree(out.parent, ignore_errors=True)
    out.mkdir(parents=True)
    for i in range(1, 101):
        (out / f"{i}.json").write_text(json.dumps(preds[str(i)], ensure_ascii=False, indent=1), encoding="utf-8")
    shutil.make_archive(str(ROOT / "out" / args.out), "zip", root_dir=out.parent, base_dir="output")
    print(f"-> out/{args.out}.zip")

    print("\nMẫu triệu chứng (chương R):")
    shown = 0
    for f, i, e in tgt:
        c = preds[f][i]
        if e["type"] == "TRIỆU_CHỨNG" and c["candidates"] and shown < 8:
            print(f"   {c['text'][:20]:22s} -> {c['candidates'][0]}")
            shown += 1


if __name__ == "__main__":
    main()
