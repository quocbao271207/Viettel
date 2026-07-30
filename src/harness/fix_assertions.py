#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sửa assertion ở những span mà >=k voter ĐỘC LẬP cùng đồng thuận KHÁC bản nền.

    python3 -m src.harness.fix_assertions --k 2 --dry
    python3 -m src.harness.fix_assertions --k 2 --out out/candidates/21_assert_fix.zip

ĐÂY LÀ THÍ NGHIỆM SẠCH NHẤT CÓ THỂ DỰNG:
không thêm, không bớt, không đụng `text`/`position`/`candidates` — chỉ đổi `assertions`.
⇒ **WER và J_cand BẤT BIẾN về mặt toán học.** Điểm đổi bao nhiêu thì toàn bộ nằm ở J_assert,
không cần suy đoán nhân quả. (Bản 08 từng dùng đúng kiểu này: +0.205 điểm, WER & J_cand phẳng.)

Chỉ sửa khi CẢ >=k voter cho CÙNG một nhãn và nhãn đó khác bản nền. Voter bất đồng nhau
-> giữ nguyên bản nền (không có tín hiệu thì không động vào).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.harness import validate                       # noqa: E402
from src.harness.build import resolve_voter, write_zip  # noqa: E402

BASE_ZIP = ROOT / "out/submitted/14_repeat_36.4914.zip"
VOTES = ROOT / "dev/votes_v2"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="",
                    help="zip nền để chồng lên (mặc định: bản 14). Cho phép nối các bước: span_fix -> assert -> prune ...")
    ap.add_argument("--k", type=int, default=2)
    ap.add_argument("--out", default="")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--assert-mode", choices=("full", "add", "none"), default="full",
                    help="full = theo đồng thuận voter (ĐÃ ĐO: voter chỉ đúng ~36%% khi bất đồng "
                         "-> bản 21 LỖ 0.24 điểm). add = CHỈ thêm nhãn, không bao giờ gỡ "
                         "(giả thuyết: gold dùng isHistorical rộng rãi, bản 14 duyệt tay đã đúng, "
                         "voter sai chủ yếu vì GỠ isHistorical). none = không đụng assertion.")
    ap.add_argument("--fix-types", action="store_true",
                    help="SỬA CẢ TYPE khi >=k voter đồng thuận type khác bản nền. "
                         "Đề gọi sai type là 'phạt kép' (0đ cả 3 trục + tạo concept ma). "
                         "Đổi type sang loại không được chấm mã thì candidates bị xoá theo spec §5 "
                         "— tức bản này KHÔNG còn thuần một trục nữa. Nộp riêng.")
    args = ap.parse_args()

    base = validate.load_zip(Path(args.base) if args.base else BASE_ZIP)
    resolved = {}
    for f in sorted(VOTES.glob("*.json")):
        r, _ = resolve_voter(json.loads(f.read_text(encoding="utf-8")), apply_ban=False)
        resolved[f.stem] = r
    if len(resolved) < args.k:
        raise SystemExit(f"chỉ có {len(resolved)} voter, không đủ cho k={args.k}")
    print(f"voter: {sorted(resolved)}")

    stats, changes, tchanges = Counter(), [], []
    out = {}
    for fid in sorted(base, key=int):
        rows = []
        for e in base[fid]:
            e = dict(e)
            # --- sửa TYPE trước (nếu bật): khớp span BỎ QUA type để thấy voter gán loại gì
            if args.fix_types:
                tv = Counter()
                for per_file in resolved.values():
                    for v in per_file.get(fid, []):
                        if v["position"] == e["position"]:
                            tv[v["type"]] += 1
                if tv and tv.most_common(1)[0][1] >= args.k \
                        and tv.most_common(1)[0][0] != e["type"] and len(tv) == 1:
                    newt = tv.most_common(1)[0][0]
                    tchanges.append((fid, e["text"], e["type"], newt))
                    e["type"] = newt
                    if newt not in ("CHẨN_ĐOÁN", "THUỐC"):
                        e["candidates"] = []       # spec §5: 3 type còn lại không có mã
            key = (e["position"][0], e["position"][1], e["type"])
            votes = Counter()
            for vn, per_file in resolved.items():
                for v in per_file.get(fid, []):
                    if (v["position"][0], v["position"][1], v["type"]) == key:
                        votes[tuple(sorted(v["assertions"]))] += 1
            cur = tuple(sorted(e["assertions"]))
            new = e["assertions"]
            if args.assert_mode == "none":
                stats["không đụng assertion (--assert-mode none)"] += 1
                rows.append({**e, "assertions": new})
                continue
            if not votes:
                stats["không voter nào chạm span này"] += 1
            elif votes.most_common(1)[0][1] < args.k:
                stats[f"voter bất đồng nhau (<{args.k} cùng nhãn) — GIỮ NGUYÊN"] += 1
            elif votes.most_common(1)[0][0] == cur:
                stats["voter xác nhận bản nền"] += 1
            elif args.assert_mode == "add" and not set(cur) <= set(votes.most_common(1)[0][0]):
                stats["voter GỠ nhãn — bỏ qua (--assert-mode add)"] += 1
            else:
                new = list(votes.most_common(1)[0][0])
                stats["SỬA theo đồng thuận voter"] += 1
                raw = validate.read_raw(int(fid))
                changes.append((fid, e["text"], e["type"], list(cur), new,
                                raw[max(0, key[0] - 45):key[1] + 12].replace("\n", "⏎")))
            rows.append({**e, "assertions": new})
        out[fid] = rows

    tot = sum(stats.values())
    print(f"\ntrên {tot} concept bản nền:")
    for k, n in stats.most_common():
        print(f"   {n:5d} ({n/tot*100:5.1f}%)  {k}")

    print(f"\nphân bố thay đổi:")
    for (a, b), n in Counter((tuple(c[3]), tuple(c[4])) for c in changes).most_common(12):
        print(f"   {n:4d}×   {list(a) or '[]'}  ->  {list(b) or '[]'}")
    print(f"\n15 ca đầu:")
    for fid, t, ty, a, b, ctx in changes[:15]:
        print(f"   file {fid:>3s} {ty:18s} {t[:24]!r:26s} {a or '[]'} -> {b or '[]'}")
        print(f"        ...{ctx[-58:]}")

    if tchanges:
        print(f"\nSỬA TYPE: {len(tchanges)} ca (đồng thuận >={args.k} voter)")
        for (a, b), n in Counter((c[2], c[3]) for c in tchanges).most_common():
            print(f"   {n:4d}×   {a:20s} -> {b}")

    if args.dry or not args.out:
        return
    # Bất biến: text và position TUYỆT ĐỐI không đổi. type/candidates chỉ đổi khi bật --fix-types.
    for fid in base:
        assert len(base[fid]) == len(out[fid]), f"file {fid} lệch số concept"
        for a, b in zip(base[fid], out[fid]):
            assert (a["text"], a["position"]) == (b["text"], b["position"]), \
                   f"file {fid}: thí nghiệm đụng vào text/position — SAI"
            if not args.fix_types:
                assert (a["type"], a["candidates"]) == (b["type"], b["candidates"]), \
                       f"file {fid}: đụng type/mã dù không bật --fix-types"
            if args.assert_mode == "none":
                assert a["assertions"] == b["assertions"], \
                       f"file {fid}: đụng assertion dù --assert-mode none"
    errs = validate.validate(out)
    if errs:
        print(f"\n❌ {len(errs)} lỗi — KHÔNG ghi zip")
        for e in errs[:20]:
            print("  -", e)
        raise SystemExit(1)
    write_zip(out, Path(args.out))
    if args.fix_types:
        print(f"\n✅ ghi {args.out} — {len(changes)} assertion + {len(tchanges)} type đổi. "
              f"text/vị trí bất biến; type và mã CÓ đổi (đã assert)")
    else:
        print(f"\n✅ ghi {args.out} — {len(changes)} assertion đổi, "
              f"text/vị trí/type/mã BẤT BIẾN (đã assert)")


if __name__ == "__main__":
    main()
