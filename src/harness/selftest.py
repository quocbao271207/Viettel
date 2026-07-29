#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HARNESS TỰ CHỨNG MINH — vòng khứ hồi trên bản 14.

    python3 -m src.harness.selftest

Lấy bản 14 (36.4914, tốt nhất), quay ngược thành "phiếu voter" (text + 15 ký tự ngữ cảnh
hai bên, y hệt cái LLM phải trả), rồi cho chạy qua đúng đường ống định vị của harness.
Nếu không khôi phục được ~100% thì harness đang LÀM MẤT concept, và mọi data sinh mới
bằng nó cũng sẽ mất y như vậy — phải sửa harness trước khi tiêu một lượt gọi model nào.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.harness import validate                      # noqa: E402
from src.harness.build import resolve_voter           # noqa: E402

BASE = ROOT / "out/submitted/14_repeat_36.4914.zip"


def to_votes(base: dict) -> dict:
    """Bản nộp -> phiếu voter (giả lập LLM trả text + before/after 15 ký tự)."""
    votes = {}
    for fid, items in base.items():
        raw = validate.read_raw(int(fid))
        votes[fid] = [{"text": raw[e["position"][0]:e["position"][1]], "type": e["type"],
                       "assertions": e["assertions"],
                       "before": raw[max(0, e["position"][0] - 15):e["position"][0]],
                       "after": raw[e["position"][1]:e["position"][1] + 15]}
                      for e in items]
    return votes


def main() -> None:
    base = validate.load_zip(BASE)
    res, st = resolve_voter(to_votes(base), apply_ban=False)
    got = {(f, e["position"][0], e["position"][1], e["type"]) for f, v in res.items() for e in v}
    want = {(f, e["position"][0], e["position"][1], e["type"]) for f, v in base.items() for e in v}
    pct = len(got & want) / len(want) * 100
    print(f"VÒNG KHỨ HỒI: {len(got & want)}/{len(want)} = {pct:.2f}%")
    print(f"  sai vị trí: {len(got - want)}   |   mất: {len(want - got)}")
    for r, n in st.most_common():
        if r != "NHẬN":
            print(f"    {n:5d}  {r}")
    for fid, s, t, ty in sorted(want - got)[:10]:
        raw = validate.read_raw(int(fid))
        print(f"    MẤT file {fid} [{s}:{t}] {ty} {raw[s:t]!r}")

    if len(got - want) or pct < 99.5:
        raise SystemExit(f"\n❌ harness làm mất/lệch concept — SỬA TRƯỚC KHI SINH DATA.")
    print("\n✅ harness tái lập được bản 14 — an toàn để sinh data mới.")


if __name__ == "__main__":
    main()
