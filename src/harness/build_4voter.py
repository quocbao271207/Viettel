#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dựng THANG ĐỒNG THUẬN 4 VOTER — chạy ngay khi c.json và d.json đủ 100 file.

    python3 -m src.harness.build_4voter

Vì sao đáng làm: bản 76 (thêm 311 concept đồng thuận 2/2 voter) ăn **+0.8732**, mức tăng
lớn nhất từ trước tới nay và là lần đầu CẢ BA TRỤC cùng tăng. Với 4 voter:

- `k>=2 trong 4` bắt được nhiều concept đúng hơn hẳn `k>=2 trong 2` (pool rộng hơn).
- `k>=3` cho mức chính xác cao hơn, dùng khi k>=2 quá liều.
- Tín hiệu "KHÔNG voter nào xác nhận" (dùng cho đãi bỏ) mạnh hơn nhiều: 0/4 đáng tin
  hơn 0/2 rất nhiều. Ngưỡng đãi bỏ có thể đẩy xa hơn mức ~65 concept đã chạm trần.

Mọi bản dựng trên nền tốt nhất hiện tại và đều qua cổng cứng trước khi ghi.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
VOTES = ROOT / "dev/votes_v2"
OUT = ROOT / "out/candidates"
BEST = "out/candidates/76_best_aug_k2.zip"      # 38.2704
CODES = "dev/newcodes_v2.json"


def run(args: list[str]) -> tuple[int, str]:
    r = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def main() -> None:
    # --- cổng: mọi voter phải đủ 100 file, nếu không thì đồng thuận bị lệch
    ok = True
    for p in sorted(VOTES.glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        have = sum(1 for i in range(1, 101) if d.get(str(i)))
        n = sum(len(v) for v in d.values())
        print(f"[{p.stem}] {n} concept / {have}/100 file" + ("" if have == 100 else "  ⚠️ THIẾU"))
        ok &= have == 100
    if not ok:
        raise SystemExit("\n❌ Chưa đủ phiếu. Chạy merge_parts và đợi voter xong đã — "
                         "voter thiếu file làm lệch SỐ PHIẾU, đúng chỗ cơ chế đồng thuận dựa vào.")

    JOBS = [
        ("80_aug4_k2.zip", "THÊM concept >=2/4 voter — pool rộng hơn hẳn bản 76",
         ["-m", "src.harness.augment", "--k", "2", "--extra-codes", CODES, "--base", BEST, "--out"]),
        ("81_aug4_k3.zip", "THÊM concept >=3/4 voter — chính xác cao hơn",
         ["-m", "src.harness.augment", "--k", "3", "--extra-codes", CODES, "--base", BEST, "--out"]),
        ("82_aug4_k4.zip", "THÊM concept 4/4 voter — chắc chắn nhất, ít nhất",
         ["-m", "src.harness.augment", "--k", "4", "--extra-codes", CODES, "--base", BEST, "--out"]),
        ("83_prune4.zip", "ĐÃI BỎ: không voter nào trong 4 xác nhận (tín hiệu mạnh hơn 0/2)",
         ["-m", "src.harness.prune", "--rule", "uncorroborated", "--min-votes", "1",
          "--base", BEST, "--out"]),
        ("84_span4.zip", "THU NGẮN ranh giới theo đồng thuận 4 voter",
         ["-m", "src.harness.fix_spans", "--k", "2", "--extra-codes", CODES,
          "--base", BEST, "--out"]),
    ]
    built = []
    for name, desc, cmd in JOBS:
        print("\n" + "=" * 70)
        print(f"{name}  —  {desc}")
        rc, out = run([*cmd, str(OUT / name)])
        tail = [l for l in out.strip().splitlines() if l.strip()]
        print("\n".join(tail[-6:]))
        if rc == 0:
            built.append(name)
            rc2, d = run(["-m", "src.harness.diff", BEST, str(OUT / name)])
            print("--- diff so nền 38.2704 ---")
            print("\n".join(d.strip().splitlines()[2:8]))

    print("\n" + "=" * 70)
    print(f"DỰNG XONG {len(built)}/{len(JOBS)}")
    for n in built:
        print(f"   {n}")
    print("\nNộp 80 trước (pool rộng nhất), rồi 81/82 để tìm ngưỡng k tối ưu.")


if __name__ == "__main__":
    main()
