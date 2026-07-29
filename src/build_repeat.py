#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bản 14 = nền bản 13 + các LẦN NHẮC LẶP LẠI bị bỏ sót.

    python3 src/build_repeat.py --base out/submitted/13_gold_lab_fixes_35.2306.zip \
        --review dev/repeat_review.json --out out/candidates/14_repeat.zip

Spec §quy tắc 1: "Trích MỖI LẦN NHẮC riêng". Gold trích mọi lần nhắc, ta chỉ trích
một phần -> mỗi lần nhắc thiếu là một concept gold ta chắc chắn miss.

Cách làm: lấy tập text đã trích làm từ điển, quét lại 100 file tìm lần nhắc CHƯA
đánh dấu (ranh giới âm tiết, ưu tiên cụm dài nhất, không chồng lấn concept nền),
rồi LLM duyệt từng ca trong ngữ cảnh (keep/type/assertions) -> dev/repeat_review.json.

candidates cho concept mới: COPY từ concept nền cùng (text, type) — không đoán mã mới.
Nhờ vậy diff so bản 13 chỉ là THÊM concept, không đụng concept cũ.
"""
from __future__ import annotations
import argparse, collections, json, re, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWED_ASSERT = {"isNegated", "isHistorical", "isFamily"}
TYPES = {"THUỐC", "CHẨN_ĐOÁN", "TRIỆU_CHỨNG", "TÊN_XÉT_NGHIỆM", "KẾT_QUẢ_XÉT_NGHIỆM"}
CODED_TYPES = {"CHẨN_ĐOÁN", "THUỐC"}  # spec: chỉ 2 type này có candidates
WORD = re.compile(r"[0-9A-Za-zÀ-ỹ]")
NUMERIC = re.compile(r"^[\d.,]+$")


def load_base(path: Path) -> dict[str, list]:
    with zipfile.ZipFile(path) as z:
        return {Path(n).stem: json.loads(z.read(n).decode("utf-8"))
                for n in z.namelist() if n.endswith(".json")}


def scan_repeats(base: dict[str, list], raws: dict[str, str], stage: int = 1) -> list[dict]:
    """Tìm mọi lần nhắc lặp của text đã có trong từ điển mà chưa được đánh dấu.

    stage 1 (bản 14): khớp CHÍNH XÁC, chỉ cụm >=2 âm tiết hoặc >=5 ký tự.
    stage 2 (bản 15): thêm (a) cụm 1 âm tiết ngắn — trừ SỐ TRẦN vì khớp rác khắp nơi,
                      và (b) biến thể hoa/thường + khoảng trắng/gạch nối của cụm dài.
    """
    lex: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for concepts in base.values():
        for c in concepts:
            lex[c["text"]][c["type"]] += 1

    out = []
    for stem in sorted(raws, key=int):
        raw = raws[stem]
        taken = [tuple(c["position"]) for c in base.get(stem, [])]
        for text, tc in sorted(lex.items(), key=lambda kv: -len(kv[0])):
            short = len(text.split()) < 2 and len(text) < 5
            if stage == 1 and short:
                continue
            if stage == 2 and short and NUMERIC.match(text):
                continue
            if stage == 1:
                matches = re.finditer(re.escape(text), raw)
            else:
                parts = [p for p in re.split(r"[\s\-–]+", text.strip()) if p]
                pat = r"[\s\-–]+".join(re.escape(p) for p in parts)
                matches = re.compile(pat, re.IGNORECASE).finditer(raw)
            for m in matches:
                s, e = m.span()
                # stage 2 chỉ xét phần CÒN LẠI sau stage 1 (khớp chính xác đã lấy rồi)
                if stage == 2 and not short and raw[s:e] == text:
                    continue
                if s > 0 and WORD.match(raw[s - 1]):
                    continue
                if e < len(raw) and WORD.match(raw[e]):
                    continue
                if any(min(e, b) > max(s, a) for a, b in taken):
                    continue
                taken.append((s, e))
                out.append({"file": stem, "start": s, "end": e, "text": raw[s:e],
                            "type_goi_y": tc.most_common(1)[0][0]})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="out/submitted/14_repeat_36.4914.zip")
    ap.add_argument("--review", default="dev/repeat2_review.json")
    ap.add_argument("--out", default="out/candidates/15_repeat2.zip")
    ap.add_argument("--stage", type=int, default=2, choices=(1, 2))
    ap.add_argument("--dump-cands", help="chỉ quét và ghi ứng viên ra file, không build")
    args = ap.parse_args()

    base = load_base(ROOT / args.base)
    raws = {p.stem: p.read_text(encoding="utf-8") for p in (ROOT / "input").glob("*.txt")}
    cands = scan_repeats(base, raws, stage=args.stage)
    cands.sort(key=lambda c: (int(c["file"]), c["start"]))

    if args.dump_cands:
        Path(args.dump_cands).write_text(
            json.dumps(cands, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{len(cands)} ứng viên -> {args.dump_cands}")
        return

    review = {int(r["id"]): r for r in json.loads((ROOT / args.review).read_text("utf-8"))}
    code_of = {(c["text"], c["type"]): c.get("candidates", [])
               for concepts in base.values() for c in concepts if c.get("candidates")}

    added = collections.Counter()
    dropped = 0
    for i, cand in enumerate(cands):
        r = review.get(i)
        if r is None or not r.get("keep"):
            dropped += 1
            continue
        typ = r.get("type") or cand["type_goi_y"]
        if typ not in TYPES:
            dropped += 1
            continue
        raw = raws[cand["file"]]
        s, e = cand["start"], cand["end"]
        assert raw[s:e] == cand["text"], f"lệch vị trí {cand}"
        asserts = [a for a in r.get("assertions", []) if a in ALLOWED_ASSERT]
        cands_codes = code_of.get((cand["text"], typ), []) if typ in CODED_TYPES else []
        base[cand["file"]].append({"text": cand["text"], "type": typ,
                                   "candidates": list(cands_codes),
                                   "assertions": asserts, "position": [s, e]})
        added[typ] += 1

    # verify + đóng gói
    bad = 0
    for stem, concepts in base.items():
        concepts.sort(key=lambda c: c["position"][0])
        for c in concepts:
            s, e = c["position"]
            if raws[stem][s:e] != c["text"]:
                bad += 1
            if c["type"] not in CODED_TYPES and c["candidates"]:
                bad += 1
            if set(c["assertions"]) - ALLOWED_ASSERT:
                bad += 1
    outp = ROOT / args.out
    outp.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(outp, "w", zipfile.ZIP_DEFLATED) as z:
        for stem, concepts in sorted(base.items(), key=lambda kv: int(kv[0])):
            z.writestr(f"output/{stem}.json", json.dumps(concepts, ensure_ascii=False, indent=1))

    total = sum(len(v) for v in base.values())
    print(f"thêm {sum(added.values())} concept, bỏ {dropped} ứng viên -> tổng {total}")
    print(" ", dict(added))
    print(f"vi phạm verify: {bad}  ->  {outp}")


if __name__ == "__main__":
    main()
