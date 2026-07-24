#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""In raw + concept (đánh số, kèm assertion hiện tại) cho 1 dải file, để Fable 5 duyệt assertion.
    python3 src/dump_files.py 1 6
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sections

ROOT = Path(__file__).resolve().parent.parent
g = json.loads((ROOT / "dev/gold_curated.json").read_text(encoding="utf-8"))
a, b = int(sys.argv[1]), int(sys.argv[2])
for fid in map(str, range(a, b + 1)):
    raw = sections.read_raw(ROOT / "input" / f"{fid}.txt")
    print(f"\n{'='*70}\n### FILE {fid}\n{'='*70}")
    print(raw)
    print(f"\n--- CONCEPT file {fid} (idx | assert hiện tại | type | text) ---")
    for i, e in enumerate(g.get(fid, [])):
        cur = e["assertions"][0] if e["assertions"] else "∅"
        print(f"{i:2d} | {cur:13s} | {e['type']:11s} | {e['text']}")
