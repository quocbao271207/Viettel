#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DỰNG TOÀN BỘ ứng viên nộp bằng MỘT lệnh — mỗi bản là một thí nghiệm tách bạch.

    python3 -m src.harness.make_submissions

Không có bước sửa tay ở giữa. Muốn đổi kết quả thì sửa `dev/SPEC_V2.md` + `spec.py`
rồi chạy lại lệnh này. Mọi zip đều phải qua `validate` mới được ghi.

Mỗi bản đổi ĐÚNG một thứ so bản 14, để điểm nhận về quy được nhân quả:

  18_prune       bản 14 TRỪ cụm không voter độc lập nào xác nhận
  19_augment     bản 14 CỘNG concept >=2 voter đồng thuận đúng span
  20_cleanroom   dựng lại hoàn toàn từ phiếu voter, k>=2 (không dùng bản 14 làm nền)
  21_assert      chỉ đổi assertions (text/vị trí/mã BẤT BIẾN — thí nghiệm sạch nhất)
  22_types       chỉ đổi type + mã kéo theo
  23_span_fix    THU NGẮN ranh giới span sai — số concept BẤT BIẾN, ăn cả ba trục
  24_span_both   sửa ranh giới cả hai hướng
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "out/candidates"
BASE = "out/submitted/14_repeat_36.4914.zip"

JOBS = [
    ("21_assert_consensus.zip", "thí nghiệm SẠCH NHẤT — chỉ assertions đổi",
     ["-m", "src.harness.fix_assertions", "--k", "2", "--out"]),
    ("22_type_fix.zip", "chỉ type + mã kéo theo",
     ["-m", "src.harness.fix_assertions", "--k", "2", "--fix-types", "--out"]),
    ("18_prune_uncorroborated.zip", "TRỪ cụm không voter nào xác nhận (hướng CHƯA TỪNG THỬ)",
     ["-m", "src.harness.prune", "--rule", "uncorroborated", "--min-votes", "1", "--out"]),
    ("19_augment_k2.zip", "CỘNG concept 2 voter đồng thuận đúng span",
     ["-m", "src.harness.augment", "--k", "2",
      "--extra-codes", "dev/newcodes_v2.json", "--out"]),
    ("20_cleanroom_k2.zip", "dựng lại HOÀN TOÀN từ phiếu voter, k>=2",
     ["-m", "src.harness.build", "--k", "2", "--out"]),
    ("23_span_fix.zip", "THU NGẮN ranh giới span theo đồng thuận — ăn CẢ BA trục",
     ["-m", "src.harness.fix_spans", "--k", "2",
      "--extra-codes", "dev/newcodes_v2.json", "--out"]),
    ("24_span_fix_both.zip", "sửa ranh giới CẢ HAI hướng (nới rộng rủi ro hơn)",
     ["-m", "src.harness.fix_spans", "--k", "2", "--both",
      "--extra-codes", "dev/newcodes_v2.json", "--out"]),
]


def run(args: list[str]) -> tuple[int, str]:
    r = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print("=" * 74)
    print("KIỂM TRA HARNESS TRƯỚC (bắt buộc)")
    print("=" * 74)
    rc, out = run(["-m", "src.harness.selftest"])
    print(out.strip().splitlines()[-1] if out.strip() else "")
    if rc:
        raise SystemExit("❌ selftest KHÔNG đạt — dừng, không dựng bản nào.")

    built = []
    for name, desc, cmd in JOBS:
        print("\n" + "=" * 74)
        print(f"{name}  —  {desc}")
        print("=" * 74)
        rc, out = run([*cmd, str(OUT / name)])
        tail = [ln for ln in out.strip().splitlines() if ln.strip()]
        print("\n".join(tail[-14:]))
        if rc:
            print(f"⚠️  BỎ QUA {name} (lỗi ở trên)")
            continue
        built.append(name)
        rc2, d = run(["-m", "src.harness.diff", BASE, str(OUT / name)])
        print("\n--- diff so bản 14 ---")
        print("\n".join(d.strip().splitlines()[2:12]))

    print("\n" + "=" * 74)
    print(f"DỰNG XONG {len(built)}/{len(JOBS)} bản -> {OUT}")
    for n in built:
        print(f"   {n}")
    print("\nMỗi bản đổi ĐÚNG một trục. Nộp lần lượt, ghi điểm vào out/SCORES.md,")
    print("rồi mới gộp các hướng thắng.")


if __name__ == "__main__":
    main()
