#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gán nhãn FIRST-PASS toàn bộ 100 file -> dev/gold_autofill.json để đội y DUYỆT & SỬA.

    python3 src/autolabel.py

KHÔNG phải gold thật. Là bản nháp máy:
  • THUỐC   : dùng pipeline extract.py (đã validate trên leaderboard — tin được).
  • CHẨN_ĐOÁN: lexicon bệnh + gợi ý mã ICD-10 (verify tồn tại trong gazetteer). BIẾN THỂ mã CẦN DUYỆT.
  • TRIỆU_CHỨNG: lexicon triệu chứng. Recall vừa phải — người duyệt CẮT bớt / THÊM.
Định dạng y hệt dev/to_annotate.json (line-based). Duyệt xong đổi tên -> dev/gold.json rồi:
    python3 src/make_devset.py --check      # -> dev/gold_resolved.json
    python3 src/evaluate.py out/<pred>.json dev/gold_resolved.json
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import gazetteer, sections, extract  # noqa: E402

REPO = ROOT.parent

# ---- Lexicon TRIỆU_CHỨNG (ưu tiên cụm dài match trước) ----
SYMPTOMS = [
    "khó thở", "đau đầu", "đau bụng", "đau ngực", "đau họng", "đau lưng", "đau khớp",
    "đau cơ", "đau nhức", "buồn nôn", "chóng mặt", "hoa mắt", "phát ban", "ban đỏ",
    "vàng da", "vàng mắt", "tiêu chảy", "táo bón", "chảy máu", "đánh trống ngực",
    "co giật", "khó nuốt", "mất ngủ", "sụt cân", "chán ăn", "đầy hơi", "ợ nóng",
    "ợ chua", "khó tiêu", "yếu cơ", "đổ mồ hôi", "ớn lạnh", "khát nước", "tiểu buốt",
    "tiểu rắt", "tiểu nhiều", "tiểu ra máu", "cứng khớp", "hồi hộp", "sổ mũi",
    "nghẹt mũi", "hắt hơi", "đau tai", "ù tai", "mờ mắt", "khó chịu", "mệt mỏi",
    "sốt cao", "sốt", "ho", "nôn", "ói", "ngứa", "sưng", "phù", "tê", "run", "ngất", "choáng",
]

# ---- Lexicon CHẨN_ĐOÁN -> mã ICD-10 gợi ý (sẽ verify tồn tại trong gazetteer) ----
DISEASES = {
    "kawasaki": "M303", "thiếu men g6pd": "D550", "viêm phổi": "J189", "suy tim": "I509",
    "tăng huyết áp": "I10", "đái tháo đường": "E119", "viêm dạ dày": "K2970",
    "loét tá tràng": "K269", "loét dạ dày": "K259", "viêm loét đại tràng": "K5190",
    "xơ gan": "K7460", "viêm túi mật": "K819", "viêm tụy": "K8590", "hen suyễn": "J45909",
    "hen phế quản": "J45909", "sỏi thận": "N200", "sỏi mật": "K8020", "thiếu máu": "D649",
    "bệnh dại": "A829", "viêm gan": "K739", "viêm khớp": "M1990", "trầm cảm": "F329",
    "viêm phế quản": "J40", "viêm xoang": "J329", "viêm họng": "J029", "viêm amidan": "J0390",
    "nhồi máu cơ tim": "I219", "đột quỵ": "I639", "suy thận": "N19", "suy thận mạn": "N189",
    "viêm nha chu": "K0530", "viêm da": "L309", "mụn trứng cá": "L709", "rụng tóc": "L659",
    "viêm mô tế bào": "L0390", "viêm tủy xương": "M869", "hẹp ống sống": "M4800",
    "hội chứng ruột kích thích": "K589", "bệnh mạch vành": "I2510", "xơ vữa động mạch": "I7090",
    "ung thư biểu mô tuyến đại tràng": "C189", "ung thư đại tràng": "C189",
    "bệnh bạch cầu dòng tủy mãn tính": "C9210", "tiền sản giật": "O1490",
}

WORDSEP = r"(?<![A-Za-zÀ-ỹ])"  # ranh giới trái: không phải chữ cái


