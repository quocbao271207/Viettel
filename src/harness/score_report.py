#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Đọc `out/RESULTS.csv` sau khi điền điểm -> diễn giải luôn, không phải tự tính.

    python3 -m src.harness.score_report

Chỉ cần điền 4 cột `diem, WER, J_assert, J_cand` cho những bản đã nộp. Bản chưa nộp
để trống, công cụ tự bỏ qua. Nó sẽ:

1. **Kiểm số học** — `0.3(1−WER) + 0.3·J_assert + 0.4·J_cand` có ra đúng `diem` không.
   Lệch > 0.01 nghĩa là chép nhầm số HOẶC công thức ta hiểu sai. Bắt lỗi ngay tại chỗ.
2. **Kiểm chứng metric** — bản `21_assert_consensus` PHẢI có WER và J_cand y hệt bản 14.
   Nếu khác, mô hình metric (`src/evaluate.py`) sai và mọi suy luận dựa trên nó phải xem lại.
3. Tách đóng góp từng trục ra ĐIỂM (WER×0.3, J_assert×0.3, J_cand×0.4) — biết hướng nào
   ăn ở đâu, thay vì chỉ biết tổng tăng hay giảm.
4. Lợi ích biên mỗi concept — so trực tiếp với lịch sử bản 14..17.
5. Đường liều-đáp cho các cặp cùng đòn bẩy khác liều.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CSV = ROOT / "out/RESULTS.csv"

# Cặp cùng ĐÒN BẨY khác LIỀU — dùng vẽ đường liều-đáp
DOSE_PAIRS = [
    ("23_span_fix", "24_span_fix_both", "ranh giới span: chỉ thu ngắn -> cả hai hướng"),
    ("18_prune_uncorroborated", "25_prune_k2", "ĐÃI BỎ: 49 -> 74 concept"),
    ("19_augment_k2", "26_augment_k1", "THÊM: 232 -> 367 concept"),
    ("20_cleanroom_k2", "30_cleanroom_k1", "clean-room: k>=2 -> k>=1"),
]
# Lịch sử để so lợi ích biên (điểm / concept thay đổi)
HISTORY = [("14 nhân bản text đã ăn điểm", 313, +1.2608),
           ("15 cụm 1 âm tiết", 147, -0.0750),
           ("16 trích lại + sinh tồn", 251, -0.6128),
           ("17 trích lại concept cụ thể", 113, -0.5641)]


def f(x: str) -> float | None:
    x = (x or "").strip().replace(",", ".")
    try:
        return float(x)
    except ValueError:
        return None


