#!/usr/bin/env python3
"""Gán mã ICD-10 cho concept phi-thuốc bằng SapBERT-XLMR (khớp chéo ngôn ngữ, KHÔNG dịch).

    python3 src/add_icd10.py --in out/baseline.json --out B3

Vì sao làm: đo từ leaderboard, B1 cho J_ass/J_cand = 3.01 trong khi P10 cho 0.33.
Hai chỉ số dùng chung mẫu số ⇒ ~168 concept phi-thuốc ĐÃ khớp gold, gold_assertion
rỗng nhưng gold_candidates KHÔNG rỗng. Tức CHẨN_ĐOÁN/TRIỆU_CHỨNG CÓ mã ICD-10
(chương R của ICD-10 có cả mã triệu chứng) và ta đang trả [] nên ăn 0.

Vì sao gần như không rủi ro: với concept mà gold CÓ mã, Jaccard(gold,[]) = 0 và
Jaccard(gold,[mã sai]) = 0 — đoán không bao giờ tệ hơn để rỗng. Chỉ mất ở concept mà
gold RỖNG (đo được ~17/978). Hoà vốn ở độ chính xác ~10%; SapBERT đo được ~50%.

Cần data/icd10_sapbert.pt (chạy src/test_sapbert.py trước để dựng index).
"""
from __future__ import annotations

import argparse
import json
import shutil
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
import torch  # noqa: E402
from transformers import AutoModel, AutoTokenizer  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MODEL = "cambridgeltl/SapBERT-UMLS-2020AB-all-lang-from-XLMR"
INDEX = ROOT / "data" / "icd10_sapbert.pt"


def dotted(code: str) -> str:
    """D259 -> D25.9 . File CMS không có dấu chấm; chưa rõ BTC muốn dạng nào."""
    return code if len(code) <= 3 else f"{code[:3]}.{code[3:]}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", default="out/baseline.json")
    ap.add_argument("--out", default="B3")
    ap.add_argument("--dots", action="store_true", help="xuất mã dạng D25.9 thay vì D259")
    ap.add_argument("--min-score", type=float, default=0.0,
                    help="chỉ gán khi cosine ≥ ngưỡng (0 = luôn gán, vì cược một chiều)")
    args = ap.parse_args()

    if not INDEX.exists():
        raise SystemExit(f"Thiếu {INDEX}. Chạy: python3 src/test_sapbert.py")
    idx = torch.load(INDEX, weights_only=False)
    E, codes = idx["E"], idx["codes"]
    print(f"index ICD-10: {len(codes):,} mã")

    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(MODEL)
    mdl = AutoModel.from_pretrained(MODEL).eval().to(dev)

    preds = json.loads((ROOT / args.src).read_text(encoding="utf-8"))
    targets = [(fid, i, e) for fid, v in preds.items() for i, e in enumerate(v)
               if e["type"] != "THUỐC"]
    texts = [e["text"] for _, _, e in targets]
    print(f"cần gán mã: {len(texts)} concept phi-thuốc")

    vecs = []
    for i in range(0, len(texts), 256):
        enc = tok(texts[i : i + 256], return_tensors="pt", padding=True,
                  truncation=True, max_length=32).to(dev)
        with torch.inference_mode():
            o = mdl(**enc)
        vecs.append(torch.nn.functional.normalize(o.last_hidden_state[:, 0, :], dim=-1).cpu())
    Q = torch.cat(vecs)

    scores, best = (Q @ E.T).max(dim=1)
    n_assigned = 0
    for (fid, i, _), s, b in zip(targets, scores.tolist(), best.tolist()):
        if s < args.min_score:
            continue
        code = codes[b]
        preds[fid][i]["candidates"] = [dotted(code) if args.dots else code]
        n_assigned += 1
    print(f"đã gán: {n_assigned} ({n_assigned/max(len(texts),1):.0%}) | "
          f"cosine trung bình {scores.mean():.3f}")

    out_dir = ROOT / "out" / args.out / "output"
    if out_dir.parent.exists():
        shutil.rmtree(out_dir.parent)
    out_dir.mkdir(parents=True)
    for i in range(1, 101):
        clean = [{k: v for k, v in e.items() if not k.startswith("_")} for e in preds[str(i)]]
        (out_dir / f"{i}.json").write_text(json.dumps(clean, ensure_ascii=False, indent=1), encoding="utf-8")
    shutil.make_archive(str(ROOT / "out" / args.out), "zip", root_dir=out_dir.parent, base_dir="output")
    print(f"-> out/{args.out}.zip")

    print("\nMẫu:")
    for (fid, i, _), s, b in list(zip(targets, scores.tolist(), best.tolist()))[:10]:
        e = preds[fid][i]
        print(f"  [{s:.3f}] {str(e['candidates']):9s} {e['text'][:44]}")


if __name__ == "__main__":
    main()
