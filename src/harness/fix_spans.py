#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SỬA RANH GIỚI SPAN theo đồng thuận voter — đòn bẩy ăn CẢ BA TRỤC cùng lúc.

    python3 -m src.harness.fix_spans --k 2 --dry
    python3 -m src.harness.fix_spans --k 2 --out out/candidates/23_span_fix.zip
    python3 -m src.harness.fix_spans --k 2 --both --out ...   # sửa cả hướng nới rộng

VẤN ĐỀ: bản 14 hay nuốt cả mệnh đề mô tả vào một span:

    'nhiều loét tá tràng và hồi tràng'   ->  'loét tá tràng'
    'buồn nôn và tiêu chảy'              ->  'tiêu chảy'     (GỘP 2 triệu chứng làm 1!)
    'xuất huyết dưới nhện vùng trán phải'->  'xuất huyết dưới nhện'
    'Chụp cắt lớp vi tính (CT Scanner)'  ->  'Chụp cắt lớp vi tính'

Span sai ranh giới là loại lỗi TỆ NHẤT trong bộ metric này:
- WER: mọi từ thừa là một Insertion, tính thẳng vào lỗi.
- J_assert / J_cand: khoá ghép không khớp -> mất luôn cả concept, dù đã nhận ra đúng khái niệm.

Sửa được ranh giới là ăn cả ba trục. Mặc định CHỈ thu ngắn (`bản 14 dài lê thê`) — hướng
nới rộng (`--both`) rủi ro hơn vì thêm từ vào chuỗi so khớp WER, nên tách ra để đo riêng.

Chỉ sửa khi >=k voter ĐỘC LẬP cùng chốt CHÍNH XÁC một ranh giới thay thế.
"""
from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.harness import spec, validate                              # noqa: E402
from src.harness.build import code_map_from_base, resolve_voter, write_zip  # noqa: E402

BASE_ZIP = ROOT / "out/submitted/14_repeat_36.4914.zip"
VOTES = ROOT / "dev/votes_v2"


def norm(s: str) -> str:
    return unicodedata.normalize("NFC", s or "").strip().lower()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="",
                    help="zip nền để chồng lên (mặc định: bản 14). Cho phép nối các bước: span_fix -> assert -> prune ...")
    ap.add_argument("--k", type=int, default=2)
    ap.add_argument("--both", action="store_true",
                    help="sửa cả hướng NỚI RỘNG (bản nền cắt cụt), không chỉ thu ngắn")
    ap.add_argument("--out", default="")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--extra-codes", default="",
                    help="JSON {'text\\tTYPE': ['mã']} bổ sung — cụm sau khi thu ngắn "
                         "thường là tên bệnh phổ biến hơn nên tra mã được")
    args = ap.parse_args()

    base = validate.load_zip(Path(args.base) if args.base else BASE_ZIP)
    resolved = {}
    for f in sorted(VOTES.glob("*.json")):
        r, _ = resolve_voter(json.loads(f.read_text(encoding="utf-8")), apply_ban=True)
        resolved[f.stem] = r
    print(f"voter: {sorted(resolved)} (k={args.k}, "
          f"{'cả hai hướng' if args.both else 'CHỈ thu ngắn'})")

    cmap = code_map_from_base()
    if args.extra_codes and Path(args.extra_codes).exists():
        extra = json.loads(Path(args.extra_codes).read_text(encoding="utf-8"))
        for k, v in extra.items():
            t, ty = k.split("\t")
            if v:
                cmap[(norm(t), ty)] = v
        print(f"nạp thêm {sum(1 for v in extra.values() if v)} mã từ {args.extra_codes}")
    out, changes, stats = {}, [], Counter()
    for fid in sorted(base, key=int):
        raw = validate.read_raw(int(fid))
        have = {(e["position"][0], e["position"][1]) for e in base[fid]}
        vs: dict[tuple, set] = defaultdict(set)
        for vn, per_file in resolved.items():
            for e in per_file.get(fid, []):
                vs[(e["position"][0], e["position"][1], e["type"])].add(vn)

        rows, taken = [], set()
        for e in base[fid]:
            s, t = e["position"]
            alts = [(k, v) for k, v in vs.items()
                    if len(v) >= args.k and s < k[1] and t > k[0]
                    and (k[0], k[1]) != (s, t) and (k[0], k[1]) not in have]
            if not alts:
                stats["giữ nguyên (không có ứng viên)"] += 1
                rows.append(e)
                continue
            # chọn span thay thế CHỒNG LẤN NHIỀU NHẤT
            k, _ = max(alts, key=lambda x: min(x[0][1], t) - max(x[0][0], s))
            shorter = (k[1] - k[0]) < (t - s)
            if not shorter and not args.both:
                stats["giữ nguyên (ứng viên dài hơn, cần --both)"] += 1
                rows.append(e)
                continue
            if (k[0], k[1]) in taken:      # đã dùng ranh giới này cho concept khác trong file
                stats["giữ nguyên (ranh giới đã bị chiếm)"] += 1
                rows.append(e)
                continue
            taken.add((k[0], k[1]))
            newtext, newtype = raw[k[0]:k[1]], k[2]
            cands = (list(cmap.get((norm(newtext), newtype), []))
                     if newtype in spec.CODED_TYPES else [])
            stats["SỬA thu ngắn" if shorter else "SỬA nới rộng"] += 1
            changes.append((fid, e["text"], newtext, e["type"], newtype, shorter,
                            bool(e["candidates"]), bool(cands)))
            rows.append({"text": newtext, "type": newtype, "candidates": cands,
                         "assertions": e["assertions"], "position": [k[0], k[1]]})
        out[fid] = sorted(rows, key=lambda r: (r["position"][0], r["position"][1]))

    tot = sum(stats.values())
    print(f"\ntrên {tot} concept bản nền:")
    for k, n in stats.most_common():
        print(f"   {n:5d} ({n/tot*100:5.1f}%)  {k}")
    lost = sum(1 for c in changes if c[6] and not c[7])
    print(f"\n{len(changes)} ranh giới sửa | {lost} ca MẤT mã (text mới chưa có trong code_map)")
    print(f"\n25 ca đầu:")
    for fid, old, new, t1, t2, sh, _, _ in changes[:25]:
        ty = t1 if t1 == t2 else f"{t1}->{t2}"
        print(f"   file {fid:>3s} {ty:20s} {old[:40]!r}  =>  {new[:32]!r}")

    if args.dry or not args.out:
        return
    errs = validate.validate(out)
    if errs:
        print(f"\n❌ {len(errs)} lỗi — KHÔNG ghi zip")
        for e in errs[:25]:
            print("  -", e)
        raise SystemExit(1)
    write_zip(out, Path(args.out))
    n = sum(len(v) for v in out.values())
    assert n == sum(len(v) for v in base.values()), "số concept phải BẤT BIẾN"
    print(f"\n✅ ghi {args.out} — {n} concept (số lượng bất biến, chỉ ranh giới đổi)")


if __name__ == "__main__":
    main()
