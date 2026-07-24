#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dò concept có assertion NGHI SAI theo tiêu đề MỤC trong văn bản (context-aware).
Thu hẹp việc duyệt: chỉ soi concept nằm trong mục tiền sử/gia đình mà đang để ∅ (hoặc ngược lại).

    python3 src/scan_assertions.py            # in bảng nghi ngờ + gợi ý
    python3 src/scan_assertions.py --patch dev/assertion_patch_auto.json   # xuất patch gợi ý để duyệt
"""
import argparse, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sections

ROOT = Path(__file__).resolve().parent.parent

# tiêu đề mục -> nhãn ngữ cảnh
HIST = re.compile(r"tiền sử|bệnh lý mạn|bệnh mãn|bệnh nền|tiền căn|thuốc (trước|đã dùng trước)|"
                  r"mạn tính\b|trong nhiều năm|đã (phẫu thuật|điều trị)", re.IGNORECASE)
FAM = re.compile(r"tiền sử gia đình|gia đình:|của (mẹ|bố|cha|ông|bà|con|anh|chị|em)|"
                 r"mẹ (em|tôi|bị)|bố (em|tôi|bị)|ông (em|nội|ngoại)|bà (em|nội|ngoại)|di truyền hoặc gia đình", re.IGNORECASE)
PRESENT = re.compile(r"triệu chứng hiện tại|bệnh sử hiện tại|lý do (vào|nhập) viện|khám lâm sàng|"
                     r"hiện tại\b|tại bệnh viện|thăm khám", re.IGNORECASE)
NEG = re.compile(r"\bkhông\b|\bchưa\b|\bkhông có\b|phủ định|loại trừ|âm tính", re.IGNORECASE)


def section_at(raw, pos):
    """Nhãn mục gần nhất phía trên vị trí pos: 'hist' | 'fam' | 'present' | None."""
    head = raw[:pos]
    # tìm header gần nhất (theo dòng)
    best = (None, -1)
    for m in HIST.finditer(head):
        if m.start() > best[1]: best = ("hist", m.start())
    for m in FAM.finditer(head):
        if m.start() > best[1]: best = ("fam", m.start())
    for m in PRESENT.finditer(head):
        if m.start() > best[1]: best = ("present", m.start())
    return best[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--patch", help="xuất patch gợi ý (ghi index cần đổi) ra file")
    args = ap.parse_args()
    g = json.loads((ROOT / "dev/gold_curated.json").read_text(encoding="utf-8"))
    patch = {}
    n_flag = 0
    for fid in map(str, range(1, 101)):
        raw = sections.read_raw(ROOT / "input" / f"{fid}.txt")
        fpatch = {}
        for i, e in enumerate(g.get(fid, [])):
            cur = e["assertions"][0] if e["assertions"] else ""
            s = e["position"][0]
            sec = section_at(raw, s)
            # dòng chứa concept có từ phủ định gần?
            line_start = raw.rfind("\n", 0, s) + 1
            line = raw[line_start:raw.find("\n", s) if raw.find("\n", s) > 0 else len(raw)]
            suggest = None
            if sec == "fam":
                suggest = "isFamily"
            elif sec == "hist":
                suggest = "isHistorical"
            # chỉ nâng ∅ -> hist/fam (bỏ isNegated vì heuristic dòng quá nhiễu; present giữ nguyên)
            if suggest is not None and suggest != cur and cur == "":
                fpatch[str(i)] = suggest
                n_flag += 1
                print(f"F{fid:>3} #{i:<2} [{cur or '∅':13s}->{suggest or '∅':13s}] {e['type'][:3]} {e['text'][:34]!r}")
        if fpatch:
            patch[fid] = fpatch
    print(f"\n{n_flag} concept nghi sai assertion (theo mục). File có nghi ngờ: {len(patch)}")
    if args.patch:
        Path(args.patch).write_text(json.dumps(patch, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"-> {args.patch} (DUYỆT rồi mới apply)")


if __name__ == "__main__":
    main()