def _spans_for(text: str, terms) -> list[tuple[int, int, str, str]]:
    """Trả (start,end,surface,code) — longest match, không chồng lấn. terms: list hoặc dict."""
    is_dict = isinstance(terms, dict)
    keys = sorted(terms, key=len, reverse=True)  # dài trước
    found: list[tuple[int, int, str, str]] = []
    occupied = [False] * len(text)
    for term in keys:
        for m in re.finditer(WORDSEP + re.escape(term) + r"(?![A-Za-zÀ-ỹ])", text, re.I):
            s, e = m.start(), m.end()
            if any(occupied[s:e]):
                continue
            for i in range(s, e):
                occupied[i] = True
            found.append((s, e, text[s:e], terms[term] if is_dict else ""))
    return found


def label_file(fid: int, gaz, drug_idx, valid_icd) -> list[dict]:
    raw = sections.read_raw(REPO / "input" / f"{fid}.txt")
    items = []
    for ln in sections.parse(raw):
        t = ln.text
        concepts = []
        occ = [False] * len(t)

        # (1) THUỐC — pipeline
        for s, e, ing in extract.find_drugs(t, drug_idx):
            e2 = extract.expand_span(t, s, e)
            span = t[s:e2].rstrip(" ,.")
            e2 = s + len(span)
            if any(occ[s:e2]):
                continue
            for i in range(s, e2):
                occ[i] = True
            concepts.append({"text": span, "type": "THUỐC",
                             "candidates": extract.resolve_rxnorm(gaz, span, ing),
                             "assertions": extract.assertions_for(ln, span)})

        # (2) CHẨN_ĐOÁN — lexicon + ICD gợi ý
        for s, e, surface, code in _spans_for(t, DISEASES):
            if any(occ[s:e]):
                continue
            for i in range(s, e):
                occ[i] = True
            cands = [code] if code in valid_icd else []
            concepts.append({"text": surface, "type": "CHẨN_ĐOÁN",
                             "candidates": cands, "assertions": []})

        # (3) TRIỆU_CHỨNG — lexicon
        for s, e, surface, _ in _spans_for(t, SYMPTOMS):
            if any(occ[s:e]):
                continue
            for i in range(s, e):
                occ[i] = True
            concepts.append({"text": surface, "type": "TRIỆU_CHỨNG",
                             "candidates": [], "assertions": []})

        concepts.sort(key=lambda c: t.find(c["text"]))
        items.append({"line": t, "section": ln.section, "sub": ln.sub,
                      "auto_skip": ln.skip, "concepts": concepts})
    return items


def main():
    gaz = gazetteer.load()
    drug_idx = extract.build_drug_index(gaz)
    valid_icd = set(gaz.get("icd_code2en", {}))
    # cảnh báo mã ICD gợi ý không tồn tại
    bad = [f"{k}={v}" for k, v in DISEASES.items() if v not in valid_icd]
    if bad:
        print(f"[!] {len(bad)} mã ICD gợi ý KHÔNG có trong gazetteer (bỏ, để [] cho người duyệt):")
        for b in bad[:20]:
            print("    ", b)

    out = {}
    n_drug = n_dx = n_sym = 0
    for fid in range(1, 101):
        items = label_file(fid, gaz, drug_idx, valid_icd)
        out[str(fid)] = items
        for it in items:
            for c in it["concepts"]:
                n_drug += c["type"] == "THUỐC"
                n_dx += c["type"] == "CHẨN_ĐOÁN"
                n_sym += c["type"] == "TRIỆU_CHỨNG"

    dev = REPO / "dev"
    dev.mkdir(exist_ok=True)
    (dev / "gold_autofill.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    tot = n_drug + n_dx + n_sym
    print(f"\n-> dev/gold_autofill.json : 100 file, {tot} concept nháp")
    print(f"   THUỐC {n_drug} (tin) | CHẨN_ĐOÁN {n_dx} (duyệt mã ICD) | TRIỆU_CHỨNG {n_sym} (cắt/thêm)")
    print(f"   Duyệt xong -> đổi tên dev/gold.json -> python3 src/make_devset.py --check")


if __name__ == "__main__":
    main()
