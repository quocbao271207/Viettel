#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""THÊM concept mà >=k voter ĐỘC LẬP cùng trích nhưng bản nền thiếu.

    python3 -m src.harness.augment --k 2 --dry
    python3 -m src.harness.augment --k 2 --out out/candidates/19_consensus_add.zip

Vì sao lần này khác bản 15/16/17 (ba lần thêm đều lỗ)?
Ba bản đó thêm concept do MỘT lượt LLM tự nghĩ ra, duyệt bằng mắt. Ở đây concept phải được
>=k model ĐỘC LẬP, mù với nhau và mù với bản nền, cùng trích ĐÚNG một span. Đo trên 30 file
đầu: hai voter đồng thuận 86% mức cụm — nên "cả hai cùng chỉ vào một chỗ" là tín hiệu mạnh
hơn hẳn "một model nghĩ ra rồi người duyệt".

Vẫn là một CANH BẠC: ngưỡng hoà vốn 32.6% (J_assert). Nộp để đo, đừng gộp với bản đãi bỏ.

Ghi chú về mã (đã tính lại từ công thức chấm):
concept khớp gold mà `candidates` rỗng đóng góp ĐÚNG BẰNG concept không trích (cả hai đều
+1 mẫu số, +0 tử số). Nên mã rỗng KHÔNG bị phạt riêng — nó chỉ bỏ lỡ phần được cộng.
Vì vậy ở đây thêm cả concept chưa tra được mã, và gán mã sau nếu tra được.
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


def load_voters() -> tuple[dict[str, dict], list[str]]:
    out, names = {}, []
    for f in sorted(VOTES.glob("*.json")):
        r, _ = resolve_voter(json.loads(f.read_text(encoding="utf-8")), apply_ban=True)
        out[f.stem] = r
        names.append(f.stem)
    return out, names


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="",
                    help="zip nền để chồng lên (mặc định: bản 14). Cho phép nối các bước: span_fix -> assert -> prune ...")
    ap.add_argument("--k", type=int, default=2, help="số voter độc lập tối thiểu")
    ap.add_argument("--out", default="")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--extra-codes", default="",
                    help="JSON {'text\\tTYPE': ['mã']} bổ sung cho cụm mới")
    args = ap.parse_args()

    base = validate.load_zip(Path(args.base) if args.base else BASE_ZIP)
    resolved, names = load_voters()
    if len(names) < args.k:
        raise SystemExit(f"chỉ có {len(names)} voter, không đủ cho k={args.k}")
    done_files = sorted({f for r in resolved.values() for f, v in r.items() if v}, key=int)
    print(f"voter: {names} | file có phiếu: {len(done_files)}/100")

    cmap = code_map_from_base()
    if args.extra_codes:
        for k, v in json.loads(Path(args.extra_codes).read_text(encoding="utf-8")).items():
            t, ty = k.split("\t")
            cmap[(norm(t), ty)] = v

    out, added_rows = {}, []
    for fid in sorted(base, key=int):
        have = {(e["position"][0], e["position"][1], e["type"]) for e in base[fid]}
        spans = sorted((e["position"][0], e["position"][1]) for e in base[fid])
        votes: dict[tuple, dict] = {}
        for vn, per_file in resolved.items():
            for e in per_file.get(fid, []):
                key = (e["position"][0], e["position"][1], e["type"])
                slot = votes.setdefault(key, {"text": e["text"], "voters": set(),
                                              "asserts": Counter()})
                slot["voters"].add(vn)
                slot["asserts"][tuple(e["assertions"])] += 1
        new = []
        for (s, t, ty), slot in votes.items():
            if (s, t, ty) in have:
                continue
            if len(slot["voters"]) < args.k:
                continue
            if any(s < b and t > a for a, b in spans):   # chồng lấn span nền -> bỏ
                continue
            new.append({"text": slot["text"], "type": ty,
                        "candidates": list(cmap.get((norm(slot["text"]), ty), []))
                                      if ty in spec.CODED_TYPES else [],
                        "assertions": list(slot["asserts"].most_common(1)[0][0]),
                        "position": [s, t]})
        added_rows += [(fid, r) for r in new]
        out[fid] = sorted(base[fid] + new, key=lambda r: (r["position"][0], r["position"][1]))

    n0, n1 = sum(len(v) for v in base.values()), sum(len(v) for v in out.values())
    print(f"\nTHÊM {n1-n0} concept (đồng thuận >={args.k}/{len(names)} voter độc lập)")
    ty = Counter(r["type"] for _, r in added_rows)
    for k, n in ty.most_common():
        print(f"   {k:22s} {n:5d}")
    uncoded = [(f, r) for f, r in added_rows
               if r["type"] in spec.CODED_TYPES and not r["candidates"]]
    print(f"   {sum(1 for _, r in added_rows if r['type'] in spec.CODED_TYPES)} thuộc "
          f"CHẨN_ĐOÁN/THUỐC — trong đó {len(uncoded)} CHƯA tra được mã")

    surf = Counter((norm(r["text"]), r["type"]) for _, r in added_rows)
    print(f"\n{len(surf)} cụm bề mặt mới — 25 cụm nhiều lần nhắc nhất:")
    for (t, ty_), n in surf.most_common(25):
        mark = "" if (t, ty_) in cmap or ty_ not in spec.CODED_TYPES else "  [CHƯA CÓ MÃ]"
        print(f"   {n:4d}×  {ty_:20s} {t[:44]!r}{mark}")

    need = sorted({(norm(r["text"]), r["type"]) for _, r in uncoded})
    if need:
        p = ROOT / "dev/need_codes.json"
        p.write_text(json.dumps([{"text": t, "type": ty} for t, ty in need],
                                ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n-> {p.name}: {len(need)} cụm cần gán mã")

    if args.dry or not args.out:
        return
    errs = validate.validate(out)
    if errs:
        print(f"\n❌ {len(errs)} lỗi — KHÔNG ghi zip")
        for e in errs[:20]:
            print("  -", e)
        raise SystemExit(1)
    write_zip(out, Path(args.out))
    print(f"\n✅ ghi {args.out}  ({n1} concept)")


if __name__ == "__main__":
    main()