def main() -> None:
    if not CSV.exists():
        raise SystemExit(f"Không thấy {CSV}")
    rows = list(csv.DictReader(CSV.open(encoding="utf-8")))
    done = [r for r in rows if f(r["diem"]) is not None]
    base = next((r for r in rows if r["stt"] == "0"), None)
    if not base or f(base["diem"]) is None:
        raise SystemExit("Hàng stt=0 (bản nền 14) phải có đủ điểm — đừng xoá.")
    B = {k: f(base[k]) for k in ("diem", "WER", "J_assert", "J_cand")}

    print(f"NỀN bản 14: {B['diem']:.4f}  (WER {B['WER']:.4f} · J_assert {B['J_assert']:.4f} "
          f"· J_cand {B['J_cand']:.4f})")
    print(f"đã điền {len(done)-1}/{len(rows)-1} bản\n")

    # ---------------------------------------------------------- 1. kiểm số học
    bad = []
    for r in done:
        w, a, c, d = (f(r[k]) for k in ("WER", "J_assert", "J_cand", "diem"))
        if None in (w, a, c, d):
            continue
        calc = 0.3 * (1 - w / 100) + 0.3 * (a / 100) + 0.4 * (c / 100)
        if abs(calc * 100 - d) > 0.01:
            bad.append((r["ban"], d, calc * 100))
    if bad:
        print("⚠️  SỐ KHÔNG KHỚP CÔNG THỨC — chép nhầm, hoặc công thức ta hiểu SAI:")
        for n, d, calc in bad:
            print(f"     {n}: ghi {d:.4f} nhưng 0.3(1−WER)+0.3A+0.4C = {calc:.4f}")
        print()

    # ------------------------------------------------ 2. kiểm chứng metric (bản 21)
    s = next((r for r in done if r["ban"].startswith("21_")), None)
    if s:
        dw, dc = f(s["WER"]) - B["WER"], f(s["J_cand"]) - B["J_cand"]
        print("── KIỂM CHỨNG METRIC (bản 21 chỉ đổi assertions) ──")
        if abs(dw) < 1e-6 and abs(dc) < 1e-6:
            print("   ✅ WER và J_cand BẤT BIẾN đúng như dự đoán — mô hình metric ĐÚNG.")
            print(f"   ⇒ toàn bộ thay đổi nằm ở J_assert: {f(s['J_assert'])-B['J_assert']:+.4f}"
                  f" = {(f(s['J_assert'])-B['J_assert'])*0.3:+.4f} điểm")
        else:
            print(f"   ❌ WER lệch {dw:+.4f}, J_cand lệch {dc:+.4f} — LẼ RA PHẢI BẰNG 0.")
            print("   ⇒ mô hình metric SAI. Xem lại chặn trên gold (≤4600) và ngưỡng hoà vốn")
            print("      32.6% trong dev/SPEC_V2.md §6-7 TRƯỚC KHI tin bất kỳ suy luận nào khác.")
        print()

    # ------------------------------------------------- 3. bảng phân rã theo trục
    print("── ĐÓNG GÓP TỪNG TRỤC (quy ra ĐIỂM) ──")
    print(f"{'bản':30s} {'điểm':>8s} {'Δtổng':>7s} │ {'ΔWER':>7s} {'Δassert':>8s} {'Δcand':>7s}")
    res = []
    for r in done:
        if r["stt"] == "0":
            continue
        w, a, c, d = (f(r[k]) for k in ("WER", "J_assert", "J_cand", "diem"))
        if None in (w, a, c, d):
            continue
        pw, pa, pc = -(w - B["WER"]) * 0.3, (a - B["J_assert"]) * 0.3, (c - B["J_cand"]) * 0.4
        res.append((r, d, d - B["diem"], pw, pa, pc))
    for r, d, dt, pw, pa, pc in sorted(res, key=lambda x: -x[1]):
        mark = "✅" if dt > 0 else "❌"
        print(f"{mark} {r['ban'][:27]:27s} {d:8.4f} {dt:+7.4f} │ {pw:+7.4f} {pa:+8.4f} {pc:+7.4f}")

    # ----------------------------------------------------- 4. lợi ích biên
    print("\n── LỢI ÍCH BIÊN mỗi concept thay đổi ──")
    print("   (lịch sử: bản 14 +0.00403 · bản 15 −0.00051 · bản 16 −0.00244 · bản 17 −0.00499)")
    for r, d, dt, *_ in sorted(res, key=lambda x: -x[2]):
        n = int(r["them"] or 0) + int(r["bo"] or 0) + int(r["assert_doi"] or 0)
        if n:
            print(f"   {r['ban'][:30]:30s} {n:5d} thay đổi  {dt/n:+.5f} điểm/thay đổi")

    # ----------------------------------------------------- 5. đường liều-đáp
    got = {r["ban"]: (d, dt) for r, d, dt, *_ in res}
    pairs = [(lo, hi, lbl) for lo, hi, lbl in DOSE_PAIRS if lo in got and hi in got]
    if pairs:
        print("\n── ĐƯỜNG LIỀU-ĐÁP ──")
        for lo, hi, lbl in pairs:
            a, bb = got[lo][1], got[hi][1]
            if bb > a > 0:
                verdict = "cả hai lời và liều mạnh HƠN ⇒ TĂNG LIỀU NỮA"
            elif a > 0 >= bb:
                verdict = "liều nhẹ lời, liều mạnh lỗ ⇒ tối ưu NẰM GIỮA"
            elif a > bb:
                verdict = "liều nhẹ tốt hơn ⇒ GIẢM LIỀU"
            else:
                verdict = "cả hai lỗ ⇒ BỎ HƯỚNG NÀY"
            print(f"   {lbl}\n      {a:+.4f} -> {bb:+.4f}   {verdict}")

    # ----------------------------------------------------- 6. cộng dồn?
    parts = {k: got[v][1] for k, v in
             (("span", "23_span_fix"), ("assert", "21_assert_consensus"),
              ("prune", "18_prune_uncorroborated"), ("augment", "19_augment_k2"))
             if v in got}
    if len(parts) >= 2 and "29_all_four" in got:
        tong = sum(parts.values())
        thuc = got["29_all_four"][1]
        print(f"\n── CÓ CỘNG DỒN KHÔNG ──")
        print(f"   tổng các hướng riêng lẻ ({'+'.join(parts)}) = {tong:+.4f}")
        print(f"   bản gộp 29_all_four thực tế              = {thuc:+.4f}")
        print(f"   ⇒ {'CỘNG DỒN TỐT' if thuc >= tong*0.8 else 'TRIỆT TIÊU NHAU — gộp có hại'}")

    if res:
        best = max(res, key=lambda x: x[1])
        print(f"\n🏆 TỐT NHẤT: {best[0]['ban']} = {best[1]:.4f} ({best[2]:+.4f} so bản 14)")


if __name__ == "__main__":
    main()
