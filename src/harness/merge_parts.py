#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gộp phiếu theo mảnh: dev/votes_v2/parts/<voter>_<lo>-<hi>.json -> dev/votes_v2/<voter>.json

    python3 -m src.harness.merge_parts

Báo rõ voter nào thiếu file nào — thiếu là phải chạy lại đúng mảnh đó, KHÔNG được lặng lẽ
bỏ qua (voter thiếu file làm lệch số phiếu, đúng chỗ mà cơ chế đồng thuận dựa vào).
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
PARTS = ROOT / "dev/votes_v2/parts"
OUT = ROOT / "dev/votes_v2"


def main() -> None:
    by_voter: dict[str, dict] = defaultdict(dict)
    for p in sorted(PARTS.glob("*.json")):
        m = re.match(r"^([a-z0-9]+)_(\d+)-(\d+)$", p.stem)
        if not m:
            print(f"⚠️  bỏ qua tên lạ: {p.name}")
            continue
        voter = m.group(1)
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"❌ {p.name} JSON hỏng: {e}")
            continue
        for fid, items in data.items():
            if not isinstance(items, list):
                continue
            if fid in by_voter[voter]:
                print(f"⚠️  {voter}: file {fid} bị ghi bởi 2 mảnh — giữ mảnh đầu")
                continue
            by_voter[voter][fid] = items

    if not by_voter:
        raise SystemExit(f"Không có mảnh nào trong {PARTS}")

    OUT.mkdir(parents=True, exist_ok=True)
    for voter, data in sorted(by_voter.items()):
        missing = [str(i) for i in range(1, 101) if str(i) not in data]
        n = sum(len(v) for v in data.values())
        path = OUT / f"{voter}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        flag = f"  ⚠️  THIẾU {len(missing)} file: {missing[:12]}" if missing else "  ✅ đủ 100 file"
        print(f"[{voter}] {n} concept thô / {len(data)} file -> {path.name}{flag}")

    # Cổng MẬT ĐỘ: agent có thể ghi file kết quả sau khi mới làm được vài file đầu
    # (đã xảy ra: d_51-75 chỉ làm 6/25 file). File thiếu thì báo ở trên; nhưng agent
    # đọc LƯỚT thì file vẫn đủ mà số concept tụt hẳn — chỉ so chéo giữa voter mới thấy.
    if len(by_voter) < 2:
        return
    print("\n── CỔNG MẬT ĐỘ (so chéo giữa các voter) ──")
    bad = 0
    for fid in (str(i) for i in range(1, 101)):
        counts = {v: len(d.get(fid, [])) for v, d in by_voter.items() if fid in d}
        if len(counts) < 2:
            continue
        med = sorted(counts.values())[len(counts) // 2]
        for v, c in counts.items():
            if med >= 8 and c < med * 0.5:
                print(f"   ⚠️  voter {v} file {fid}: {c} concept, trung vị {med} — nghi đọc lướt")
                bad += 1
    print("   ✅ không voter nào lệch bất thường" if not bad
          else f"   {bad} ca nghi vấn — cân nhắc chạy lại đúng các file đó")


if __name__ == "__main__":
    main()
