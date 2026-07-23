#!/usr/bin/env python3
"""Kiểm chứng: SapBERT-XLMR có khớp được text tiếng Việt -> mã ICD-10 KHÔNG cần dịch?

Bối cảnh: đã chứng minh (12/12 khớp nguyên văn) rằng span CHẨN_ĐOÁN trong đề CHÍNH LÀ
preferred term của ICD-10-CM dịch máy. Câu hỏi còn lại là bắc cầu VI->ICD bằng gì.

Đã thử và LOẠI:
  Helsinki-NLP/opus-mt-en-vi          -> dịch ra rác lặp vô hạn, fuzzy 42/100, 0/10
  VietAI/envit5-translation           -> vỡ với transformers 5.7 (tokenizer T5 cũ)
  paraphrase-multilingual-MiniLM-L12  -> top-1 1/10, top-5 3/10  (không đủ chuyên y sinh)

SapBERT được huấn luyện self-alignment trên UMLS đa ngữ — đúng công cụ cho việc này.
"""
from __future__ import annotations

import json
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
import torch  # noqa: E402
from transformers import AutoModel, AutoTokenizer  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MODEL = "cambridgeltl/SapBERT-UMLS-2020AB-all-lang-from-XLMR"

PROBE = [
    ("u cơ trơn tử cung, không đặc hiệu", "D259"),
    ("xuất huyết nội sọ không do chấn thương, không đặc hiệu", "I629"),
    ("bệnh thận mạn, không đặc hiệu", "N189"),
    ("suy tim, không đặc hiệu", "I509"),
    ("tăng huyết áp vô căn (nguyên phát)", "I10"),
    ("bệnh phổi tắc nghẽn mạn tính, không xác định", "J449"),
    ("nhiễm khuẩn đường tiết niệu, vị trí không xác định", "N390"),
    ("bệnh gút không đặc hiệu", "M109"),
    ("hạ huyết áp, không đặc hiệu", "I959"),
    ("cường cận giáp nguyên phát", "E210"),
    ("viêm túi mật cấp tính không biến chứng", "K800"),
    ("hội chứng turner, không đặc hiệu", "Q969"),
]


def main() -> None:
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(MODEL)
    mdl = AutoModel.from_pretrained(MODEL).eval().to(dev)
    print(f"model {MODEL.split('/')[-1]} | {sum(p.numel() for p in mdl.parameters())/1e6:.0f}M | {dev}", flush=True)

    def embed(texts: list[str], bs: int = 384) -> torch.Tensor:
        out = []
        t0 = time.time()
        for i in range(0, len(texts), bs):
            e = tok(texts[i : i + bs], return_tensors="pt", padding=True,
                    truncation=True, max_length=32).to(dev)
            with torch.inference_mode():
                o = mdl(**e)
            out.append(torch.nn.functional.normalize(o.last_hidden_state[:, 0, :], dim=-1).cpu())
            if i and i % (bs * 20) == 0:
                r = i / (time.time() - t0)
                print(f"  {i:6,}/{len(texts):,}  {r:.0f}/s  còn ~{(len(texts)-i)/r/60:.1f}p", flush=True)
        return torch.cat(out)

    rows = [(l[:8].strip(), l[8:].strip())
            for l in (ROOT / "data/icd10_raw/icd10cm_codes_2026.txt").read_text(encoding="utf-8").splitlines()
            if l.strip()]
    print(f"mã hoá {len(rows):,} mô tả ICD-10-CM ...", flush=True)
    t0 = time.time()
    E = embed([d for _, d in rows])
    print(f"  xong {time.time()-t0:.0f}s -> {tuple(E.shape)}", flush=True)

    Q = embed([p[0] for p in PROBE])
    S = Q @ E.T

    lines, t1, t5 = [], 0, 0
    for i, (vi, want) in enumerate(PROBE):
        v, idx = S[i].topk(5)
        codes = [rows[j][0] for j in idx]
        t1 += codes[0] == want
        t5 += want in codes
        hit = "✅" if codes[0] == want else ("🔶top5" if want in codes else "❌")
        lines.append(f" {hit:6s} {vi[:42]:44s} -> {codes[0]:7s} ({v[0]:.3f}) đúng={want}")
        if codes[0] != want:
            lines.append(f"        dự đoán: {rows[idx[0]][1][:60]}")
    print("\n=== SapBERT-XLMR: tiếng Việt -> ICD-10, KHÔNG dịch ===")
    print("\n".join(lines))
    print(f"\n>>> top-1: {t1}/{len(PROBE)}   top-5: {t5}/{len(PROBE)}")

    (ROOT / "out" / "sapbert_test.json").write_text(
        json.dumps({"top1": t1, "top5": t5, "n": len(PROBE)}, ensure_ascii=False))
    torch.save({"E": E, "codes": [c for c, _ in rows]}, ROOT / "data" / "icd10_sapbert.pt")
    print("-> data/icd10_sapbert.pt (index đã cache)")


if __name__ == "__main__":
    main()
