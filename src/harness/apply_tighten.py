#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Áp các đề xuất THU NGẮN span từ `dev/span_tighten/batch_*.json`.

    python3 -m src.harness.apply_tighten --base out/candidates/36_span_fix_k1.zip \
        --out out/candidates/42_tighten.zip

Khác `fix_spans.py` ở chỗ: `fix_spans` chỉ thay được bằng ranh giới mà VOTER đã trích;
ở đây là một lượt soi CÓ CHỦ ĐÍCH vào các span còn dài mà không voter nào chạm tới —
đúng chỗ `fix_spans` đã cạn (chỉ còn 2 ca khai thác được).

Bất biến: `new` phải là **chuỗi con LIÊN TỤC, NGUYÊN VĂN** của `old`, và vị trí mới phải
nằm TRỌN trong span cũ. Ca nào không thoả thì LOẠI, không đoán.
"""
from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.harness import spec, validate                              # noqa: E402
from src.harness.build import code_map_from_base, write_zip         # noqa: E402

TIGHTEN = ROOT / "dev/span_tighten"


def norm(s: str) -> str:
    return unicodedata.normalize("NFC", s or "").strip().lower()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="out/candidates/36_span_fix_k1.zip")
    ap.add_argument("--out", default="")
    ap.add_argument("--extra-codes", default="dev/newcodes_v2.json")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    props: dict[tuple[str, str], str] = {}
    files = sorted(TIGHTEN.glob("batch_*.json"))
    if not files:
        raise SystemExit(f"Chưa có đề xuất nào trong {TIGHTEN}")
    for p in files:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"❌ {p.name} JSON hỏng: {e}")
            continue
        n = 0
        for r in data:
            if not all(k in r for k in ("file", "old", "new")):
                continue
            props[(str(r["file"]), r["old"])] = r["new"]
            n += 1
        print(f"[{p.stem}] {n} đề xuất")
    print(f"tổng {len(props)} cặp (file, old) duy nhất\n")

    base = validate.load_zip(Path(args.base))
    cmap = code_map_from_base()
    ep = Path(args.extra_codes)
    if ep.exists():
        for k, v in json.loads(ep.read_text(encoding="utf-8")).items():
            t, ty = k.split("\t")
            if v:
                cmap[(norm(t), ty)] = v

    out, stats, changes = {}, Counter(), []
    for fid in sorted(base, key=int):
        raw = validate.read_raw(int(fid))
        rows, used = [], set()
        for e in base[fid]:
            new = props.get((fid, e["text"]))
            s, t = e["position"]
            if new is None:
                stats["không có đề xuất"] += 1
                rows.append(e)
                continue
            off = e["text"].find(new)
            if off < 0 or not new or len(new) >= len(e["text"]):
                stats["LOẠI: `new` không phải chuỗi con ngắn hơn của `old`"] += 1
                rows.append(e)
                continue
            ns, nt = s + off, s + off + len(new)
            if raw[ns:nt] != new:
                stats["LOẠI: vị trí mới không khớp nguyên văn raw"] += 1
                rows.append(e)
                continue
            if (ns, nt) in used:
                stats["LOẠI: ranh giới mới đã bị chiếm trong file"] += 1
                rows.append(e)
                continue
            used.add((ns, nt))
            cands = (list(cmap.get((norm(new), e["type"]), []))
                     if e["type"] in spec.CODED_TYPES else [])
            stats["THU NGẮN"] += 1
            changes.append((fid, e["text"], new, e["type"],
                            bool(e["candidates"]), bool(cands)))
            rows.append({"text": new, "type": e["type"], "candidates": cands,
                         "assertions": e["assertions"], "position": [ns, nt]})
        out[fid] = sorted(rows, key=lambda r: (r["position"][0], r["position"][1]))

    tot = sum(stats.values())
    print(f"trên {tot} concept của {Path(args.base).name}:")
    for k, n in stats.most_common():
        print(f"   {n:5d}  {k}")
    lost = sum(1 for c in changes if c[4] and not c[5])
    print(f"\n{len(changes)} span thu ngắn | {lost} ca mất mã")
    print("\n20 ca đầu:")
    for fid, old, new, ty, _, _ in changes[:20]:
        print(f"   file {fid:>3s} {ty:18s} {old[:44]!r}  =>  {new[:32]!r}")

    if args.dry or not args.out:
        return
    n0, n1 = sum(len(v) for v in base.values()), sum(len(v) for v in out.values())
    assert n0 == n1, f"số concept phải BẤT BIẾN ({n0} -> {n1})"
    errs = validate.validate(out)
    if errs:
        print(f"\n❌ {len(errs)} lỗi — KHÔNG ghi zip")
        for e in errs[:20]:
            print("  -", e)
        raise SystemExit(1)
    write_zip(out, Path(args.out))
    print(f"\n✅ ghi {args.out} — {n1} concept (số lượng bất biến)")


if __name__ == "__main__":
    main()
