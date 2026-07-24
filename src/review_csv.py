#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Duyệt gold bằng BẢNG TÍNH (Excel/Google Sheets) thay vì sửa JSON tay.

    python3 src/review_csv.py export   # out/baseline_all.json -> dev/gold_review.csv
    # ... mở dev/gold_review.csv bằng Excel/Sheets, sửa, lưu lại (giữ UTF-8) ...
    python3 src/review_csv.py import   # dev/gold_review.csv -> dev/gold_resolved.json
    python3 src/evaluate.py out/baseline_all.json dev/gold_resolved.json

CÁCH DUYỆT trong bảng tính:
  • Cột `bo` = 'x'  -> XOÁ concept này (máy bắt nhầm, vd "phù" trong "phù hợp", tên người).
  • MỖI LẦN NHẮC = 1 dòng riêng (start/end khác nhau). Đề tính mỗi lần là 1 concept
    (vd "táo bón" xuất hiện 2 lần = 2 concept). => ĐỪNG xoá lần nhắc ĐÚNG chỉ vì nó lặp.
  • Sửa thẳng `text` / `type` / `candidates` / `assertions`.
  • THÊM concept bỏ sót: thêm 1 DÒNG MỚI, để trống `start/end`, điền `file` + `text`
    (nguyên văn) + `type`. Máy sẽ tự tìm vị trí (lần XUẤT HIỆN ĐẦU — nếu cần lần khác
    thì điền start/end tay).
  • `candidates`/`assertions`: nhiều giá trị ngăn bằng ';'  (vd "R05;R509").
"""
from __future__ import annotations
import csv, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import sections  # noqa: E402

SRC = ROOT / "out/baseline_all.json"          # có sẵn position
CSV_PATH = ROOT / "dev/gold_review.csv"
COLS = ["file", "start", "end", "context", "text", "type", "candidates", "assertions", "bo"]
TYPES = {"THUỐC", "CHẨN_ĐOÁN", "TRIỆU_CHỨNG"}


def window(raw: str, s: int, e: int, pad: int = 35) -> str:
    """Cửa sổ ngắn quanh concept để duyệt (không phải cả đoạn), đánh dấu 【...】."""
    a, b = max(0, s - pad), min(len(raw), e + pad)
    return (raw[a:s] + "【" + raw[s:e] + "】" + raw[e:b]).replace("\n", " ")


def export():
    data = json.loads(SRC.read_text(encoding="utf-8"))
    rows = []
    for fid in sorted(data, key=int):
        raw = sections.read_raw(ROOT / "input" / f"{fid}.txt")
        for c in data[fid]:
            s, e = c["position"]
            rows.append({
                "file": fid, "start": s, "end": e, "context": window(raw, s, e),
                "text": c["text"], "type": c["type"],
                "candidates": ";".join(c.get("candidates", [])),
                "assertions": ";".join(c.get("assertions", [])), "bo": "",
            })
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    print(f"-> {CSV_PATH}  ({len(rows)} dòng)  | cột `context` có 【concept】 để dễ soi")
    print("   Mở Excel/Sheets, duyệt, lưu UTF-8 rồi: python3 src/review_csv.py import")


def imp():
    gold, errs, n = {str(i): [] for i in range(1, 101)}, [], 0
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        for ln, r in enumerate(csv.DictReader(f), 2):
            if (r.get("bo") or "").strip().lower() == "x":
                continue
            text = (r.get("text") or "").strip()
            if not text:
                continue
            fid, typ = (r.get("file") or "").strip(), (r.get("type") or "").strip()
            if typ not in TYPES:
                errs.append(f"dòng {ln}: type sai {typ!r} — {text[:30]}")
                continue
            raw = sections.read_raw(ROOT / "input" / f"{fid}.txt")
            # dùng start/end nếu có & khớp; nếu không thì tìm nguyên văn
            try:
                s = int(float(r.get("start"))); e = int(float(r.get("end")))
            except (TypeError, ValueError):
                s = e = -1
            if not (0 <= s < e and raw[s:e] == text):
                s = raw.find(text)
                e = s + len(text)
            if s < 0:
                errs.append(f"dòng {ln}: file {fid} KHÔNG chứa nguyên văn {text[:34]!r}")
                continue
            cands = [x.strip() for x in (r.get("candidates") or "").split(";") if x.strip()]
            asrt = [x.strip() for x in (r.get("assertions") or "").split(";") if x.strip()]
            gold[fid].append({"text": text, "type": typ, "candidates": cands,
                              "assertions": asrt, "position": [s, e]})
            n += 1
    for fid in gold:
        gold[fid].sort(key=lambda e: e["position"][0])
    print(f"{n} concept hợp lệ | {len(errs)} lỗi")
    for e in errs[:15]:
        print("  ❌", e)
    if not errs:
        (ROOT / "dev/gold_resolved.json").write_text(json.dumps(gold, ensure_ascii=False, indent=1), encoding="utf-8")
        print("-> dev/gold_resolved.json\n   Đo: python3 src/evaluate.py out/baseline_all.json dev/gold_resolved.json")


if __name__ == "__main__":
    (imp if len(sys.argv) > 1 and sys.argv[1] == "import" else export)()
