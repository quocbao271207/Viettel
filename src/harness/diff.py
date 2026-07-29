#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""So hai bản nộp — để mỗi lượt nộp là một THÍ NGHIỆM ĐỌC ĐƯỢC.

    python3 -m src.harness.diff out/submitted/14_repeat_36.4914.zip out/candidates/18_x.zip

Chỉ có 5 lượt nộp/ngày. Nộp một bản mà không biết chính xác nó khác bản nền chỗ nào là
phí một quan sát: điểm đổi mà không quy được cho nguyên nhân nào. Công cụ này ép mọi bản
nộp phải khai rõ nó đổi cái gì, và cảnh báo nếu đổi nhiều thứ cùng lúc (không tách được nhân quả).
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.harness import spec, validate  # noqa: E402


def key(fid: str, e: dict) -> tuple:
    return (fid, e["position"][0], e["position"][1], e["type"])


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("dùng: python3 -m src.harness.diff <nền.zip> <mới.zip>")
    a = validate.load_zip(sys.argv[1])
    b = validate.load_zip(sys.argv[2])
    ia = {key(f, e): e for f, v in a.items() for e in v}
    ib = {key(f, e): e for f, v in b.items() for e in v}

    added, removed, common = set(ib) - set(ia), set(ia) - set(ib), set(ia) & set(ib)
    ch_assert = [k for k in common if ia[k]["assertions"] != ib[k]["assertions"]]
    ch_cand = [k for k in common if ia[k]["candidates"] != ib[k]["candidates"]]

    print(f"nền : {len(ia)} concept   ({Path(sys.argv[1]).name})")
    print(f"mới : {len(ib)} concept   ({Path(sys.argv[2]).name})")
    print(f"\n  + THÊM   {len(added)}")
    print(f"  − BỎ     {len(removed)}")
    print(f"  ~ đổi assertion  {len(ch_assert)}")
    print(f"  ~ đổi mã         {len(ch_cand)}")

    for label, ks, src in (("THÊM", added, ib), ("BỎ", removed, ia)):
        if not ks:
            continue
        ty = Counter(src[k]["type"] for k in ks)
        print(f"\n{label} theo type: " + " · ".join(f"{t} {n}" for t, n in ty.most_common()))
        surf = Counter((src[k]["text"].strip().lower(), src[k]["type"]) for k in ks)
        for (t, ty_), n in surf.most_common(15):
            print(f"   {n:4d}×  {ty_:20s} {t[:52]!r}")

    for k in ch_assert[:10]:
        print(f"   assertion  file {k[0]} {ia[k]['text']!r}: "
              f"{ia[k]['assertions']} -> {ib[k]['assertions']}")
    for k in ch_cand[:10]:
        print(f"   mã         file {k[0]} {ia[k]['text']!r}: "
              f"{ia[k]['candidates']} -> {ib[k]['candidates']}")

    # cảnh báo: đổi nhiều trục cùng lúc thì không quy được nhân quả
    axes = sum(bool(x) for x in (added, removed, ch_assert, ch_cand))
    coded_delta = sum(1 for k in added | removed
                      if (ib.get(k) or ia[k])["type"] in spec.CODED_TYPES)
    print(f"\n{coded_delta} concept thay đổi thuộc CHẨN_ĐOÁN/THUỐC (đụng trục J_cand)")
    if axes > 1:
        print(f"⚠️  bản này đổi {axes} trục cùng lúc — nếu điểm đổi sẽ KHÔNG tách được "
              f"nguyên nhân. Cân nhắc tách thành nhiều lượt nộp.")
    else:
        print("✅ chỉ đổi 1 trục — điểm nhận về quy được nhân quả sạch.")


if __name__ == "__main__":
    main()
