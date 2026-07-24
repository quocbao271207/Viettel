#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Vote lại ASSERTION trên bộ gold claude (KHÔNG thêm/bớt concept) bằng gpt+gpt41.
Chỉ đổi khi các voter phụ ĐỒNG THUẬN một assertion khác -> giữ WER & candidates, chỉ J_assert đổi.

    python3 src/assertion_vote.py --gold dev/gold_resolved.json --out dev/gold_assvote.json
    python3 src/assertion_vote.py ... --dry          # chỉ đếm thay đổi, không ghi
    python3 src/assertion_vote.py ... --min-agree 2  # số voter phụ phải đồng thuận (mặc định 2)

Khớp concept phụ với concept gold bằng CHỒNG LẤN span cùng type (định vị bằng before+text).
"""
from __future__ import annotations
import argparse, json, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import sections  # noqa: E402
from gold_triangulate import resolve_positions  # noqa: E402

AUX = ["gpt", "gpt41"]  # voter phụ (nền claude tin cậy, chỉ override khi phụ đồng thuận)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", default="dev/gold_resolved.json")
    ap.add_argument("--out", default="dev/gold_assvote.json")
    ap.add_argument("--min-agree", type=int, default=2, help="số voter phụ phải đồng thuận mới override")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    gold = json.loads((ROOT / args.gold).read_text(encoding="utf-8"))
    aux = {n: json.loads((ROOT / f"dev/votes/{n}.json").read_text(encoding="utf-8"))
           for n in AUX if (ROOT / f"dev/votes/{n}.json").exists()}
    print(f"voter phụ: {list(aux)} | min-agree={args.min_agree}")

    changes = Counter()   # (từ, sang) -> số lần
    n_change = 0
    for fid in map(str, range(1, 101)):
        raw = sections.read_raw(ROOT / "input" / f"{fid}.txt")
        # span assertion của từng voter phụ trong file này
        aux_spans = []  # (s, e, type, assertion)
        for data in aux.values():
            aux_spans.append(resolve_positions(raw, data.get(fid, [])))
        for e in gold.get(fid, []):
            s, en = e["position"]
            cur = e["assertions"][0] if e["assertions"] else ""
            votes = []
            for spans in aux_spans:  # mỗi voter phụ đóng góp TỐI ĐA 1 phiếu (concept chồng lấn nhất)
                best = None
                for (as_, ae, at, aa, _) in spans:
                    if at == e["type"] and min(ae, en) > max(as_, s):  # chồng lấn cùng type
                        ov = min(ae, en) - max(as_, s)
                        if best is None or ov > best[0]:
                            best = (ov, aa)
                if best is not None:
                    votes.append(best[1])
            if len(votes) < args.min_agree:
                continue
            top, cnt = Counter(votes).most_common(1)[0]
            if cnt >= args.min_agree and top != cur:
                changes[(cur or "∅", top or "∅")] += 1
                n_change += 1
                if not args.dry:
                    e["assertions"] = [top] if top else []

    print(f"\n{n_change} concept đổi assertion (trên {sum(len(v) for v in gold.values())}):")
    for (a, b), c in changes.most_common():
        print(f"  {a:14s} -> {b:14s} : {c}")
    if not args.dry:
        (ROOT / args.out).write_text(json.dumps(gold, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"-> {args.out}")


if __name__ == "__main__":
    main()
