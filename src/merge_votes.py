#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gộp dev/votes/parts/*.json -> dev/votes/<name>.json + kiểm định vị được không.

    python3 src/merge_votes.py --name claude
"""
from __future__ import annotations
import argparse, glob, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import sections  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="claude")
    args = ap.parse_args()

    merged = {}
    for f in sorted(glob.glob(str(ROOT / "dev/votes/parts/*.json"))):
        merged.update(json.loads(Path(f).read_text(encoding="utf-8")))

    # kiểm định vị: before+text hoặc text có trong file không
    tot = resolvable = 0
    per_type = {}
    for fid in map(str, range(1, 101)):
        raw = sections.read_raw(ROOT / "input" / f"{fid}.txt")
        for c in merged.get(fid, []):
            tot += 1
            per_type[c.get("type", "?")] = per_type.get(c.get("type", "?"), 0) + 1
            t = c.get("text", "")
            b = (c.get("before") or "")[-15:]
            if t and (raw.find(b + t) >= 0 or raw.find(t) >= 0):
                resolvable += 1

    out = ROOT / "dev/votes" / f"{args.name}.json"
    out.write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
    have = sorted(int(k) for k in merged)
    missing = [i for i in range(1, 101) if str(i) not in merged]
    print(f"-> {out}")
    print(f"   file có mặt: {len(merged)}/100" + (f"  THIẾU: {missing}" if missing else "  (đủ 100)"))
    print(f"   concept: {tot} | định vị được: {resolvable} ({resolvable/max(tot,1):.0%}) | type: {per_type}")


if __name__ == "__main__":
    main()
