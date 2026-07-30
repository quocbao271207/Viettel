#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GHI NHẬN một lượt nộp vào sổ — chạy NGAY sau khi nhận điểm, đừng để dồn.

    python3 -m src.harness.log_submission \
        --ban 85_cleanroom_curated_assert --nen 82x_cleanroom4_k2 \
        --diem 38.9 --wer 55.5 --assert 50.5 --cand 26.1 \
        --nhan-xet "ghép assertion duyệt tay có lời"

Nó tự làm hết phần tính toán và diễn giải, để việc ghi sổ không tốn công và không
bị bỏ qua lúc đang vội:
  1. KIỂM SỐ HỌC — 0.3(1−WER)+0.3A+0.4C có ra đúng `diem` không (bắt chép nhầm ngay).
  2. Tách Δ ra ĐIỂM theo từng trục, để biết bản này ăn/lỗ Ở ĐÂU chứ không chỉ bao nhiêu.
  3. Đếm số concept thêm/bớt (đọc thẳng từ zip) và tính lợi ích biên mỗi concept.
  4. Tự kết luận: TỐT NHẤT MỚI / có lời / lỗ.
  5. Ghi vào `out/SUBMISSIONS.md` và `out/RESULTS.csv`.

Lý do phải ghi từng lượt: cả chiến lược của dự án này được lái bằng CHÊNH LỆCH giữa các
lượt nộp, không phải bằng điểm tuyệt đối. Mất một dòng là mất một quan sát không mua lại được
(5-20 lượt/ngày và deadline cứng). Đã có lần gán nhầm ảnh kết quả cho bản 63/64 và phải
truy ngược bằng bất biến WER mới phát hiện — ghi ngay lúc nộp thì không xảy ra chuyện đó.
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.harness import validate  # noqa: E402

LOG = ROOT / "out/SUBMISSIONS.md"
CSV = ROOT / "out/RESULTS.csv"


def load(name: str) -> dict | None:
    for d in ("out/candidates", "out/submitted"):
        for p in (ROOT / d).glob(f"{name}*.zip"):
            return validate.load_zip(p)
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ban", required=True, help="tên bản (khớp tên zip, không cần đuôi)")
    ap.add_argument("--nen", default="", help="tên bản NỀN để so — bỏ trống thì so bản tốt nhất")
    ap.add_argument("--diem", type=float, required=True)
    ap.add_argument("--wer", type=float, required=True)
    ap.add_argument("--assert", dest="assert_", type=float, required=True)
    ap.add_argument("--cand", type=float, required=True)
    ap.add_argument("--nhan-xet", default="", help="đánh giá bằng lời — VÌ SAO ăn/lỗ")
    ap.add_argument("--gio", default="", help="giờ nộp, vd '13:23'")
    args = ap.parse_args()

    # --- 1. kiểm số học
    calc = (0.3 * (1 - args.wer / 100) + 0.3 * args.assert_ / 100 + 0.4 * args.cand / 100) * 100
    warn = ""
    if abs(calc - args.diem) > 0.01:
        warn = (f"\n> ⚠️ **SỐ KHÔNG KHỚP CÔNG THỨC**: ghi {args.diem:.4f} nhưng "
                f"0.3(1−WER)+0.3A+0.4C = {calc:.4f}. Kiểm lại đã chép đúng chưa.")
        print(warn.strip())

    # --- 2. nền để so
    rows = list(csv.DictReader(CSV.open(encoding="utf-8"))) if CSV.exists() else []
    done = [r for r in rows if r["diem"].strip() and r["stt"] != "0"]
    if args.nen:
        base_row = next((r for r in rows if r["ban"].startswith(args.nen)), None)
    else:
        base_row = max(done, key=lambda r: float(r["diem"])) if done else None
    if base_row is None or not base_row["diem"].strip():
        raise SystemExit(f"Không tìm thấy bản nền {args.nen!r} đã có điểm trong {CSV.name}")
    bd, bw, ba, bc = (float(base_row[k]) for k in ("diem", "WER", "J_assert", "J_cand"))
    base_name = base_row["ban"].replace(" (DA NOP)", "")

    # --- 3. tách Δ ra điểm
    dw, da, dc = -(args.wer - bw) * 0.3, (args.assert_ - ba) * 0.3, (args.cand - bc) * 0.4
    dt = args.diem - bd

    # --- 4. đếm concept
    nb, nn = load(base_name), load(args.ban)
    delta_txt = ""
    if nb and nn:
        kb = {(f, e["position"][0], e["position"][1], e["type"]) for f, v in nb.items() for e in v}
        kn = {(f, e["position"][0], e["position"][1], e["type"]) for f, v in nn.items() for e in v}
        add, rem = len(kn - kb), len(kb - kn)
        n_ch = add + rem
        delta_txt = f"{len(kn)} concept · +{add} −{rem}"
        if n_ch:
            delta_txt += f" · **{dt/n_ch:+.5f} điểm/thay đổi**"

    best = max((float(r["diem"]) for r in done), default=0)
    verdict = ("🏆 **TỐT NHẤT MỚI**" if args.diem > best
               else "✅ có lời" if dt > 0 else "❌ LỖ")

    stamp = args.gio or datetime.now().strftime("%H:%M")
    entry = f"""
### {args.ban} — {args.diem:.4f} {verdict}
*nộp {stamp} · nền so sánh: `{base_name}` ({bd:.4f})*{warn}

| | điểm | WER | J_assert | J_cand |
|---|---|---|---|---|
| nền | {bd:.4f} | {bw:.4f} | {ba:.4f} | {bc:.4f} |
| **bản này** | **{args.diem:.4f}** | {args.wer:.4f} | {args.assert_:.4f} | {args.cand:.4f} |
| Δ quy ra ĐIỂM | **{dt:+.4f}** | {dw:+.4f} | {da:+.4f} | {dc:+.4f} |

{delta_txt}

**Đánh giá:** {args.nhan_xet or '_(chưa ghi)_'}
"""
    LOG.parent.mkdir(parents=True, exist_ok=True)
    if not LOG.exists():
        LOG.write_text("# SỔ NỘP BÀI — ghi NGAY sau mỗi lượt\n", encoding="utf-8")
    LOG.write_text(LOG.read_text(encoding="utf-8") + entry, encoding="utf-8")

    for r in rows:
        if r["ban"].startswith(args.ban):
            r["diem"], r["WER"] = f"{args.diem:.4f}", f"{args.wer:.4f}"
            r["J_assert"], r["J_cand"] = f"{args.assert_:.4f}", f"{args.cand:.4f}"
            r["ghi_chu"] = args.nhan_xet
            if not r["ban"].endswith("(DA NOP)"):
                r["ban"] += " (DA NOP)"
    if rows:
        with CSV.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=rows[0].keys())
            w.writeheader()
            w.writerows(rows)

    print(entry)
    print(f"-> ghi vào {LOG.name} và {CSV.name}")


if __name__ == "__main__":
    main()
