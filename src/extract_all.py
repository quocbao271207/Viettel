#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NER MỞ RỘNG: THUỐC + CHẨN_ĐOÁN + TRIỆU_CHỨNG -> out/baseline_all.json + out/<name>.zip

    python3 src/extract_all.py --out C1               # curated ICD cho bệnh, [] cho triệu chứng
    python3 src/extract_all.py --out C1 --no-symptoms # bỏ triệu chứng (thận trọng hơn)

Thuốc: pipeline extract.py (đã validate leaderboard, RxNorm). Chẩn đoán/triệu chứng:
lexicon trong autolabel.py. Mã ICD chẩn đoán: curated (autolabel.DISEASES). Triệu chứng
để [] — sẽ gán mã R bằng SapBERT ở bước add_icd10.py (một chiều, gần như không rủi ro).

⚠️ CHƯA đo bằng gold. text_score = mean(1-WER) KHÔNG chặn dưới -> trích thừa/sai làm ÂM.
Đây là bản để DUYỆT + đo bằng dev/gold_resolved.json trước khi nộp.
"""
from __future__ import annotations
import argparse, json, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import gazetteer, sections, extract, autolabel  # noqa: E402
REPO = ROOT.parent
OUT = REPO / "out"

GOLD_W = 4171  # ngân sách từ gold (hiệu chỉnh từ probe4: 159 từ, WER 96.19%)


def extract_file_all(fid: int, gaz, drug_idx, valid_icd, with_symptoms: bool) -> list[dict]:
    raw = sections.read_raw(REPO / "input" / f"{fid}.txt")
    ents: list[dict] = []
    for ln in sections.parse(raw):
        t = ln.text
        occ = [False] * len(t)

        def claim(s, e):
            if any(occ[s:e]):
                return False
            for i in range(s, e):
                occ[i] = True
            return True

        def add(s, e, text, typ, cands, asserts):
            abs_s = ln.start + s
            assert raw[abs_s:abs_s + len(text)] == text, f"offset lệch f{fid}: {text!r}"
            ents.append({"text": text, "type": typ, "candidates": cands,
                         "assertions": asserts, "position": [abs_s, abs_s + len(text)]})

        # (1) THUỐC
        for s, e, ing in extract.find_drugs(t, drug_idx):
            e2 = extract.expand_span(t, s, e)
            span = t[s:e2].rstrip(" ,.")
            e2 = s + len(span)
            if claim(s, e2):
                add(s, e2, span, "THUỐC", extract.resolve_rxnorm(gaz, span, ing),
                    extract.assertions_for(ln, span))

        # (2) CHẨN_ĐOÁN — lexicon + curated ICD
        for s, e, surface, code in autolabel._spans_for(t, autolabel.DISEASES):
            if claim(s, e):
                add(s, e, surface, "CHẨN_ĐOÁN", [code] if code in valid_icd else [], [])

        # (3) TRIỆU_CHỨNG — lexicon (mã R gán sau bằng SapBERT)
        if with_symptoms:
            for s, e, surface, _ in autolabel._spans_for(t, autolabel.SYMPTOMS):
                if claim(s, e):
                    add(s, e, surface, "TRIỆU_CHỨNG", [], [])

    ents.sort(key=lambda x: x["position"][0])
    return ents


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="C1")
    ap.add_argument("--no-symptoms", action="store_true")
    args = ap.parse_args()

    gaz = gazetteer.load()
    drug_idx = extract.build_drug_index(gaz)
    valid_icd = set(gaz.get("icd_code2en", {}))

    preds = {}
    for fid in range(1, 101):
        preds[str(fid)] = extract_file_all(fid, gaz, drug_idx, valid_icd, not args.no_symptoms)

    OUT.mkdir(exist_ok=True)
    (OUT / "baseline_all.json").write_text(json.dumps(preds, ensure_ascii=False, indent=1), encoding="utf-8")

    sub = OUT / args.out / "output"
    if sub.parent.exists():
        shutil.rmtree(sub.parent)
    sub.mkdir(parents=True)
    for i in range(1, 101):
        (sub / f"{i}.json").write_text(json.dumps(preds[str(i)], ensure_ascii=False, indent=1), encoding="utf-8")
    shutil.make_archive(str(OUT / args.out), "zip", root_dir=sub.parent, base_dir="output")

    allc = [e for v in preds.values() for e in v]
    from collections import Counter
    types = Counter(e["type"] for e in allc)
    words = sum(len(e["text"].split()) for e in allc)
    with_c = sum(1 for e in allc if e["candidates"])
    files_ne = sum(1 for v in preds.values() if v)
    print(f"-> out/{args.out}.zip  |  {len(allc)} concept / {files_ne} file")
    print(f"   THUỐC {types['THUỐC']} | CHẨN_ĐOÁN {types['CHẨN_ĐOÁN']} | TRIỆU_CHỨNG {types['TRIỆU_CHỨNG']}")
    print(f"   có candidates: {with_c}  |  tổng {words} từ")
    print(f"   NGÂN SÁCH TỪ: {words}/{GOLD_W} gold ({words/GOLD_W:.0%}) — "
          f"{'⚠️ VƯỢT, nguy cơ WER âm' if words > GOLD_W else 'trong ngưỡng, WER lạc quan ≈ ' + f'{max(0,1-words/GOLD_W)*100:.0f}%'}")


if __name__ == "__main__":
    main()
