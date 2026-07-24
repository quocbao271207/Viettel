#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pre-pass sửa phiếu voter: concept có text LÀ tên thuốc nhưng bị gán CHẨN_ĐOÁN/TRIỆU_CHỨNG
-> ép type=THUỐC (sai type = 0đ cả 3 trục + concept ma, xem HANDOFF §6).

    python3 src/force_drugs.py --voter claude          # sửa dev/votes/claude.json (có .bak)
    python3 src/force_drugs.py --voter claude --dry    # chỉ liệt kê, không ghi

Bảo thủ: chỉ ép khi text BẮT ĐẦU bằng tên thuốc trong gazetteer và phần đuôi còn lại
chỉ là liều/đường dùng (mg, ml, po, bid...), tránh đụng "ngộ độc paracetamol", "dị ứng penicillin".
"""
from __future__ import annotations
import argparse, json, re, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import gazetteer, extract  # noqa: E402

# đuôi cho phép sau tên thuốc: liều + đơn vị + đường dùng + tần suất
TAIL_TOK = re.compile(
    r"^(?:[\d.,/:%\-()+xX]+|mg|mcg|ml|g|gram|units?|unt|iu|đơn|vị|po|iv|sc|im|pr|sl|neb|inh|"
    r"oral|uống|tiêm|bid|tid|qid|daily|qd|qhs|qam|q\d+h|prn|xl|er|sr|cr|la|xr|tab|cap|viên|gói|ống)$",
    re.IGNORECASE)
# nếu text chứa các từ này thì KHÔNG ép (là chẩn đoán/triệu chứng liên quan thuốc)
BLOCK = re.compile(r"ngộ độc|dị ứng|quá liều|phản ứng|tác dụng phụ|lệ thuộc|nghiện", re.IGNORECASE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voter", required=True)
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    gaz = gazetteer.load()
    idx = extract.build_drug_index(gaz)
    path = ROOT / f"dev/votes/{args.voter}.json"
    data = json.loads(path.read_text(encoding="utf-8"))

    flips = []
    for fid, concepts in data.items():
        for c in concepts:
            text = (c.get("text") or "").strip()
            typ = c.get("type")
            if not text or typ == "THUỐC" or BLOCK.search(text):
                continue
            hits = extract.find_drugs(text, idx)
            if not hits or hits[0][0] != 0:          # phải bắt đầu bằng tên thuốc
                continue
            tail = text[hits[0][1]:]
            if all(TAIL_TOK.match(t) for t in tail.split()):
                flips.append((fid, text, typ))
                c["type"] = "THUỐC"

    for fid, text, typ in flips:
        print(f"  file {fid}: {typ} -> THUỐC | {text!r}")
    print(f"{len(flips)} concept ép về THUỐC")
    if flips and not args.dry:
        shutil.copy(path, path.with_suffix(".json.bak"))
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"đã ghi {path} (backup .bak)")


if __name__ == "__main__":
    main()
